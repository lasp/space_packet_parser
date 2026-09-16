"""Tests for constructs that exist only in XTCE 1.3.

Everything here needs the 1.3 schema or a 1.3-only element; nothing in this module is meaningful
under XTCE 1.2. Behavior shared by both versions lives in the general modules (`test_definitions`,
`test_encodings`, `test_validation`), and behavior that spans versions lives in
`test_version_conversion` and `test_version_validation`.
"""

import io

import lxml.etree as ElementTree
import pytest

import space_packet_parser as spp
from space_packet_parser.generators.ccsds import create_ccsds_packet
from space_packet_parser.xtce import XTCE_1_3_XMLNS, definitions, encodings
from space_packet_parser.xtce.validation import validate_xtce

XTCE_1_3_ONLY_FIXTURE = "test_xtce_1_3_only_features.xml"


def test_xtce_1_3_only_features_validate_against_the_1_3_schema(test_data_dir):
    """A document using XTCE 1.3-only constructs validates against the bundled 1.3 schema"""
    result = validate_xtce(
        test_data_dir / XTCE_1_3_ONLY_FIXTURE,
        level="all",
        print_results=False,
        allow_schema_download=False,
    )
    assert result.valid
    assert result.schema_version == "1.3"
    assert result.xtce_version == "1.3"


def test_xtce_1_3_only_features_are_rejected_by_the_1_2_schema(test_data_dir):
    """The 1.3-only fixture is genuinely 1.3, not a 1.2 document wearing a 1.3 namespace

    Rewritten into the *1.2* namespace and validated against the 1.2 schema, it must still fail —
    and fail on its content, not on a namespace mismatch. Otherwise a test could pass without the
    1.3 schema ever being consulted, simply because the URIs did not match.
    """
    as_xtce_1_2 = (test_data_dir / XTCE_1_3_ONLY_FIXTURE).read_bytes().replace(b"20250214", b"20180204")

    result = validate_xtce(
        io.BytesIO(as_xtce_1_2),
        level="schema",
        print_results=False,
        raise_on_error=False,
        allow_schema_download=False,
    )

    assert not result.valid
    # A namespace mismatch would mask the real errors, so assert it is *not* what happened.
    assert not any(error.error_code == "INVALID_XTCE_NAMESPACE" for error in result.errors)
    messages = " ".join(error.message for error in result.errors)
    # SpaceSystem/@systemType is new in 1.3.
    assert "systemType" in messages
    # So is a variable-length string with no declared buffer length.
    assert "LeadingSize" in messages
    assert "TerminationChar" in messages


def test_validation_with_1_3_local_xsd(test_data_dir, bundled_xsd_path):
    """A 1.3 document validates against an explicitly supplied 1.3 schema"""
    result = validate_xtce(
        test_data_dir / "test_xtce_1_3.xml",
        level="schema",
        print_results=False,
        local_xsd=bundled_xsd_path("1.3"),
    )
    assert result.valid
    assert result.schema_version == "1.3"


def test_variable_length_strings_parse_and_decode(test_data_dir):
    """XTCE 1.3 lets a variable-length string derive its buffer length from its own delimiter

    XTCE 1.2 requires a `DynamicValue` or `DiscreteLookupList` to declare the raw buffer length, and
    treats `LeadingSize`/`TerminationChar` as optional. XTCE 1.3 inverts that: the declared length is
    optional and one of the delimiters is required. A 1.3 document using the delimiter-only form must
    parse, and the buffer length must be derived from the delimiter itself.
    """
    xdef = definitions.XtcePacketDefinition.from_xtce(test_data_dir / XTCE_1_3_ONLY_FIXTURE)

    pascal = xdef.parameter_types["PASCAL_STR_Type"].encoding
    assert pascal.leading_length_size == 8
    assert pascal.max_size_in_bits == 256
    # No declared buffer length at all: that is the point of the 1.3 form.
    assert pascal.dynamic_length_reference is None
    assert pascal.discrete_lookup_length is None
    assert pascal.fixed_length is None

    c_string = xdef.parameter_types["C_STR_Type"].encoding
    assert c_string.termination_character == b"\x00"
    assert c_string.max_size_in_bits == 256

    # A CCSDS header, then "HELLO" as a Pascal string (5 bytes = 40 bits), then "BYE\0".
    packet_bytes = create_ccsds_packet(data=bytes([40]) + b"HELLO" + b"BYE\x00", apid=11)
    packet = xdef.parse_bytes(packet_bytes)
    assert packet["PASCAL_STR"] == "HELLO"
    assert packet["C_STR"] == "BYE"


def test_variable_length_string_round_trips(test_data_dir):
    """The 1.3 delimiter-only string form survives serialization, including maxSizeInBits"""
    xdef = definitions.XtcePacketDefinition.from_xtce(test_data_dir / XTCE_1_3_ONLY_FIXTURE)
    tree = xdef.to_xml_tree()

    variable_elements = tree.getroot().findall(f".//{{{XTCE_1_3_XMLNS}}}Variable")
    assert len(variable_elements) == 2
    for variable in variable_elements:
        # maxSizeInBits is required on Variable by the XTCE schema in both versions, so it must be
        # written back out or the document will not validate.
        assert variable.attrib["maxSizeInBits"] == "256"
        # The delimiter is the only child: no DynamicValue was invented on the way out.
        assert [ElementTree.QName(child).localname for child in variable] in (
            ["LeadingSize"],
            ["TerminationChar"],
        )


def test_leading_size_tag_is_bounded_by_max_size_in_bits():
    """A size tag reporting more than maxSizeInBits must be rejected, not read past the field

    The size tag comes from the packet, so it is untrusted. On the derived (1.3) path it is the only
    thing determining how much of the packet the string consumes, so an oversized tag would silently
    eat bytes belonging to later fields.
    """
    encoding = encodings.StringDataEncoding(leading_length_size=8, max_size_in_bits=64)

    # 56 bits of content + the 8-bit tag is exactly the 64-bit maximum: allowed.
    ok = spp.SpacePacket(binary_data=bytes([56]) + b"ABCDEFG")
    assert encoding.parse_value(ok) == "ABCDEFG"

    # 64 bits of content + the 8-bit tag is 72 bits, over the maximum.
    too_long = spp.SpacePacket(binary_data=bytes([64]) + b"ABCDEFGH")
    with pytest.raises(ValueError, match="exceeds the declared maxSizeInBits=64"):
        encoding.parse_value(too_long)


def test_space_system_type_attributes_round_trip(test_data_dir):
    """XTCE 1.3 SpaceSystem/@systemType and @assetType survive a read/write cycle

    These are 1.3-only root attributes carrying real metadata, so dropping them on round trip would
    silently downgrade the document to the schema default.
    """
    xdef = definitions.XtcePacketDefinition.from_xtce(test_data_dir / XTCE_1_3_ONLY_FIXTURE)
    assert xdef.space_system_type == "asset"

    root = xdef.to_xml_tree().getroot()
    assert root.attrib["systemType"] == "asset"


def test_space_system_type_attributes_are_optional(test_data_dir):
    """A document that omits the 1.3-only attributes neither gains nor requires them"""
    xdef = definitions.XtcePacketDefinition.from_xtce(test_data_dir / "test_xtce_1_3.xml")
    assert xdef.asset_type is None

    root = xdef.to_xml_tree().getroot()
    assert "assetType" not in root.attrib


def test_asset_type_is_written_when_set():
    """assetType is free-form and is written through unchanged"""
    xdef = definitions.XtcePacketDefinition(
        xtce_standard_version="1.3",
        space_system_name="Sat",
        space_system_type="assetGroup",
        asset_type="constellation",
    )
    root = xdef.to_xml_tree().getroot()
    assert root.attrib["systemType"] == "assetGroup"
    assert root.attrib["assetType"] == "constellation"
