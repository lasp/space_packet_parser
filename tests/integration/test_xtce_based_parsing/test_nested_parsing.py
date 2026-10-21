"""Test parsing a packet definition whose packet types live in nested SpaceSystems"""

import struct

import space_packet_parser as spp
from space_packet_parser.generators.ccsds import create_ccsds_packet
from space_packet_parser.xtce import definitions


def test_nested_spacesystem_packet_parsing(nested_test_data_dir):
    """Test parsing one packet of each child SpaceSystem from a single definition"""
    nested_xtce = nested_test_data_dir / "nested_spacesystems.xml"
    nested_definition = definitions.XtcePacketDefinition.from_xtce(xtce_document=nested_xtce)
    assert isinstance(nested_definition, definitions.XtcePacketDefinition)

    # APID 10 (SENSOR_A): a local type and a root type, referred to by absolute path
    packet_a = nested_definition.parse_bytes(create_ccsds_packet(data=struct.pack(">BH", 200, 1234), apid=10))
    assert isinstance(packet_a, spp.SpacePacket)
    assert packet_a["PKT_APID"].raw_value == 10
    assert packet_a["READING_SMALL"].raw_value == 200
    assert packet_a["READING_WIDE"].raw_value == 1234

    # APID 11 (SENSOR_B): VALUE_Type is signed 16 bit here, not the 8 bit VALUE_Type of SENSOR_A
    packet_b = nested_definition.parse_bytes(create_ccsds_packet(data=struct.pack("<hB", -300, 7), apid=11))
    assert isinstance(packet_b, spp.SpacePacket)
    assert packet_b["PKT_APID"].raw_value == 11
    assert packet_b["READING_SIGNED"].raw_value == -300
    assert packet_b["FLAGS"].raw_value == 7

    # APID 12 (DIAGNOSTICS): a grandchild that takes VALUE_Type of its parent by relative path
    packet_diagnostics = nested_definition.parse_bytes(create_ccsds_packet(data=struct.pack("<Bh", 3, -1234), apid=12))
    assert isinstance(packet_diagnostics, spp.SpacePacket)
    assert packet_diagnostics["PKT_APID"].raw_value == 12
    assert packet_diagnostics["STATUS"].raw_value == 3
    assert packet_diagnostics["OFFSET"].raw_value == -1234
