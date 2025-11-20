"""UDP packet generator.

This module provides functionality for parsing UDP (User Datagram Protocol) packets from binary data sources.
UDP is a connectionless transport protocol defined in RFC 768.

Classes
-------
UDPPacketBytes : bytes
    Binary representation of a UDP packet with header field accessors.

Functions
---------
create_udp_packet : UDPPacketBytes
    Factory function to create UDP packets from components.
udp_generator : Iterator[UDPPacketBytes]
    Generator that yields UDP packets from binary data sources.
"""

import socket
import time
from collections.abc import Iterator
from typing import BinaryIO

from space_packet_parser.generators.utils import _print_progress, _setup_binary_reader


class UDPPacketBytes(bytes):
    """Binary (bytes) representation of a UDP packet.

    Methods to extract the UDP header fields are added to the raw bytes object.
    This class follows the same pattern as CCSDSPacketBytes.

    UDP Packet Structure (RFC 768):
    - Source Port: 16 bits (0-65535)
    - Destination Port: 16 bits (0-65535)
    - Length: 16 bits (total length in bytes including 8-byte header)
    - Checksum: 16 bits (optional error checking)
    - Data: Variable length payload
    """

    HEADER_LENGTH_BYTES = 8

    def __new__(cls, value: bytes):
        """Create a new UDPPacketBytes object with validation.

        Parameters
        ----------
        value : bytes
            Raw bytes of a UDP packet.

        Raises
        ------
        ValueError
            If the packet is shorter than the minimum UDP header length (8 bytes).
        """
        if len(value) < cls.HEADER_LENGTH_BYTES:
            raise ValueError(f"UDP packet must be at least {cls.HEADER_LENGTH_BYTES} bytes (got {len(value)} bytes)")
        return super().__new__(cls, value)

    def __str__(self) -> str:
        """Return a human-readable string representation of the UDP packet header."""
        return (
            f"UDPPacket Header: ({self.source_port=}, {self.dest_port=}, {self.length=}, {self.checksum=})"
        ).replace("self.", "")

    @property
    def source_port(self) -> int:
        """UDP source port (16 bits, bytes 0-1)."""
        return (self[0] << 8) | self[1]

    @property
    def dest_port(self) -> int:
        """UDP destination port (16 bits, bytes 2-3)."""
        return (self[2] << 8) | self[3]

    @property
    def length(self) -> int:
        """UDP packet length in bytes, including 8-byte header (16 bits, bytes 4-5)."""
        return (self[4] << 8) | self[5]

    @property
    def checksum(self) -> int:
        """UDP checksum (16 bits, bytes 6-7)."""
        return (self[6] << 8) | self[7]

    @property
    def header_values(self) -> tuple[int, ...]:
        """Convenience property for tuple of header values.

        Returns
        -------
        tuple[int, ...]
            Tuple containing (source_port, dest_port, length, checksum).
        """
        return (self.source_port, self.dest_port, self.length, self.checksum)

    @property
    def header(self) -> bytes:
        """Convenience property returns the UDP header bytes (first 8 bytes).

        Returns
        -------
        bytes
            The 8-byte UDP header.
        """
        return self[:8]

    @property
    def data(self) -> bytes:
        """Convenience property returns only the UDP payload data (no header).

        Returns
        -------
        bytes
            The UDP payload data without the header.
        """
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
        Payload data bytes.
    source_port : int
        UDP source port (16 bits, 0-65535).
    dest_port : int
        UDP destination port (16 bits, 0-65535).
    checksum : int
        UDP checksum (16 bits, 0-65535). Use 0 if not computed.

    Returns
    -------
    UDPPacketBytes
        Resulting binary UDP packet.

    Raises
    ------
    ValueError
        If any field value is out of range or if the total packet length exceeds 65535 bytes.

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
    try:
        header = (
            source_port.to_bytes(2, "big")
            + dest_port.to_bytes(2, "big")
            + length.to_bytes(2, "big")
            + checksum.to_bytes(2, "big")
        )
        packet = header + data
    except (TypeError, AttributeError) as e:
        raise TypeError("UDP header fields must be integers and data must be bytes.") from e

    return UDPPacketBytes(packet)


def udp_generator(
    binary_data: BinaryIO | socket.socket | bytes,
    *,
    buffer_read_size_bytes: int | None = None,
    show_progress: bool = False,
) -> Iterator[UDPPacketBytes]:
    """A generator that reads UDP packets from binary data.

    Each iteration yields a UDPPacketBytes object representing a single UDP packet.
    The generator reads the UDP length field to determine packet boundaries.

    Parameters
    ----------
    binary_data : Union[BinaryIO, socket.socket, bytes]
        Binary data source containing UDP packets. Can be a file-like object, socket, or bytes.
    buffer_read_size_bytes : int, optional
        Number of bytes to read from e.g. a BufferedReader or socket binary data source on each read attempt.
        If None, defaults to 4096 bytes from a socket, -1 (full read) from a file.
    show_progress : bool
        Default False.
        If True, prints a status bar. Note that for socket sources, the percentage will be zero until the generator
        ends.

    Yields
    ------
    UDPPacketBytes
        The bytes of a single UDP packet.

    Notes
    -----
    This generator assumes:
    - Binary data contains back-to-back UDP packets with no additional framing
    - Each packet has a valid length field
    - No error checking or recovery from malformed packets
    """
    n_bytes_parsed = 0  # Keep track of how many bytes we have parsed
    n_packets_parsed = 0  # Keep track of how many packets we have parsed
    header_length_bytes = UDPPacketBytes.HEADER_LENGTH_BYTES
    read_buffer, total_length_bytes, read_bytes_from_source, buffer_read_size_bytes = _setup_binary_reader(
        binary_data, buffer_read_size_bytes
    )
    current_pos = 0  # Keep track of where we are in the buffer
    start_time = time.time_ns()

    while True:
        if n_bytes_parsed == total_length_bytes:
            break  # Exit if we know the length and we've reached it

        if show_progress:
            _print_progress(
                current_bytes=n_bytes_parsed,
                total_bytes=total_length_bytes,
                start_time_ns=start_time,
                current_packets=n_packets_parsed,
            )

        if current_pos > 20_000_000:
            # Only trim the buffer after 20 MB read to prevent modifying
            # the bitstream and trimming after every packet
            read_buffer = read_buffer[current_pos:]
            current_pos = 0

        # Fill buffer enough to parse a header
        while len(read_buffer) - current_pos < header_length_bytes:
            result = read_bytes_from_source(buffer_read_size_bytes)
            if not result:  # If there is verifiably no more data to add, break
                break
            read_buffer += result

        # Check if we have enough data for a complete header
        if len(read_buffer) - current_pos < header_length_bytes:
            break  # Not enough data for a header, we're done

        # Extract the length field (bytes 4-5) to determine total packet size
        length_byte_offset = current_pos + 4
        length = (read_buffer[length_byte_offset] << 8) | read_buffer[length_byte_offset + 1]

        if length < header_length_bytes:
            raise ValueError(f"Invalid UDP length field: {length} (must be at least 8)")

        # Fill buffer enough to parse the complete packet
        while len(read_buffer) - current_pos < length:
            result = read_bytes_from_source(buffer_read_size_bytes)
            if not result:
                break
            read_buffer += result

        # Check if we have enough data for the complete packet
        if len(read_buffer) - current_pos < length:
            break  # Not enough data for the complete packet

        # Extract the complete packet
        packet_bytes = read_buffer[current_pos : current_pos + length]
        current_pos += length
        n_packets_parsed += 1
        n_bytes_parsed += length

        yield UDPPacketBytes(packet_bytes)

    if show_progress:
        _print_progress(
            current_bytes=n_bytes_parsed,
            total_bytes=total_length_bytes,
            start_time_ns=start_time,
            current_packets=n_packets_parsed,
            end="\n",
            log=True,
        )
