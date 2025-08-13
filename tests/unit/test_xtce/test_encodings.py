"""DataEncoding Tests"""

import lxml.etree as ElementTree
import pytest

from space_packet_parser.xtce import XTCE_1_2_XMLNS, calibrators, comparisons, encodings


@pytest.mark.parametrize(
    ("xml_string", "expectation"),
    [
        (
            f"""
<xtce:StringDataEncoding encoding="UTF-16BE" xmlns:xtce="{XTCE_1_2_XMLNS}">
    <xtce:SizeInBits>
        <xtce:Fixed>
            <xtce:FixedValue>32</xtce:FixedValue>
        </xtce:Fixed>
        <xtce:TerminationChar>0058</xtce:TerminationChar>
    </xtce:SizeInBits>
</xtce:StringDataEncoding>
""",
            encodings.StringDataEncoding(fixed_raw_length=32, termination_character="0058", encoding="UTF-16BE"),
        ),
        (
            f"""
<xtce:StringDataEncoding xmlns:xtce="{XTCE_1_2_XMLNS}">
    <xtce:SizeInBits>
        <xtce:Fixed>
            <xtce:FixedValue>17</xtce:FixedValue>
        </xtce:Fixed>
        <xtce:LeadingSize sizeInBitsOfSizeTag="3"/>
    </xtce:SizeInBits>
</xtce:StringDataEncoding>
""",
            encodings.StringDataEncoding(fixed_raw_length=17, leading_length_size=3),
        ),
        (
            f"""
<xtce:StringDataEncoding xmlns:xtce="{XTCE_1_2_XMLNS}">
    <xtce:Variable maxSizeInBits="32">
        <xtce:DynamicValue>
            <xtce:ParameterInstanceRef parameterRef="SizeFromThisParameter"/>
            <xtce:LinearAdjustment intercept="25" slope="8"/>
        </xtce:DynamicValue>
        <xtce:TerminationChar>58</xtce:TerminationChar>
    </xtce:Variable>
</xtce:StringDataEncoding>
""",
            encodings.StringDataEncoding(
                dynamic_length_reference="SizeFromThisParameter",
                length_linear_adjuster=object(),
                termination_character="58",
            ),
        ),
        (
            f"""
<xtce:StringDataEncoding xmlns:xtce="{XTCE_1_2_XMLNS}">
    <xtce:Variable maxSizeInBits="32">
        <xtce:DynamicValue>
            <xtce:ParameterInstanceRef parameterRef="SizeFromThisParameter"/>
            <xtce:LinearAdjustment intercept="25" slope="8"/>
        </xtce:DynamicValue>
        <xtce:LeadingSize sizeInBitsOfSizeTag="3"/>
    </xtce:Variable>
</xtce:StringDataEncoding>
""",
            encodings.StringDataEncoding(
                dynamic_length_reference="SizeFromThisParameter", length_linear_adjuster=object(), leading_length_size=3
            ),
        ),
        (
            f"""
<xtce:StringDataEncoding xmlns:xtce="{XTCE_1_2_XMLNS}">
    <xtce:Variable maxSizeInBits="32">
        <xtce:DiscreteLookupList>
            <xtce:DiscreteLookup value="10">
                <xtce:Comparison parameterRef="P1" value="1"/>
            </xtce:DiscreteLookup>
            <xtce:DiscreteLookup value="25">
                <xtce:Comparison parameterRef="P1" value="2"/>
            </xtce:DiscreteLookup>
        </xtce:DiscreteLookupList>
        <xtce:TerminationChar>58</xtce:TerminationChar>
    </xtce:Variable>
</xtce:StringDataEncoding>
""",
            encodings.StringDataEncoding(
                discrete_lookup_length=[
                    comparisons.DiscreteLookup([comparisons.Comparison("1", "P1")], 10),
                    comparisons.DiscreteLookup([comparisons.Comparison("2", "P1")], 25),
                ],
                termination_character="58",
            ),
        ),
        (
            f"""
<xtce:StringDataEncoding xmlns:xtce="{XTCE_1_2_XMLNS}">
    <xtce:Variable maxSizeInBits="32">
        <xtce:DiscreteLookupList>
            <xtce:DiscreteLookup value="10">
                <xtce:Comparison parameterRef="P1" value="1"/>
            </xtce:DiscreteLookup>
            <xtce:DiscreteLookup value="25">
                <xtce:Comparison parameterRef="P1" value="2"/>
            </xtce:DiscreteLookup>
        </xtce:DiscreteLookupList>
        <xtce:LeadingSize sizeInBitsOfSizeTag="3"/>
    </xtce:Variable>
</xtce:StringDataEncoding>
""",
            encodings.StringDataEncoding(
                discrete_lookup_length=[
                    comparisons.DiscreteLookup([comparisons.Comparison("1", "P1")], 10),
                    comparisons.DiscreteLookup([comparisons.Comparison("2", "P1")], 25),
                ],
                leading_length_size=3,
            ),
        ),
        (
            f"""
<xtce:StringDataEncoding xmlns:xtce="{XTCE_1_2_XMLNS}">
    <xtce:SizeInBits>
        <xtce:Fixed>
            <xtce:InvalidTag>9000</xtce:InvalidTag>
        </xtce:Fixed>
    </xtce:SizeInBits>
</xtce:StringDataEncoding>
""",
            AttributeError(),
        ),
    ],
)
def test_string_data_encoding(elmaker, xtce_parser, xml_string: str, expectation):
    """Test parsing a StringDataEncoding from an XML string"""
    element = ElementTree.fromstring(xml_string, parser=xtce_parser)

    if isinstance(expectation, Exception):
        with pytest.raises(type(expectation)):
            encodings.StringDataEncoding.from_xml(element)
    else:
        result = encodings.StringDataEncoding.from_xml(element)
        assert result == expectation
        # Recover XML and re-parse it to check it's recoverable
        result_string = ElementTree.tostring(result.to_xml(elmaker=elmaker), pretty_print=True).decode()
        full_circle = encodings.StringDataEncoding.from_xml(ElementTree.fromstring(result_string, parser=xtce_parser))
        assert full_circle == expectation


@pytest.mark.parametrize(
    ("args", "kwargs", "expected_error", "expected_error_msg"),
    [
        ((), {"encoding": "bad"}, ValueError, "Encoding must be one of"),
        ((), {"encoding": "UTF-16"}, ValueError, "Byte order must be specified for multi-byte character encodings."),
        ((), {"byte_order": "invalid"}, ValueError, "If specified, byte order must be one of"),
        (
            (),
            {"termination_character": "FF", "leading_length_size": 8},
            ValueError,
            "Got both a termination character and a leading size",
        ),
        (
            (),
            {},
            ValueError,
            "Expected exactly one of dynamic length reference, discrete length lookup, or fixed length",
        ),
        (
            (),
            {"length_linear_adjuster": lambda x: x, "fixed_raw_length": 32},
            ValueError,
            "Got a length linear adjuster for a string whose length is not specified by a dynamic",
        ),
        (
            (),
            {"fixed_raw_length": 32, "termination_character": "0F0F"},
            ValueError,
            "Expected a hex string representation of a single character",
        ),
    ],
)
def test_string_data_encoding_validation(args, kwargs, expected_error, expected_error_msg):
    """Test initialization errors for StringDataEncoding"""
    with pytest.raises(expected_error, match=expected_error_msg):
        encodings.StringDataEncoding(*args, **kwargs)


@pytest.mark.parametrize(
    ("xml_string", "expectation"),
    [
        (
            f"""
<xtce:IntegerDataEncoding xmlns:xtce="{XTCE_1_2_XMLNS}" sizeInBits="4" encoding="unsigned"/>
""",
            encodings.IntegerDataEncoding(size_in_bits=4, encoding="unsigned"),
        ),
        (
            f"""
<xtce:IntegerDataEncoding xmlns:xtce="{XTCE_1_2_XMLNS}" sizeInBits="4"/>
""",
            encodings.IntegerDataEncoding(size_in_bits=4, encoding="unsigned"),
        ),
        (
            f"""
<xtce:IntegerDataEncoding xmlns:xtce="{XTCE_1_2_XMLNS}" sizeInBits="16" encoding="unsigned">
    <xtce:DefaultCalibrator>
        <xtce:PolynomialCalibrator>
            <xtce:Term exponent="1" coefficient="1.215500e-02"/>
            <xtce:Term exponent="0" coefficient="2.540000e+00"/>
        </xtce:PolynomialCalibrator>
    </xtce:DefaultCalibrator>
</xtce:IntegerDataEncoding>
""",
            encodings.IntegerDataEncoding(
                size_in_bits=16,
                encoding="unsigned",
                default_calibrator=calibrators.PolynomialCalibrator(
                    [calibrators.PolynomialCoefficient(0.012155, 1), calibrators.PolynomialCoefficient(2.54, 0)]
                ),
            ),
        ),
        (
            f"""
<xtce:IntegerDataEncoding xmlns:xtce="{XTCE_1_2_XMLNS}" sizeInBits="12" encoding="unsigned">
    <xtce:ContextCalibratorList>
        <xtce:ContextCalibrator>
            <xtce:ContextMatch>
                <xtce:ComparisonList>
                    <xtce:Comparison comparisonOperator="&gt;=" value="0" parameterRef="MSN__PARAM"/>
                    <xtce:Comparison comparisonOperator="&lt;" value="678" parameterRef="MSN__PARAM"/>
                </xtce:ComparisonList>
            </xtce:ContextMatch>
            <xtce:Calibrator>
                <xtce:PolynomialCalibrator>
                    <xtce:Term exponent="0" coefficient="142.998"/>
                    <xtce:Term exponent="1" coefficient="-0.349712"/>
                </xtce:PolynomialCalibrator>
            </xtce:Calibrator>
        </xtce:ContextCalibrator>
        <xtce:ContextCalibrator>
            <xtce:ContextMatch>
                <xtce:ComparisonList>
                    <xtce:Comparison comparisonOperator="&gt;=" value="678" parameterRef="MSN__PARAM"/>
                    <xtce:Comparison comparisonOperator="&lt;=" value="4096" parameterRef="MSN__PARAM"/>
                </xtce:ComparisonList>
            </xtce:ContextMatch>
            <xtce:Calibrator>
                <xtce:PolynomialCalibrator>
                    <xtce:Term exponent="0" coefficient="100.488"/>
                    <xtce:Term exponent="1" coefficient="-0.110197"/>
                </xtce:PolynomialCalibrator>
            </xtce:Calibrator>
        </xtce:ContextCalibrator>
    </xtce:ContextCalibratorList>
</xtce:IntegerDataEncoding>
""",
            encodings.IntegerDataEncoding(
                size_in_bits=12,
                encoding="unsigned",
                default_calibrator=None,
                context_calibrators=[
                    calibrators.ContextCalibrator(
                        match_criteria=[
                            comparisons.Comparison(
                                required_value="0", operator=">=", referenced_parameter="MSN__PARAM"
                            ),
                            comparisons.Comparison(
                                required_value="678", operator="<", referenced_parameter="MSN__PARAM"
                            ),
                        ],
                        calibrator=calibrators.PolynomialCalibrator(
                            coefficients=[
                                calibrators.PolynomialCoefficient(142.998, 0),
                                calibrators.PolynomialCoefficient(-0.349712, 1),
                            ]
                        ),
                    ),
                    calibrators.ContextCalibrator(
                        match_criteria=[
                            comparisons.Comparison(
                                required_value="678", operator=">=", referenced_parameter="MSN__PARAM"
                            ),
                            comparisons.Comparison(
                                required_value="4096", operator="<=", referenced_parameter="MSN__PARAM"
                            ),
                        ],
                        calibrator=calibrators.PolynomialCalibrator(
                            coefficients=[
                                calibrators.PolynomialCoefficient(100.488, 0),
                                calibrators.PolynomialCoefficient(-0.110197, 1),
                            ]
                        ),
                    ),
                ],
            ),
        ),
    ],
)
def test_integer_data_encoding(elmaker, xtce_parser, xml_string: str, expectation):
    """Test parsing an IntegerDataEncoding from an XML string"""
    element = ElementTree.fromstring(xml_string, parser=xtce_parser)

    if isinstance(expectation, Exception):
        with pytest.raises(type(expectation)):
            encodings.IntegerDataEncoding.from_xml(element)
    else:
        result = encodings.IntegerDataEncoding.from_xml(element)
        assert result == expectation
        # Recover XML and re-parse it to check it's recoverable
        result_string = ElementTree.tostring(result.to_xml(elmaker=elmaker), pretty_print=True).decode()
        full_circle = encodings.IntegerDataEncoding.from_xml(ElementTree.fromstring(result_string, parser=xtce_parser))
        assert full_circle == expectation


@pytest.mark.parametrize(
    ("args", "kwargs", "expected_error", "expected_error_msg"),
    [
        ((32, "invalid-encoding"), {}, ValueError, "Encoding must be one of"),
        ((32, "unsigned"), {"byte_order": "noSignificantBitsAtAll!"}, ValueError, "Byte order must be one of"),
    ],
)
def test_integer_data_encoding_validation(args, kwargs, expected_error, expected_error_msg):
    """Test initialization errors for IntegerDataEncoding"""
    with pytest.raises(expected_error, match=expected_error_msg):
        encodings.IntegerDataEncoding(*args, **kwargs)


@pytest.mark.parametrize(
    ("xml_string", "expectation"),
    [
        (
            f"""
<xtce:FloatDataEncoding xmlns:xtce="{XTCE_1_2_XMLNS}" sizeInBits="4" encoding="IEEE754"/>
""",
            ValueError(),
        ),
        (
            f"""
<xtce:FloatDataEncoding xmlns:xtce="{XTCE_1_2_XMLNS}" sizeInBits="16">
    <xtce:DefaultCalibrator>
        <xtce:PolynomialCalibrator>
            <xtce:Term exponent="1" coefficient="1.215500e-02"/>
            <xtce:Term exponent="0" coefficient="2.540000e+00"/>
        </xtce:PolynomialCalibrator>
    </xtce:DefaultCalibrator>
</xtce:FloatDataEncoding>
""",
            encodings.FloatDataEncoding(
                size_in_bits=16,
                encoding="IEEE754",
                default_calibrator=calibrators.PolynomialCalibrator(
                    [calibrators.PolynomialCoefficient(0.012155, 1), calibrators.PolynomialCoefficient(2.54, 0)]
                ),
            ),
        ),
        (
            f"""
<xtce:FloatDataEncoding xmlns:xtce="{XTCE_1_2_XMLNS}" sizeInBits="16">
    <xtce:ContextCalibratorList>
        <xtce:ContextCalibrator>
            <xtce:ContextMatch>
                <xtce:ComparisonList>
                    <xtce:Comparison comparisonOperator="&gt;=" value="0" parameterRef="MSN__PARAM"/>
                    <xtce:Comparison comparisonOperator="&lt;" value="678" parameterRef="MSN__PARAM"/>
                </xtce:ComparisonList>
            </xtce:ContextMatch>
            <xtce:Calibrator>
                <xtce:PolynomialCalibrator>
                    <xtce:Term exponent="0" coefficient="142.998"/>
                    <xtce:Term exponent="1" coefficient="-0.349712"/>
                </xtce:PolynomialCalibrator>
            </xtce:Calibrator>
        </xtce:ContextCalibrator>
        <xtce:ContextCalibrator>
            <xtce:ContextMatch>
                <xtce:ComparisonList>
                    <xtce:Comparison comparisonOperator="&gt;=" value="678" parameterRef="MSN__PARAM"/>
                    <xtce:Comparison comparisonOperator="&lt;=" value="4096" parameterRef="MSN__PARAM"/>
                </xtce:ComparisonList>
            </xtce:ContextMatch>
            <xtce:Calibrator>
                <xtce:PolynomialCalibrator>
                    <xtce:Term exponent="0" coefficient="100.488"/>
                    <xtce:Term exponent="1" coefficient="-0.110197"/>
                </xtce:PolynomialCalibrator>
            </xtce:Calibrator>
        </xtce:ContextCalibrator>
    </xtce:ContextCalibratorList>
    <xtce:DefaultCalibrator>
        <xtce:PolynomialCalibrator>
            <xtce:Term exponent="1" coefficient="1.215500e-02"/>
            <xtce:Term exponent="0" coefficient="2.540000e+00"/>
        </xtce:PolynomialCalibrator>
    </xtce:DefaultCalibrator>
</xtce:FloatDataEncoding>
""",
            encodings.FloatDataEncoding(
                size_in_bits=16,
                encoding="IEEE754",
                default_calibrator=calibrators.PolynomialCalibrator(
                    [calibrators.PolynomialCoefficient(0.012155, 1), calibrators.PolynomialCoefficient(2.54, 0)]
                ),
                context_calibrators=[
                    calibrators.ContextCalibrator(
                        match_criteria=[
                            comparisons.Comparison(
                                required_value="0", operator=">=", referenced_parameter="MSN__PARAM"
                            ),
                            comparisons.Comparison(
                                required_value="678", operator="<", referenced_parameter="MSN__PARAM"
                            ),
                        ],
                        calibrator=calibrators.PolynomialCalibrator(
                            coefficients=[
                                calibrators.PolynomialCoefficient(142.998, 0),
                                calibrators.PolynomialCoefficient(-0.349712, 1),
                            ]
                        ),
                    ),
                    calibrators.ContextCalibrator(
                        match_criteria=[
                            comparisons.Comparison(
                                required_value="678", operator=">=", referenced_parameter="MSN__PARAM"
                            ),
                            comparisons.Comparison(
                                required_value="4096", operator="<=", referenced_parameter="MSN__PARAM"
                            ),
                        ],
                        calibrator=calibrators.PolynomialCalibrator(
                            coefficients=[
                                calibrators.PolynomialCoefficient(100.488, 0),
                                calibrators.PolynomialCoefficient(-0.110197, 1),
                            ]
                        ),
                    ),
                ],
            ),
        ),
    ],
)
def test_float_data_encoding(elmaker, xtce_parser, xml_string: str, expectation):
    """Test parsing an FloatDataEncoding from an XML string"""
    element = ElementTree.fromstring(xml_string, parser=xtce_parser)

    if isinstance(expectation, Exception):
        with pytest.raises(type(expectation)):
            encodings.FloatDataEncoding.from_xml(element)
    else:
        result = encodings.FloatDataEncoding.from_xml(element)
        assert result == expectation
        # Recover XML and re-parse it to check it's recoverable
        result_string = ElementTree.tostring(result.to_xml(elmaker=elmaker), pretty_print=True).decode()
        full_circle = encodings.FloatDataEncoding.from_xml(ElementTree.fromstring(result_string, parser=xtce_parser))
        assert full_circle == expectation


@pytest.mark.parametrize(
    ("args", "kwargs", "expected_error", "expected_error_msg"),
    [
        ((32,), {"encoding": "foo"}, ValueError, "Invalid encoding type"),
        ((32,), {"encoding": "DEC"}, NotImplementedError, "Although the XTCE spec allows"),
        ((16,), {"encoding": "MILSTD_1750A"}, ValueError, "MIL-1750A encoded floats must be 32 bits"),
        ((8,), {"encoding": "IEEE754"}, ValueError, "Invalid size_in_bits value for IEEE754 FloatDataEncoding"),
        ((8,), {"encoding": "IEEE754_1985"}, ValueError, "Invalid size_in_bits value for IEEE754 FloatDataEncoding"),
    ],
)
def test_float_data_encoding_validation(args, kwargs, expected_error, expected_error_msg):
    """Test initialization errors for FloatDataEncoding"""
    with pytest.raises(expected_error, match=expected_error_msg):
        encodings.FloatDataEncoding(*args, **kwargs)


@pytest.mark.parametrize(
    ("xml_string", "expectation"),
    [
        (
            f"""
<xtce:BinaryDataEncoding xmlns:xtce="{XTCE_1_2_XMLNS}">
    <xtce:SizeInBits>
        <xtce:FixedValue>256</xtce:FixedValue>
    </xtce:SizeInBits>
</xtce:BinaryDataEncoding>
""",
            encodings.BinaryDataEncoding(fixed_size_in_bits=256),
        ),
        (
            f"""
<xtce:BinaryDataEncoding xmlns:xtce="{XTCE_1_2_XMLNS}">
    <xtce:SizeInBits>
        <xtce:DynamicValue>
            <xtce:ParameterInstanceRef parameterRef="SizeFromThisParameter"/>
            <xtce:LinearAdjustment intercept="25" slope="8"/>
        </xtce:DynamicValue>
    </xtce:SizeInBits>
</xtce:BinaryDataEncoding>
""",
            encodings.BinaryDataEncoding(
                size_reference_parameter="SizeFromThisParameter", linear_adjuster=lambda x: 25 + 8 * x
            ),
        ),
        (
            f"""
<xtce:BinaryDataEncoding xmlns:xtce="{XTCE_1_2_XMLNS}">
    <xtce:SizeInBits>
        <xtce:DiscreteLookupList>
            <xtce:DiscreteLookup value="10">
                <xtce:Comparison parameterRef="P1" value="1"/>
            </xtce:DiscreteLookup>
            <xtce:DiscreteLookup value="25">
                <xtce:Comparison parameterRef="P1" value="2"/>
            </xtce:DiscreteLookup>
        </xtce:DiscreteLookupList>
    </xtce:SizeInBits>
</xtce:BinaryDataEncoding>
""",
            encodings.BinaryDataEncoding(
                size_discrete_lookup_list=[
                    comparisons.DiscreteLookup([comparisons.Comparison("1", "P1")], 10),
                    comparisons.DiscreteLookup([comparisons.Comparison("2", "P1")], 25),
                ]
            ),
        ),
    ],
)
def test_binary_data_encoding(elmaker, xtce_parser, xml_string: str, expectation):
    """Test parsing an BinaryDataEncoding from an XML string"""
    element = ElementTree.fromstring(xml_string, parser=xtce_parser)

    if isinstance(expectation, Exception):
        with pytest.raises(type(expectation)):
            encodings.BinaryDataEncoding.from_xml(element)
    else:
        result = encodings.BinaryDataEncoding.from_xml(element)
        assert result == expectation
        # Recover XML and re-parse it to check it's recoverable
        result_string = ElementTree.tostring(result.to_xml(elmaker=elmaker), pretty_print=True).decode()
        full_circle = encodings.BinaryDataEncoding.from_xml(ElementTree.fromstring(result_string, parser=xtce_parser))
        assert full_circle == expectation


@pytest.mark.parametrize(
    ("args", "kwargs", "expected_error", "expected_error_msg"),
    [
        ((), {}, ValueError, "Binary data encoding initialized with no way to determine a size"),
    ],
)
def test_binary_data_encoding_validation(args, kwargs, expected_error, expected_error_msg):
    """Test initialization errors for BinaryDataEncoding"""
    with pytest.raises(expected_error, match=expected_error_msg):
        encodings.BinaryDataEncoding(*args, **kwargs)
