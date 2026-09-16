# Packet Bytes Generators

Packet bytes generators are functions that yield individual packets as `bytes` objects (or
subclasses of `bytes`) from a binary data source. Space Packet Parser provides built-in generators
like `ccsds_generator`, `fixed_length_generator`, and `udp_generator`, but you can write custom
generators to parse any packet format you need.

A generator function should accept a binary data source (file-like object, socket, or bytes) and
yield packet bytes one at a time. The built-in generator implementations in
`space_packet_parser/generators/` provide complete examples of how to implement packet bytes
generators. Custom generators allow you to adapt Space Packet Parser to work with any binary
packet format.

## XTCE Is Not CCSDS-Specific

While XTCE is commonly used with CCSDS packets, the XTCE standard is not limited to representing
CCSDS packet structures. The CCSDS header information (`VERSION`, `TYPE`, `APID`, etc.) is not
required by XTCE. You can define XTCE packet structures for any binary format and use a custom or
built-in generator to yield those packets for parsing.

## Built-in Generators

### CCSDS Generator

The `ccsds_generator` parses CCSDS Space Packets according to the CCSDS standard. It uses the
packet length field in the CCSDS header to determine packet boundaries and supports features like
segmented packet reassembly.

```python
from space_packet_parser import ccsds_generator, load_xtce

packet_definition = load_xtce("my_ccsds_packets.xml")
for packet_bytes in ccsds_generator(binary_data):
    parsed = packet_definition.parse_bytes(packet_bytes)
    print(parsed)
```

### Fixed Length Generator

The `fixed_length_generator` yields fixed-size chunks from binary data. This is useful for packet
formats where all packets have a known, constant length.

```python
from space_packet_parser import load_xtce
from space_packet_parser.generators import fixed_length_generator

packet_definition = load_xtce("my_fixed_length_packets.xml")
for packet_bytes in fixed_length_generator(binary_data, packet_length_bytes=64):
    parsed = packet_definition.parse_bytes(packet_bytes)
    print(parsed)
```

### UDP Generator

The `udp_generator` parses UDP (User Datagram Protocol) packets from binary data. It reads the UDP
length field from each packet header to determine packet boundaries. The generator yields
`UDPPacketBytes` objects that expose UDP header fields (source port, destination port, length,
checksum) as properties.

```python
from space_packet_parser import load_xtce
from space_packet_parser.generators import udp_generator

packet_definition = load_xtce("my_udp_packets.xml")
for udp_packet in udp_generator(binary_data):
    # Access UDP header fields directly
    print(f"From port {udp_packet.source_port} to port {udp_packet.dest_port}")
    # Parse the packet using XTCE
    parsed = packet_definition.parse_bytes(udp_packet)
    print(parsed)
```

## Writing Custom Generators

### The Generator Contract

A packet bytes generator must satisfy a short contract:

- It accepts a binary data source as its first positional argument. The built-in generators accept
  a file-like object, a socket, or raw `bytes`; any options beyond the data source are keyword-only
  by convention.
- It yields exactly one packet's worth of bytes per iteration.
- Each yielded chunk must contain **every** byte that the XTCE container describes, including
  leading fields such as a sync marker or a length field. `parse_bytes` issues a warning when the
  number of bits it parses does not match the number of bits it was handed, which is the usual
  symptom of a generator whose packet boundaries disagree with the XTCE definition.
- It may yield a subclass of `bytes` that exposes packet metadata as properties, the way
  `CCSDSPacketBytes` exposes `apid` and `UDPPacketBytes` exposes `source_port`. Such metadata is
  what a `packet_filter` inspects to reject packets before they are parsed.

A minimal fixed-length generator follows this pattern:

```python
def custom_generator(binary_data, *, packet_length):
    """Yields fixed-length packets from binary data."""
    while True:
        packet_bytes = binary_data.read(packet_length)
        if not packet_bytes:
            break
        yield packet_bytes
```

### Determining Packet Length from the Packet Itself

Many formats carry their own length. The generator below locates packets by a sync marker and
reads a packet-defined length field to find the end of each packet:

```python
def sync_marker_generator(binary_data, *, sync_marker=b"\xde\xad\xbe\xef"):
    """Yields sync-marker-delimited, length-prefixed packets from binary data."""
    buffer = binary_data.read() if hasattr(binary_data, "read") else binary_data
    header_length = len(sync_marker) + 1  # sync marker plus the one-byte length field
    position = 0
    while True:
        start = buffer.find(sync_marker, position)
        if start == -1:
            break
        if start + header_length > len(buffer):
            break  # Truncated packet: the length field itself was cut off
        payload_length = buffer[start + len(sync_marker)]
        end = start + header_length + payload_length
        if end > len(buffer):
            break  # Truncated packet at the end of the stream
        # The sync marker and length field are described by the XTCE container, so they are
        # included in the yielded chunk.
        yield buffer[start:end]
        position = end
```

This example reads a file-like object or raw `bytes`; it does not support parsing directly from a
socket. For an example that does, see the
[IDEX waveform socket example](https://github.com/lasp/space_packet_parser/blob/main/examples/parsing_and_plotting_idex_waveforms_from_socket.py).
Note that socket reading is built into the default CCSDS packet generator; see
`space_packet_parser/generators/ccsds.py`.

A definition for a format like this has no `CCSDSPacket` container, so the root container to parse
from must be named explicitly. Note that `load_xtce` does not accept this argument; pass it to
`parse_bytes` (or to `XtcePacketDefinition.from_xtce`) instead:

```python
from space_packet_parser import load_xtce

packet_definition = load_xtce("my_sensor_packets.xml")
for packet_bytes in sync_marker_generator(binary_data):
    parsed = packet_definition.parse_bytes(packet_bytes, root_container_name="SensorPacket")
    print(parsed)
```

A custom generator also works with the Xarray interface. Pass it to `create_dataset` as
`packet_bytes_generator`, with any generator options in `generator_kwargs`. `create_dataset` keys
its result by the `apid` property on the `bytes` object each generator yields (as `CCSDSPacketBytes`
and `UDPPacketBytes` expose), falling back to `0` when that property is absent — so packets from a
generator that yields plain `bytes`, like `sync_marker_generator` above, are all grouped under key
`0`.

For a complete, runnable demonstration of all of the above, see the
[non-CCSDS parsing example](https://github.com/lasp/space_packet_parser/blob/main/examples/parsing_non_ccsds_packets.py).

For more sophisticated generators that handle multiple input types (files, sockets, bytes) and
provide progress tracking, see the implementations of the built-in generators in
`space_packet_parser/generators/`. These demonstrate best practices like using the
`_setup_binary_reader` utility for handling different data sources and optional progress bars.

## Filtering Packets

For generators that expose packet metadata (like `CCSDSPacketBytes` with its `apid` property), you
can filter packets before parsing to improve performance. See the
[packet filtering example](https://github.com/lasp/space_packet_parser/blob/main/examples/packet_filtering.py)
for a complete, runnable demonstration.
