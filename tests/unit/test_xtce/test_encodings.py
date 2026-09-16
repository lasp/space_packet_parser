"""DataEncoding Tests"""

import lxml.etree as ElementTree
import pytest

import space_packet_parser as spp
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
                max_size_in_bits=32,
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
                dynamic_length_reference="SizeFromThisParameter",
                length_linear_adjuster=object(),
                leading_length_size=3,
                max_size_in_bits=32,
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
                max_size_in_bits=32,
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
                max_size_in_bits=32,
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
            "Expected one of dynamic length reference, discrete length lookup, or fixed length",
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


def test_variable_string_without_max_size_warns_on_serialization(elmaker):
    """maxSizeInBits is required on Variable by both XTCE schemas, so its absence is surfaced

    An encoding read from a document always has it (the schema requires it), but one built in
    Python may not, in which case there is no way to infer an upper bound. Warn rather than guess.
    """
    encoding = encodings.StringDataEncoding(dynamic_length_reference="LEN")
    with pytest.warns(UserWarning, match="no max_size_in_bits"):
        element = encoding.to_xml(elmaker=elmaker)
    assert "maxSizeInBits" not in element.find(f"{{{XTCE_1_2_XMLNS}}}Variable").attrib

    encoding = encodings.StringDataEncoding(dynamic_length_reference="LEN", max_size_in_bits=128)
    element = encoding.to_xml(elmaker=elmaker)
    assert element.find(f"{{{XTCE_1_2_XMLNS}}}Variable").attrib["maxSizeInBits"] == "128"


@pytest.mark.parametrize(
    ("kwargs", "raw_data", "expected"),
    [
        # XTCE 1.3 Pascal string: buffer is the 8-bit size tag plus the 24 bits it reports.
        ({"leading_length_size": 8, "max_size_in_bits": 256}, bytes([24]) + b"ABCtrailing", "ABC"),
        # XTCE 1.3 C string: buffer runs up to and including the terminator.
        ({"termination_character": "00", "max_size_in_bits": 256}, b"ABC\x00trailing", "ABC"),
    ],
)
def test_string_encoding_derives_buffer_length_from_delimiter(kwargs, raw_data, expected):
    """With no declared buffer length (XTCE 1.3), the delimiter determines how much to read"""
    encoding = encodings.StringDataEncoding(**kwargs)
    packet = spp.SpacePacket(binary_data=raw_data)
    assert encoding.parse_value(packet) == expected
    # Only the delimited buffer is consumed; the trailing bytes are left for the next field.
    assert packet._parsing_pos == (len(expected) + 1) * 8


def test_string_encoding_termination_scan_respects_max_size_in_bits():
    """The scan for a termination character is bounded by maxSizeInBits, per the XTCE schema"""
    encoding = encodings.StringDataEncoding(termination_character="00", max_size_in_bits=16)
    packet = spp.SpacePacket(binary_data=b"ABCDEF\x00")
    with pytest.raises(ValueError, match="without finding the termination character"):
        encoding.parse_value(packet)


def test_termination_scan_does_not_match_across_character_boundaries():
    """A multi-byte terminator must be found on a character boundary, not anywhere in the bytes

    b"\\x41\\x00\\x00\\x42" in UTF-16BE is the two characters U+4100 U+0042 and contains no
    terminator, even though the byte sequence b"\\x00\\x00" appears inside it.
    """
    encoding = encodings.StringDataEncoding(encoding="UTF-16BE", termination_character="0000", max_size_in_bits=256)
    packet = spp.SpacePacket(binary_data=b"\x41\x00\x00\x42" + "!".encode("utf-16-be") + b"\x00\x00")
    assert encoding.parse_value(packet) == "䄀B!"


@pytest.mark.parametrize(
    ("encoding_name", "termination_character", "raw_data", "expected"),
    [
        # UTF-8 is variable-width, so a multi-byte terminator (U+00A5) sits at a byte offset that is
        # not a multiple of its own length. Scanning by a fixed stride would step straight over it.
        ("UTF-8", "c2a5", b"A\xc2\xa5XX", "A"),
        ("UTF-8", "00", b"AB\x00XX", "AB"),
        # Fixed-width encodings are scanned a character at a time.
        ("UTF-16BE", "0000", "AB".encode("utf-16-be") + b"\x00\x00", "AB"),
        ("UTF-16LE", "0000", "AB".encode("utf-16-le") + b"\x00\x00", "AB"),
        ("UTF-32BE", "00000000", "AB".encode("utf-32-be") + b"\x00" * 4, "AB"),
    ],
)
def test_termination_character_search_handles_variable_width_encodings(
    encoding_name, termination_character, raw_data, expected
):
    """Finding the terminator must work for variable-width encodings as well as fixed-width ones"""
    encoding = encodings.StringDataEncoding(
        encoding=encoding_name,
        termination_character=termination_character,
        fixed_raw_length=len(raw_data) * 8,
    )
    assert encoding.parse_value(spp.SpacePacket(binary_data=raw_data)) == expected


@pytest.mark.parametrize(
    ("attributes", "expected"),
    [
        # XTCE 1.3 defaults slope to 1 and intercept to 0, so an omitted attribute leaves the value
        # untouched rather than collapsing the adjustment to a constant.
        ({"intercept": "8"}, 24.0),
        ({"slope": "8"}, 128.0),
        ({}, 16.0),
        ({"slope": "8", "intercept": "25"}, 153.0),
    ],
)
def test_linear_adjustment_attribute_defaults(xtce_parser, attributes, expected):
    """An omitted LinearAdjustment slope means 1, not 0"""
    rendered = " ".join(f'{name}="{value}"' for name, value in attributes.items())
    element = ElementTree.fromstring(
        f'<xtce:DynamicValue xmlns:xtce="{XTCE_1_2_XMLNS}">'
        f'<xtce:ParameterInstanceRef parameterRef="P1"/>'
        f"<xtce:LinearAdjustment {rendered}/>"
        f"</xtce:DynamicValue>",
        parser=xtce_parser,
    )
    adjuster = encodings.DataEncoding._get_linear_adjuster(element)
    assert adjuster(16) == expected


@pytest.mark.parametrize(
    ("encoding_name", "char_width"),
    [
        ("UTF-16", 2),
        ("UTF-16LE", 2),
        ("UTF-16BE", 2),
        ("UTF-32", 4),
        ("UTF-32LE", 4),
        ("UTF-32BE", 4),
    ],
)
def test_fixed_width_encodings_do_not_match_a_straddling_terminator(encoding_name, char_width):
    """Every fixed-width encoding is scanned a character at a time, not byte by byte

    Covers the bare `UTF-16`/`UTF-32` spellings as well as the explicitly endian ones, so that a
    missing entry in the character-width table is caught rather than silently falling back to a
    byte-by-byte scan. The expected widths are written out here rather than read from the table
    under test.
    """
    encoding = encodings.StringDataEncoding(
        encoding=encoding_name,
        byte_order="mostSignificantByteFirst",
        termination_character="00" * char_width,
        max_size_in_bits=256,
    )
    # Two non-null characters whose bytes nonetheless contain a run of nulls as long as the
    # terminator, straddling the boundary between them. There is no terminator in this buffer.
    straddling = (b"\x41" + b"\x00" * (char_width - 1)) + (b"\x00" * (char_width - 1) + b"\x42")
    assert encoding._find_termination_character(straddling) == -1
    # The same buffer with a real, character-aligned terminator appended.
    assert encoding._find_termination_character(straddling + b"\x00" * char_width) == len(straddling)


def test_empty_termination_char_element_uses_the_schema_default(xtce_parser):
    """An empty <TerminationChar/> means the XSD default, which is a null byte in both versions

    The element is declared `default="00"` in both the XTCE 1.2 and 1.3 schemas, so an empty element
    is schema-valid and means a null terminator. lxml reports an empty element's text as None, and
    nothing here applies XSD defaults, so reading it as "absent" would reject a valid C string.
    """
    element = ElementTree.fromstring(
        f"""
<xtce:StringDataEncoding xmlns:xtce="{XTCE_1_2_XMLNS}" encoding="UTF-8">
    <xtce:Variable maxSizeInBits="256">
        <xtce:DynamicValue>
            <xtce:ParameterInstanceRef parameterRef="LEN"/>
        </xtce:DynamicValue>
        <xtce:TerminationChar/>
    </xtce:Variable>
</xtce:StringDataEncoding>
""",
        parser=xtce_parser,
    )
    encoding = encodings.StringDataEncoding.from_xml(element)
    assert encoding.termination_character == b"\x00"


def test_string_encoding_requires_some_length_specifier():
    """An encoding with neither a declared buffer length nor a delimiter is rejected"""
    with pytest.raises(ValueError, match="Expected one of dynamic length reference"):
        encodings.StringDataEncoding()


def test_termination_delimited_string_must_start_on_a_byte_boundary():
    """Scanning for a terminator needs byte alignment, and says so rather than misreading

    Only reachable on the XTCE 1.3 derived path, where the terminator is what determines how much of
    the packet to consume; with a declared buffer length the scan happens inside an already-read
    buffer and alignment is not in question.
    """
    encoding = encodings.StringDataEncoding(termination_character="00", max_size_in_bits=256)
    packet = spp.SpacePacket(binary_data=b"\xff" + b"AB\x00")
    packet._read_from_binary_as_int(3)  # leave the cursor mid-byte

    with pytest.raises(ValueError, match="must begin on a byte boundary"):
        encoding.parse_value(packet)
