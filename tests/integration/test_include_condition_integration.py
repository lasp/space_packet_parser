"""Integration tests for IncludeCondition support using full XTCE documents"""

import struct
from pathlib import Path

import pytest

from space_packet_parser import SpacePacket
from space_packet_parser.xtce import definitions


@pytest.fixture
def xtce_definition():
    """Load the XTCE definition for IncludeCondition testing"""
    test_data_dir = Path(__file__).parent.parent / "test_data"
    xtce_file = test_data_dir / "test_include_condition.xml"
    return definitions.XtcePacketDefinition.from_xtce(xtce_file)


def test_include_condition_both_true(xtce_definition):
    """Test parsing when both conditional parameters should be included (Mode=1, Flag=1)"""
    # Create packet data: Mode=1, Flag=1, OptionalData1=111, OptionalData2=222, MandatoryData=333
    packet_data = struct.pack(">BBHHI", 1, 1, 111, 222, 333)
    packet = SpacePacket(binary_data=packet_data)
    
    # Parse the packet
    xtce_definition.containers["ConditionalTestPacket"].parse(packet)
    
    # Verify all parameters were parsed
    assert packet["Mode"] == 1
    assert packet["Flag"] == 1
    assert packet["OptionalData1"] == 111
    assert packet["OptionalData2"] == 222
    assert packet["MandatoryData"] == 333


def test_include_condition_first_true_second_false(xtce_definition):
    """Test parsing when only first conditional parameter should be included (Mode=1, Flag=0)"""
    # Create packet data: Mode=1, Flag=0, OptionalData1=444, MandatoryData=555
    # OptionalData2 should be skipped
    packet_data = struct.pack(">BBHI", 1, 0, 444, 555)
    packet = SpacePacket(binary_data=packet_data)
    
    # Parse the packet
    xtce_definition.containers["ConditionalTestPacket"].parse(packet)
    
    # Verify correct parameters were parsed
    assert packet["Mode"] == 1
    assert packet["Flag"] == 0
    assert packet["OptionalData1"] == 444
    assert "OptionalData2" not in packet  # Should be skipped
    assert packet["MandatoryData"] == 555


def test_include_condition_first_false_second_true(xtce_definition):
    """Test parsing when only second conditional parameter should be included (Mode=0, Flag=1)"""
    # Create packet data: Mode=0, Flag=1, OptionalData2=666, MandatoryData=777
    # OptionalData1 should be skipped
    packet_data = struct.pack(">BBHI", 0, 1, 666, 777)
    packet = SpacePacket(binary_data=packet_data)
    
    # Parse the packet
    xtce_definition.containers["ConditionalTestPacket"].parse(packet)
    
    # Verify correct parameters were parsed
    assert packet["Mode"] == 0
    assert packet["Flag"] == 1
    assert "OptionalData1" not in packet  # Should be skipped
    assert packet["OptionalData2"] == 666
    assert packet["MandatoryData"] == 777


def test_include_condition_both_false(xtce_definition):
    """Test parsing when both conditional parameters should be skipped (Mode=0, Flag=0)"""
    # Create packet data: Mode=0, Flag=0, MandatoryData=888
    # Both OptionalData1 and OptionalData2 should be skipped
    packet_data = struct.pack(">BBI", 0, 0, 888)
    packet = SpacePacket(binary_data=packet_data)
    
    # Parse the packet
    xtce_definition.containers["ConditionalTestPacket"].parse(packet)
    
    # Verify correct parameters were parsed
    assert packet["Mode"] == 0
    assert packet["Flag"] == 0
    assert "OptionalData1" not in packet  # Should be skipped
    assert "OptionalData2" not in packet  # Should be skipped
    assert packet["MandatoryData"] == 888


def test_include_condition_with_generator(xtce_definition):
    """Test parsing multiple packets using a generator"""
    # Create multiple test packets
    packets_data = [
        struct.pack(">BBHHI", 1, 1, 100, 200, 300),  # Both included
        struct.pack(">BBHI", 1, 0, 400, 500),        # Only OptionalData1
        struct.pack(">BBHI", 0, 1, 600, 700),        # Only OptionalData2
        struct.pack(">BBI", 0, 0, 800),              # Neither included
    ]
    
    # Parse all packets
    parsed_packets = []
    for packet_data in packets_data:
        packet = SpacePacket(binary_data=packet_data)
        xtce_definition.containers["ConditionalTestPacket"].parse(packet)
        parsed_packets.append(packet)
    
    # Verify first packet (both included)
    assert parsed_packets[0]["Mode"] == 1
    assert parsed_packets[0]["Flag"] == 1
    assert parsed_packets[0]["OptionalData1"] == 100
    assert parsed_packets[0]["OptionalData2"] == 200
    assert parsed_packets[0]["MandatoryData"] == 300
    
    # Verify second packet (only OptionalData1)
    assert parsed_packets[1]["Mode"] == 1
    assert parsed_packets[1]["Flag"] == 0
    assert parsed_packets[1]["OptionalData1"] == 400
    assert "OptionalData2" not in parsed_packets[1]
    assert parsed_packets[1]["MandatoryData"] == 500
    
    # Verify third packet (only OptionalData2)
    assert parsed_packets[2]["Mode"] == 0
    assert parsed_packets[2]["Flag"] == 1
    assert "OptionalData1" not in parsed_packets[2]
    assert parsed_packets[2]["OptionalData2"] == 600
    assert parsed_packets[2]["MandatoryData"] == 700
    
    # Verify fourth packet (neither included)
    assert parsed_packets[3]["Mode"] == 0
    assert parsed_packets[3]["Flag"] == 0
    assert "OptionalData1" not in parsed_packets[3]
    assert "OptionalData2" not in parsed_packets[3]
    assert parsed_packets[3]["MandatoryData"] == 800


def test_include_condition_bit_position_tracking(xtce_definition):
    """Test that bit position tracking remains accurate when parameters are skipped"""
    # Create packet with Mode=0, Flag=0 (both optional params skipped)
    packet_data = struct.pack(">BBI", 0, 0, 12345678)
    packet = SpacePacket(binary_data=packet_data)
    
    # Parse the packet
    xtce_definition.containers["ConditionalTestPacket"].parse(packet)
    
    # Verify that MandatoryData was parsed correctly despite skipped parameters
    assert packet["MandatoryData"] == 12345678
    
    # Verify bit position tracking is correct (2 bytes for Mode+Flag, 4 bytes for MandatoryData = 48 bits)
    assert packet._parsing_pos == 48
