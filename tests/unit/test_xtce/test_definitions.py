"""Tests for space_packet_parser.xtcedef"""

import io

import pytest
from lxml import etree as ElementTree

import space_packet_parser as spp
import space_packet_parser.generators.ccsds
import space_packet_parser.xtce.parameter_types
from space_packet_parser import common
from space_packet_parser.exceptions import UnrecognizedPacketTypeError
from space_packet_parser.xtce import comparisons, containers, definitions, encodings, parameters

# Minimal definition with no CCSDS header and no PKT_APID parameter (see issue #276)
NO_CCSDS_XTCE = """<xtce:SpaceSystem name="NoCcsds" xmlns:xtce="http://www.omg.org/spec/XTCE/20180204">
  <xtce:TelemetryMetaData>
    <xtce:ParameterTypeSet>
      <xtce:IntegerParameterType name="U8_Type" signed="false">
        <xtce:IntegerDataEncoding sizeInBits="8" encoding="unsigned"/>
      </xtce:IntegerParameterType>
    </xtce:ParameterTypeSet>
    <xtce:ParameterSet>
      <xtce:Parameter name="COUNTER" parameterTypeRef="U8_Type"/>
    </xtce:ParameterSet>
    <xtce:ContainerSet>
      <xtce:SequenceContainer name="AbstractRoot" abstract="true">
        <xtce:EntryList><xtce:ParameterRefEntry parameterRef="COUNTER"/></xtce:EntryList>
      </xtce:SequenceContainer>
      <xtce:SequenceContainer name="Child">
        <xtce:EntryList/>
        <xtce:BaseContainer containerRef="AbstractRoot">
          <xtce:RestrictionCriteria>
            <xtce:Comparison parameterRef="COUNTER" value="99" useCalibratedValue="false"/>
          </xtce:RestrictionCriteria>
        </xtce:BaseContainer>
      </xtce:SequenceContainer>
    </xtce:ContainerSet>
  </xtce:TelemetryMetaData>
</xtce:SpaceSystem>
"""

# Nested_Packets is the root. SENSOR_A, SENSOR_B and SENSOR_C are its children, and DIAGNOSTICS is the child of SENSOR_B.
# SENSOR_B has no TelemetryMetaData, and SENSOR_C has a ParameterSet only.
NESTED_SETS_XTCE = """<xtce:SpaceSystem name="Nested_Packets" xmlns:xtce="http://www.omg.org/spec/XTCE/20180204">
  <xtce:TelemetryMetaData>
    <xtce:ParameterTypeSet>
      <xtce:IntegerParameterType name="BYTE_Type" signed="false">
        <xtce:IntegerDataEncoding sizeInBits="8" encoding="unsigned"/>
      </xtce:IntegerParameterType>
    </xtce:ParameterTypeSet>
    <xtce:ParameterSet>
      <xtce:Parameter name="PKT_APID" parameterTypeRef="BYTE_Type"/>
    </xtce:ParameterSet>
    <xtce:ContainerSet>
      <xtce:SequenceContainer name="CCSDSPacket" abstract="true">
        <xtce:EntryList><xtce:ParameterRefEntry parameterRef="PKT_APID"/></xtce:EntryList>
      </xtce:SequenceContainer>
    </xtce:ContainerSet>
  </xtce:TelemetryMetaData>
  <xtce:SpaceSystem name="SENSOR_A">
    <xtce:TelemetryMetaData>
      <xtce:ParameterTypeSet>
        <xtce:IntegerParameterType name="VALUE_Type" signed="false">
          <xtce:IntegerDataEncoding sizeInBits="8" encoding="unsigned"/>
        </xtce:IntegerParameterType>
      </xtce:ParameterTypeSet>
      <xtce:ParameterSet>
        <xtce:Parameter name="READING_SMALL" parameterTypeRef="VALUE_Type"/>
        <xtce:Parameter name="READING_WIDE" parameterTypeRef="/Nested_Packets/BYTE_Type"/>
      </xtce:ParameterSet>
      <xtce:ContainerSet/>
    </xtce:TelemetryMetaData>
  </xtce:SpaceSystem>
  <xtce:SpaceSystem name="SENSOR_B">
    <xtce:SpaceSystem name="DIAGNOSTICS">
      <xtce:TelemetryMetaData>
        <xtce:ParameterTypeSet>
          <xtce:IntegerParameterType name="VALUE_Type" signed="true">
            <xtce:IntegerDataEncoding sizeInBits="16" encoding="twosComplement"/>
          </xtce:IntegerParameterType>
        </xtce:ParameterTypeSet>
        <xtce:ParameterSet>
          <xtce:Parameter name="STATUS" parameterTypeRef="VALUE_Type"/>
          <xtce:Parameter name="OFFSET" parameterTypeRef="./VALUE_Type"/>
        </xtce:ParameterSet>
        <xtce:ContainerSet>
          <xtce:SequenceContainer name="DIAGNOSTICS">
            <xtce:EntryList>
              <xtce:ParameterRefEntry parameterRef="STATUS"/>
              <xtce:ParameterRefEntry parameterRef="/Nested_Packets/PKT_APID"/>
            </xtce:EntryList>
            <xtce:BaseContainer containerRef="/Nested_Packets/CCSDSPacket">
              <xtce:RestrictionCriteria>
                <xtce:Comparison parameterRef="/Nested_Packets/PKT_APID" value="12" useCalibratedValue="false"/>
              </xtce:RestrictionCriteria>
            </xtce:BaseContainer>
          </xtce:SequenceContainer>
        </xtce:ContainerSet>
      </xtce:TelemetryMetaData>
    </xtce:SpaceSystem>
  </xtce:SpaceSystem>
  <xtce:SpaceSystem name="SENSOR_C">
    <xtce:TelemetryMetaData>
      <xtce:ParameterSet>
        <xtce:Parameter name="READING" parameterTypeRef="/Nested_Packets/BYTE_Type"/>
      </xtce:ParameterSet>
    </xtce:TelemetryMetaData>
  </xtce:SpaceSystem>
</xtce:SpaceSystem>
"""


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


def test_parse_bytes_unrecognized_packet_without_pkt_apid():
    """Test that an unrecognized packet raises UnrecognizedPacketTypeError for a definition with no PKT_APID

    XTCE has no notion of the CCSDS standard, so the error path must not assume a parameter named PKT_APID exists.
    Regression test for https://github.com/lasp/space_packet_parser/issues/276
    """
    xdef = definitions.XtcePacketDefinition.from_xtce(io.StringIO(NO_CCSDS_XTCE), root_container_name="AbstractRoot")

    # COUNTER=7, so the Child restriction criteria (COUNTER == 99) fail and AbstractRoot has no valid inheritors
    with pytest.raises(UnrecognizedPacketTypeError, match=r"abstract container \(AbstractRoot\)") as exc_info:
        xdef.parse_bytes(b"\x07")

    # The message must not pretend to know an APID that does not exist in this definition
    assert "APID" not in str(exc_info.value)
    # The partially parsed packet is the main diagnostic the error exists to carry
    assert exc_info.value.partial_data is not None
    assert exc_info.value.partial_data["COUNTER"] == 7


def test_parse_bytes_unrecognized_packet_reports_apid(test_data_dir):
    """Test that an unrecognized CCSDS packet still reports its APID in the UnrecognizedPacketTypeError message"""
    xdef = definitions.XtcePacketDefinition.from_xtce(test_data_dir / "test_xtce.xml")

    # APID 2047 is not defined in test_xtce.xml
    unknown_apid_packet = space_packet_parser.generators.ccsds.create_ccsds_packet(
        data=bytes(65), apid=2047, sequence_flags=space_packet_parser.generators.ccsds.SequenceFlags.UNSEGMENTED
    )

    with pytest.raises(UnrecognizedPacketTypeError, match="APID=2047") as exc_info:
        xdef.parse_bytes(unknown_apid_packet)

    assert exc_info.value.partial_data["PKT_APID"] == 2047


def test_parse_bytes_unrecognized_packet_ccsds_bytes_without_pkt_apid():
    """Test that the CCSDS header printout is used when the bytes are CCSDSPacketBytes but no PKT_APID is parsed

    Regression test for the fallback branch added in https://github.com/lasp/space_packet_parser/pull/282
    """
    xdef = definitions.XtcePacketDefinition.from_xtce(io.StringIO(NO_CCSDS_XTCE), root_container_name="AbstractRoot")

    # COUNTER=7 fails the Child restriction criteria. Pad to a full 6-byte header so the printout has real values.
    ccsds_bytes = space_packet_parser.generators.ccsds.CCSDSPacketBytes(b"\x07" + bytes(7))
    with pytest.raises(UnrecognizedPacketTypeError, match="CCSDSPacket Header") as exc_info:
        xdef.parse_bytes(ccsds_bytes)

    assert "APID=" not in str(exc_info.value)
    assert exc_info.value.partial_data["COUNTER"] == 7

    # Even a CCSDSPacketBytes too short for a full header must not break error reporting
    with pytest.raises(UnrecognizedPacketTypeError, match="incomplete, 1 of 6 bytes") as exc_info:
        xdef.parse_bytes(space_packet_parser.generators.ccsds.CCSDSPacketBytes(b"\x07"))
    assert exc_info.value.partial_data["COUNTER"] == 7


@pytest.mark.parametrize("space_system_path", ["/Root", "/Root/A", "/Root/A/B/C"])
@pytest.mark.parametrize(
    ("reference", "expected"),
    [
        ("/Root/Name", "/Root/Name"),
        ("/Root/A/Name", "/Root/A/Name"),
        ("/Root/A/./Name", "/Root/A/Name"),
        ("/Root/A/../B/Name", "/Root/B/Name"),
    ],
)
def test_resolve_reference_absolute(space_system_path, reference, expected):
    """Test that a reference starting with "/" is returned as a clean full path, whatever SpaceSystem contains it"""
    assert definitions.XtcePacketDefinition._resolve_reference(reference, space_system_path) == expected


@pytest.mark.parametrize("space_system_path", ["/Root", "/Root/A", "/Root/A/B/C"])
@pytest.mark.parametrize("reference", ["Name", "./Name"])
def test_resolve_reference_inside_space_system(space_system_path, reference):
    """Test that a bare reference and a "./" reference both give the path of the SpaceSystem plus the reference"""
    resolved = definitions.XtcePacketDefinition._resolve_reference(reference, space_system_path)
    assert resolved == f"{space_system_path}/Name"


@pytest.mark.parametrize(
    ("number_of_parents", "expected"),
    [
        (0, "/Root/A/B/C/Name"),
        (1, "/Root/A/B/Name"),
        (2, "/Root/A/Name"),
        (3, "/Root/Name"),
        (4, "/Name"),
        (5, "/Name"),
        (6, "/Name"),
    ],
)
def test_resolve_reference_parent(number_of_parents, expected):
    """Test that each ".." removes one SpaceSystem from the end of the path, and that extra ".." are ignored"""
    reference = "../" * number_of_parents + "Name"
    assert definitions.XtcePacketDefinition._resolve_reference(reference, "/Root/A/B/C") == expected


def test_qualify_names():
    """Test that every item name and every reference in the root SpaceSystem and in all its children becomes a full
    path, and that nothing else in the document changes"""
    xtce_element_class = common.NamespaceAwareElement
    xtce_parser = ElementTree.XMLParser()
    xtce_parser.set_element_class_lookup(ElementTree.ElementDefaultClassLookup(element=xtce_element_class))
    root = ElementTree.fromstring(NESTED_SETS_XTCE, parser=xtce_parser)
    xtce_element_class.set_ns_prefix("xtce")
    xtce_element_class.set_nsmap(root.nsmap)

    # The attribute that refers to each kind of item, and the items of that kind
    item_paths = {
        "parameterTypeRef": "//xtce:ParameterTypeSet/*",
        "parameterRef": "//xtce:ParameterSet/*",
        "containerRef": "//xtce:ContainerSet/*",
    }
    items = {
        reference_attribute: root.xpath(item_path, namespaces=root.nsmap)
        for reference_attribute, item_path in item_paths.items()
    }
    all_items = [item for kind_items in items.values() for item in kind_items]

    # Parameter types, then parameters, then containers, each in document order
    expected_names = [
        "/Nested_Packets/BYTE_Type",
        "/Nested_Packets/SENSOR_A/VALUE_Type",
        "/Nested_Packets/SENSOR_B/DIAGNOSTICS/VALUE_Type",
        "/Nested_Packets/PKT_APID",
        "/Nested_Packets/SENSOR_A/READING_SMALL",
        "/Nested_Packets/SENSOR_A/READING_WIDE",
        "/Nested_Packets/SENSOR_B/DIAGNOSTICS/STATUS",
        "/Nested_Packets/SENSOR_B/DIAGNOSTICS/OFFSET",
        "/Nested_Packets/SENSOR_C/READING",
        "/Nested_Packets/CCSDSPacket",
        "/Nested_Packets/SENSOR_B/DIAGNOSTICS/DIAGNOSTICS",
    ]

    def unrewritten_parts():
        """Tag and attributes of every element, without the attributes that _qualify_names rewrites"""
        parts = []
        for element in root.iter():
            rewritten = {"parameterRef", "parameterTypeRef", "containerRef"}
            if element in all_items:
                rewritten.add("name")
            parts.append(
                (element.tag, {name: value for name, value in element.attrib.items() if name not in rewritten})
            )
        return parts

    parts_before = unrewritten_parts()

    definitions.XtcePacketDefinition._qualify_names(root, "/Nested_Packets")

    # Each item name is the path of its SpaceSystem plus its own name
    assert [item.attrib["name"] for item in all_items] == expected_names

    # Each reference names an existing item of the right kind, and the names of one kind are unique
    for reference_attribute, kind_items in items.items():
        names = [item.attrib["name"] for item in kind_items]
        assert len(set(names)) == len(names)
        for referring_element in root.xpath(f"//*[@{reference_attribute}]"):
            assert referring_element.attrib[reference_attribute] in names

    # Everything except the item names and the references is as it was
    assert unrewritten_parts() == parts_before


@pytest.mark.parametrize(
    ("container_keys", "space_system_name", "name", "expected"),
    [
        # Loaded from a file: the keys are full paths
        (["/Root/CCSDSPacket"], "Root", "/Root/CCSDSPacket", "/Root/CCSDSPacket"),
        (["/Root/CCSDSPacket"], "Root", "CCSDSPacket", "/Root/CCSDSPacket"),
        (["/Root/SENSOR_B/DIAGNOSTICS"], "Root", "SENSOR_B/DIAGNOSTICS", "/Root/SENSOR_B/DIAGNOSTICS"),
        (["/Root/CCSDSPacket"], "Root", "Missing", "/Root/Missing"),
        # Created in Python code, not loaded from a file: the keys are short and there is no root name
        (["CCSDSPacket"], None, "CCSDSPacket", "CCSDSPacket"),
    ],
)
def test_resolve_container_name(container_keys, space_system_name, name, expected):
    """Test that a name which is already a key is returned unchanged, and that any other name gets the root path in
    front of it. A name that does not exist does not raise here. The lookup in parse_bytes raises the KeyError."""
    container_set = [containers.SequenceContainer(name=key, entry_list=[]) for key in container_keys]
    definition = definitions.XtcePacketDefinition(
        container_set=container_set, root_container_name=container_keys[0], space_system_name=space_system_name
    )

    assert definition._resolve_container_name(name) == expected


def test_move_items_to_root():
    """Test that every item of the child SpaceSystems ends up in the three sets of the root SpaceSystem, in document
    order and with nothing lost or doubled"""
    xtce_element_class = common.NamespaceAwareElement
    xtce_parser = ElementTree.XMLParser()
    xtce_parser.set_element_class_lookup(ElementTree.ElementDefaultClassLookup(element=xtce_element_class))
    root = ElementTree.fromstring(NESTED_SETS_XTCE, parser=xtce_parser)
    xtce_element_class.set_ns_prefix("xtce")
    xtce_element_class.set_nsmap(root.nsmap)

    # Each kind of set, and the names it must hold in document order: the root first, then each child
    expected_names = {
        "ParameterTypeSet": [
            "/Nested_Packets/BYTE_Type",
            "/Nested_Packets/SENSOR_A/VALUE_Type",
            "/Nested_Packets/SENSOR_B/DIAGNOSTICS/VALUE_Type",
        ],
        "ParameterSet": [
            "/Nested_Packets/PKT_APID",
            "/Nested_Packets/SENSOR_A/READING_SMALL",
            "/Nested_Packets/SENSOR_A/READING_WIDE",
            "/Nested_Packets/SENSOR_B/DIAGNOSTICS/STATUS",
            "/Nested_Packets/SENSOR_B/DIAGNOSTICS/OFFSET",
            "/Nested_Packets/SENSOR_C/READING",
        ],
        "ContainerSet": [
            "/Nested_Packets/CCSDSPacket",
            "/Nested_Packets/SENSOR_B/DIAGNOSTICS/DIAGNOSTICS",
        ],
    }

    definitions.XtcePacketDefinition._qualify_names(root, "/Nested_Packets")
    definitions.XtcePacketDefinition._move_items_to_root(root)

    for set_name, names in expected_names.items():
        root_sets = root.findall(f"TelemetryMetaData/{set_name}")
        assert len(root_sets) == 1
        assert [item.attrib["name"] for item in root_sets[0].findall("*")] == names

        # The sets of the child SpaceSystems may remain, but they are empty
        child_sets = root.findall(f".//SpaceSystem/TelemetryMetaData/{set_name}")
        assert all(len(child_set.findall("*")) == 0 for child_set in child_sets)


def test_move_items_to_root_makes_missing_set():
    """Test that a root SpaceSystem without a set gets one, holding the items of its child"""
    # The root has no TelemetryMetaData, so it has no ParameterSet. Its child has one parameter.
    xtce_string = """<xtce:SpaceSystem name="Root" xmlns:xtce="http://www.omg.org/spec/XTCE/20180204">
      <xtce:SpaceSystem name="Child">
        <xtce:TelemetryMetaData>
          <xtce:ParameterSet>
            <xtce:Parameter name="READING" parameterTypeRef="BYTE_Type"/>
          </xtce:ParameterSet>
        </xtce:TelemetryMetaData>
      </xtce:SpaceSystem>
    </xtce:SpaceSystem>"""
    xtce_element_class = common.NamespaceAwareElement
    xtce_parser = ElementTree.XMLParser()
    xtce_parser.set_element_class_lookup(ElementTree.ElementDefaultClassLookup(element=xtce_element_class))
    root = ElementTree.fromstring(xtce_string, parser=xtce_parser)
    xtce_element_class.set_ns_prefix("xtce")
    xtce_element_class.set_nsmap(root.nsmap)

    definitions.XtcePacketDefinition._qualify_names(root, "/Root")
    definitions.XtcePacketDefinition._move_items_to_root(root)

    # find adds the XTCE prefix, so this finds the new set only if it is in the XTCE namespace
    parameter_set = root.find("TelemetryMetaData/ParameterSet")
    assert parameter_set is not None
    assert [item.attrib["name"] for item in parameter_set.findall("*")] == ["/Root/Child/READING"]
