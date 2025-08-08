"""Tests for common module"""

import pytest

from space_packet_parser import common


def test_attr_comparable():
    """Test abstract class that allows comparisons based on all non-callable attributes"""

    class TestClass(common.AttrComparable):
        """Test Class"""

        def __init__(self, public, private, dunder):
            self.public = public
            self._private = private
            self.__dunder = dunder  # Dundered attributes are ignored (they get mangled by class name on construction)

        @property
        def entertained(self):
            """Properties are compared"""
            return 10 * self.public

        def ignored(self, x):
            """Methods are ignored"""
            return 2 * x

    a = TestClass(1, 2, 9)
    a.__doc__ = "foobar"  # Ignored dunder method
    b = TestClass(1, 2, 10)
    assert a == b
    a.public += 1  # Change an attribute that _does_ get compared
    with pytest.raises(AssertionError):
        assert a == b


@pytest.mark.parametrize(
    ("raw_value", "start", "nbits", "expected"),
    [
        (0b11000000, 0, 2, 0b11),
        (0b11000000, 1, 2, 0b10),
        (0b11000000, 2, 2, 0b00),
        (0b11000011, 6, 2, 0b11),
        (0b11000011, 7, 1, 0b1),
        # Go across byte boundaries
        (0b1100001111000011, 6, 4, 0b1111),
        (0b1100001111000011, 6, 6, 0b111100),
        (0b1100001111000011, 8, 6, 0b110000),
        (0b1100001111000011, 8, 8, 0b11000011),
        # Multiple bytes
        (0b110000111100001100000000, 8, 10, 0b1100001100),
        (0b110000111100001100000000, 0, 24, 0b110000111100001100000000),
    ],
)
def test_raw_packet_reads(raw_value, start, nbits, expected):
    raw_bytes = raw_value.to_bytes((raw_value.bit_length() + 7) // 8, "big")
    packet = common.SpacePacket(binary_data=raw_bytes)
    packet._parsing_pos = start
    assert packet._read_from_binary_as_int(nbits) == expected
    assert packet._parsing_pos == start + nbits
    # Reset the position and read again but as raw bytes this time
    packet._parsing_pos = start
    # the value 0 has a bit_length of 0, so we need to ensure we have at least 1 byte
    assert packet._read_from_binary_as_bytes(nbits) == expected.to_bytes(
        (max(expected.bit_length(), 1) + 7) // 8, "big"
    )
    assert packet._parsing_pos == start + nbits


def test_read_beyond_end_of_packet():
    packet = common.SpacePacket(binary_data=b"123")
    with pytest.raises(ValueError, match="Tried to read beyond the end of the packet"):
        packet._read_from_binary_as_bytes(25)
    with pytest.raises(ValueError, match="Tried to read beyond the end of the packet"):
        packet._read_from_binary_as_int(25)


def test_packet_data_lookups():
    packet = common.SpacePacket(binary_data=b"123")
    assert packet.binary_data == b"123"
    # There are no items yet, so it should be an empty dictionary
    assert packet == {}
    # Now populate some packet items
    packet.update({x: x for x in range(10)})
    assert packet[5] == 5
    assert packet == {x: x for x in range(10)}

    with pytest.raises(KeyError):
        packet[10]

    # Deprecated properties that can be removed in the future
    with pytest.warns(DeprecationWarning, match="The header property is deprecated"):
        assert packet.header == {x: x for x in range(7)}
    with pytest.warns(DeprecationWarning, match="The user_data property is deprecated"):
        assert packet.user_data == {x: x for x in range(7, 10)}
    with pytest.warns(DeprecationWarning, match="The raw_data property is deprecated"):
        assert packet.raw_data == b"123"
    with pytest.warns(DeprecationWarning, match="The 'raw_data' keyword argument is deprecated"):
        assert common.SpacePacket(binary_data=b"123") == common.SpacePacket(raw_data=b"123")


def test_deprecated_packet_module():
    with pytest.warns(DeprecationWarning, match="The space_packet_parser.packets module is deprecated"):
        from space_packet_parser import packets
    assert packets.SpacePacket == common.SpacePacket


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
