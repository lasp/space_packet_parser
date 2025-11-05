"""Utility functions for building packet generators."""

import datetime as dt
import io
import logging
import socket
import time
from functools import singledispatch
from os import PathLike
from pathlib import Path

logger = logging.getLogger(__name__)


@singledispatch
def _read_packet_file(packet_file) -> bytes | io.BufferedIOBase | io.RawIOBase:
    """Read a packet file or file-like object and return an object suitable for passing to a generator.

    Specifically this function prepares the input for use with _setup_binary_reader.

    Parameters
    ----------
    packet_file : Union[str, Path, PathLike, io.BufferedIOBase, io.RawIOBase, bytes]

    Notes
    -----
    This function handles strings and pathlike objects but it reads the full file into memory for the generator.
    This alleviates the need for generators to internally handle opening and closing files.
    For a more memory efficient approach, pass an opened file object.
    """
    raise OSError(f"Unable to open and read packet_file type: {type(packet_file)}")


@_read_packet_file.register(io.BufferedIOBase)
@_read_packet_file.register(io.RawIOBase)
def _(packet_file: io.BufferedIOBase | io.RawIOBase) -> io.BufferedIOBase | io.RawIOBase:
    """File-like object, this can be passed directly to a generator."""
    return packet_file


@_read_packet_file.register
def _(packet_file: bytes) -> bytes:
    """bytes input, return as-is."""
    return packet_file


@_read_packet_file.register
def _(packet_file: str) -> bytes:
    """String file path, open and read bytes."""
    with open(packet_file, "rb") as f:
        return f.read()


@_read_packet_file.register
def _(packet_file: Path) -> bytes:
    """Path file path, open and read bytes.

    Notes
    -----
    This is a bit inefficient as we have to read the entire file into memory, but it does ensure we close the file after reading.
    """
    with packet_file.expanduser().open("rb") as f:
        return f.read()


@_read_packet_file.register
def _(packet_file: PathLike) -> bytes:
    """PathLike file path (e.g. anything supporting the Path interface), open and read bytes.

    Notes
    -----
    This is a bit inefficient as we have to read the entire file into memory, but it does ensure we close the file after reading.
    """
    with open(packet_file, "rb") as f:
        return f.read()


@singledispatch
def _setup_binary_reader(binary_data, buffer_read_size_bytes=None) -> tuple:
    """Helper to set up reading from binary_data (file, socket, bytes) for a packet generator.

    Parameters
    ----------
    binary_data : Union[io.BufferedIOBase, socket.socket, bytes]
        The binary data source to read from.
    buffer_read_size_bytes : Optional[int]
        The number of bytes to read at a time from the source. If None, defaults to a sensible value based on the type of source.

    Returns
    -------
    read_buffer, total_length_bytes, read_bytes_from_source, buffer_read_size_bytes

    Notes
    -----
    This function does not handle pathlike objects. It expects objects to be opened and readable already.
    """
    raise OSError(f"Unrecognized data source: {binary_data}")


@_setup_binary_reader.register(io.BufferedIOBase)
@_setup_binary_reader.register(io.RawIOBase)
def _(binary_data: io.BufferedIOBase | io.RawIOBase, buffer_read_size_bytes=None) -> tuple:
    """Set up a binary reader from a file-like object."""
    read_buffer = b""
    if buffer_read_size_bytes is None:
        # Default to a full read of the file
        buffer_read_size_bytes = -1
    total_length_bytes = binary_data.seek(0, io.SEEK_END)
    binary_data.seek(0, 0)
    read_bytes_from_source = binary_data.read
    logger.info(
        f"Creating packet generator from a filelike object, {binary_data}. Total length is {total_length_bytes} bytes"
    )
    return read_buffer, total_length_bytes, read_bytes_from_source, buffer_read_size_bytes


@_setup_binary_reader.register
def _(binary_data: socket.socket, buffer_read_size_bytes=None) -> tuple:
    """Set up a binary reader from a socket object."""
    read_buffer = b""
    total_length_bytes = None  # We don't know how long it is
    if buffer_read_size_bytes is None:
        # Default to 4096 bytes from a socket
        buffer_read_size_bytes = 4096
    read_bytes_from_source = binary_data.recv
    logger.info("Creating packet generator to read from a socket. Total length to parse is unknown.")
    return read_buffer, total_length_bytes, read_bytes_from_source, buffer_read_size_bytes


@_setup_binary_reader.register
def _(binary_data: bytes, buffer_read_size_bytes=None) -> tuple:
    """Set up a binary reader from a bytes object."""
    read_buffer = b""
    read_buffer = binary_data
    total_length_bytes = len(read_buffer)

    def read_bytes_from_source(size: int) -> bytes:
        """No data to read, we've filled the read_buffer already."""
        return b""

    logger.info(f"Creating packet generator from a bytes object. Total length is {total_length_bytes} bytes")
    return read_buffer, total_length_bytes, read_bytes_from_source, buffer_read_size_bytes


@_setup_binary_reader.register
def _(binary_data: io.TextIOWrapper, buffer_read_size_bytes=None):
    """Informative error if someone tries to pass a text file."""
    raise OSError("Packet data file opened in TextIO mode. You must open packet data in binary mode.")


def _print_progress(
    *,
    current_bytes: int,
    total_bytes: int | None,
    start_time_ns: int,
    current_packets: int,
    end: str = "\r",
    log: bool = False,
):
    """Prints a progress bar for a packet generator, including statistics on parsing rate.

    Parameters
    ----------
    current_bytes : int
        Number of bytes parsed so far.
    total_bytes : Optional[int]
        Number of total bytes to parse, if known. None otherwise.
    current_packets : int
        Number of packets parsed so far.
    start_time_ns : int
        Start time on system clock, in nanoseconds.
    end : str
        Print function end string. Default is `\\r` to create a dynamically updating loading bar.
    log : bool
        If True, log the progress bar at INFO level.
    """
    progress_char = "="
    bar_length = 20

    if total_bytes is not None:  # If we actually have an endpoint (i.e. not using a socket)
        percentage: str | int = int((current_bytes / total_bytes) * 100)  # Percent Completed Calculation
        progress = int((bar_length * current_bytes) / total_bytes)  # Progress Done Calculation
    else:
        percentage = "???"
        progress = 0

    # Fast calls initially on Windows can result in a zero elapsed time
    elapsed_ns = max(time.time_ns() - start_time_ns, 1)
    delta = dt.timedelta(microseconds=elapsed_ns / 1e3)
    kbps = int(current_bytes * 8e6 / elapsed_ns)  # 8 bits per byte, 1E9 s per ns, 1E3 bits per kb
    pps = int(current_packets * 1e9 / elapsed_ns)
    info_str = (
        f"[Elapsed: {delta}, Parsed {current_bytes} bytes ({current_packets} packets) at {kbps}kb/s ({pps}pkts/s)]"
    )
    loadbar = f"Progress: [{progress * progress_char:{bar_length}}]{percentage}% {info_str}"
    print(loadbar, end=end)
    if log:
        logger.info(loadbar)
