"""Fixed length packet generator."""

import socket
import time
from collections.abc import Iterator
from typing import BinaryIO

from space_packet_parser.generators.utils import _print_progress, _setup_binary_reader


def fixed_length_generator(
    binary_data: BinaryIO | socket.socket | bytes,
    *,
    packet_length_bytes: int,
    buffer_read_size_bytes: int | None = None,
    show_progress: bool = False,
) -> Iterator[bytes]:
    """A generator that yields fixed-length chunks from binary_data.

    Parameters
    ----------
    binary_data : Union[BinaryIO, socket.socket, bytes]
        Binary data source.
    packet_length_bytes : int
        Number of bytes per packet to yield.
    buffer_read_size_bytes : int, optional
        Number of bytes to read from the source per read.
    show_progress : bool
        If True, prints a status bar.

    Yields
    ------
    bytes
        Fixed-length packet bytes.
    """
    n_bytes_parsed = 0  # Keep track of how many bytes we have parsed
    n_packets_parsed = 0  # Keep track of how many packets we have parsed
    read_buffer, total_length_bytes, read_bytes_from_source, buffer_read_size_bytes = _setup_binary_reader(
        binary_data, buffer_read_size_bytes
    )
    current_pos = 0  # Keep track of where we are in the buffer
    start_time = time.time_ns()
    while True:
        if n_bytes_parsed == total_length_bytes:
            break
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
        while len(read_buffer) - current_pos < packet_length_bytes:
            result = read_bytes_from_source(buffer_read_size_bytes)
            if not result:
                break
            read_buffer += result
        packet_bytes = read_buffer[current_pos : current_pos + packet_length_bytes]
        current_pos += packet_length_bytes
        n_packets_parsed += 1
        n_bytes_parsed += packet_length_bytes
        yield packet_bytes
    if show_progress:
        _print_progress(
            current_bytes=n_bytes_parsed,
            total_bytes=total_length_bytes,
            start_time_ns=start_time,
            current_packets=n_packets_parsed,
            end="\n",
            log=True,
        )
