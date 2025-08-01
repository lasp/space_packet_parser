"""Tests for comparisons"""
import lxml.etree as ElementTree
import pytest

from space_packet_parser import Packet, common
from space_packet_parser.exceptions import ComparisonError
from space_packet_parser.xtce import XTCE_1_2_XMLNS, comparisons


@pytest.mark.parametrize(
    ('xml_string', 'test_parsed_data', 'current_parsed_value', 'expected_comparison_result'),
    [
        (f"""
<xtce:Comparison xmlns:xtce="{XTCE_1_2_XMLNS}"
    comparisonOperator="==" value="678" parameterRef="MSN__PARAM"/>
""",
         Packet(**{'MSN__PARAM': common.FloatParameter(678, 3)}), None, True),
        (f"""
<xtce:Comparison xmlns:xtce="{XTCE_1_2_XMLNS}"
    comparisonOperator="eq" value="678" parameterRef="MSN__PARAM"/>
""",
         Packet(**{'MSN__PARAM': common.FloatParameter(668, 3)}), None, False),
        (f"""
<xtce:Comparison xmlns:xtce="{XTCE_1_2_XMLNS}"
    comparisonOperator="!=" value="678" parameterRef="MSN__PARAM"/>
""",
         Packet(**{'MSN__PARAM': common.FloatParameter(678, 3)}), None, False),
        (f"""
<xtce:Comparison xmlns:xtce="{XTCE_1_2_XMLNS}"
    comparisonOperator="neq" value="678" parameterRef="MSN__PARAM"/>
""",
         Packet(**{'MSN__PARAM': common.FloatParameter(658, 3)}), None, True),
        (f"""
<xtce:Comparison xmlns:xtce="{XTCE_1_2_XMLNS}"
    comparisonOperator="&lt;" value="678" parameterRef="MSN__PARAM"/>
""",
         Packet(**{'MSN__PARAM': common.FloatParameter(679, 3)}), None, False),
        (f"""
<xtce:Comparison xmlns:xtce="{XTCE_1_2_XMLNS}"
    comparisonOperator="lt" value="678" parameterRef="MSN__PARAM"/>
""",
         Packet(**{'MSN__PARAM': common.FloatParameter(670, 3)}), None, True),
        (f"""
<xtce:Comparison xmlns:xtce="{XTCE_1_2_XMLNS}"
    comparisonOperator="&gt;" value="678" parameterRef="MSN__PARAM"/>
""",
         Packet(**{'MSN__PARAM': common.FloatParameter(678, 3)}), None, False),
        (f"""
<xtce:Comparison xmlns:xtce="{XTCE_1_2_XMLNS}"
    comparisonOperator="gt" value="678" parameterRef="MSN__PARAM"/>
""",
         Packet(**{'MSN__PARAM': common.FloatParameter(679, 3)}), None, True),
        (f"""
<xtce:Comparison xmlns:xtce="{XTCE_1_2_XMLNS}"
    comparisonOperator="&lt;=" value="678" parameterRef="MSN__PARAM"/>
""",
         Packet(**{'MSN__PARAM': common.FloatParameter(660, 3)}), None, True),
        (f"""
<xtce:Comparison xmlns:xtce="{XTCE_1_2_XMLNS}"
    comparisonOperator="leq" value="678" parameterRef="MSN__PARAM"/>
""",
         Packet(**{'MSN__PARAM': common.FloatParameter(690, 3)}), None, False),
        (f"""
<xtce:Comparison xmlns:xtce="{XTCE_1_2_XMLNS}"
    comparisonOperator="&gt;=" value="678" parameterRef="MSN__PARAM"/>
""",
         Packet(**{'MSN__PARAM': common.FloatParameter(660, 3)}), None, False),
        (f"""
<xtce:Comparison xmlns:xtce="{XTCE_1_2_XMLNS}"
    comparisonOperator="geq" value="678" parameterRef="MSN__PARAM"/>
""",
         Packet(**{'MSN__PARAM': common.FloatParameter(690, 3)}), None, True),
        (f"""
<xtce:Comparison xmlns:xtce="{XTCE_1_2_XMLNS}"
    comparisonOperator="==" value="678" parameterRef="MSN__PARAM" useCalibratedValue="false"/>
""",
         Packet(**{'MSN__PARAM': common.FloatParameter(690, 678)}), None, True),
        (f"""
<xtce:Comparison xmlns:xtce="{XTCE_1_2_XMLNS}"
    comparisonOperator="==" value="678" parameterRef="MSN__PARAM" useCalibratedValue="true"/>
""",
         Packet(**{'MSN__PARAM': common.FloatParameter(678, 3)}), None, True),
        (f"""
<xtce:Comparison xmlns:xtce="{XTCE_1_2_XMLNS}"
    comparisonOperator="==" value="foostring" parameterRef="MSN__PARAM" useCalibratedValue="false"/>
""",
         Packet(**{'MSN__PARAM': common.StrParameter('calibratedfoostring', 'foostring')}), None, True),
        (f"""
<xtce:Comparison xmlns:xtce="{XTCE_1_2_XMLNS}"
    comparisonOperator="==" value="3.14" parameterRef="MSN__PARAM"/>
""",
         Packet(**{'MSN__PARAM': common.FloatParameter(3.14, 1)}), None, True),
        (f"""
<xtce:Comparison xmlns:xtce="{XTCE_1_2_XMLNS}"
    comparisonOperator="==" value="3.0" parameterRef="REFERENCE_TO_OWN_RAW_VAL"/>
""",
         {}, 3.0, True),
        (f"""
<xtce:Comparison xmlns:xtce="{XTCE_1_2_XMLNS}"
    comparisonOperator="==" value="3" parameterRef="REFERENCE_TO_OWN_RAW_VAL"/>
""",
         {}, 3, True),
        (f"""
<xtce:Comparison xmlns:xtce="{XTCE_1_2_XMLNS}"
    comparisonOperator="==" value="foostr" parameterRef="REFERENCE_TO_OWN_RAW_VAL"/>
""",
         {}, "foostr", True),
        (f"""
<xtce:Comparison xmlns:xtce="{XTCE_1_2_XMLNS}"
    comparisonOperator="==" value="3.0" parameterRef="REFERENCE_TO_OWN_RAW_VAL"/>
""",
         {}, 3, ComparisonError("Fails to parse a float string 3.0 into an int")),
    ]
)
@pytest.mark.filterwarnings("ignore:Performing a comparison against a current value")
def test_comparison(elmaker, xtce_parser,
                    xml_string, test_parsed_data, current_parsed_value, expected_comparison_result):
    """Test Comparison object"""
    element = ElementTree.fromstring(xml_string, parser=xtce_parser)
    comparison = comparisons.Comparison.from_xml(element)
    if isinstance(expected_comparison_result, Exception):
        with pytest.raises(type(expected_comparison_result)):
            comparison.evaluate(test_parsed_data, current_parsed_value)
    else:
        assert comparison.evaluate(test_parsed_data, current_parsed_value) == expected_comparison_result
        # Recover XML and re-parse it to check it's reproducible
        result_string = ElementTree.tostring(comparison.to_xml(elmaker=elmaker), pretty_print=True).decode()
        full_circle = comparisons.Comparison.from_xml(ElementTree.fromstring(result_string, parser=xtce_parser))
        assert full_circle.evaluate(test_parsed_data, current_parsed_value) == expected_comparison_result


@pytest.mark.parametrize(
    ("args", "kwargs", "expected_error", "expected_error_msg"),
    [(("3", "REFERENCE_TO_OWN_RAW_VAL", "~="), {}, ValueError, "Unrecognized operator syntax ~=")]
)
def test_comparison_validity_check(args, kwargs, expected_error, expected_error_msg):
    """Test validation checks when creating a Comparison"""
    with pytest.raises(expected_error, match=expected_error_msg):
        comparisons.Comparison(*args, **kwargs)


@pytest.mark.parametrize(
    ('xml_string', 'test_parsed_data', 'expected_condition_result'),
    [
        (f"""
<xtce:Condition xmlns:xtce="{XTCE_1_2_XMLNS}">
    <xtce:ParameterInstanceRef parameterRef="P1"/>
    <xtce:ComparisonOperator>&gt;=</xtce:ComparisonOperator>
    <xtce:ParameterInstanceRef parameterRef="P2"/>
</xtce:Condition>
""",
         Packet(**{'P1': common.IntParameter(700, 4),
          'P2': common.IntParameter(678, 3)}), True),
        (f"""
<xtce:Condition xmlns:xtce="{XTCE_1_2_XMLNS}">
    <xtce:ParameterInstanceRef parameterRef="P1"/>
    <xtce:ComparisonOperator>&gt;=</xtce:ComparisonOperator>
    <xtce:Value>4</xtce:Value>
</xtce:Condition>
""",
         Packet(**{'P1': common.IntParameter(700, 4)}), True),
        (f"""
<xtce:Condition xmlns:xtce="{XTCE_1_2_XMLNS}">
    <xtce:ParameterInstanceRef parameterRef="P1"/>
    <xtce:ComparisonOperator>==</xtce:ComparisonOperator>
    <xtce:ParameterInstanceRef parameterRef="P2"/>
</xtce:Condition>
""",
         Packet(**{'P1': common.IntParameter(700, 4),
          'P2': common.IntParameter(678, 3)}), False),
        (f"""
<xtce:Condition xmlns:xtce="{XTCE_1_2_XMLNS}">
    <xtce:ParameterInstanceRef parameterRef="P1" useCalibratedValue="false"/>
    <xtce:ComparisonOperator>==</xtce:ComparisonOperator>
    <xtce:ParameterInstanceRef parameterRef="P2" useCalibratedValue="false"/>
</xtce:Condition>
""",
         Packet(**{'P1': common.StrParameter('abcd'),
          'P2': common.StrParameter('abcd')}), True),
        (f"""
<xtce:Condition xmlns:xtce="{XTCE_1_2_XMLNS}">
    <xtce:ParameterInstanceRef parameterRef="P1"/>
    <xtce:ComparisonOperator>==</xtce:ComparisonOperator>
    <xtce:ParameterInstanceRef parameterRef="P2"/>
</xtce:Condition>
""",
         Packet(**{'P1': common.FloatParameter(3.14, 1),
          'P2': common.FloatParameter(3.14, 180)}), True),
    ]
)
def test_condition(elmaker, xtce_parser, xml_string, test_parsed_data, expected_condition_result):
    """Test Condition object"""
    element = ElementTree.fromstring(xml_string, parser=xtce_parser)
    condition = comparisons.Condition.from_xml(element)
    assert condition.evaluate(test_parsed_data, None) == expected_condition_result
    # Recover XML and re-parse it to check it's reproducible
    result_string = ElementTree.tostring(condition.to_xml(elmaker=elmaker), pretty_print=True).decode()
    full_circle = comparisons.Condition.from_xml(ElementTree.fromstring(result_string, parser=xtce_parser))
    assert full_circle.evaluate(test_parsed_data) == expected_condition_result


@pytest.mark.parametrize(
    ("args", "kwargs", "expected_error", "expected_error_msg"),
    [
        (("X", "~="), {"right_value": "4"},
         ValueError, "Unrecognized operator syntax ~="),
        (("X", "=="), {"right_param": "R", "right_value": "1"},
         comparisons.ComparisonError, "Received both a right_value and a right_param reference to Condition"),
        (("X", "=="), {"right_value": "4", "right_use_calibrated_value": True},
         comparisons.ComparisonError, "Unable to use calibrated form of a fixed value in Condition")
    ]
)
def test_condition_validity_check(args, kwargs, expected_error, expected_error_msg):
    """Test validation checks when creating a Condition"""
    with pytest.raises(expected_error, match=expected_error_msg):
        comparisons.Condition(*args, **kwargs)


@pytest.mark.parametrize(
    ('xml_string', 'test_parsed_data', 'expected_result'),
    [
        (f"""
<xtce:BooleanExpression xmlns:xtce="{XTCE_1_2_XMLNS}">
    <xtce:ORedConditions>
        <xtce:Condition>
            <xtce:ParameterInstanceRef parameterRef="P"/>
            <xtce:ComparisonOperator>==</xtce:ComparisonOperator>
            <xtce:Value>100</xtce:Value>
        </xtce:Condition>
        <xtce:ANDedConditions>
            <xtce:Condition>
                <xtce:ParameterInstanceRef parameterRef="P2"/>
                <xtce:ComparisonOperator>&lt;=</xtce:ComparisonOperator>
                <xtce:ParameterInstanceRef parameterRef="P3"/>
            </xtce:Condition>
            <xtce:Condition>
                <xtce:ParameterInstanceRef parameterRef="P4"/>
                <xtce:ComparisonOperator>!=</xtce:ComparisonOperator>
                <xtce:Value>99</xtce:Value>
            </xtce:Condition>
        </xtce:ANDedConditions>
    </xtce:ORedConditions>
</xtce:BooleanExpression>
""",
         Packet(**{'P': common.IntParameter(0, 4),
                        'P2': common.IntParameter(700, 4),
                        'P3': common.IntParameter(701, 4),
                        'P4': common.IntParameter(98, 4)}), True),
        (f"""
<xtce:BooleanExpression xmlns:xtce="{XTCE_1_2_XMLNS}">
    <xtce:ANDedConditions>
        <xtce:Condition>
            <xtce:ParameterInstanceRef parameterRef="P"/>
            <xtce:ComparisonOperator>==</xtce:ComparisonOperator>
            <xtce:Value>100</xtce:Value>
        </xtce:Condition>
        <xtce:Condition>
            <xtce:ParameterInstanceRef parameterRef="P0"/>
            <xtce:ComparisonOperator>&gt;=</xtce:ComparisonOperator>
            <xtce:ParameterInstanceRef parameterRef="P1"/>
        </xtce:Condition>
        <xtce:ORedConditions>
            <xtce:Condition>
                <xtce:ParameterInstanceRef parameterRef="P2"/>
                <xtce:ComparisonOperator>&lt;=</xtce:ComparisonOperator>
                <xtce:ParameterInstanceRef parameterRef="P3"/>
            </xtce:Condition>
            <xtce:Condition>
                <xtce:ParameterInstanceRef parameterRef="P4"/>
                <xtce:ComparisonOperator>!=</xtce:ComparisonOperator>
                <xtce:Value>99</xtce:Value>
            </xtce:Condition>
        </xtce:ORedConditions>
    </xtce:ANDedConditions>
</xtce:BooleanExpression>
""",
         Packet(**{'P': common.IntParameter(100, 4),
                        'P0': common.IntParameter(678, 4),
                        'P1': common.IntParameter(500, 4),
                        'P2': common.IntParameter(700, 4),
                        'P3': common.IntParameter(701, 4),
                        'P4': common.IntParameter(99, 4)}), True),
    ]
)
def test_boolean_expression(elmaker, xtce_parser, xml_string, test_parsed_data, expected_result):
    """Test BooleanExpression object"""
    element = ElementTree.fromstring(xml_string, parser=xtce_parser)
    if isinstance(expected_result, Exception):
        with pytest.raises(type(expected_result)):
            comparisons.BooleanExpression.from_xml(element)
    else:
        expression = comparisons.BooleanExpression.from_xml(element)
        assert expression.evaluate(test_parsed_data, current_parsed_value=None) == expected_result
        # Recover XML and re-parse it to check it's reproducible
        result_string = ElementTree.tostring(expression.to_xml(elmaker=elmaker), pretty_print=True).decode()
        full_circle = comparisons.BooleanExpression.from_xml(ElementTree.fromstring(result_string, parser=xtce_parser))
        assert full_circle.evaluate(test_parsed_data) == expected_result


@pytest.mark.parametrize(
    ('xml_string', 'test_parsed_data', 'expected_lookup_result'),
    [
        (f"""
<xtce:DiscreteLookup value="10" xmlns:xtce="{XTCE_1_2_XMLNS}">
    <xtce:Comparison useCalibratedValue="false" parameterRef="P1" value="1"/>
</xtce:DiscreteLookup>
""",
         Packet(**{'P1': common.IntParameter(678, 1)}), 10),
        (f"""
<xtce:DiscreteLookup value="10" xmlns:xtce="{XTCE_1_2_XMLNS}">
    <xtce:Comparison useCalibratedValue="false" parameterRef="P1" value="1"/>
</xtce:DiscreteLookup>
""",
         Packet(**{'P1': common.IntParameter(678, 0)}), None),
        (f"""
<xtce:DiscreteLookup value="11" xmlns:xtce="{XTCE_1_2_XMLNS}">
    <xtce:ComparisonList>
        <xtce:Comparison comparisonOperator="&gt;=" value="678" parameterRef="MSN__PARAM1"/>
        <xtce:Comparison comparisonOperator="&lt;" value="4096" parameterRef="MSN__PARAM2"/>
    </xtce:ComparisonList>
</xtce:DiscreteLookup>
""",
         Packet(**{
             'MSN__PARAM1': common.IntParameter(680, 3),
             'MSN__PARAM2': common.IntParameter(3000, 3),
         }), 11),
    ]
)
def test_discrete_lookup(elmaker, xtce_parser, xml_string, test_parsed_data, expected_lookup_result):
    """Test DiscreteLookup object"""
    element = ElementTree.fromstring(xml_string, parser=xtce_parser)
    discrete_lookup = comparisons.DiscreteLookup.from_xml(element)
    assert discrete_lookup.evaluate(test_parsed_data, current_parsed_value=None) == expected_lookup_result
    # Recover XML and re-parse it to check it's reproducible
    result_string = ElementTree.tostring(discrete_lookup.to_xml(elmaker=elmaker), pretty_print=True).decode()
    full_circle = comparisons.DiscreteLookup.from_xml(ElementTree.fromstring(result_string, parser=xtce_parser))
    assert full_circle.evaluate(test_parsed_data) == expected_lookup_result
