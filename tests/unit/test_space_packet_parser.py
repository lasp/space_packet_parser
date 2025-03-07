"""Tests for main space_packet_parser.__init__ module"""
import space_packet_parser
from space_packet_parser.xtce import definitions


def test_load_xtce(jpss_test_data_dir, tmp_path):
    """Test high level function for loading an XTCE definition file"""
    xtcedef = space_packet_parser.load_xtce(jpss_test_data_dir / "jpss1_geolocation_xtce_v1.xml")
    assert isinstance(xtcedef, definitions.XtcePacketDefinition)

    outpath = tmp_path / "test_output.xml"
    xtcedef.write_xml(outpath)
    assert outpath.exists()

    assert space_packet_parser.load_xtce(outpath) == xtcedef
