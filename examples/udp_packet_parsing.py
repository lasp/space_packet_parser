"""Example of creating a custom generator for parsing UDP packets.

This example demonstrates how to:
1. Create a custom packet bytes class (UDPPacketBytes) that exposes UDP header fields as properties
2. Implement a custom generator (udp_generator) that yields individual UDP packets from binary data
3. Define an XTCE packet structure for non-CCSDS packets (UDP packets)
4. Parse UDP packets using the XTCE definition

UDP Packet Structure:
- Source Port: 16 bits (0-65535)
- Destination Port: 16 bits (0-65535)
- Length: 16 bits (total length in bytes including 8-byte header)
- Checksum: 16 bits (optional error checking)
- Data: Variable length payload
"""

from collections.abc import Iterator
from pathlib import Path
from typing import BinaryIO, Union

import space_packet_parser as spp


class UDPPacketBytes(bytes):
    """Binary (bytes) representation of a UDP packet.

    Methods to extract the UDP header fields are added to the raw bytes object.
    This class follows the same pattern as CCSDSPacketBytes.
    """

    HEADER_LENGTH_BYTES = 8

    def __str__(self) -> str:
        return (
            f"UDPPacket Header: ({self.source_port=}, {self.dest_port=}, {self.length=}, {self.checksum=})"
        ).replace("self.", "")

    @property
    def source_port(self) -> int:
        """UDP source port (16 bits, bytes 0-1)"""
        return (self[0] << 8) | self[1]

    @property
    def dest_port(self) -> int:
        """UDP destination port (16 bits, bytes 2-3)"""
        return (self[2] << 8) | self[3]

    @property
    def length(self) -> int:
        """UDP packet length in bytes, including 8-byte header (16 bits, bytes 4-5)"""
        return (self[4] << 8) | self[5]

    @property
    def checksum(self) -> int:
        """UDP checksum (16 bits, bytes 6-7)"""
        return (self[6] << 8) | self[7]

    @property
    def header_values(self) -> tuple[int, ...]:
        """Convenience property for tuple of header values"""
        return (self.source_port, self.dest_port, self.length, self.checksum)

    @property
    def header(self) -> bytes:
        """Convenience property returns the UDP header bytes (first 8 bytes)"""
        return self[:8]

    @property
    def data(self) -> bytes:
        """Convenience property returns only the UDP payload data (no header)"""
        return self[8:]


def create_udp_packet(
    data: bytes = b"",
    *,
    source_port: int = 0,
    dest_port: int = 0,
    checksum: int = 0,
) -> UDPPacketBytes:
    """Create a binary UDP packet from input values.

    Pack the header fields into the proper bit locations and append the data bytes.

    Parameters
    ----------
    data : bytes
        Payload data bytes
    source_port : int
        UDP source port (16 bits, 0-65535)
    dest_port : int
        UDP destination port (16 bits, 0-65535)
    checksum : int
        UDP checksum (16 bits, 0-65535). Use 0 if not computed.

    Returns
    -------
    : UDPPacketBytes
        Resulting binary UDP packet

    Notes
    -----
    This function is useful for generating test UDP packets for debugging or mocking purposes.
    The length field is automatically computed as 8 + len(data).
    """
    if source_port < 0 or source_port > 65535:
        raise ValueError("source_port must be between 0 and 65535")
    if dest_port < 0 or dest_port > 65535:
        raise ValueError("dest_port must be between 0 and 65535")
    if checksum < 0 or checksum > 65535:
        raise ValueError("checksum must be between 0 and 65535")

    length = 8 + len(data)  # UDP length includes the 8-byte header
    if length > 65535:
        raise ValueError("UDP packet length (header + data) cannot exceed 65535 bytes")

    # Pack the header fields (all 16-bit big-endian unsigned integers)
    header = (
        source_port.to_bytes(2, "big")
        + dest_port.to_bytes(2, "big")
        + length.to_bytes(2, "big")
        + checksum.to_bytes(2, "big")
    )

    packet = header + data
    return UDPPacketBytes(packet)


def udp_generator(
    binary_data: Union[BinaryIO, bytes],
) -> Iterator[UDPPacketBytes]:
    """A generator that reads UDP packets from binary data.

    Each iteration yields a UDPPacketBytes object representing a single UDP packet.
    The generator reads the UDP length field to determine packet boundaries.

    Parameters
    ----------
    binary_data : Union[BinaryIO, bytes]
        Binary data source containing UDP packets. Can be a file-like object or bytes.

    Yields
    ------
    UDPPacketBytes
        The bytes of a single UDP packet.

    Notes
    -----
    This is a simplified generator that assumes:
    - Binary data contains back-to-back UDP packets with no additional framing
    - Each packet has a valid length field
    - No error checking or recovery from malformed packets
    """
    # Convert bytes to a BytesIO-like interface if needed
    if isinstance(binary_data, bytes):
        from io import BytesIO

        binary_data = BytesIO(binary_data)

    while True:
        # Read the UDP header (8 bytes)
        header = binary_data.read(UDPPacketBytes.HEADER_LENGTH_BYTES)
        if len(header) < UDPPacketBytes.HEADER_LENGTH_BYTES:
            break  # Not enough data for a header, we're done

        # Extract the length field (bytes 4-5) to determine payload size
        length = (header[4] << 8) | header[5]
        data_length = length - UDPPacketBytes.HEADER_LENGTH_BYTES

        if data_length < 0:
            raise ValueError(f"Invalid UDP length field: {length} (must be at least 8)")

        # Read the payload data
        data = binary_data.read(data_length)
        if len(data) < data_length:
            # Not enough data for the complete packet
            break

        # Combine header and data into a complete packet
        packet = header + data
        yield UDPPacketBytes(packet)


if __name__ == "__main__":
    # Find the XTCE definition file
    script_dir = Path(__file__).parent.resolve()
    xtce_file = script_dir / "../tests/test_data/udp_packet.xml"

    # Load the UDP packet definition from XTCE
    packet_definition = spp.load_xtce(xtce_file)

    print("=" * 70)
    print("UDP Packet Parsing Example")
    print("=" * 70)
    print()

    # Create 5 artificial UDP packets with different configurations
    packets_data = [
        create_udp_packet(
            data=b"Hello, World!",
            source_port=12345,
            dest_port=80,
            checksum=0x1234,
        ),
        create_udp_packet(
            data=b"UDP packet #2",
            source_port=8080,
            dest_port=443,
            checksum=0xABCD,
        ),
        create_udp_packet(
            data=b"Short",
            source_port=5000,
            dest_port=5001,
            checksum=0x0000,
        ),
        create_udp_packet(
            data=b"Testing UDP parsing with a longer payload message",
            source_port=53,
            dest_port=53,
            checksum=0xFFFF,
        ),
        create_udp_packet(
            data=b"Last packet",
            source_port=9999,
            dest_port=1234,
            checksum=0x5678,
        ),
    ]

    # Concatenate all packets into a single binary stream
    binary_stream = b"".join(packets_data)

    print(f"Created {len(packets_data)} UDP packets ({len(binary_stream)} bytes total)")
    print()

    # Use the custom UDP generator to parse the binary stream
    print("Parsing UDP packets:")
    print("-" * 70)

    for i, udp_packet_bytes in enumerate(udp_generator(binary_stream), start=1):
        # Display header information from the UDPPacketBytes object
        print(f"\nPacket {i}:")
        print(f"  {udp_packet_bytes}")
        print(f"  Data length: {len(udp_packet_bytes.data)} bytes")
        print(f"  Data preview: {udp_packet_bytes.data[:50]!r}")

        # Parse the packet using the XTCE definition
        parsed_packet = packet_definition.parse_bytes(udp_packet_bytes, root_container_name="UDPPacket")

        # Display parsed values
        print(f"  Parsed SOURCE_PORT: {parsed_packet['SOURCE_PORT']}")
        print(f"  Parsed DEST_PORT: {parsed_packet['DEST_PORT']}")
        print(f"  Parsed UDP_LENGTH: {parsed_packet['UDP_LENGTH']}")
        print(f"  Parsed CHECKSUM: 0x{parsed_packet['CHECKSUM']:04X}")

    print()
    print("-" * 70)
    print("Example complete!")
