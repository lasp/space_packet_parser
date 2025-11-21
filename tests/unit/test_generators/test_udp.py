"""Tests for UDP packet generator."""

import socket
from io import BytesIO

import pytest

from space_packet_parser.generators.udp import UDPPacketBytes, create_udp_packet, udp_generator
from space_packet_parser.xtce.definitions import XtcePacketDefinition


@pytest.mark.parametrize(
    ("input_var", "input_value"),
    [
        ("source_port", 0),
        ("source_port", 65535),
        ("dest_port", 0),
        ("dest_port", 65535),
        ("checksum", 0),
        ("checksum", 65535),
        ("data", b""),
        ("data", bytes(1)),
        pytest.param("data", bytes(65527), id="max-data-bytes"),  # 65535 - 8 = 65527 max data
    ],
)
def test_create_udp_packet_input_range(input_var, input_value):
    """Validate the min/max integer inputs for UDP packet creation."""
    p = create_udp_packet(**{input_var: input_value})
    if input_var == "data":
        assert p.data == input_value
    else:
        assert getattr(p, input_var) == input_value


@pytest.mark.parametrize(
    ("input_var", "input_value", "err_msg"),
    [
        ("source_port", -1, "source_port must be between 0 and 65535"),
        ("source_port", 65536, "source_port must be between 0 and 65535"),
        ("dest_port", -1, "dest_port must be between 0 and 65535"),
        ("dest_port", 65536, "dest_port must be between 0 and 65535"),
        ("checksum", -1, "checksum must be between 0 and 65535"),
        ("checksum", 65536, "checksum must be between 0 and 65535"),
        pytest.param(
            "data", bytes(65528), "UDP packet length .* cannot exceed 65535 bytes", id="max-data-bytes-exceeded"
        ),
    ],
)
def test_create_udp_packet_value_range_error(input_var, input_value, err_msg):
    """Validate that out-of-range values raise ValueError with appropriate messages."""
    with pytest.raises(ValueError, match=err_msg):
        create_udp_packet(**{input_var: input_value})


@pytest.mark.parametrize("input_var", ["source_port", "dest_port", "checksum"])
@pytest.mark.parametrize("input_value", [1.0, "1", 0.5])
def test_create_udp_packet_type_validation(input_var, input_value):
    """Only integers are allowed for UDP header fields."""
    with pytest.raises(TypeError):
        create_udp_packet(**{input_var: input_value})


def test_udp_packet_bytes_attributes():
    """Test that UDPPacketBytes properties correctly extract header fields."""
    p = create_udp_packet(
        data=b"test_data",
        source_port=12345,
        dest_port=54321,
        checksum=0xABCD,
    )

    # Check individual properties
    assert p.source_port == 12345
    assert p.dest_port == 54321
    assert p.checksum == 0xABCD
    assert p.length == 8 + 9  # 8-byte header + 9-byte data = 17

    # Check convenience properties
    assert p.header_values == (12345, 54321, 17, 0xABCD)
    assert p.header == p[:8]
    assert len(p.header) == 8
    assert p.data == b"test_data"

    # Check total length
    assert len(p) == 8 + 9


def test_udp_packet_bytes_str_representation():
    """Test the string representation of UDPPacketBytes."""
    p = create_udp_packet(source_port=80, dest_port=443, checksum=12345, data=b"hello")
    str_repr = str(p)
    assert "source_port=80" in str_repr
    assert "dest_port=443" in str_repr
    assert "length=13" in str_repr  # 8 + 5
    assert "checksum=12345" in str_repr


def test_udp_packet_bytes_validation():
    """Test that UDPPacketBytes validates minimum packet length."""
    # Valid minimum packet (8 bytes header, no data)
    valid_packet = create_udp_packet(data=b"")
    assert len(valid_packet) == 8

    # Too short - should raise ValueError
    with pytest.raises(ValueError, match="UDP packet must be at least 8 bytes"):
        UDPPacketBytes(b"1234567")  # Only 7 bytes

    with pytest.raises(ValueError, match="UDP packet must be at least 8 bytes"):
        UDPPacketBytes(b"")  # Empty


def test_udp_generator_from_bytes():
    """Test udp_generator with bytes input."""
    # Single packet
    p1 = create_udp_packet(data=b"packet1", source_port=1234, dest_port=5678)
    packets = list(udp_generator(p1))
    assert len(packets) == 1
    assert packets[0].source_port == 1234
    assert packets[0].dest_port == 5678
    assert packets[0].data == b"packet1"

    # Multiple packets
    p2 = create_udp_packet(data=b"packet2", source_port=9999, dest_port=8888)
    combined = p1 + p2
    packets = list(udp_generator(combined))
    assert len(packets) == 2
    assert packets[0].data == b"packet1"
    assert packets[1].data == b"packet2"
    assert packets[1].source_port == 9999


def test_udp_generator_from_file():
    """Test udp_generator with file-like object (BytesIO)."""
    p1 = create_udp_packet(data=b"file_packet_1", source_port=100)
    p2 = create_udp_packet(data=b"file_packet_2", source_port=200)

    # Create a BytesIO object simulating a file
    file_like = BytesIO(p1 + p2)

    packets = list(udp_generator(file_like))
    assert len(packets) == 2
    assert packets[0].source_port == 100
    assert packets[0].data == b"file_packet_1"
    assert packets[1].source_port == 200
    assert packets[1].data == b"file_packet_2"


def test_udp_generator_from_socket():
    """Test udp_generator with socket input."""
    test_packet = create_udp_packet(data=b"socket_test", source_port=8080, dest_port=9090)

    # Create a socket pair for testing
    send, recv = socket.socketpair()
    send.send(test_packet)

    # Read from the socket
    packet = next(udp_generator(recv))
    assert packet.source_port == 8080
    assert packet.dest_port == 9090
    assert packet.data == b"socket_test"

    send.close()
    recv.close()


def test_udp_generator_show_progress():
    """Test udp_generator with show_progress enabled."""
    p = create_udp_packet(data=b"progress_test")

    # This should not raise an error and should complete the iteration
    gen = udp_generator(p, show_progress=True)
    packets = list(gen)
    assert len(packets) == 1


def test_udp_generator_empty_input():
    """Test udp_generator with empty input."""
    packets = list(udp_generator(b""))
    assert len(packets) == 0


def test_udp_generator_incomplete_header():
    """Test udp_generator with incomplete header data."""
    # Only 5 bytes - not enough for an 8-byte UDP header
    incomplete_data = b"\x00\x01\x02\x03\x04"
    packets = list(udp_generator(incomplete_data))
    assert len(packets) == 0


def test_udp_generator_incomplete_packet():
    """Test udp_generator with incomplete packet data."""
    # Create a packet and truncate it
    p = create_udp_packet(data=b"12345678")
    incomplete_p = p[:-3]  # Remove last 3 bytes

    # The generator should not yield an incomplete packet
    packets = list(udp_generator(incomplete_p))
    assert len(packets) == 0


def test_udp_generator_invalid_length_field():
    """Test udp_generator with invalid length field (less than 8)."""
    # Manually create a packet with invalid length field
    # Length field is at bytes 4-5
    invalid_packet = b"\x00\x50\x00\x50"  # source and dest ports
    invalid_packet += b"\x00\x07"  # Invalid length: 7 (less than minimum of 8)
    invalid_packet += b"\x00\x00"  # checksum

    with pytest.raises(ValueError, match="Invalid UDP length field: 7"):
        list(udp_generator(invalid_packet))


def test_udp_generator_various_packet_sizes():
    """Test udp_generator with various packet sizes to ensure length calculation is correct."""
    test_sizes = [0, 1, 10, 100, 256, 512, 1024, 5000]

    packets_data = b""
    for size in test_sizes:
        p = create_udp_packet(data=b"x" * size, source_port=size)
        packets_data += p

    parsed_packets = list(udp_generator(packets_data))
    assert len(parsed_packets) == len(test_sizes)

    for i, size in enumerate(test_sizes):
        assert parsed_packets[i].source_port == size
        assert len(parsed_packets[i].data) == size
        assert parsed_packets[i].length == 8 + size


def test_udp_generator_large_buffer():
    """Test that large packets trigger buffer trimming (20 MB threshold)."""
    # Create enough packets to exceed 20 MB buffer threshold
    large_packet = create_udp_packet(data=b"x" * 10000)

    # Create 2100 packets (21 MB worth of data)
    packets_data = large_packet * 2100

    # This should work without issues despite buffer trimming
    parsed_packets = list(udp_generator(packets_data))
    assert len(parsed_packets) == 2100

    # Verify all packets are parsed correctly
    for packet in parsed_packets:
        assert len(packet.data) == 10000


def test_udp_generator_with_xtce_parsing(test_data_dir):
    """Test integration of udp_generator with XTCE parsing."""
    # Load the UDP XTCE definition
    udp_xtce_file = test_data_dir / "udp_packet.xml"
    packet_definition = XtcePacketDefinition.from_xtce(udp_xtce_file, root_container_name="UDPPacket")

    # Create a test UDP packet with known values
    test_data = b"Hello, UDP!"
    p = create_udp_packet(
        data=test_data,
        source_port=12345,
        dest_port=54321,
        checksum=0x1234,
    )

    # Parse using the generator and XTCE definition
    packets = list(udp_generator(p))
    assert len(packets) == 1

    parsed = packet_definition.parse_bytes(packets[0], root_container_name="UDPPacket")

    # Verify parsed values match
    assert parsed["SOURCE_PORT"].raw_value == 12345
    assert parsed["DEST_PORT"].raw_value == 54321
    assert parsed["UDP_LENGTH"].raw_value == 8 + len(test_data)
    assert parsed["CHECKSUM"].raw_value == 0x1234
    assert parsed["DATA"].raw_value == test_data


def test_udp_generator_text_file_error(tmp_path):
    """Test that udp_generator raises error for text mode files."""
    # Create a temporary file
    test_file = tmp_path / "test.txt"
    test_file.write_text("not binary data")

    # Open in text mode and try to use it
    with test_file.open("rt") as f:
        with pytest.raises(OSError, match="Packet data file opened in TextIO mode"):
            next(udp_generator(f))


def test_udp_generator_unrecognized_source():
    """Test that udp_generator raises error for unrecognized data sources."""
    with pytest.raises(OSError, match="Unrecognized data source"):
        next(udp_generator(12345))  # Integer is not a valid source
