"""Tests for the generators.utils module"""

import io
import socket
from unittest.mock import Mock

import pytest

from space_packet_parser.generators.utils import _read_packet_file, _setup_binary_reader


@pytest.mark.parametrize(
    ("input_data", "expected_data"),
    [
        pytest.param(b"test packet data", b"test packet data", id="bytes-direct"),
        pytest.param(b"\x01\x02\x03\x04", b"\x01\x02\x03\x04", id="bytes-binary"),
        pytest.param(b"", b"", id="bytes-empty"),
    ],
)
def test_read_packet_file_bytes(input_data, expected_data):
    """Test _read_packet_file with bytes input."""
    result = _read_packet_file(input_data)
    assert result == expected_data
    assert isinstance(result, bytes)
    _setup_binary_reader(result)


@pytest.mark.parametrize(
    "file_content",
    [
        b"test file content",
        b"\x00\x01\x02\x03\x04\x05",
        b"",
        b"\xff" * 1000,  # Larger file
    ],
)
def test_read_packet_file_string_path(tmp_path, file_content):
    """Test _read_packet_file with string file path."""
    test_file = tmp_path / "test_packet.bin"
    test_file.write_bytes(file_content)

    result = _read_packet_file(str(test_file))
    assert result == file_content
    assert isinstance(result, bytes)
    _setup_binary_reader(result)


@pytest.mark.parametrize(
    "file_content",
    [
        b"path object test",
        b"\x10\x20\x30",
        b"",
    ],
)
def test_read_packet_file_path_object(tmp_path, file_content):
    """Test _read_packet_file with Path object."""
    test_file = tmp_path / "test_packet.bin"
    test_file.write_bytes(file_content)

    result = _read_packet_file(test_file)
    assert result == file_content
    assert isinstance(result, bytes)
    _setup_binary_reader(result)


@pytest.mark.parametrize(
    "file_content",
    [
        b"buffered io test",
        b"\x01\x02\x03",
        b"",
    ],
)
def test_read_packet_file_buffered_io(file_content):
    """Test _read_packet_file with BufferedIOBase (BytesIO)."""
    bio = io.BytesIO(file_content)
    result = _read_packet_file(bio)
    assert result.read() == file_content
    _setup_binary_reader(result)


def test_read_packet_file_raw_io(tmp_path):
    """Test _read_packet_file with RawIOBase (opened file)."""
    test_content = b"raw io test"
    test_file = tmp_path / "test_packet.bin"
    test_file.write_bytes(test_content)

    with open(test_file, "rb") as f:
        result = _read_packet_file(f)
        assert result.read() == test_content
        _setup_binary_reader(result)


@pytest.mark.parametrize(
    ("input_data", "expected_error", "error_pattern"),
    [
        pytest.param(42, OSError, r"Unable to open and read packet_file type: <class 'int'>", id="unsupported-int"),
        pytest.param([], OSError, r"Unable to open and read packet_file type: <class 'list'>", id="unsupported-list"),
        pytest.param({}, OSError, r"Unable to open and read packet_file type: <class 'dict'>", id="unsupported-dict"),
        pytest.param(
            None, OSError, r"Unable to open and read packet_file type: <class 'NoneType'>", id="unsupported-none"
        ),
    ],
)
def test_read_packet_file_unsupported_types(input_data, expected_error, error_pattern):
    """Test _read_packet_file with unsupported input types."""
    with pytest.raises(expected_error, match=error_pattern):
        _read_packet_file(input_data)


@pytest.mark.parametrize(
    ("file_content", "buffer_size", "expected_buffer_size"),
    [
        pytest.param(b"test file io", None, -1, id="filelike-default-buffer"),
        pytest.param(b"test file io", 1024, 1024, id="filelike-custom-buffer"),
        pytest.param(b"\x01\x02\x03", 512, 512, id="filelike-small-custom-buffer"),
        pytest.param(b"", None, -1, id="filelike-empty-file"),
    ],
)
def test_setup_binary_reader_file_like(tmp_path, file_content, buffer_size, expected_buffer_size):
    """Test _setup_binary_reader with file-like objects."""
    test_file = tmp_path / "test_packet.bin"
    test_file.write_bytes(file_content)

    with open(test_file, "rb") as f:
        read_buffer, total_length, read_func, actual_buffer_size = _setup_binary_reader(f, buffer_size)

        assert read_buffer == b""
        assert total_length == len(file_content)
        assert callable(read_func)
        assert actual_buffer_size == expected_buffer_size
        assert read_func == f.read


def test_setup_binary_reader_bytesio():
    """Test _setup_binary_reader with BytesIO object."""
    test_data = b"bytesio test data"
    bio = io.BytesIO(test_data)

    read_buffer, total_length, read_func, buffer_size = _setup_binary_reader(bio)

    assert read_buffer == b""
    assert total_length == len(test_data)
    assert callable(read_func)
    assert buffer_size == -1
    assert read_func == bio.read


@pytest.mark.parametrize(
    ("buffer_size", "expected_buffer_size"),
    [
        pytest.param(None, 4096, id="socket-default-buffer"),
        pytest.param(8192, 8192, id="socket-custom-buffer"),
        pytest.param(1024, 1024, id="socket-small-buffer"),
    ],
)
def test_setup_binary_reader_socket(buffer_size, expected_buffer_size):
    """Test _setup_binary_reader with socket objects."""
    mock_socket = Mock(spec=socket.socket)

    read_buffer, total_length, read_func, actual_buffer_size = _setup_binary_reader(mock_socket, buffer_size)

    assert read_buffer == b""
    assert total_length is None
    assert callable(read_func)
    assert actual_buffer_size == expected_buffer_size
    assert read_func == mock_socket.recv


@pytest.mark.parametrize(
    "test_bytes",
    [
        b"test bytes data",
        b"\x00\x01\x02\x03",
        b"",
        b"\xff" * 1000,
    ],
)
def test_setup_binary_reader_bytes(test_bytes):
    """Test _setup_binary_reader with bytes objects."""
    read_buffer, total_length, read_func, buffer_size = _setup_binary_reader(test_bytes)

    assert read_buffer == test_bytes
    assert total_length == len(test_bytes)
    assert callable(read_func)
    assert read_func(10) == b""
    assert buffer_size is None


def test_setup_binary_reader_text_file(tmp_path):
    """Test _setup_binary_reader with actual text file (should raise error)."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("text content")

    with open(test_file) as text_file:
        with pytest.raises(OSError, match=r"Packet data file opened in TextIO mode"):
            _setup_binary_reader(text_file)
