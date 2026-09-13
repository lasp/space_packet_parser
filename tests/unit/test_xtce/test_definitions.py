"""Tests for space_packet_parser.xtcedef"""

import io

import pytest
from lxml import etree as ElementTree

import space_packet_parser as spp
import space_packet_parser.generators.ccsds
import space_packet_parser.xtce.parameter_types
from space_packet_parser import xtce
from space_packet_parser.xtce import comparisons, containers, definitions, encodings, parameters


def test_xtce_definition_from_xtce_inputs(test_data_dir):
    """Test that we can create an XtcePacketDefinition from various inputs"""
    # Test from a Path
    definitions.XtcePacketDefinition.from_xtce(test_data_dir / "test_xtce.xml")

    # Test from a string path
    definitions.XtcePacketDefinition.from_xtce(str(test_data_dir / "test_xtce.xml"))

    # Test from a file-like object
    with (test_data_dir / "test_xtce.xml").open("r") as f:
        definitions.XtcePacketDefinition.from_xtce(f)

    xtce_str = """<xtce:SpaceSystem name="XTCEStringTest"
                  xmlns:xtce="http://www.omg.org/spec/XTCE/20180204"
                  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                  xsi:schemaLocation="http://www.omg.org/spec/XTCE/20180204
                                      https://www.omg.org/spec/XTCE/20180204/SpaceSystem.xsd">
    <xtce:Header date="2024-03-05T13:36:00MST" version="1.0"/>
    <xtce:TelemetryMetaData>
        <xtce:ParameterTypeSet>
        </xtce:ParameterTypeSet>
        <xtce:ParameterSet>
        </xtce:ParameterSet>
        <xtce:ContainerSet>
        </xtce:ContainerSet>
    </xtce:TelemetryMetaData>
</xtce:SpaceSystem>"""

    # Test from a string input
    definitions.XtcePacketDefinition.from_xtce(io.StringIO(xtce_str))

    # XTCE string with encoding specified in document
    xtce_bytes = b"""<?xml version='1.0' encoding='UTF-8'?>
<xtce:SpaceSystem name="XTCEBytesTest"
                  xmlns:xtce="http://www.omg.org/spec/XTCE/20180204"
                  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                  xsi:schemaLocation="http://www.omg.org/spec/XTCE/20180204
                                      https://www.omg.org/spec/XTCE/20180204/SpaceSystem.xsd">
    <xtce:Header date="2024-03-05T13:36:00MST" version="1.0"/>
    <xtce:TelemetryMetaData>
        <xtce:ParameterTypeSet>
        </xtce:ParameterTypeSet>
        <xtce:ParameterSet>
        </xtce:ParameterSet>
        <xtce:ContainerSet>
        </xtce:ContainerSet>
    </xtce:TelemetryMetaData>
</xtce:SpaceSystem>"""

    # Test from a bytes input
    definitions.XtcePacketDefinition.from_xtce(io.BytesIO(xtce_bytes))


def test_definition_with_nonstandard_namespace_string():
    """Test definition parsing on XTCE document with non-standard namespace identifier

    Usually the namespace is "http://www.omg.org/spec/XTCE/20180204", but this test uses "http://www.omg.org/spec/xtce"
    """
    xtce_str = """<xtce:SpaceSystem name="XTCENamespaceNameChangeTest"
                  xmlns:xtce="http://www.omg.org/spec/xtce"
                  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                  xsi:schemaLocation="http://www.omg.org/spec/xtce
                                      https://www.omg.org/spec/XTCE/20180204/SpaceSystem.xsd">
    <xtce:Header date="2024-03-05T13:36:00MST" version="1.0"/>
    <xtce:TelemetryMetaData>
        <xtce:ParameterTypeSet>
        </xtce:ParameterTypeSet>
        <xtce:ParameterSet>
        </xtce:ParameterSet>
        <xtce:ContainerSet>
        </xtce:ContainerSet>
    </xtce:TelemetryMetaData>
</xtce:SpaceSystem>"""

    defn = definitions.XtcePacketDefinition.from_xtce(io.StringIO(xtce_str))
    assert defn.ns == {"xtce": "http://www.omg.org/spec/xtce", "xsi": "http://www.w3.org/2001/XMLSchema-instance"}
    assert defn.xtce_ns_prefix == "xtce"
    assert defn.xtce_ns_uri == "http://www.omg.org/spec/xtce"


@pytest.mark.parametrize(
    ("xtcedoc", "warning_expected"),
    [("test_xtce.xml", False), ("test_xtce_default_namespace.xml", False), ("test_xtce_no_namespace.xml", True)],
)
def test_parsing_xtce_document(test_data_dir, xtcedoc, warning_expected):
    """Tests parsing an entire XTCE document and makes assertions about the contents"""
    with open(test_data_dir / xtcedoc) as x:
        if warning_expected:
            with pytest.warns(UserWarning, match="No XTCE namespace found in the document."):
                xdef = definitions.XtcePacketDefinition.from_xtce(x)
        else:
            xdef = definitions.XtcePacketDefinition.from_xtce(x)

    # Test Parameter Types
    ptname = "USEC_Type"
    pt = xdef.parameter_types[ptname]
    assert pt.name == ptname
    assert pt.unit == "us"
    assert isinstance(pt.encoding, encodings.IntegerDataEncoding)

    # Test Parameters
    pname = "ADAET1DAY"  # Named parameter
    p = xdef.parameters[pname]
    assert p.name == pname
    assert p.short_description == "Ephemeris Valid Time, Days Since 1/1/1958"
    assert p.long_description is None

    pname = "USEC"
    p = xdef.parameters[pname]
    assert p.name == pname
    assert p.short_description == "Secondary Header Fine Time (microsecond)"
    assert p.long_description == "CCSDS Packet 2nd Header Fine Time in microseconds."

    # Test Sequence Containers
    scname = "SecondaryHeaderContainer"
    sc = xdef.containers[scname]
    assert sc.name == scname
    assert sc == containers.SequenceContainer(
        name=scname,
        entry_list=[
            parameters.Parameter(
                name="DOY",
                parameter_type=space_packet_parser.xtce.parameter_types.FloatParameterType(
                    name="DOY_Type",
                    encoding=encodings.IntegerDataEncoding(size_in_bits=16, encoding="unsigned"),
                    unit="day",
                ),
                short_description="Secondary Header Day of Year",
                long_description="CCSDS Packet 2nd Header Day of Year in days.",
            ),
            parameters.Parameter(
                name="MSEC",
                parameter_type=space_packet_parser.xtce.parameter_types.FloatParameterType(
                    name="MSEC_Type",
                    encoding=encodings.IntegerDataEncoding(size_in_bits=32, encoding="unsigned"),
                    unit="ms",
                ),
                short_description="Secondary Header Coarse Time (millisecond)",
                long_description="CCSDS Packet 2nd Header Coarse Time in milliseconds.",
            ),
            parameters.Parameter(
                name="USEC",
                parameter_type=space_packet_parser.xtce.parameter_types.FloatParameterType(
                    name="USEC_Type",
                    encoding=encodings.IntegerDataEncoding(size_in_bits=16, encoding="unsigned"),
                    unit="us",
                ),
                short_description="Secondary Header Fine Time (microsecond)",
                long_description="CCSDS Packet 2nd Header Fine Time in microseconds.",
            ),
        ],
        short_description=None,
        long_description="Container for telemetry secondary header items",
        base_container_name=None,
        restriction_criteria=None,
        abstract=True,
        inheritors=None,
    )


def test_generating_xtce_from_objects():
    """Tests our ability to create an XTCE definition directly from Python objects"""
    uint1 = space_packet_parser.xtce.parameter_types.IntegerParameterType(
        name="UINT1_Type", encoding=encodings.IntegerDataEncoding(size_in_bits=1, encoding="unsigned")
    )

    uint2 = space_packet_parser.xtce.parameter_types.IntegerParameterType(
        name="UINT2_Type", encoding=encodings.IntegerDataEncoding(size_in_bits=2, encoding="unsigned")
    )

    uint3 = space_packet_parser.xtce.parameter_types.IntegerParameterType(
        name="UINT3_Type", encoding=encodings.IntegerDataEncoding(size_in_bits=3, encoding="unsigned")
    )

    uint11 = space_packet_parser.xtce.parameter_types.IntegerParameterType(
        name="UINT11_Type", encoding=encodings.IntegerDataEncoding(size_in_bits=11, encoding="unsigned")
    )

    uint14 = space_packet_parser.xtce.parameter_types.IntegerParameterType(
        name="UINT14_Type", encoding=encodings.IntegerDataEncoding(size_in_bits=14, encoding="unsigned")
    )

    uint16 = space_packet_parser.xtce.parameter_types.IntegerParameterType(
        name="UINT16_Type", encoding=encodings.IntegerDataEncoding(size_in_bits=16, encoding="unsigned")
    )

    multiply_nested_container = containers.SequenceContainer(
        name="NestedContainer",
        abstract=True,
        entry_list=[
            parameters.Parameter(
                name="REPEATABLY_NESTED",
                parameter_type=space_packet_parser.xtce.parameter_types.IntegerParameterType(
                    name="REPEATABLY_NESTED_Type",
                    encoding=encodings.IntegerDataEncoding(size_in_bits=32, encoding="unsigned"),
                ),
            )
        ],
    )

    apid_filtered_container = containers.SequenceContainer(
        name="APID_3200",
        abstract=False,
        base_container_name="RootContainer",
        restriction_criteria=[
            comparisons.Comparison(
                required_value="3200", referenced_parameter="APID", operator="==", use_calibrated_value=True
            )
        ],
        entry_list=[
            multiply_nested_container,
            parameters.Parameter(
                name="SCI_DATA_LEN_BYTES",
                parameter_type=space_packet_parser.xtce.parameter_types.IntegerParameterType(
                    name="SCI_DATA_LEN_BYTES_Type",
                    encoding=encodings.IntegerDataEncoding(size_in_bits=8, encoding="unsigned"),
                ),
            ),
            parameters.Parameter(
                name="VAR_SCI_DATA",
                parameter_type=space_packet_parser.xtce.parameter_types.BinaryParameterType(
                    name="VAR_SCI_DATA_Type",
                    encoding=encodings.BinaryDataEncoding(
                        size_reference_parameter="SCI_DATA_LEN_BYTES", linear_adjuster=lambda x: 8 * x
                    ),
                ),
            ),
        ],
    )

    root_container = containers.SequenceContainer(
        name="RootContainer",
        abstract=True,
        inheritors=[apid_filtered_container.name],
        entry_list=[
            parameters.Parameter(name="VERSION", parameter_type=uint3, short_description="CCSDS header version"),
            parameters.Parameter(name="TYPE", parameter_type=uint1, short_description="CCSDS header type"),
            parameters.Parameter(
                name="SEC_HDR_FLG", parameter_type=uint1, short_description="CCSDS header secondary header flag"
            ),
            parameters.Parameter(name="APID", parameter_type=uint11, short_description="CCSDS header APID"),
            parameters.Parameter(
                name="SEQ_FLGS", parameter_type=uint2, short_description="CCSDS header sequence flags"
            ),
            parameters.Parameter(
                name="SRC_SEQ_CTR", parameter_type=uint14, short_description="CCSDS header source sequence counter"
            ),
            parameters.Parameter(name="PKT_LEN", parameter_type=uint16, short_description="CCSDS header packet length"),
            multiply_nested_container,
        ],
    )

    # This list of sequence containers internally contains all parameters and parameter types
    sequence_containers = [root_container, apid_filtered_container, multiply_nested_container]

    # Create the definition object
    definition = definitions.XtcePacketDefinition(
        container_set=sequence_containers,
        root_container_name=root_container.name,
        date="2025-01-01T01:01:01",
        space_system_name="Test Space System Name",
    )

    # Serialize it to an XML string
    xtce_string = ElementTree.tostring(definition.to_xml_tree(), pretty_print=True).decode()

    # Reparse that string into a new definition object using from_document
    reparsed_definition = definitions.XtcePacketDefinition.from_xtce(
        io.StringIO(xtce_string), root_container_name=root_container.name
    )

    assert reparsed_definition == definition


@pytest.mark.parametrize(
    ("xml", "ns_prefix", "uri", "ns", "warning_expected", "new_ns_prefix", "new_uri", "new_ns", "new_warning_expected"),
    [
        # Custom namespace to new custom namespace
        (
            """
<custom:SpaceSystem xmlns:custom="http://www.fake-test.org/space/xtce" name="custom_to_custom">
    <custom:Header date="2024-03-05T13:36:00MST" version="1.0" author="Gavin Medley"/>
    <custom:TelemetryMetaData>
        <custom:ParameterTypeSet/>
        <custom:ParameterSet/>
        <custom:ContainerSet/>
    </custom:TelemetryMetaData>
</custom:SpaceSystem>
""",
            "custom",
            "http://www.fake-test.org/space/xtce",
            {"custom": "http://www.fake-test.org/space/xtce"},
            False,
            "xtcenew",
            "http://www.fake-test.org/space/xtce",
            {"xtcenew": "http://www.fake-test.org/space/xtce"},
            False,
        ),
        # Default namespace to custom namespace
        (
            """
<SpaceSystem xmlns="http://www.fake-test.org/space/xtce" name="default_to_custom">
    <Header date="2024-03-05T13:36:00MST" version="1.0" author="Gavin Medley"/>
    <TelemetryMetaData>
        <ParameterTypeSet/>
        <ParameterSet/>
        <ContainerSet/>
    </TelemetryMetaData>
</SpaceSystem>
""",
            None,
            "http://www.fake-test.org/space/xtce",
            {None: "http://www.fake-test.org/space/xtce"},
            False,
            "xtce",
            "http://www.fake-test.org/space/xtce",
            {"xtce": "http://www.fake-test.org/space/xtce"},
            False,
        ),
        # Custom namespace to default namespace
        (
            """
<custom:SpaceSystem xmlns:custom="http://www.fake-test.org/space/xtce" name="custom_to_default">
    <custom:Header date="2024-03-05T13:36:00MST" version="1.0" author="Gavin Medley"/>
    <custom:TelemetryMetaData>
        <custom:ParameterTypeSet/>
        <custom:ParameterSet/>
        <custom:ContainerSet/>
    </custom:TelemetryMetaData>
</custom:SpaceSystem>
""",
            "custom",
            "http://www.fake-test.org/space/xtce",
            {"custom": "http://www.fake-test.org/space/xtce"},
            False,
            None,
            "http://www.fake-test.org/space/xtce",
            {None: "http://www.fake-test.org/space/xtce"},
            False,
        ),
        # No namespace to custom namespace
        (
            """
<SpaceSystem name="no_namespace_to_custom">
    <Header date="2024-03-05T13:36:00MST" version="1.0" author="Gavin Medley"/>
    <TelemetryMetaData>
        <ParameterTypeSet/>
        <ParameterSet/>
        <ContainerSet/>
    </TelemetryMetaData>
</SpaceSystem>
""",
            None,
            None,
            {},
            True,
            "xtcenew",
            "http://www.fake-test.org/space/xtce",
            {"xtcenew": "http://www.fake-test.org/space/xtce"},
            False,
        ),
        # Custom namespace to no namespace
        (
            """
<custom:SpaceSystem xmlns:custom="http://www.fake-test.org/space/xtce" name="custom_to_no_namespace">
    <custom:Header date="2024-03-05T13:36:00MST" version="1.0" author="Gavin Medley"/>
    <custom:TelemetryMetaData>
        <custom:ParameterTypeSet/>
        <custom:ParameterSet/>
        <custom:ContainerSet/>
    </custom:TelemetryMetaData>
</custom:SpaceSystem>
""",
            "custom",
            "http://www.fake-test.org/space/xtce",
            {"custom": "http://www.fake-test.org/space/xtce"},
            False,
            None,
            None,
            {},
            True,
        ),
    ],
)
def test_custom_namespacing(
    xml, ns_prefix, uri, ns, warning_expected, new_ns_prefix, new_uri, new_ns, new_warning_expected
):
    """Test parsing XTCE with various namespace configurations

    This tests the behavior of changing namespacing on an XtcePacketDefinition object, which may have an explicitly prefixed
    namespace, a default namespace, or no namespace at all. Any time we parse or serialize and XML tree in the absence of
    a defined namespace, we should issue a warning.
    """
    # Parse directly from string, inferring the namespace mapping
    if warning_expected:
        # Parsing a document with no namespace should issue a warning
        with pytest.warns(UserWarning, match="No XTCE namespace found in the document."):
            xdef = definitions.XtcePacketDefinition.from_xtce(io.StringIO(xml))
    else:
        xdef = definitions.XtcePacketDefinition.from_xtce(io.StringIO(xml))

    if warning_expected:
        with pytest.warns(
            UserWarning, match="No XTCE namespace defined. This is invalid per XSD, but will be serialized."
        ):
            default_tree = xdef.to_xml_tree()
    else:
        default_tree = xdef.to_xml_tree()
    # Assert that we know what the inferred mapping is
    assert default_tree.getroot().nsmap == ns

    # Prove we can find an element using the ns label prefix, if any
    if ns:
        ns_label = [k for k, v in ns.items() if v == uri][0]
        prefix = f"{ns_label}:" if ns_label else ""
    else:
        prefix = ""
    assert default_tree.find(f"{prefix}TelemetryMetaData", ns) is not None

    # And also using the URI literal, if any
    prefix = f"{{{uri}}}" if uri else ""
    assert default_tree.find(f"{prefix}TelemetryMetaData", ns) is not None

    # Create the XML tree using a custom namespace label for the XTCE schema
    xdef.ns = new_ns
    xdef.xtce_ns_uri = new_uri
    if new_warning_expected:
        # Changing to no-namespacing will issue a warning
        with pytest.warns(
            UserWarning, match="No XTCE namespace defined. This is invalid per XSD, but will be serialized."
        ):
            new_tree = xdef.to_xml_tree()
    else:
        new_tree = xdef.to_xml_tree()

    # Assert the new mapping was applied
    assert new_tree.getroot().nsmap == new_ns

    # Prove we can find an element using the ns label prefix, if any
    if new_ns:
        ns_label = [k for k, v in new_ns.items() if v == new_uri][0]
        prefix = f"{ns_label}:" if ns_label else ""
    else:
        prefix = ""
    assert new_tree.find(f"{prefix}TelemetryMetaData", new_ns) is not None

    # And also using the new URI literal, if any
    prefix = f"{{{new_uri}}}" if new_uri else ""
    assert new_tree.find(f"{prefix}TelemetryMetaData", new_ns) is not None


def test_uniqueness_of_parsed_xtce_objects():
    """When we parse a document, we expect a singleton reference to each parameter, parameter type and sequence
    container definition. This test proves that these references are all unique
    """
    xtce = """
<xtce:SpaceSystem xmlns:xtce="http://www.omg.org/space/xtce" name="Libera">
    <xtce:Header date="2021-06-08T14:11:00MST" version="1.0" author="Gavin Medley"/>
    <xtce:TelemetryMetaData>
        <xtce:ParameterTypeSet>
            <xtce:IntegerParameterType name="UINT3_Type" signed="false">
                <xtce:IntegerDataEncoding sizeInBits="3" encoding="unsigned"/>
            </xtce:IntegerParameterType>
            <xtce:IntegerParameterType name="UINT1_Type" signed="false">
                <xtce:IntegerDataEncoding sizeInBits="1" encoding="unsigned"/>
            </xtce:IntegerParameterType>
        </xtce:ParameterTypeSet>
        <xtce:ParameterSet>
            <xtce:Parameter name="PARAM_1" parameterTypeRef="UINT3_Type"/>
            <xtce:Parameter name="PARAM_2" parameterTypeRef="UINT3_Type"/>
            <xtce:Parameter name="PARAM_3" parameterTypeRef="UINT1_Type"/>
            <xtce:Parameter name="PARAM_4" parameterTypeRef="UINT1_Type"/>
        </xtce:ParameterSet>
        <xtce:ContainerSet>
            <xtce:SequenceContainer name="CCSDSPacket" abstract="true">
                <xtce:EntryList>
                    <xtce:ParameterRefEntry parameterRef="PARAM_1"/>
                    <xtce:ParameterRefEntry parameterRef="PARAM_2"/>
                </xtce:EntryList>
            </xtce:SequenceContainer>
            <xtce:SequenceContainer name="CCSDSTelemetryPacket" abstract="true">
                <xtce:LongDescription>Super-container for all telemetry packets</xtce:LongDescription>
                <xtce:EntryList/>
                <xtce:BaseContainer containerRef="CCSDSPacket">
                    <xtce:RestrictionCriteria>
                        <xtce:Comparison parameterRef="PARAM_1" value="0" useCalibratedValue="false"/>
                    </xtce:RestrictionCriteria>
                </xtce:BaseContainer>
            </xtce:SequenceContainer>
            <xtce:SequenceContainer name="SecondaryHeaderContainer" abstract="true">
                <xtce:EntryList>
                    <xtce:ParameterRefEntry parameterRef="PARAM_3"/>
                </xtce:EntryList>
            </xtce:SequenceContainer>
            <xtce:SequenceContainer name="USES_SecondaryHeaderContainer">
                <xtce:EntryList>
                    <xtce:ContainerRefEntry containerRef="SecondaryHeaderContainer"/>
                    <xtce:ParameterRefEntry parameterRef="PARAM_4"/>
                </xtce:EntryList>
                <xtce:BaseContainer containerRef="CCSDSTelemetryPacket">
                    <xtce:RestrictionCriteria>
                        <xtce:Comparison parameterRef="PARAM_2" value="11" useCalibratedValue="false"/>
                    </xtce:RestrictionCriteria>
                </xtce:BaseContainer>
            </xtce:SequenceContainer>
            <xtce:SequenceContainer name="ALSO_USES_SecondaryHeaderContainer">
                <xtce:EntryList>
                    <xtce:ContainerRefEntry containerRef="SecondaryHeaderContainer"/>
                    <xtce:ParameterRefEntry parameterRef="PARAM_1"/>
                </xtce:EntryList>
            </xtce:SequenceContainer>
        </xtce:ContainerSet>
    </xtce:TelemetryMetaData>
</xtce:SpaceSystem>
"""
    xdef = definitions.XtcePacketDefinition.from_xtce(io.StringIO(xtce))

    def_param_ids = [id(p) for p in xdef.parameters.values()]
    def_param_type_ids = [id(pt) for pt in xdef.parameter_types.values()]
    def_cont_ids = [id(sc) for sc in xdef.containers.values()]

    def _flatten_container(container: containers.SequenceContainer):
        for entry in container.entry_list:
            if isinstance(entry, containers.SequenceContainer):
                if id(entry) not in def_cont_ids:
                    raise AssertionError(f"{entry.name} object not in def.containers")
                _flatten_container(entry)
            else:
                if id(entry.parameter_type) not in def_param_type_ids:
                    raise AssertionError(f"{entry.parameter_type.name} not in definition.parameter_types")
                if id(entry) not in def_param_ids:
                    raise AssertionError(f"{entry.name} not in definition.parameters")

    for sc in xdef.containers.values():
        _flatten_container(sc)


def test_uniqueness_of_reused_sequence_container(jpss_test_data_dir):
    """Test that a reused sequence container element (nested into multiple entry lists)
    is still the same object

    This is a rather particular test that tests for regressions on a specific fixed behavior
    """
    jpss_xtce = jpss_test_data_dir / "contrived_inheritance_structure.xml"
    jpss_definition = definitions.XtcePacketDefinition.from_xtce(xtce_document=jpss_xtce)
    assert isinstance(jpss_definition, definitions.XtcePacketDefinition)

    # Prove that parsed sequence container objects are referencing the same objects, not duplicates
    unused_secondary_header_container_ref = jpss_definition.containers["UNUSED"].entry_list[0]
    assert isinstance(unused_secondary_header_container_ref, containers.SequenceContainer)
    jpss_att_ephem_header_container_ref = jpss_definition.containers["JPSS_ATT_EPHEM"].entry_list[0]
    assert isinstance(jpss_att_ephem_header_container_ref, containers.SequenceContainer)
    assert unused_secondary_header_container_ref in jpss_definition.containers.values()
    assert jpss_att_ephem_header_container_ref in jpss_definition.containers.values()
    assert unused_secondary_header_container_ref is jpss_att_ephem_header_container_ref


def test_deprecated_definition_class(test_data_dir):
    """Test that the deprecated XtcePacketDefinition class still works"""
    with pytest.warns(DeprecationWarning, match="The space_packet_parser.definitions module is deprecated"):
        from space_packet_parser.definitions import XtcePacketDefinition as DeprecatedXtcePacketDefinition

    with pytest.warns(DeprecationWarning, match="This class is deprecated"):
        xtce = DeprecatedXtcePacketDefinition(test_data_dir / "test_xtce.xml")
    assert xtce.containers == definitions.XtcePacketDefinition.from_xtce(test_data_dir / "test_xtce.xml").containers


def test_definition_from_file_error():
    """Nicer error message when calling the class directly"""
    with pytest.raises(TypeError, match="container_set must be an iterable of SequenceContainer objects"):
        definitions.XtcePacketDefinition("test_xtce.xml")


def test_parse_methods(test_data_dir):
    """Test parsing a packet from an XTCE document"""
    xdef = definitions.XtcePacketDefinition.from_xtce(test_data_dir / "test_xtce.xml")

    # Test parsing a packet
    empty_packet_data = space_packet_parser.generators.ccsds.create_ccsds_packet(
        data=bytes(65), apid=11, sequence_flags=space_packet_parser.generators.ccsds.SequenceFlags.UNSEGMENTED
    )

    # Parse in the simplest way and compare result to other parse methods
    packet = xdef.parse_bytes(empty_packet_data)
    # Raw bytes should work too, not required to be a CCSDSPacketBytes object
    assert packet == xdef.parse_bytes(bytes(empty_packet_data))
    # Emit a warning if we have too many bytes for this definition
    with pytest.warns(UserWarning, match="Number of bits parsed"):
        assert packet == xdef.parse_bytes(empty_packet_data + b"\x00\x00")

    # Deprecated parse_ccsds_packet method, can be removed in a future version
    empty_packet = spp.SpacePacket(binary_data=empty_packet_data)
    with pytest.warns(DeprecationWarning, match="parse_ccsds_packet is deprecated"):
        with pytest.warns(DeprecationWarning, match="parse_packet is deprecated"):
            assert packet == xdef.parse_ccsds_packet(empty_packet)

    # Deprecated parse_packet method, can be removed in a future version
    empty_packet = spp.SpacePacket(binary_data=empty_packet_data)
    with pytest.warns(DeprecationWarning, match="parse_packet is deprecated"):
        assert packet == xdef.parse_packet(empty_packet)


def test_parse_packet_extra_bytes(test_data_dir):
    """Test parsing a packet that has too many raw bytes

    This should warn the user that there is unparsed data
    """
    xdef = definitions.XtcePacketDefinition.from_xtce(test_data_dir / "test_xtce.xml")

    # Test parsing a packet that is longer than the definition
    too_long_packet_data = space_packet_parser.generators.ccsds.create_ccsds_packet(
        data=bytes(70), apid=11, sequence_flags=space_packet_parser.generators.ccsds.SequenceFlags.UNSEGMENTED
    )

    with pytest.warns(
        UserWarning, match=r"Number of bits parsed \(568b\) did not match the length of data available \(608b\)"
    ):
        xdef.parse_bytes(too_long_packet_data)


def test_parse_packet_too_few_bytes(test_data_dir):
    """Test parsing a packet that has too few raw bytes

    This should raise an exception
    """
    xdef = definitions.XtcePacketDefinition.from_xtce(test_data_dir / "test_xtce.xml")

    # Test parsing a packet that is longer than the definition
    too_short_packet_data = space_packet_parser.generators.ccsds.create_ccsds_packet(
        data=bytes(60), apid=11, sequence_flags=space_packet_parser.generators.ccsds.SequenceFlags.UNSEGMENTED
    )

    with pytest.raises(
        ValueError,
        match=r"Tried to read beyond the end of the packet data. "
        r"Tried to read 32 bits from position 504 in a packet of length 528 bits.",
    ):
        xdef.parse_bytes(too_short_packet_data)


# --------------------------------------------------------------------------------------
# XTCE version awareness (1.2 and 1.3)
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


def test_xtce_1_2_and_1_3_definitions_parse_packets_identically(test_data_dir, jpss_test_data_dir):
    """Packets parse to the same values whether the definition is XTCE 1.2 or 1.3"""
    xdef_12 = definitions.XtcePacketDefinition.from_xtce(test_data_dir / "test_xtce.xml")
    xdef_13 = definitions.XtcePacketDefinition.from_xtce(test_data_dir / "test_xtce_1_3.xml")

    with open(jpss_test_data_dir / "J01_G011_LZ_2021-04-09T00-00-00Z_V01.DAT1", "rb") as f:
        packet_bytes = list(spp.ccsds_generator(f))[:5]

    assert [dict(xdef_12.parse_bytes(b)) for b in packet_bytes] == [dict(xdef_13.parse_bytes(b)) for b in packet_bytes]


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


def test_convert_definition_to_unknown_version_raises(test_data_dir):
    """Retargeting at a version this library does not know about is an error"""
    xdef = definitions.XtcePacketDefinition.from_xtce(test_data_dir / "test_xtce.xml")
    with pytest.raises(ValueError, match="Unrecognized XTCE version"):
        xdef.xtce_standard_version = "9.9"
