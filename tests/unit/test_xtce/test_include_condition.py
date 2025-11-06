"""Tests for IncludeCondition support in ParameterRefEntry"""

import struct

import pytest

from space_packet_parser import SpacePacket
from space_packet_parser.xtce import comparisons, containers, encodings, parameter_types, parameters


@pytest.fixture
def parameter_types_fixture():
    """Create common parameter types for testing"""
    return {
        "uint8": parameter_types.IntegerParameterType(
            name="UINT8_Type", encoding=encodings.IntegerDataEncoding(size_in_bits=8, encoding="unsigned")
        ),
        "uint16": parameter_types.IntegerParameterType(
            name="UINT16_Type", encoding=encodings.IntegerDataEncoding(size_in_bits=16, encoding="unsigned")
        ),
        "uint32": parameter_types.IntegerParameterType(
            name="UINT32_Type", encoding=encodings.IntegerDataEncoding(size_in_bits=32, encoding="unsigned")
        ),
    }


def test_parameter_ref_entry_no_condition():
    """Test ParameterRefEntry without any condition - should always parse"""
    # Create parameter type and parameter
    uint8_type = parameter_types.IntegerParameterType(
        name="UINT8_Type", encoding=encodings.IntegerDataEncoding(size_in_bits=8, encoding="unsigned")
    )
    param = parameters.Parameter(name="TestParam", parameter_type=uint8_type)

    # Create ParameterRefEntry without condition
    param_ref_entry = containers.ParameterRefEntry(parameter_ref="TestParam", include_condition=None)

    # Create packet with test data
    test_data = struct.pack(">B", 42)
    packet = SpacePacket(binary_data=test_data)

    # Parse the entry
    param_ref_entry.parse(packet, parameter_lookup={"TestParam": param})

    # Verify parameter was parsed
    assert "TestParam" in packet
    assert packet["TestParam"] == 42


def test_parameter_ref_entry_with_simple_condition_true(parameter_types_fixture):
    """Test ParameterRefEntry with simple condition that evaluates to True"""
    # Create parameters
    flag_param = parameters.Parameter(name="CSFlag", parameter_type=parameter_types_fixture["uint8"])
    checksum_param = parameters.Parameter(name="CheckSum", parameter_type=parameter_types_fixture["uint16"])

    # Create condition: CheckSum is included if CSFlag == 1
    include_condition = comparisons.Comparison(required_value="1", referenced_parameter="CSFlag", operator="==")

    # Create ParameterRefEntry with condition
    checksum_entry = containers.ParameterRefEntry(
        parameter_ref="CheckSum", include_condition=include_condition, repeat_entry=None
    )

    # Create packet with CSFlag=1, CheckSum=1234
    test_data = struct.pack(">BH", 1, 1234)
    packet = SpacePacket(binary_data=test_data)

    # Parse the flag first
    flag_param.parse(packet)
    assert packet["CSFlag"] == 1

    # Now parse the conditional checksum entry
    checksum_entry.parse(packet, parameter_lookup={"CheckSum": checksum_param})

    # Verify checksum was parsed
    assert "CheckSum" in packet
    assert packet["CheckSum"] == 1234


def test_parameter_ref_entry_with_simple_condition_false(parameter_types_fixture):
    """Test ParameterRefEntry with simple condition that evaluates to False"""
    # Create parameters
    flag_param = parameters.Parameter(name="CSFlag", parameter_type=parameter_types_fixture["uint8"])
    checksum_param = parameters.Parameter(name="CheckSum", parameter_type=parameter_types_fixture["uint16"])

    # Create condition: CheckSum is included if CSFlag == 1
    include_condition = comparisons.Comparison(required_value="1", referenced_parameter="CSFlag", operator="==")

    # Create ParameterRefEntry with condition
    checksum_entry = containers.ParameterRefEntry(
        parameter_ref="CheckSum", include_condition=include_condition, repeat_entry=None
    )

    # Create packet with CSFlag=0, CheckSum=1234 (but checksum should be skipped)
    test_data = struct.pack(">BH", 0, 1234)
    packet = SpacePacket(binary_data=test_data)

    # Parse the flag first
    flag_param.parse(packet)
    assert packet["CSFlag"] == 0

    # Now parse the conditional checksum entry
    checksum_entry.parse(packet, parameter_lookup={"CheckSum": checksum_param})

    # Verify checksum was NOT parsed
    assert "CheckSum" not in packet
    # Verify parsing position didn't advance (still at bit 8)
    assert packet._parsing_pos == 8


def test_sequence_container_with_include_condition_true(parameter_types_fixture):
    """Test SequenceContainer with ParameterRefEntry that has IncludeCondition evaluating to True"""
    # Create parameters
    flag_param = parameters.Parameter(name="CSFlag", parameter_type=parameter_types_fixture["uint8"])
    checksum_param = parameters.Parameter(name="CheckSum", parameter_type=parameter_types_fixture["uint16"])
    data_param = parameters.Parameter(name="Data", parameter_type=parameter_types_fixture["uint32"])

    # Create condition
    include_condition = comparisons.Comparison(required_value="1", referenced_parameter="CSFlag", operator="==")

    # Create ParameterRefEntry with condition
    checksum_entry = containers.ParameterRefEntry(parameter_ref="CheckSum", include_condition=include_condition)

    # Create container
    param_lookup = {"CSFlag": flag_param, "CheckSum": checksum_param, "Data": data_param}
    test_container = containers.SequenceContainer(
        name="TestContainer",
        entry_list=[flag_param, checksum_entry, data_param],
        _parameter_lookup=param_lookup,
    )

    # Create packet: CSFlag=1, CheckSum=5678, Data=123456
    test_data = struct.pack(">BHI", 1, 5678, 123456)
    packet = SpacePacket(binary_data=test_data)

    # Parse the container
    test_container.parse(packet)

    # Verify all parameters were parsed
    assert packet["CSFlag"] == 1
    assert packet["CheckSum"] == 5678
    assert packet["Data"] == 123456


def test_sequence_container_with_include_condition_false(parameter_types_fixture):
    """Test SequenceContainer with ParameterRefEntry that has IncludeCondition evaluating to False"""
    # Create parameters
    flag_param = parameters.Parameter(name="CSFlag", parameter_type=parameter_types_fixture["uint8"])
    checksum_param = parameters.Parameter(name="CheckSum", parameter_type=parameter_types_fixture["uint16"])
    data_param = parameters.Parameter(name="Data", parameter_type=parameter_types_fixture["uint32"])

    # Create condition
    include_condition = comparisons.Comparison(required_value="1", referenced_parameter="CSFlag", operator="==")

    # Create ParameterRefEntry with condition
    checksum_entry = containers.ParameterRefEntry(parameter_ref="CheckSum", include_condition=include_condition)

    # Create container
    param_lookup = {"CSFlag": flag_param, "CheckSum": checksum_param, "Data": data_param}
    test_container = containers.SequenceContainer(
        name="TestContainer",
        entry_list=[flag_param, checksum_entry, data_param],
        _parameter_lookup=param_lookup,
    )

    # Create packet: CSFlag=0, CheckSum should be skipped, Data=123456
    # Since checksum is 2 bytes but skipped, we only need CSFlag + Data
    test_data = struct.pack(">BI", 0, 123456)
    packet = SpacePacket(binary_data=test_data)

    # Parse the container
    test_container.parse(packet)

    # Verify flag and data were parsed, but checksum was skipped
    assert packet["CSFlag"] == 0
    assert "CheckSum" not in packet
    assert packet["Data"] == 123456


def test_parameter_ref_entry_with_repeat_entry_raises():
    """Test that ParameterRefEntry with RepeatEntry raises NotImplementedError"""
    # Create parameter
    uint8_type = parameter_types.IntegerParameterType(
        name="UINT8_Type", encoding=encodings.IntegerDataEncoding(size_in_bits=8, encoding="unsigned")
    )
    param = parameters.Parameter(name="TestParam", parameter_type=uint8_type)

    # Create ParameterRefEntry with repeat_entry
    param_ref_entry = containers.ParameterRefEntry(parameter_ref="TestParam", include_condition=None, repeat_entry=True)

    # Create packet
    test_data = struct.pack(">B", 42)
    packet = SpacePacket(binary_data=test_data)

    # Parse should raise NotImplementedError
    with pytest.raises(NotImplementedError, match="RepeatEntry is not currently supported"):
        param_ref_entry.parse(packet, parameter_lookup={"TestParam": param})


def test_parameter_ref_entry_multiple_conditions(parameter_types_fixture):
    """Test ParameterRefEntry with different comparison operators"""
    # Create parameters
    value_param = parameters.Parameter(name="Value", parameter_type=parameter_types_fixture["uint8"])
    result_param = parameters.Parameter(name="Result", parameter_type=parameter_types_fixture["uint16"])

    # Test greater than condition
    include_condition = comparisons.Comparison(required_value="10", referenced_parameter="Value", operator=">")
    result_entry = containers.ParameterRefEntry(parameter_ref="Result", include_condition=include_condition)

    # Test with value > 10 (should include)
    test_data = struct.pack(">BH", 15, 999)
    packet = SpacePacket(binary_data=test_data)
    value_param.parse(packet)
    result_entry.parse(packet, parameter_lookup={"Result": result_param})
    assert packet["Result"] == 999

    # Test with value <= 10 (should skip)
    test_data = struct.pack(">BH", 5, 888)
    packet = SpacePacket(binary_data=test_data)
    value_param.parse(packet)
    result_entry.parse(packet, parameter_lookup={"Result": result_param})
    assert "Result" not in packet


def test_parameter_ref_entry_to_xml_without_condition():
    """Test ParameterRefEntry.to_xml() without condition"""
    from lxml.builder import ElementMaker

    em = ElementMaker(namespace="http://www.omg.org/space/xtce", nsmap={"xtce": "http://www.omg.org/space/xtce"})

    param_ref_entry = containers.ParameterRefEntry(parameter_ref="TestParam")
    xml_element = param_ref_entry.to_xml(elmaker=em)

    # Verify XML structure
    assert xml_element.tag == "{http://www.omg.org/space/xtce}ParameterRefEntry"
    assert xml_element.attrib["parameterRef"] == "TestParam"
    assert len(xml_element) == 0  # No child elements


def test_parameter_ref_entry_to_xml_with_condition():
    """Test ParameterRefEntry.to_xml() with IncludeCondition"""
    from lxml.builder import ElementMaker

    em = ElementMaker(namespace="http://www.omg.org/space/xtce", nsmap={"xtce": "http://www.omg.org/space/xtce"})

    include_condition = comparisons.Comparison(required_value="1", referenced_parameter="CSFlag", operator="==")
    param_ref_entry = containers.ParameterRefEntry(parameter_ref="TestParam", include_condition=include_condition)
    xml_element = param_ref_entry.to_xml(elmaker=em)

    # Verify XML structure
    assert xml_element.tag == "{http://www.omg.org/space/xtce}ParameterRefEntry"
    assert xml_element.attrib["parameterRef"] == "TestParam"
    assert len(xml_element) == 1  # Has IncludeCondition child

    # Verify IncludeCondition
    include_cond_elem = xml_element[0]
    assert include_cond_elem.tag == "{http://www.omg.org/space/xtce}IncludeCondition"
    assert len(include_cond_elem) == 1  # Has Comparison child

    # Verify Comparison
    comparison_elem = include_cond_elem[0]
    assert comparison_elem.tag == "{http://www.omg.org/space/xtce}Comparison"
    assert comparison_elem.attrib["parameterRef"] == "CSFlag"
    assert comparison_elem.attrib["value"] == "1"


def test_sequence_container_with_multiple_conditional_parameters(parameter_types_fixture):
    """Test SequenceContainer with multiple conditional parameters"""
    # Create parameters
    mode_param = parameters.Parameter(name="Mode", parameter_type=parameter_types_fixture["uint8"])
    flag_param = parameters.Parameter(name="Flag", parameter_type=parameter_types_fixture["uint8"])
    data1_param = parameters.Parameter(name="Data1", parameter_type=parameter_types_fixture["uint16"])
    data2_param = parameters.Parameter(name="Data2", parameter_type=parameter_types_fixture["uint16"])
    data3_param = parameters.Parameter(name="Data3", parameter_type=parameter_types_fixture["uint32"])

    # Create conditions
    condition1 = comparisons.Comparison(required_value="1", referenced_parameter="Mode", operator="==")
    condition2 = comparisons.Comparison(required_value="1", referenced_parameter="Flag", operator="==")

    # Create ParameterRefEntries with conditions
    data1_entry = containers.ParameterRefEntry(parameter_ref="Data1", include_condition=condition1)
    data2_entry = containers.ParameterRefEntry(parameter_ref="Data2", include_condition=condition2)

    # Create container
    param_lookup = {
        "Mode": mode_param,
        "Flag": flag_param,
        "Data1": data1_param,
        "Data2": data2_param,
        "Data3": data3_param,
    }
    test_container = containers.SequenceContainer(
        name="TestContainer",
        entry_list=[mode_param, flag_param, data1_entry, data2_entry, data3_param],
        _parameter_lookup=param_lookup,
    )

    # Test case 1: Mode=1, Flag=1 - both Data1 and Data2 should be parsed
    test_data = struct.pack(">BBHHI", 1, 1, 111, 222, 333)
    packet = SpacePacket(binary_data=test_data)
    test_container.parse(packet)
    assert packet["Mode"] == 1
    assert packet["Flag"] == 1
    assert packet["Data1"] == 111
    assert packet["Data2"] == 222
    assert packet["Data3"] == 333

    # Test case 2: Mode=1, Flag=0 - only Data1 should be parsed
    test_data = struct.pack(">BBHI", 1, 0, 444, 555)
    packet = SpacePacket(binary_data=test_data)
    test_container.parse(packet)
    assert packet["Mode"] == 1
    assert packet["Flag"] == 0
    assert packet["Data1"] == 444
    assert "Data2" not in packet
    assert packet["Data3"] == 555

    # Test case 3: Mode=0, Flag=1 - only Data2 should be parsed
    test_data = struct.pack(">BBHI", 0, 1, 666, 777)
    packet = SpacePacket(binary_data=test_data)
    test_container.parse(packet)
    assert packet["Mode"] == 0
    assert packet["Flag"] == 1
    assert "Data1" not in packet
    assert packet["Data2"] == 666
    assert packet["Data3"] == 777

    # Test case 4: Mode=0, Flag=0 - neither Data1 nor Data2 should be parsed
    test_data = struct.pack(">BBI", 0, 0, 888)
    packet = SpacePacket(binary_data=test_data)
    test_container.parse(packet)
    assert packet["Mode"] == 0
    assert packet["Flag"] == 0
    assert "Data1" not in packet
    assert "Data2" not in packet
    assert packet["Data3"] == 888


def test_parameter_ref_entry_from_xml_with_condition():
    """Test parsing ParameterRefEntry from XML with IncludeCondition"""
    from lxml import etree

    xml_str = """
    <ParameterRefEntry parameterRef="CheckSum">
        <IncludeCondition>
            <Comparison parameterRef="CSFlag" value="1" comparisonOperator="==" useCalibratedValue="true"/>
        </IncludeCondition>
    </ParameterRefEntry>
    """
    element = etree.fromstring(xml_str)

    # Parse the ParameterRefEntry
    param_ref_entry = containers.ParameterRefEntry.from_xml(element)

    # Verify structure
    assert param_ref_entry.parameter_ref == "CheckSum"
    assert param_ref_entry.include_condition is not None
    assert isinstance(param_ref_entry.include_condition, comparisons.Comparison)
    assert param_ref_entry.include_condition.referenced_parameter == "CSFlag"
    assert param_ref_entry.include_condition.required_value == "1"
    assert param_ref_entry.include_condition.operator == "=="
    assert param_ref_entry.repeat_entry is None


def test_parameter_ref_entry_from_xml_with_repeat_entry():
    """Test parsing ParameterRefEntry from XML with RepeatEntry"""
    from lxml import etree

    xml_str = """
    <ParameterRefEntry parameterRef="TestParam">
        <RepeatEntry>
            <Count>5</Count>
        </RepeatEntry>
    </ParameterRefEntry>
    """
    element = etree.fromstring(xml_str)

    # Parse the ParameterRefEntry
    param_ref_entry = containers.ParameterRefEntry.from_xml(element)

    # Verify structure
    assert param_ref_entry.parameter_ref == "TestParam"
    assert param_ref_entry.include_condition is None
    assert param_ref_entry.repeat_entry is True  # Placeholder value


def test_parameter_ref_entry_from_xml_without_condition():
    """Test parsing ParameterRefEntry from XML without IncludeCondition"""
    from lxml import etree

    xml_str = '<ParameterRefEntry parameterRef="TestParam"/>'
    element = etree.fromstring(xml_str)

    # Parse the ParameterRefEntry
    param_ref_entry = containers.ParameterRefEntry.from_xml(element)

    # Verify structure
    assert param_ref_entry.parameter_ref == "TestParam"
    assert param_ref_entry.include_condition is None
    assert param_ref_entry.repeat_entry is None
