"""Test parsing of CTIM instrument data"""

import pytest

from space_packet_parser import generators
from space_packet_parser.xtce import definitions


@pytest.mark.filterwarnings("ignore:Number of bits parsed")
def test_ctim_parsing(ctim_test_data_dir):
    """Test parsing CTIM data"""
    print("Loading and parsing packet definition")
    test_xtce = ctim_test_data_dir / "ctim_xtce_v1.xml"
    pkt_def = definitions.XtcePacketDefinition.from_xtce(test_xtce)
    print("Done")

    print("Loading and parsing data")
    test_packet_file = ctim_test_data_dir / "ccsds_2021_155_14_39_51"
    with open(test_packet_file, "rb") as pkt_file:
        ccsds_gen = generators.ccsds_generator(pkt_file, show_progress=True)
        packets = [
            pkt_def.parse_bytes(binary_data, root_container_name="CCSDSTelemetryPacket") for binary_data in ccsds_gen
        ]

    assert len(packets) == 1499
    assert packets[159]["PKT_APID"].raw_value == 34
    assert packets[159]["SHCOARSE"].raw_value == 481168702
    apids = {p["PKT_APID"].raw_value for p in packets}
    print(apids)
