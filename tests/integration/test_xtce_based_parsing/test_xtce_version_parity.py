"""Integration tests proving XTCE 1.3 support against real mission packet definitions.

None of these mission definitions uses a construct that differs between XTCE 1.2 and 1.3 (see
test_xtce_1_3_only_features.xml for those), so each one moved to the 1.3 namespace must parse to
exactly the same objects and decode packets to exactly the same values. Rather than committing a second copy of every (large) mission definition, each test
rewrites the 1.2 namespace to the 1.3 namespace in memory and compares the two results.
"""

import io

import pytest

import space_packet_parser as spp
from space_packet_parser import xtce
from space_packet_parser.xtce.definitions import XtcePacketDefinition
from space_packet_parser.xtce.validation import validate_xtce


def _as_xtce_1_3(definition_path) -> io.BytesIO:
    """Rewrite an XTCE 1.2 document as the equivalent XTCE 1.3 document.

    Only the namespace URI and the schema it points at change. That is a valid conversion for these
    particular documents because none of them uses a construct whose meaning or validity differs
    between the two versions; it is not a general-purpose converter.
    """
    source = definition_path.read_bytes()
    assert xtce.XTCE_1_2_XMLNS.encode() in source, f"{definition_path} is not an XTCE 1.2 document"
    rewritten = source.replace(xtce.XTCE_1_2_XMLNS.encode(), xtce.XTCE_1_3_XMLNS.encode())
    rewritten = rewritten.replace(xtce.XTCE_1_2_XSD_URL.encode(), xtce.XTCE_1_3_XSD_URL.encode())
    return io.BytesIO(rewritten)


@pytest.fixture
def mission_definition_path(request, test_data_dir):
    """Resolve a mission definition path from a "subdir/filename" id"""
    return test_data_dir / request.param


MISSION_DEFINITIONS = [
    "ctim/ctim_xtce_v1.xml",
    "jpss/jpss1_geolocation_xtce_v1.xml",
    "suda/suda_combined_science_definition.xml",
    "idex/idex_combined_science_definition.xml",
]


@pytest.mark.parametrize("mission_definition_path", MISSION_DEFINITIONS, indirect=True)
def test_mission_definitions_parse_identically_as_xtce_1_3(mission_definition_path):
    """Every mission definition yields identical objects when expressed in XTCE 1.3"""
    definition_12 = XtcePacketDefinition.from_xtce(mission_definition_path)
    definition_13 = XtcePacketDefinition.from_xtce(_as_xtce_1_3(mission_definition_path))

    assert definition_12.xtce_standard_version == "1.2"
    assert definition_13.xtce_standard_version == "1.3"

    assert definition_13.parameter_types == definition_12.parameter_types
    assert definition_13.parameters == definition_12.parameters
    assert definition_13.containers == definition_12.containers


@pytest.mark.parametrize("mission_definition_path", MISSION_DEFINITIONS, indirect=True)
def test_mission_definitions_validate_as_xtce_1_3(mission_definition_path):
    """Every mission definition is valid against the bundled 1.3 schema once moved to 1.3

    ``allow_schema_download=False`` keeps this offline: the 1.3 schema must come from the copy
    bundled with the package.
    """
    result = validate_xtce(
        _as_xtce_1_3(mission_definition_path),
        level="schema",
        print_results=False,
        raise_on_error=False,
        allow_schema_download=False,
    )
    assert result.schema_version == "1.3"
    assert result.xtce_version == "1.3"
    assert result.valid, [str(error) for error in result.errors[:5]]


@pytest.mark.parametrize(
    ("definition_name", "packet_file_name", "root_container_name"),
    [
        ("ctim/ctim_xtce_v1.xml", "ctim/ccsds_2021_155_14_39_51", "CCSDSTelemetryPacket"),
        ("jpss/jpss1_geolocation_xtce_v1.xml", "jpss/J01_G011_LZ_2021-04-09T00-00-00Z_V01.DAT1", "CCSDSPacket"),
    ],
)
@pytest.mark.filterwarnings("ignore:Number of bits parsed")
def test_mission_packets_decode_identically_under_xtce_1_3(
    test_data_dir, definition_name, packet_file_name, root_container_name
):
    """Real packets decode to identical values under the 1.2 and 1.3 forms of a definition"""
    definition_path = test_data_dir / definition_name
    definition_12 = XtcePacketDefinition.from_xtce(definition_path)
    definition_13 = XtcePacketDefinition.from_xtce(_as_xtce_1_3(definition_path))

    with open(test_data_dir / packet_file_name, "rb") as f:
        packet_bytes = list(spp.ccsds_generator(f))

    assert packet_bytes, "expected at least one packet in the test data file"
    parsed_12 = [dict(definition_12.parse_bytes(b, root_container_name=root_container_name)) for b in packet_bytes]
    parsed_13 = [dict(definition_13.parse_bytes(b, root_container_name=root_container_name)) for b in packet_bytes]
    assert parsed_13 == parsed_12


@pytest.mark.parametrize("mission_definition_path", MISSION_DEFINITIONS, indirect=True)
def test_xtce_1_3_round_trip_is_schema_valid(mission_definition_path):
    """A definition read as 1.3 and written back out is still a valid 1.3 document

    Serialization names the 1.3 XSD in ``xsi:schemaLocation``, so the written document validates
    without the reader having to supply a schema.
    """
    definition = XtcePacketDefinition.from_xtce(_as_xtce_1_3(mission_definition_path))
    serialized = io.BytesIO()
    definition.to_xml_tree().write(serialized, xml_declaration=True, encoding="utf-8")
    serialized.seek(0)

    result = validate_xtce(
        serialized,
        level="schema",
        print_results=False,
        raise_on_error=False,
        allow_schema_download=False,
    )
    assert result.schema_location == xtce.XTCE_1_3_XSD_URL
    assert result.valid, [str(error) for error in result.errors[:5]]
