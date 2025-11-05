"""Packet generator utilities for CCSDS packets.

The parsing begins with binary data representing CCSDS Packets. A user can then create a generator
from the binary data reading from a filelike object or a socket. The ``ccsds_generator`` function yields
``CCSDSPacketBytes`` objects that are the raw binary data of a single CCSDS packet. The ``CCSDSPacketBytes``
class can be used to inspect the CCSDS header fields of the packet, but it does not have any
parsed content from the data field. This generator is useful for debugging and passing off
to other parsing functions.
"""

import io
import logging
import socket
import time
import warnings
from collections.abc import Iterator
from enum import IntEnum

from space_packet_parser.common import SpacePacket
from space_packet_parser.generators.utils import _print_progress, _setup_binary_reader

logger = logging.getLogger(__name__)


class SequenceFlags(IntEnum):
    """Enumeration of the possible sequence flags in a CCSDS packet."""

    CONTINUATION = 0
    FIRST = 1
    LAST = 2
    UNSEGMENTED = 3


class CCSDSPacketBytes(bytes):
    """Binary (bytes) representation of a CCSDS packet.

    Methods to extract the header fields are added to the raw bytes object.
    """

    HEADER_LENGTH_BYTES = 6

    def __str__(self) -> str:
        return (
            f"CCSDSPacket Header: ({self.version_number=}, {self.type=}, "
            f"{self.secondary_header_flag=}, {self.apid=}, {self.sequence_flags=}, "
            f"{self.sequence_count=}, {self.data_length=})"
        ).replace("self.", "")

    @property
    def version_number(self) -> int:
        """CCSDS Packet Version Number"""
        # First 3 bits
        return (self[0] >> 5) & 0b111

    @property
    def type(self) -> int:
        """CCSDS Packet Type

        0 = Telemetry Packet
        1 = Telecommand Packet
        """
        # 4th bit
        return (self[0] >> 4) & 0b1

    @property
    def secondary_header_flag(self) -> int:
        """CCSDS Secondary Header Flag

        0 = No secondary header
        1 = Secondary header present
        """
        # 5th bit
        return (self[0] >> 3) & 0b1

    @property
    def apid(self) -> int:
        """CCSDS Application Process Identifier (APID)"""
        # 11 bits starting at the 6th bit (finishes the second byte)
        return ((self[0] << 8) | self[1]) & 0b11111111111

    @property
    def sequence_flags(self) -> int:
        """CCSDS Packet Sequence Flags

        00 = Continuation packet
        01 = First packet
        10 = Last packet
        11 = Unsegmented packet (standalone)
        """
        # 2 bits starting at the beginning of the 3rd byte
        return (self[2] >> 6) & 0b11

    @property
    def sequence_count(self) -> int:
        """CCSDS Packet Sequence Count"""
        # 14 bits starting at the 3rd bit of the 3rd byte
        # goes through the end of the 4th byte
        return ((self[2] << 8) | self[3]) & 0b11111111111111

    @property
    def data_length(self) -> int:
        """CCSDS Packet Data Length

        Section 4.1.3.5.3 The length count C shall be expressed as:
        C = (Total Number of Octets in the Packet Data Field) - 1
        """
        # Final 2 bytes
        return self[4] << 8 | self[5]

    @property
    def header_values(self) -> tuple[int, ...]:
        """Convenience property for tuple of header values"""
        return (
            self.version_number,
            self.type,
            self.secondary_header_flag,
            self.apid,
            self.sequence_flags,
            self.sequence_count,
            self.data_length,
        )

    @property
    def header(self) -> bytes:
        """Convenience property returns the CCSDS header bytes"""
        return self[:6]

    @property
    def user_data(self) -> bytes:
        """Convenience property returns only the user data bytes (no header)

        Notes:
        ------
        This includes the secondary header, if present
        """
        return self[6:]


def create_ccsds_packet(
    data=b"\x00",
    *,
    version_number=0,
    type=0,
    secondary_header_flag=0,
    apid=2047,  # 2047 is defined as a fill packet in the CCSDS spec
    sequence_flags=SequenceFlags.UNSEGMENTED,
    sequence_count=0,
) -> CCSDSPacketBytes:
    """Create a binary CCSDS packet from input values.

    Pack the header fields into the proper bit locations and append the data bytes.

    Parameters
    ----------
    data : bytes
        User data bytes (up to 65536 bytes)
    version_number : int
        CCSDS Packet Version Number (3 bits)
    type : int
        CCSDS Packet Type (1 bit)
    secondary_header_flag : int
        CCSDS Secondary Header Flag (1 bit)
    apid : int
        CCSDS Application Process Identifier (APID) (11 bits)
    sequence_flags : int
        CCSDS Packet Sequence Flags (2 bits)
    sequence_count : int
        CCSDS Packet Sequence Count (14 bits)

    Returns
    -------
    : CCSDSPacketBytes
        Resulting binary packet

    Notes
    -----
    This function is extremely useful for generating test packets for debugging or mocking purposes.
    """
    if version_number < 0 or version_number > 7:  # 3 bits
        raise ValueError("version_number must be between 0 and 7")
    if type < 0 or type > 1:  # 1 bit
        raise ValueError("type_ must be 0 or 1")
    if secondary_header_flag < 0 or secondary_header_flag > 1:  # 1 bit
        raise ValueError("secondary_header_flag must be 0 or 1")
    if apid < 0 or apid > 2047:  # 11 bits
        raise ValueError("apid must be between 0 and 2047")
    if sequence_flags < 0 or sequence_flags > 3:  # 2 bits
        raise ValueError("sequence_flags must be between 0 and 3")
    if sequence_count < 0 or sequence_count > 16383:  # 14 bits
        raise ValueError("sequence_count must be between 0 and 16383")
    if len(data) < 1 or len(data) > 65536:  # 16 bits
        raise ValueError("length of data (in bytes) must be between 1 and 65536")

    # CCSDS primary header
    # bitshift left to the correct position for that field (48 - start_bit - nbits)
    try:
        header = (
            version_number << 48 - 3
            | type << 48 - 4
            | secondary_header_flag << 48 - 5
            | apid << 48 - 16
            | sequence_flags << 48 - 18
            | sequence_count << 48 - 32
            | len(data) - 1
        )
        packet = header.to_bytes(CCSDSPacketBytes.HEADER_LENGTH_BYTES, "big") + data
    except TypeError as e:
        raise TypeError("CCSDS Header items must be integers and the input data bytes.") from e
    return CCSDSPacketBytes(packet)


class CCSDSPacket(SpacePacket):
    """Packet representing parsed data items from CCSDS packet(s). DEPRECATED

    This class is deprecated and will be removed in a future release. Use the SpacePacket class instead.
    In an XTCE representation, there is no guarantee that the CCSDS packet header will be defined
    as individual elements. If you want to access those elements, you can use the CCSDSPacketBytes
    class to extract the header fields with specific methods.

    Container that stores the raw packet data (bytes) as an instance attribute and the parsed
    data items in a dictionary interface. A ``CCSDSPacket`` generally begins as an empty dictionary that gets
    filled as the packet is parsed. The first 7 items in the dictionary make up the
    packet header (accessed with ``CCSDSPacket.header``), and the rest of the items
    make up the user data (accessed with ``CCSDSPacket.user_data``). To access the
    raw bytes of the packet, use the ``CCSDSPacket.binary_data`` attribute.
    """

    def __init__(self, *args, **kwargs):
        warnings.warn(
            "The CCSDSPacket class is deprecated and will be removed in a future release. "
            "Use the SpacePacket class instead (no CCSDS prefix).",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(*args, **kwargs)


def ccsds_generator(
    binary_data: io.BufferedIOBase | io.RawIOBase | socket.socket | bytes,
    *,
    buffer_read_size_bytes: int | None = None,
    show_progress: bool = False,
    skip_header_bytes: int = 0,
    combine_segmented_packets: bool = False,
    secondary_header_bytes: int = 0,
) -> Iterator[CCSDSPacketBytes]:
    """A generator that reads raw packet data from a filelike object or a socket.

    Each iteration of the generator yields a ``CCSDSPacketBytes`` object that makes up
    a single CCSDS packet. If combining segmented packets is enabled, the generator will
    combine segmented packets into a single packet for parsing. This is useful for parsing
    packets that are split into multiple packets due to size constraints.

    Parameters
    ----------
    binary_data : Union[io.BufferedIOBase, io.RawIOBase, socket.socket, bytes]
        Binary data source containing CCSDSPackets.
    buffer_read_size_bytes : int, optional
        Number of bytes to read from e.g. a BufferedReader or socket binary data source on each read attempt.
        If None, defaults to 4096 bytes from a socket, -1 (full read) from a file.
    show_progress : bool
        Default False.
        If True, prints a status bar. Note that for socket sources, the percentage will be zero until the generator
        ends.
    skip_header_bytes : int
        Default 0. The parser skips this many bytes at the beginning of every packet. This allows dynamic stripping
        of additional header data that may be prepended to packets in "raw record" file formats.
    combine_segmented_packets : bool
        Default False. If True, combines segmented packets into a single packet for parsing. This is useful for
        parsing packets that are split into multiple packets due to size constraints. The packet data is combined
        by concatenating the data from each packet together. The combined packet is then parsed as a single packet.
        Only the first CCSDS header is kept when concatenating continued packets. CCSDS headers (and secondary headers)
        from continuation packets are discarded.
    secondary_header_bytes : int
        Default 0. The length of the secondary header in bytes.
        This is used to skip the secondary header of segmented packets.
        The byte layout within the returned packet has all data concatenated together as follows:
        [packet0header, packet0secondaryheader, packet0data, packet1data, packet2data, ...].

    Yields
    -------
    CCSDSPacketBytes
        The bytes of a single CCSDS packet.
    """
    n_bytes_parsed = 0  # Keep track of how many bytes we have parsed
    n_packets_parsed = 0  # Keep track of how many packets we have parsed
    header_length_bytes = CCSDSPacketBytes.HEADER_LENGTH_BYTES
    # Used to keep track of any continuation packets that we encounter
    # gathering them all up before combining them into a single packet, lookup is by APID.
    # _segmented_packets[APID] = [CCSDSPacketBytes, ...]
    _segmented_packets = {}
    read_buffer, total_length_bytes, read_bytes_from_source, buffer_read_size_bytes = _setup_binary_reader(
        binary_data, buffer_read_size_bytes
    )
    current_pos = 0  # Keep track of where we are in the buffer

    # ========
    # Packet loop. Each iteration of this loop yields a CCSDSPacketBytes object
    # ========
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
        while len(read_buffer) - current_pos < skip_header_bytes + header_length_bytes:
            result = read_bytes_from_source(buffer_read_size_bytes)
            if not result:  # If there is verifiably no more data to add, break
                break
            read_buffer += result
        # Skip the header bytes
        current_pos += skip_header_bytes
        if len(read_buffer) - current_pos < header_length_bytes:
            warnings.warn(
                f"{len(read_buffer) - current_pos} bytes left to read is not enough to read "
                f"a CCSDS header ({header_length_bytes} bytes), ending generator with leftover bytes."
            )
            break

        # per the CCSDS spec
        # 4.1.3.5.3 The length count C shall be expressed as:
        #   C = (Total Number of Octets in the Packet Data Field) – 1
        # Use direct bitshift here rather than _extract_bits for speed
        n_bytes_data = ((read_buffer[current_pos + 4] << 8) | read_buffer[current_pos + 5]) + 1
        n_bytes_packet = header_length_bytes + n_bytes_data

        # Fill the buffer enough to read a full packet, taking into account the user data length
        while len(read_buffer) - current_pos < n_bytes_packet:
            result = read_bytes_from_source(buffer_read_size_bytes)
            if not result:  # If there is verifiably no more data to add, break
                break
            read_buffer += result
        if len(read_buffer) - current_pos < n_bytes_packet:
            warnings.warn(
                f"{len(read_buffer) - current_pos} bytes left to read is not enough to read "
                f"a full packet ({n_bytes_packet}) based on the data length field, "
                "ending generator with leftover bytes."
            )
            break

        # Consider it a counted packet once we've verified that we have read the full packet and parsed the header
        # Update the number of packets and bytes parsed
        n_packets_parsed += 1
        n_bytes_parsed += skip_header_bytes + n_bytes_packet

        # current_pos is still before the header, so we are reading the entire packet here
        packet_bytes = read_buffer[current_pos : current_pos + n_bytes_packet]
        current_pos += n_bytes_packet
        # Wrap the bytes in an object that adds convenience methods for parsing the header
        ccsds_packet = CCSDSPacketBytes(packet_bytes)

        if not combine_segmented_packets or ccsds_packet.sequence_flags == SequenceFlags.UNSEGMENTED:
            yield ccsds_packet
        elif ccsds_packet.sequence_flags == SequenceFlags.FIRST:
            _segmented_packets[ccsds_packet.apid] = [ccsds_packet]
            continue
        elif not _segmented_packets.get(ccsds_packet.apid, False):
            warnings.warn(
                f"Continuation packet found without declaring the start, skipping packet with apid {ccsds_packet.apid}."
            )
            continue
        elif ccsds_packet.sequence_flags == SequenceFlags.CONTINUATION:
            _segmented_packets[ccsds_packet.apid].append(ccsds_packet)
            continue
        else:  # raw_packet_data.sequence_flags == packets.SequenceFlags.LAST:
            _segmented_packets[ccsds_packet.apid].append(ccsds_packet)
            # We have received the final packet, close it up and combine all of
            # the segmented packets into a single "packet" for XTCE parsing
            packets = _segmented_packets.pop(ccsds_packet.apid)
            sequence_counts = [p.sequence_count for p in packets]
            if not all(
                (sequence_counts[i + 1] - sequence_counts[i]) % 16384 == 1 for i in range(len(sequence_counts) - 1)
            ):
                warnings.warn(
                    f"Continuation packets for apid {ccsds_packet.apid} "
                    f"are not in sequence {sequence_counts}, skipping these packets."
                )
                continue
            # Add all content (including header) from the first packet
            binary_data = packets[0]
            # Add the continuation packets to the first packet, skipping the headers
            for p in packets[1:]:
                # The continuation packets may or may not have a secondary header,
                # so we need to account for both cases when trimming the initial header
                tmp_header_length = (
                    header_length_bytes + secondary_header_bytes if p.secondary_header_flag else header_length_bytes
                )
                binary_data += p[tmp_header_length:]
            yield CCSDSPacketBytes(binary_data)

    if show_progress:
        _print_progress(
            current_bytes=n_bytes_parsed,
            total_bytes=total_length_bytes,
            start_time_ns=start_time,
            current_packets=n_packets_parsed,
            end="\n",
            log=True,
        )
