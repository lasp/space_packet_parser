"""Integration test for parsing JPSS packets"""
import space_packet_parser as spp
from space_packet_parser.xtce import definitions


def test_jpss_xtce_packet_parsing(jpss_test_data_dir):
    """Test parsing a real XTCE document"""
    jpss_xtce = jpss_test_data_dir / 'jpss1_geolocation_xtce_v1.xml'
    jpss_definition = definitions.XtcePacketDefinition.from_xtce(xtce_document=jpss_xtce)
    assert isinstance(jpss_definition, definitions.XtcePacketDefinition)
    assert jpss_definition.parameters['USEC'].short_description == "Secondary Header Fine Time (microsecond)"
    assert jpss_definition.parameters['USEC'].long_description == "CCSDS Packet 2nd Header Fine Time in microseconds."

    jpss_packet_file = jpss_test_data_dir / 'J01_G011_LZ_2021-04-09T00-00-00Z_V01.DAT1'

    with jpss_packet_file.open('rb') as binary_data:
        jpss_packet_generator = jpss_definition.packet_generator(binary_data, show_progress=True)

        n_packets = 0
        for jpss_packet in jpss_packet_generator:
            assert isinstance(jpss_packet, spp.Packet)
            assert jpss_packet['PKT_APID'] == 11
            assert jpss_packet['VERSION'] == 0
            n_packets += 1
        assert n_packets == 7200
