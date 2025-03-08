"""Tests for main space_packet_parser.__init__ module"""
import space_packet_parser as spp
from space_packet_parser.xtce import definitions


def test_load_xtce(jpss_test_data_dir, tmp_path):
    """Test high level function for loading an XTCE definition file"""
    xtcedef = spp.load_xtce(jpss_test_data_dir / "jpss1_geolocation_xtce_v1.xml")
    assert isinstance(xtcedef, definitions.XtcePacketDefinition)

    outpath = tmp_path / "test_output.xml"
    xtcedef.write_xml(outpath)
    assert outpath.exists()

    assert spp.load_xtce(outpath) == xtcedef


def test_create_packet_list(jpss_test_data_dir):
    """Test directly creating a list of Packets from a data file and a definition"""
    jpss_packets = jpss_test_data_dir / "J01_G011_LZ_2021-04-09T00-00-00Z_V01.DAT1"
    jpss_xtce = jpss_test_data_dir / "jpss1_geolocation_xtce_v1.xml"

    # Single file
    packet_list = spp.create_packet_list(jpss_packets, jpss_xtce)
    assert len(packet_list) == 7200
    assert packet_list[0]["PKT_APID"] == 11
    assert packet_list[-1]["PKT_APID"] == 11

    # Multiple files
    packet_list = spp.create_packet_list([jpss_packets, jpss_packets], jpss_xtce)
    assert len(packet_list) == 14400
    assert packet_list[0]["PKT_APID"] == 11
    assert packet_list[-1]["PKT_APID"] == 11
