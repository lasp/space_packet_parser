"""Tests for behavior that spans XTCE versions.

Detecting which version a definition is written against, retargeting one at another version, and the
version-dependent parts of serialization. Constructs that exist only in XTCE 1.3 live in
`test_xtce_1_3_features`; version-agnostic parsing and serialization live in `test_definitions`.
"""

import io

import lxml.etree as ElementTree
import pytest

from space_packet_parser import xtce
from space_packet_parser.generators.ccsds import create_ccsds_packet
from space_packet_parser.xtce import containers, definitions, encodings, parameter_types, parameters

XTCE_1_3_ONLY_FIXTURE = "test_xtce_1_3_only_features.xml"


# --------------------------------------------------------------------------------------
# Detecting a definition's version
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("xml_file", "expected_uri", "expected_version"),
    [
        ("test_xtce.xml", xtce.XTCE_1_2_XMLNS, "1.2"),
        ("test_xtce_1_3.xml", xtce.XTCE_1_3_XMLNS, "1.3"),
    ],
)
def test_definition_reports_xtce_standard_version(test_data_dir, xml_file, expected_uri, expected_version):
    """A parsed definition reports the XTCE version implied by its namespace URI"""
    xdef = definitions.XtcePacketDefinition.from_xtce(test_data_dir / xml_file)
    assert xdef.xtce_ns_uri == expected_uri
    assert xdef.xtce_standard_version == expected_version


def test_definition_xtce_standard_version_is_none_for_nonstandard_namespace(test_data_dir):
    """A document using a namespace URI that is not a standard XTCE one parses with no version

    The library has always accepted non-standard namespace URIs, so an unrecognized URI must not
    be an error; the version is simply unknown.
    """
    with pytest.warns(UserWarning, match="No XTCE namespace found in the document."):
        no_ns = definitions.XtcePacketDefinition.from_xtce(test_data_dir / "test_xtce_no_namespace.xml")
    assert no_ns.xtce_standard_version is None

    custom_ns = definitions.XtcePacketDefinition.from_xtce(
        io.BytesIO(
            b'<SpaceSystem xmlns="http://www.fake-test.org/space/xtce" name="custom">'
            b'<Header date="2024-03-05T13:36:00MST" version="1.0"/>'
            b"<TelemetryMetaData><ParameterTypeSet/><ParameterSet/><ContainerSet/></TelemetryMetaData>"
            b"</SpaceSystem>"
        )
    )
    assert custom_ns.xtce_ns_uri == "http://www.fake-test.org/space/xtce"
    assert custom_ns.xtce_standard_version is None


def test_legacy_https_1_2_namespace_is_recognized_and_normalized():
    """Documents written by space_packet_parser <= 6.2 carry a namespace URI no schema declares

    Those documents must still be recognized as XTCE 1.2, and writing them back out must repair the
    URI rather than propagating an unvalidatable document.
    """
    legacy_uri = "https://www.omg.org/spec/XTCE/20180204"
    xdef = definitions.XtcePacketDefinition.from_xtce(
        io.BytesIO(
            f'<xtce:SpaceSystem xmlns:xtce="{legacy_uri}" name="legacy">'
            '<xtce:Header date="2024-03-05T13:36:00MST" version="1.0"/>'
            "<xtce:TelemetryMetaData><xtce:ParameterTypeSet/><xtce:ParameterSet/><xtce:ContainerSet/>"
            "</xtce:TelemetryMetaData></xtce:SpaceSystem>".encode()
        )
    )
    assert xdef.xtce_ns_uri == legacy_uri
    assert xdef.xtce_standard_version == "1.2"

    with pytest.warns(UserWarning, match="is not the targetNamespace of any XTCE schema"):
        root = xdef.to_xml_tree().getroot()

    assert ElementTree.QName(root).namespace == xtce.XTCE_1_2_XMLNS
    assert root.attrib[f"{{{xtce.XSI_XMLNS}}}schemaLocation"] == f"{xtce.XTCE_1_2_XMLNS} {xtce.XTCE_1_2_XSD_URL}"


# --------------------------------------------------------------------------------------
# The same definition expressed in either version
# --------------------------------------------------------------------------------------


def test_xtce_1_3_fixture_tracks_the_1_2_fixture(test_data_dir):
    """test_xtce_1_3.xml must stay a pure version-swap of test_xtce.xml

    The two fixtures are maintained as the same definition in two XTCE versions, and several tests
    compare them directly. Nothing else enforces that, so an edit to one would silently make those
    comparisons meaningless. Normalizing the version-specific differences must recover the 1.2 file
    exactly.
    """
    twelve = (test_data_dir / "test_xtce.xml").read_text()
    thirteen = (test_data_dir / "test_xtce_1_3.xml").read_text()

    normalized = (
        thirteen.replace(xtce.XTCE_1_3_XMLNS, xtce.XTCE_1_2_XMLNS)
        .replace(xtce.XTCE_1_3_XSD_URL, xtce.XTCE_1_2_XSD_URL)
        # systemType is a 1.3-only attribute and is the one deliberate addition.
        .replace(' systemType="asset"', "")
    )
    assert normalized == twelve


def test_xtce_1_2_and_1_3_definitions_parse_identically(test_data_dir):
    """The same definition in XTCE 1.2 and 1.3 produces the same parsed objects

    The telemetry elements this library reads are unchanged between the two versions, so apart
    from the namespace the two documents must yield identical parameter types, parameters, and
    containers.
    """
    xdef_12 = definitions.XtcePacketDefinition.from_xtce(test_data_dir / "test_xtce.xml")
    xdef_13 = definitions.XtcePacketDefinition.from_xtce(test_data_dir / "test_xtce_1_3.xml")

    assert xdef_13.parameter_types == xdef_12.parameter_types
    assert xdef_13.parameters == xdef_12.parameters
    assert xdef_13.containers == xdef_12.containers


def test_xtce_1_2_and_1_3_definitions_parse_packets_identically(test_data_dir):
    """Packets parse to the same values whether the definition is XTCE 1.2 or 1.3

    Uses a synthetic packet rather than real mission data, which the project instructions reserve for
    the integration suite. The same assertion runs over real JPSS and CTIM bytes in
    tests/integration/test_xtce_based_parsing/test_xtce_version_parity.py.
    """
    xdef_12 = definitions.XtcePacketDefinition.from_xtce(test_data_dir / "test_xtce.xml")
    xdef_13 = definitions.XtcePacketDefinition.from_xtce(test_data_dir / "test_xtce_1_3.xml")

    # 65 bytes of user data is exactly the JPSS_ATT_EPHEM payload this definition describes. Varying
    # bytes rather than zeros so that a field read from the wrong offset would change the result.
    packet_bytes = create_ccsds_packet(data=bytes(range(65)), apid=11)

    assert dict(xdef_12.parse_bytes(packet_bytes)) == dict(xdef_13.parse_bytes(packet_bytes))


def test_definition_round_trip_preserves_header_and_version(test_data_dir):
    """Reading a 1.3 document and writing it back out preserves its version and header data"""
    xdef = definitions.XtcePacketDefinition.from_xtce(test_data_dir / "test_xtce_1_3.xml")
    # Header/@version and @validationStatus describe the document, and must survive a round trip.
    assert xdef.xtce_version == "1.0"
    assert xdef.validation_status == "Working"
    assert xdef.date == "2024-03-05T13:36:00MST"

    tree = xdef.to_xml_tree()
    root = tree.getroot()
    assert ElementTree.QName(root).namespace == xtce.XTCE_1_3_XMLNS

    header = root.find(f"{{{xtce.XTCE_1_3_XMLNS}}}Header")
    assert header.attrib["version"] == "1.0"
    assert header.attrib["validationStatus"] == "Working"
    assert header.attrib["date"] == "2024-03-05T13:36:00MST"


# --------------------------------------------------------------------------------------
# Selecting a version
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("version", xtce.SUPPORTED_XTCE_VERSIONS)
def test_construct_definition_for_version(version):
    """xtce_standard_version selects the namespace URI used when serializing"""
    xdef = definitions.XtcePacketDefinition(xtce_standard_version=version)
    assert xdef.xtce_standard_version == version
    assert xdef.xtce_ns_uri == xtce.xtce_uri_for_version(version)
    assert ElementTree.QName(xdef.to_xml_tree().getroot()).namespace == xtce.xtce_uri_for_version(version)


def test_construct_definition_defaults_to_default_version():
    """Constructing without a version keeps the historical default (1.2) namespace"""
    xdef = definitions.XtcePacketDefinition()
    assert xdef.xtce_standard_version == xtce.DEFAULT_XTCE_VERSION
    assert xdef.ns == xtce.STANDARD_XTCE_NSMAP


def test_construct_definition_rejects_ns_and_version_together():
    """Specifying both a namespace mapping and a version is ambiguous and is rejected"""
    with pytest.raises(ValueError, match="Pass either ns or xtce_standard_version"):
        definitions.XtcePacketDefinition(ns=xtce.STANDARD_XTCE_NSMAP, xtce_standard_version="1.3")


@pytest.mark.parametrize("version", ["1.0", "1.1", "9.9"])
def test_cannot_select_a_version_with_no_bundled_schema(version, test_data_dir):
    """Only versions whose schema ships with the package may be selected as a write target

    Version *detection* stays permissive — a document in the XTCE 1.1 namespace is still reported as
    1.1 — but writing a document that points at a schema we do not bundle would force a network
    fetch to validate, defeating the offline guarantee.
    """
    with pytest.raises(ValueError, match="Cannot write XTCE version"):
        definitions.XtcePacketDefinition(xtce_standard_version=version)

    xdef = definitions.XtcePacketDefinition.from_xtce(test_data_dir / "test_xtce.xml")
    with pytest.raises(ValueError, match="Cannot write XTCE version"):
        xdef.xtce_standard_version = version


def test_xtce_1_1_namespace_is_still_detected():
    """Refusing to *write* 1.1 must not stop us *reporting* a 1.1 document as 1.1"""
    assert xtce.xtce_version_from_uri(xtce.XTCE_1_1_XMLNS) == "1.1"


def test_convert_definition_between_xtce_versions(test_data_dir):
    """Setting xtce_standard_version retargets a definition at another version of the standard"""
    xdef = definitions.XtcePacketDefinition.from_xtce(test_data_dir / "test_xtce.xml")
    assert xdef.xtce_standard_version == "1.2"

    xdef.xtce_standard_version = "1.3"

    assert xdef.xtce_standard_version == "1.3"
    assert xdef.ns[xdef.xtce_ns_prefix] == xtce.XTCE_1_3_XMLNS
    root = xdef.to_xml_tree().getroot()
    assert ElementTree.QName(root).namespace == xtce.XTCE_1_3_XMLNS
    assert root.attrib[f"{{{xtce.XSI_XMLNS}}}schemaLocation"].endswith(xtce.XTCE_1_3_XSD_URL)
    # Every element, not just the root, moves to the new namespace.
    assert {ElementTree.QName(el).namespace for el in root.iter()} == {xtce.XTCE_1_3_XMLNS}


def test_convert_definition_with_inconsistent_namespace_mapping_raises():
    """Retargeting a definition whose namespace mapping does not bind its XTCE URI is an error"""
    xdef = definitions.XtcePacketDefinition()
    xdef.xtce_ns_uri = "http://www.fake-test.org/space/xtce"  # not bound by xdef.ns
    with pytest.raises(ValueError, match="is not bound by its namespace mapping"):
        xdef.xtce_standard_version = "1.3"


def test_convert_definition_with_no_namespace_raises(test_data_dir):
    """A definition with no XTCE namespace at all has nothing to retarget"""
    with pytest.warns(UserWarning, match="No XTCE namespace found in the document."):
        xdef = definitions.XtcePacketDefinition.from_xtce(test_data_dir / "test_xtce_no_namespace.xml")
    assert xdef.xtce_ns_uri is None

    with pytest.raises(ValueError, match="no XTCE namespace"):
        xdef.xtce_standard_version = "1.3"


# --------------------------------------------------------------------------------------
# Version-dependent serialization
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("xml_file", "expected_uri", "expected_xsd_url"),
    [
        ("test_xtce.xml", xtce.XTCE_1_2_XMLNS, xtce.XTCE_1_2_XSD_URL),
        ("test_xtce_1_3.xml", xtce.XTCE_1_3_XMLNS, xtce.XTCE_1_3_XSD_URL),
    ],
)
def test_serialization_writes_matching_schema_location(test_data_dir, xml_file, expected_uri, expected_xsd_url):
    """Serialized output names the XSD for its own XTCE version, so it is self-validating"""
    xdef = definitions.XtcePacketDefinition.from_xtce(test_data_dir / xml_file)
    root = xdef.to_xml_tree().getroot()

    schema_location = root.attrib[f"{{{xtce.XSI_XMLNS}}}schemaLocation"]
    assert schema_location == f"{expected_uri} {expected_xsd_url}"
    assert xtce.XSI_XMLNS in root.nsmap.values()


def test_serialization_omits_schema_location_for_nonstandard_namespace():
    """A definition in a non-standard namespace names no XSD, since we do not know one for it"""
    xdef = definitions.XtcePacketDefinition(
        ns={"custom": "http://www.fake-test.org/space/xtce"}, xtce_ns_prefix="custom"
    )
    root = xdef.to_xml_tree().getroot()
    assert f"{{{xtce.XSI_XMLNS}}}schemaLocation" not in root.attrib
    # The namespace mapping is left exactly as the caller specified it.
    assert root.nsmap == {"custom": "http://www.fake-test.org/space/xtce"}


def _definition_with_string_encoding(encoding: encodings.StringDataEncoding, version: str):
    """Build a minimal definition whose single string parameter uses the given encoding"""
    return definitions.XtcePacketDefinition(
        container_set=[
            containers.SequenceContainer(
                name="CCSDSPacket",
                entry_list=[
                    parameters.Parameter(
                        name="LEN",
                        parameter_type=parameter_types.IntegerParameterType(
                            name="LEN_Type", encoding=encodings.IntegerDataEncoding(size_in_bits=8, encoding="unsigned")
                        ),
                    ),
                    parameters.Parameter(
                        name="MSG",
                        parameter_type=parameter_types.StringParameterType(name="MSG_Type", encoding=encoding),
                    ),
                ],
            )
        ],
        xtce_standard_version=version,
    )


def test_serializing_1_2_only_string_as_xtce_1_3_warns():
    """Writing a 1.2-style variable-length string as XTCE 1.3 warns that it will not validate

    The 1.2 form (a declared buffer length and no delimiter) is invalid in 1.3, so converting a
    definition that uses it must not silently produce a broken document.
    """
    xdef = _definition_with_string_encoding(
        encodings.StringDataEncoding(dynamic_length_reference="LEN", max_size_in_bits=256), "1.3"
    )

    with pytest.warns(UserWarning, match="XTCE 1.3 requires a LeadingSize or TerminationChar"):
        xdef.to_xml_tree()

    # The same definition is fine as 1.2.
    xdef.xtce_standard_version = "1.2"
    xdef.to_xml_tree()


def test_serializing_1_3_only_string_as_xtce_1_2_warns():
    """Converting the 1.3 delimiter-only string form back to 1.2 warns for the same reason"""
    xdef = _definition_with_string_encoding(
        encodings.StringDataEncoding(leading_length_size=8, max_size_in_bits=256), "1.3"
    )
    xdef.to_xml_tree()  # fine as 1.3

    xdef.xtce_standard_version = "1.2"
    with pytest.warns(UserWarning, match="XTCE 1.2 requires a DynamicValue or DiscreteLookupList"):
        xdef.to_xml_tree()


def _definition_with_time_unit(unit: str, version: str):
    """Build a minimal definition whose single time parameter declares the given unit"""
    return definitions.XtcePacketDefinition(
        container_set=[
            containers.SequenceContainer(
                name="CCSDSPacket",
                entry_list=[
                    parameters.Parameter(
                        name="MET",
                        parameter_type=parameter_types.AbsoluteTimeParameterType(
                            name="MET_Type",
                            encoding=encodings.IntegerDataEncoding(size_in_bits=32, encoding="unsigned"),
                            unit=unit,
                        ),
                    )
                ],
            )
        ],
        xtce_standard_version=version,
    )


@pytest.mark.parametrize(
    ("unit", "version"),
    [
        # picoSeconds is the 1.2 spelling; 1.3 spells it picoseconds.
        ("picoSeconds", "1.3"),
        # milliseconds was added in 1.3 and does not exist in 1.2.
        ("milliseconds", "1.2"),
    ],
)
def test_serializing_a_time_unit_the_target_version_lacks_warns(unit, version):
    """A time unit is drawn from a version-specific enumeration, so conversion can invalidate it

    The unit is document content, so it is reported rather than rewritten.
    """
    xdef = _definition_with_time_unit(unit, version)
    with pytest.warns(UserWarning, match=f"XTCE {version} does not define"):
        root = xdef.to_xml_tree().getroot()

    # The unit is written through unchanged, exactly as the warning says.
    encoding = root.find(f".//{{{xtce.xtce_uri_for_version(version)}}}Encoding")
    assert encoding.attrib["units"] == unit


@pytest.mark.parametrize(
    ("unit", "version"),
    [("seconds", "1.2"), ("seconds", "1.3"), ("picoSeconds", "1.2"), ("picoseconds", "1.3")],
)
def test_serializing_a_valid_time_unit_is_quiet(unit, version):
    """A unit the target version defines produces no warning"""
    xdef = _definition_with_time_unit(unit, version)
    xdef.to_xml_tree()


def test_serializing_1_3_only_space_system_attributes_as_xtce_1_2_warns():
    """systemType/assetType do not exist in XTCE 1.2, so converting drops them — with a warning"""
    xdef = definitions.XtcePacketDefinition(
        xtce_standard_version="1.3", space_system_name="Sat", space_system_type="asset"
    )

    xdef.xtce_standard_version = "1.2"
    with pytest.warns(UserWarning, match=r"Dropping \['systemType'\]"):
        root = xdef.to_xml_tree().getroot()

    assert "systemType" not in root.attrib
    # The attribute is dropped from the document, not from the definition object.
    assert xdef.space_system_type == "asset"
