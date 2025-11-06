"""Tests for packets"""

import socket

import pytest

import space_packet_parser.generators
from space_packet_parser import SpacePacket, common
from space_packet_parser.generators import ccsds
from space_packet_parser.xtce import definitions


@pytest.mark.parametrize(
    ("input_var", "input_value"),
    [
        ("version_number", 0),
        ("version_number", 7),
        ("type", 0),
        ("type", 1),
        ("secondary_header_flag", 0),
        ("secondary_header_flag", 1),
        ("apid", 0),
        ("apid", 2**11 - 1),
        ("sequence_flags", 0),
        ("sequence_flags", 3),
        ("sequence_count", 0),
        ("sequence_count", 2**14 - 1),
        ("data", bytes(1)),
        pytest.param("data", bytes(65536), id="max-bytes"),
    ],
)
def test_create_ccsds_packet_input_range(input_var, input_value):
    """Validate the min/max integer inputs"""
    p = ccsds.create_ccsds_packet(**{input_var: input_value})
    if input_var == "data":
        assert p[6:] == input_value
    else:
        assert getattr(p, input_var) == input_value


@pytest.mark.parametrize(
    ("input_var", "input_value", "err_msg"),
    [
        ("version_number", -1, "version_number must be between 0 and 7"),
        ("version_number", 8, "version_number must be between 0 and 7"),
        ("type", -1, "type_ must be 0 or 1"),
        ("type", 2, "type_ must be 0 or 1"),
        ("secondary_header_flag", -1, "secondary_header_flag must be 0 or 1"),
        ("secondary_header_flag", 2, "secondary_header_flag must be 0 or 1"),
        ("apid", -1, "apid must be between 0 and 2047"),
        ("apid", 2**11, "apid must be between 0 and 2047"),
        ("sequence_flags", -1, "sequence_flags must be between 0 and 3"),
        ("sequence_flags", 4, "sequence_flags must be between 0 and 3"),
        ("sequence_count", -1, "sequence_count must be between 0 and 16383"),
        ("sequence_count", 2**14, "sequence_count must be between 0 and 16383"),
        ("data", bytes(0), r"length of data \(in bytes\) must be between 1 and 65536"),
        pytest.param("data", bytes(65537), r"length of data \(in bytes\) must be between 1 and 65536", id="max-bytes"),
    ],
)
def test_create_ccsds_packet_value_range_error(input_var, input_value, err_msg):
    """Validate the min/max integer inputs"""
    with pytest.raises(ValueError, match=err_msg):
        ccsds.create_ccsds_packet(**{input_var: input_value})


@pytest.mark.parametrize(
    "input_var", ["version_number", "type", "secondary_header_flag", "apid", "sequence_flags", "sequence_count", "data"]
)
@pytest.mark.parametrize("input_value", [1.0, "1", 0.5])
def test_create_ccsds_packet_type_validation(input_var, input_value):
    """Only integers are allowed for the header fields and bytes for the data field."""
    with pytest.raises(TypeError):
        ccsds.create_ccsds_packet(**{input_var: input_value})


def test_raw_packet_attributes():
    p = ccsds.create_ccsds_packet(
        data=b"123", version_number=3, type=1, secondary_header_flag=1, apid=1234, sequence_flags=2, sequence_count=5
    )
    assert p.version_number == 3
    assert p.type == 1
    assert p.secondary_header_flag == 1
    assert p.apid == 1234
    assert p.sequence_flags == 2
    assert p.sequence_count == 5
    assert len(p) == 6 + 3
    assert p[6:] == b"123"


def test_ccsds_packet_data_lookups():
    # Deprecated CCSDSPacket class with header/user_data fields
    with pytest.warns(DeprecationWarning, match="The CCSDSPacket class is deprecated"):
        packet = ccsds.CCSDSPacket(binary_data=b"123")
    assert packet.binary_data == b"123"
    # There are no items yet, so it should be an empty dictionary
    assert packet == {}
    with pytest.warns(DeprecationWarning, match="The header property"):
        assert packet.header == {}
    with pytest.warns(DeprecationWarning, match="The user_data property"):
        assert packet.user_data == {}
    # Deprecated CCSDSPacket class, an instance of the new Packet class
    # can be removed in a future version
    with pytest.warns(DeprecationWarning, match="The CCSDSPacket class is deprecated"):
        assert isinstance(ccsds.CCSDSPacket(), SpacePacket)


def test_continuation_packets(test_data_dir):
    # This definition has 65 bytes worth of data
    d = definitions.XtcePacketDefinition.from_xtce(test_data_dir / "test_xtce.xml")
    # We can put that all in one unsegmented packet, just to verify this is working as expected
    raw_bytes = ccsds.create_ccsds_packet(data=b"0" * 65, apid=11, sequence_flags=ccsds.SequenceFlags.UNSEGMENTED)
    ccsds_generator = space_packet_parser.generators.ccsds_generator(raw_bytes)
    orig_packets = [d.parse_bytes(binary_data) for binary_data in ccsds_generator]
    assert len(orig_packets) == 1

    # Remove the sequence flags, counter, and packet length, as they are expected to vary across tests
    def remove_keys(d):
        d.pop("SEQ_FLGS")
        d.pop("PKT_LEN")
        d.pop("SRC_SEQ_CTR")

    remove_keys(orig_packets[0])

    # Now we will split the data across 2 CCSDS packets, but expect them to be combined into one for parsing purposes
    p0 = ccsds.create_ccsds_packet(data=b"0" * 64, apid=11, sequence_flags=ccsds.SequenceFlags.FIRST, sequence_count=0)
    p1 = ccsds.create_ccsds_packet(data=b"0" * 1, apid=11, sequence_flags=ccsds.SequenceFlags.LAST, sequence_count=1)
    raw_bytes = p0 + p1
    result_packets = [
        d.parse_bytes(packet)
        for packet in space_packet_parser.generators.ccsds_generator(raw_bytes, combine_segmented_packets=True)
    ]
    remove_keys(result_packets[0])
    assert result_packets == orig_packets

    # Now we will split the data across 3 CCSDS packets and test the sequence_count wrap-around
    p0 = ccsds.create_ccsds_packet(
        data=b"0" * 63, apid=11, sequence_flags=ccsds.SequenceFlags.FIRST, sequence_count=16382
    )
    p1 = ccsds.create_ccsds_packet(
        data=b"0" * 1, apid=11, sequence_flags=ccsds.SequenceFlags.CONTINUATION, sequence_count=16383
    )
    p2 = ccsds.create_ccsds_packet(data=b"0" * 1, apid=11, sequence_flags=ccsds.SequenceFlags.LAST, sequence_count=0)
    raw_bytes = p0 + p1 + p2
    result_packets = [
        d.parse_bytes(packet)
        for packet in space_packet_parser.generators.ccsds_generator(raw_bytes, combine_segmented_packets=True)
    ]
    remove_keys(result_packets[0])
    assert result_packets == orig_packets

    # Test stripping secondary headers (4 bytes per packet), should keep the first packet's header,
    # but skip the following
    # Add in 4 1s to the 2nd and 3rd packet that should be removed
    p0 = ccsds.create_ccsds_packet(
        data=b"0" * 63,
        apid=11,
        sequence_flags=ccsds.SequenceFlags.FIRST,
        sequence_count=16382,
        secondary_header_flag=False,
    )
    p1 = ccsds.create_ccsds_packet(
        data=b"1" * 4 + b"0" * 1,
        apid=11,
        sequence_flags=ccsds.SequenceFlags.CONTINUATION,
        sequence_count=16383,
        secondary_header_flag=True,
    )
    p2 = ccsds.create_ccsds_packet(
        data=b"1" * 4 + b"0" * 1,
        apid=11,
        sequence_flags=ccsds.SequenceFlags.LAST,
        sequence_count=0,
        secondary_header_flag=True,
    )
    raw_bytes = p0 + p1 + p2
    result_packets = [
        d.parse_bytes(packet)
        for packet in space_packet_parser.generators.ccsds_generator(
            raw_bytes, combine_segmented_packets=True, secondary_header_bytes=4
        )
    ]
    remove_keys(result_packets[0])
    assert result_packets == orig_packets


def test_continuation_packets_secondary_header(test_data_dir):
    """Continuation packets may or may not contain secondary headers.

    When combining the bytes from multiple packets, the secondary headers from all but the first packet
    should be stripped out.
    """
    # 8 byte long data, with 4 byte secondary headers in each packet
    data = b"0" * 8
    p0 = ccsds.create_ccsds_packet(
        data=data, apid=11, sequence_flags=ccsds.SequenceFlags.FIRST, sequence_count=0, secondary_header_flag=True
    )
    p1 = ccsds.create_ccsds_packet(
        data=data,
        apid=11,
        sequence_flags=ccsds.SequenceFlags.CONTINUATION,
        sequence_count=1,
        secondary_header_flag=True,
    )
    p2 = ccsds.create_ccsds_packet(
        data=data, apid=11, sequence_flags=ccsds.SequenceFlags.LAST, sequence_count=2, secondary_header_flag=False
    )
    raw_bytes = p0 + p1 + p2
    result_packets = [
        packet
        for packet in space_packet_parser.generators.ccsds_generator(
            raw_bytes, combine_segmented_packets=True, secondary_header_bytes=4
        )
    ]
    assert len(result_packets) == 1
    # The combined packet should strip the secondary header from packet 2, but packet 3 has no secondary header
    combined_packet = result_packets[0]
    assert combined_packet.secondary_header_flag == 1
    # The data should be 8 + 4 + 8 = 20 bytes long
    assert len(combined_packet.user_data) == 20


def test_continuation_packet_warnings(test_data_dir):
    # This definition has 65 bytes worth of data
    d = definitions.XtcePacketDefinition.from_xtce(test_data_dir / "test_xtce.xml")

    # CONTINUATION / LAST without FIRST
    p0 = ccsds.create_ccsds_packet(data=b"0" * 65, apid=11, sequence_flags=ccsds.SequenceFlags.CONTINUATION)
    p1 = ccsds.create_ccsds_packet(data=b"0" * 65, apid=11, sequence_flags=ccsds.SequenceFlags.LAST)
    raw_bytes = p0 + p1
    with pytest.warns(match="Continuation packet found without declaring the start"):
        # Nothing expected to be returned
        assert (
            len(
                [
                    d.parse_bytes(packet)
                    for packet in space_packet_parser.generators.ccsds_generator(
                        raw_bytes, combine_segmented_packets=True
                    )
                ]
            )
            == 0
        )

    # Out of sequence packets
    p0 = ccsds.create_ccsds_packet(data=b"0" * 65, apid=11, sequence_flags=ccsds.SequenceFlags.FIRST, sequence_count=1)
    p1 = ccsds.create_ccsds_packet(data=b"0" * 65, apid=11, sequence_flags=ccsds.SequenceFlags.LAST, sequence_count=0)
    raw_bytes = p0 + p1

    with pytest.warns(match="not in sequence"):
        # Nothing expected to be returned
        assert len(list(space_packet_parser.generators.ccsds_generator(raw_bytes, combine_segmented_packets=True))) == 0


@pytest.mark.parametrize(
    ("start", "nbits"),
    [(0, 1), (0, 16), (0, 8), (0, 9), (3, 5), (3, 8), (3, 13), (7, 1), (7, 2), (7, 8), (8, 1), (8, 8), (15, 1)],
)
def test__extract_bits(start, nbits):
    """Test the _extract_bits function with various start and nbits values"""
    # Test extracting bits from a bitstream
    s = "0000111100001111"
    data = int(s, 2).to_bytes(2, byteorder="big")

    assert common._extract_bits(data, start, nbits) == int(s[start : start + nbits], 2)


def test_ccsds_generator(jpss_test_data_dir):
    """Test ccsds_generator"""
    test_data_file = jpss_test_data_dir / "J01_G011_LZ_2021-04-09T00-00-00Z_V01.DAT1"
    test_packet = ccsds.create_ccsds_packet()  # defaults

    # From file
    with test_data_file.open("rb") as f:
        assert next(space_packet_parser.generators.ccsds_generator(f))

    # From socket
    send, recv = socket.socketpair()
    send.send(test_packet)
    assert next(space_packet_parser.generators.ccsds_generator(recv))
    send.close()
    recv.close()

    # From bytes
    # This covers show_progress conditional code and also the end of the iterator
    gen_from_bytes = space_packet_parser.generators.ccsds_generator(test_packet, show_progress=True)
    assert next(gen_from_bytes)
    with pytest.raises(StopIteration):
        next(gen_from_bytes)

    # From Text file (error)
    with test_data_file.open("rt") as f:
        with pytest.raises(OSError, match="Packet data file opened in TextIO mode"):
            next(space_packet_parser.generators.ccsds_generator(f))

    # Unrecognized source (error)
    with pytest.raises(OSError, match="Unrecognized data source"):
        next(space_packet_parser.generators.ccsds_generator(1))


def test_ccsds_generator_not_enough_bytes():
    """Test ccsds_generator with not enough bytes for a full header"""
    # Not enough bytes for a full CCSDS header (6 bytes) should not yield any packets
    with pytest.warns(
        UserWarning,
        match="3 bytes left to read is not enough to read a CCSDS header",
    ):
        assert len(list(space_packet_parser.generators.ccsds_generator(b"\x00\x01\x02"))) == 0

    # Make a partial packet
    p = ccsds.create_ccsds_packet(data=b"12345")
    # Remove last 2 bytes to make it incomplete
    incomplete_p = p[:-2]
    with pytest.warns(
        UserWarning,
        match="9 bytes left to read is not enough to read a full packet",
    ):
        assert len(list(space_packet_parser.generators.ccsds_generator(incomplete_p))) == 0


@pytest.mark.parametrize(
    "data_length_bytes",
    [
        1,  # Minimum data length
        255,
        256,
        512,  # Can cause issues with bitshift if implemented incorrectly
        1023,
        1024,
        1025,
        65536,  # Maximum data length
    ],
)
def test_ccsds_generator_packet_length_math(data_length_bytes):
    # Test ccsds_generator correctly calculates packet length for various data sizes,
    # especially power-of-2 boundaries
    p = ccsds.create_ccsds_packet(data=b"0" * data_length_bytes)
    parsed_p = next(space_packet_parser.generators.ccsds_generator(p))
    assert len(parsed_p) == data_length_bytes + 6
    assert parsed_p.data_length == data_length_bytes - 1
