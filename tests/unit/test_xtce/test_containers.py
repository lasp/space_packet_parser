"""Tests for the containers module"""

import struct

import pytest

from space_packet_parser import SpacePacket
from space_packet_parser.generators import ccsds
from space_packet_parser.xtce import containers, encodings, parameter_types, parameters


@pytest.fixture
def mock_container_and_packet():
    """Create a dummy packet and associated SequenceContainer to test parsing"""
    # Create parameter types for CCSDS header fields
    uint3_type = parameter_types.IntegerParameterType(
        name="UINT3_Type", encoding=encodings.IntegerDataEncoding(size_in_bits=3, encoding="unsigned")
    )
    uint1_type = parameter_types.IntegerParameterType(
        name="UINT1_Type", encoding=encodings.IntegerDataEncoding(size_in_bits=1, encoding="unsigned")
    )
    uint11_type = parameter_types.IntegerParameterType(
        name="UINT11_Type", encoding=encodings.IntegerDataEncoding(size_in_bits=11, encoding="unsigned")
    )
    uint2_type = parameter_types.IntegerParameterType(
        name="UINT2_Type", encoding=encodings.IntegerDataEncoding(size_in_bits=2, encoding="unsigned")
    )
    uint14_type = parameter_types.IntegerParameterType(
        name="UINT14_Type", encoding=encodings.IntegerDataEncoding(size_in_bits=14, encoding="unsigned")
    )
    uint16_type = parameter_types.IntegerParameterType(
        name="UINT16_Type", encoding=encodings.IntegerDataEncoding(size_in_bits=16, encoding="unsigned")
    )

    # Create parameter types for user data
    uint8_type = parameter_types.IntegerParameterType(
        name="UINT8_Type", encoding=encodings.IntegerDataEncoding(size_in_bits=8, encoding="unsigned")
    )
    uint32_type = parameter_types.IntegerParameterType(
        name="UINT32_Type", encoding=encodings.IntegerDataEncoding(size_in_bits=32, encoding="unsigned")
    )

    # Create CCSDS header parameters
    version_param = parameters.Parameter(name="VERSION", parameter_type=uint3_type)
    type_param = parameters.Parameter(name="TYPE", parameter_type=uint1_type)
    sec_hdr_flag_param = parameters.Parameter(name="SEC_HDR_FLG", parameter_type=uint1_type)
    apid_param = parameters.Parameter(name="PKT_APID", parameter_type=uint11_type)
    seq_flags_param = parameters.Parameter(name="SEQ_FLGS", parameter_type=uint2_type)
    seq_count_param = parameters.Parameter(name="SRC_SEQ_CTR", parameter_type=uint14_type)
    pkt_len_param = parameters.Parameter(name="PKT_LEN", parameter_type=uint16_type)

    # Create user data parameters
    param1 = parameters.Parameter(name="PARAM1", parameter_type=uint8_type, short_description="First test parameter")
    param2 = parameters.Parameter(name="PARAM2", parameter_type=uint16_type, short_description="Second test parameter")
    param3 = parameters.Parameter(name="PARAM3", parameter_type=uint32_type, short_description="Third test parameter")

    # Create a SequenceContainer with CCSDS header parameters followed by user data parameters
    test_container = containers.SequenceContainer(
        name="TestContainer",
        entry_list=[
            version_param,
            type_param,
            sec_hdr_flag_param,
            apid_param,
            seq_flags_param,
            seq_count_param,
            pkt_len_param,
            param1,
            param2,
            param3,
        ],
        short_description="Test container for parsing",
    )

    # Create test data: uint8=42, uint16=1234, uint32=567890123
    test_data = struct.pack(">BHI", 42, 1234, 567890123)

    # Create CCSDS packet with the test data
    packet_bytes = ccsds.create_ccsds_packet(data=test_data, apid=100, sequence_count=42)

    # Debug: print packet structure
    print(f"Test data: {test_data.hex()}")
    print(f"Full packet: {packet_bytes.hex()}")
    print(f"CCSDS header (6 bytes): {packet_bytes.header_values}")
    print(f"User data portion: {packet_bytes.user_data.hex()}")

    # Create SpacePacket from the raw bytes
    test_packet = SpacePacket(binary_data=packet_bytes)

    # Expected result after parsing
    expected_values = {"PARAM1": 42, "PARAM2": 1234, "PARAM3": 567890123}

    return test_container, test_packet, expected_values


def test_sequence_container_parse_from_space_packet(mock_container_and_packet):
    """Test successful parsing of a single SequenceContainer from a SpacePacket with raw bytes"""
    (test_container, test_packet, expected_values) = mock_container_and_packet

    # Parse the packet using the container definition
    test_container.parse(test_packet)

    # Validate the parsed results
    for param_name, expected_value in expected_values.items():
        assert param_name in test_packet, f"Parameter {param_name} not found in parsed packet"
        assert test_packet[param_name] == expected_value, (
            f"Parameter {param_name} value mismatch: expected {expected_value}, got {test_packet[param_name]}"
        )
