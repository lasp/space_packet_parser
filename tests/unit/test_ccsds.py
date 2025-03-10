"""Tests for packets"""
import pytest

from space_packet_parser import Packet, ccsds
from space_packet_parser.xtce import definitions


@pytest.mark.parametrize(("input_var", "input_value"),
                         [("version_number", 0), ("version_number", 7),
                          ("type", 0), ("type", 1),
                          ("secondary_header_flag", 0), ("secondary_header_flag", 1),
                          ("apid", 0), ("apid", 2**11 - 1),
                          ("sequence_flags", 0), ("sequence_flags", 3),
                          ("sequence_count", 0), ("sequence_count", 2**14 - 1),
                          ("data", bytes(1)), pytest.param("data", bytes(65536), id="max-bytes")])
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
        ("type", -1, "type_ must be 0 or 1"), ("type", 2, "type_ must be 0 or 1"),
        ("secondary_header_flag", -1, "secondary_header_flag must be 0 or 1"),
        ("secondary_header_flag", 2, "secondary_header_flag must be 0 or 1"),
        ("apid", -1, "apid must be between 0 and 2047"), ("apid", 2**11, "apid must be between 0 and 2047"),
        ("sequence_flags", -1, "sequence_flags must be between 0 and 3"),
        ("sequence_flags", 4, "sequence_flags must be between 0 and 3"),
        ("sequence_count", -1, "sequence_count must be between 0 and 16383"),
        ("sequence_count", 2**14, "sequence_count must be between 0 and 16383"),
        ("data", bytes(0), r"length of data \(in bytes\) must be between 1 and 65536"),
        pytest.param(
            "data", bytes(65537), r"length of data \(in bytes\) must be between 1 and 65536", id="max-bytes"
        )
    ]
)
def test_create_ccsds_packet_value_range_error(input_var, input_value, err_msg):
    """Validate the min/max integer inputs"""
    with pytest.raises(ValueError, match=err_msg):
        ccsds.create_ccsds_packet(**{input_var: input_value})

@pytest.mark.parametrize("input_var", ["version_number", "type", "secondary_header_flag", "apid",
                                       "sequence_flags", "sequence_count", "data"])
@pytest.mark.parametrize("input_value", [1.0, "1", 0.5])
def test_create_ccsds_packet_type_validation(input_var, input_value):
    """Only integers are allowed for the header fields and bytes for the data field."""
    with pytest.raises(TypeError):
        ccsds.create_ccsds_packet(**{input_var: input_value})


def test_raw_packet_attributes():
    p = ccsds.create_ccsds_packet(data=b"123", version_number=3, type=1, secondary_header_flag=1,
                                    apid=1234, sequence_flags=2, sequence_count=5)
    assert p.version_number == 3
    assert p.type == 1
    assert p.secondary_header_flag == 1
    assert p.apid == 1234
    assert p.sequence_flags == 2
    assert p.sequence_count == 5
    assert len(p) == 6 + 3
    assert p[6:] == b"123"


def test_ccsds_packet_data_lookups():
    # Deprecated CCSDSPacket class, an instance of the new Packet class
    # can be removed in a future version
    with pytest.warns(DeprecationWarning, match="The CCSDSPacket class is deprecated"):
        assert isinstance(ccsds.CCSDSPacket(), Packet)


def test_continuation_packets(test_data_dir):
    # This definition has 65 bytes worth of data
    d = definitions.XtcePacketDefinition.from_xtce(test_data_dir / "test_xtce.xml")
    # We can put that all in one unsegmented packet, just to verify this is working as expected
    raw_bytes = ccsds.create_ccsds_packet(data=b"0"*65, apid=11, sequence_flags=ccsds.SequenceFlags.UNSEGMENTED)
    orig_packets = list(d.packet_generator(raw_bytes))
    assert len(orig_packets) == 1
    # Remove the sequence flags, counter, and packet length, as they are expected to vary across tests
    def remove_keys(d):
        d.pop("SEQ_FLGS")
        d.pop("PKT_LEN")
        d.pop("SRC_SEQ_CTR")
    remove_keys(orig_packets[0])

    # Now we will split the data across 2 CCSDS packets, but expect them to be combined into one for parsing purposes
    p0 = ccsds.create_ccsds_packet(
        data=b"0"*64, apid=11, sequence_flags=ccsds.SequenceFlags.FIRST, sequence_count=0)
    p1 = ccsds.create_ccsds_packet(
        data=b"0"*1, apid=11, sequence_flags=ccsds.SequenceFlags.LAST, sequence_count=1)
    raw_bytes = p0 + p1
    result_packets = [d.parse_bytes(packet)
                      for packet in ccsds.ccsds_generator(raw_bytes, combine_segmented_packets=True)]
    remove_keys(result_packets[0])
    assert result_packets == orig_packets

    # Now we will split the data across 3 CCSDS packets and test the sequence_count wrap-around
    p0 = ccsds.create_ccsds_packet(
        data=b"0"*63, apid=11, sequence_flags=ccsds.SequenceFlags.FIRST, sequence_count=16382)
    p1 = ccsds.create_ccsds_packet(
        data=b"0"*1, apid=11, sequence_flags=ccsds.SequenceFlags.CONTINUATION, sequence_count=16383)
    p2 = ccsds.create_ccsds_packet(
        data=b"0"*1, apid=11, sequence_flags=ccsds.SequenceFlags.LAST, sequence_count=0)
    raw_bytes = p0 + p1 + p2
    result_packets = [d.parse_bytes(packet)
                      for packet in ccsds.ccsds_generator(raw_bytes, combine_segmented_packets=True)]
    remove_keys(result_packets[0])
    assert result_packets == orig_packets

    # Test stripping secondary headers (4 bytes per packet), should keep the first packet's header,
    # but skip the following
    # Add in 4 1s to the 2nd and 3rd packet that should be removed
    p0 = ccsds.create_ccsds_packet(
        data=b"0"*63, apid=11, sequence_flags=ccsds.SequenceFlags.FIRST, sequence_count=16382)
    p1 = ccsds.create_ccsds_packet(
        data=b"1"*4 + b"0"*1, apid=11, sequence_flags=ccsds.SequenceFlags.CONTINUATION, sequence_count=16383)
    p2 = ccsds.create_ccsds_packet(
        data=b"1"*4 + b"0"*1, apid=11, sequence_flags=ccsds.SequenceFlags.LAST, sequence_count=0)
    raw_bytes = p0 + p1 + p2
    result_packets = [d.parse_bytes(packet)
                      for packet in ccsds.ccsds_generator(raw_bytes,
                                                          combine_segmented_packets=True,
                                                          secondary_header_bytes=4)]
    remove_keys(result_packets[0])
    assert result_packets == orig_packets


def test_continuation_packet_warnings(test_data_dir):
    # This definition has 65 bytes worth of data
    d = definitions.XtcePacketDefinition.from_xtce(test_data_dir / "test_xtce.xml")

    # CONTINUATION / LAST without FIRST
    p0 = ccsds.create_ccsds_packet(
        data=b"0"*65, apid=11, sequence_flags=ccsds.SequenceFlags.CONTINUATION)
    p1 = ccsds.create_ccsds_packet(
        data=b"0"*65, apid=11, sequence_flags=ccsds.SequenceFlags.LAST)
    raw_bytes = p0 + p1
    with pytest.warns(match="Continuation packet found without declaring the start"):
        # Nothing expected to be returned
        assert len([d.parse_bytes(packet)
                      for packet in ccsds.ccsds_generator(raw_bytes, combine_segmented_packets=True)]) == 0

    # Out of sequence packets
    p0 = ccsds.create_ccsds_packet(
        data=b"0"*65, apid=11, sequence_flags=ccsds.SequenceFlags.FIRST, sequence_count=1)
    p1 = ccsds.create_ccsds_packet(
        data=b"0"*65, apid=11, sequence_flags=ccsds.SequenceFlags.LAST, sequence_count=0)
    raw_bytes = p0 + p1

    with pytest.warns(match="not in sequence"):
        # Nothing expected to be returned
        assert len([d.parse_bytes(packet)
                      for packet in ccsds.ccsds_generator(raw_bytes, combine_segmented_packets=True)]) == 0
