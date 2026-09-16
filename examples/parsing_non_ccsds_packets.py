"""Example of parsing a non-CCSDS packet format with a custom packet bytes generator

XTCE is a generic telemetry description standard. It has no notion of the CCSDS Space Packet
Protocol, so the CCSDS primary header fields (`VERSION`, `TYPE`, `PKT_APID`, `PKT_LEN`, etc.) are
not required. Any binary format that can be described as an ordered sequence of fields can be
described in XTCE and parsed by Space Packet Parser.

What Space Packet Parser cannot infer for a non-CCSDS format is where one packet ends and the next
begins. That is the job of a packet bytes generator: a function that consumes a binary source and
yields exactly one packet's worth of bytes per iteration. This example defines a custom generator
for a made up instrument format that has no CCSDS header at all. Packets are delimited by a sync
marker and their size is carried in a packet-defined length field:

    | SYNC 0xDEADBEEF (4 bytes) | PAYLOAD_LENGTH (1 byte) | COUNTER (2 bytes) | TEMPERATURE (2 bytes) |

Two details matter when parsing a format like this:

1. Each chunk yielded by the generator must contain *every* byte the XTCE container describes,
   including leading fields like the sync marker. `parse_bytes` warns if the number of bits it
   parses does not match the number of bits it was handed.
2. `XtcePacketDefinition.root_container_name` defaults to `"CCSDSPacket"`, so a definition whose
   root container has a different name must say so. Note that `load_xtce` does not take that
   argument; pass it to `parse_bytes` (or to `XtcePacketDefinition.from_xtce`) instead.

The example is fully self-contained. It builds both the XTCE definition and the binary stream in
memory, so it requires no external data files.
"""

import io
import struct
from collections.abc import Iterator
from typing import BinaryIO

from space_packet_parser import load_xtce
from space_packet_parser.xarr import create_dataset

# The 4-byte sync marker that precedes every packet in this made up format.
SYNC_MARKER = b"\xde\xad\xbe\xef"

# This definition's root container is not called "CCSDSPacket", so we must name it explicitly
# whenever we parse.
ROOT_CONTAINER_NAME = "SensorPacket"

# A minimal XTCE definition for the format, as an inline XML string. There is no CCSDS header
# here, just the four fields of the packet in the order they appear on the wire.
XTCE_DEFINITION = """<?xml version="1.0" encoding="UTF-8"?>
<xtce:SpaceSystem name="NonCcsdsExample"
                  xmlns:xtce="http://www.omg.org/spec/XTCE/20180204"
                  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                  xsi:schemaLocation="http://www.omg.org/spec/XTCE/20180204
                                      https://www.omg.org/spec/XTCE/20180204/SpaceSystem.xsd">
  <xtce:TelemetryMetaData>
    <xtce:ParameterTypeSet>
      <xtce:IntegerParameterType name="UINT8_Type" signed="false">
        <xtce:IntegerDataEncoding sizeInBits="8" encoding="unsigned"/>
      </xtce:IntegerParameterType>
      <xtce:IntegerParameterType name="UINT16_Type" signed="false">
        <xtce:IntegerDataEncoding sizeInBits="16" encoding="unsigned"/>
      </xtce:IntegerParameterType>
      <xtce:IntegerParameterType name="UINT32_Type" signed="false">
        <xtce:IntegerDataEncoding sizeInBits="32" encoding="unsigned"/>
      </xtce:IntegerParameterType>
    </xtce:ParameterTypeSet>
    <xtce:ParameterSet>
      <xtce:Parameter name="SYNC" parameterTypeRef="UINT32_Type"/>
      <xtce:Parameter name="PAYLOAD_LENGTH" parameterTypeRef="UINT8_Type"/>
      <xtce:Parameter name="COUNTER" parameterTypeRef="UINT16_Type"/>
      <xtce:Parameter name="TEMPERATURE" parameterTypeRef="UINT16_Type"/>
    </xtce:ParameterSet>
    <xtce:ContainerSet>
      <xtce:SequenceContainer name="SensorPacket">
        <xtce:EntryList>
          <xtce:ParameterRefEntry parameterRef="SYNC"/>
          <xtce:ParameterRefEntry parameterRef="PAYLOAD_LENGTH"/>
          <xtce:ParameterRefEntry parameterRef="COUNTER"/>
          <xtce:ParameterRefEntry parameterRef="TEMPERATURE"/>
        </xtce:EntryList>
      </xtce:SequenceContainer>
    </xtce:ContainerSet>
  </xtce:TelemetryMetaData>
</xtce:SpaceSystem>
"""


def sync_marker_generator(
    binary_data: BinaryIO | bytes,
    *,
    sync_marker: bytes = SYNC_MARKER,
) -> Iterator[bytes]:
    """A generator that yields sync-marker-delimited, length-prefixed packets from binary_data.

    Each packet begins with `sync_marker`, immediately followed by a single byte giving the number
    of payload bytes that follow it. The yielded chunk spans the whole packet, sync marker
    included, because the XTCE container describes those bytes too.

    This simplified version reads the entire source up front, which keeps the packet-boundary
    logic easy to follow, and only supports a file-like object or raw `bytes`. It does not support
    reading directly from a socket. The built-in generators in `space_packet_parser/generators/` use
    `space_packet_parser.generators.utils._setup_binary_reader` to read incrementally from files and
    sockets alike; for a custom generator that parses directly from a socket, see
    `examples/parsing_and_plotting_idex_waveforms_from_socket.py`.

    Parameters
    ----------
    binary_data : Union[BinaryIO, bytes]
        Binary data source.
    sync_marker : bytes
        Byte string that marks the start of each packet.

    Yields
    ------
    bytes
        One packet's worth of bytes, beginning with the sync marker.
    """
    buffer = binary_data.read() if hasattr(binary_data, "read") else binary_data
    header_length = len(sync_marker) + 1  # sync marker plus the one-byte length field
    position = 0
    while True:
        start = buffer.find(sync_marker, position)
        if start == -1:
            # No further sync markers. Any remaining bytes are not a packet.
            break
        if start + header_length > len(buffer):
            # Truncated packet: the length field itself was cut off.
            break
        payload_length = buffer[start + len(sync_marker)]
        end = start + header_length + payload_length
        if end > len(buffer):
            # Truncated packet: fewer payload bytes are present than the length field promises.
            break
        yield buffer[start:end]
        position = end


def build_example_stream(n_packets: int = 5) -> bytes:
    """Build an in-memory stream of example packets.

    Parameters
    ----------
    n_packets : int
        Number of packets to synthesize.

    Returns
    -------
    : bytes
        Concatenated packet bytes, each one prefixed by the sync marker and a length byte.
    """
    stream = b""
    for counter in range(n_packets):
        payload = struct.pack(">HH", counter, 300 + counter)  # COUNTER, TEMPERATURE
        stream += SYNC_MARKER + struct.pack(">B", len(payload)) + payload
    return stream


if __name__ == "__main__":
    # `load_xtce` accepts a file path or any file-like object. lxml refuses a `str` that carries an
    # XML declaration, so encode the inline definition and wrap it in a BytesIO.
    packet_definition = load_xtce(io.BytesIO(XTCE_DEFINITION.encode("utf-8")))

    stream = build_example_stream()
    print(f"Generated {len(stream)} bytes of example packet data\n")

    # Parsing packet by packet. `root_container_name` is required here because the default,
    # "CCSDSPacket", does not exist in this definition.
    parsed_packets = []
    for packet_bytes in sync_marker_generator(stream):
        packet = packet_definition.parse_bytes(packet_bytes, root_container_name=ROOT_CONTAINER_NAME)
        print(packet)
        parsed_packets.append(packet)

    # Regression-check the documented boundary behavior: build_example_stream(n_packets=5) produces
    # COUNTER 0..4 and TEMPERATURE 300..304, so a generator whose sync marker or length handling is
    # broken (silently dropping or misreading a packet) is caught here instead of only being printed.
    assert len(parsed_packets) == 5  # noqa S101
    assert [p["COUNTER"].raw_value for p in parsed_packets] == list(range(5))  # noqa S101
    assert [p["TEMPERATURE"].raw_value for p in parsed_packets] == [300 + i for i in range(5)]  # noqa S101

    # The same custom generator can drive the xarray interface. `create_dataset` keys its result by
    # the `apid` property on the yielded bytes object, falling back to 0 when that property is
    # absent — so these packets, yielded as plain bytes, are all grouped under key 0.
    datasets = create_dataset(
        packet_files=stream,
        xtce_packet_definition=packet_definition,
        packet_bytes_generator=sync_marker_generator,
        parse_bytes_kwargs={"root_container_name": ROOT_CONTAINER_NAME},
    )

    print("\nAs an xarray Dataset:")
    print(datasets[0])

    assert len(datasets) == 1  # noqa S101
    assert len(datasets[0].packet) == 5  # noqa S101
