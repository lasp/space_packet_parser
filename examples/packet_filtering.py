"""Example of filtering packets based on their APID

This example demonstrates how to filter packets based on their APID at the generator level.
It's common during ground testing that CCSDS packets are in multiplexed streams where multiple APIDs
are present in the same stream. This example shows how to filter out unwanted APIDs so that
only packets with desired APIDs are parsed and yielded by the generator. This can save a lot of
processing time by preventing unwanted packets from being parsed (and possibly failing to parse)
by the XTCE packet parser.
"""

from pathlib import Path

from space_packet_parser.generators import ccsds
from space_packet_parser.xarr import create_dataset
from space_packet_parser.xtce.definitions import XtcePacketDefinition

if __name__ == "__main__":
    script_dir = Path(__file__).parent.resolve()
    packet_file = script_dir / "../tests/test_data/ctim/ccsds_2021_155_14_39_51"
    packet_definition_file = script_dir / "../tests/test_data/ctim/ctim_xtce_v1.xml"
    packet_definition = XtcePacketDefinition.from_xtce(packet_definition_file)
    apid_of_interest = 41  # The APID we care about

    # Direct generator access patterns
    with packet_file.open("rb") as binary_data:
        # Using list comprehension
        ccsds_generator = ccsds.ccsds_generator(binary_data)
        list_comp_packets = [pkt for pkt in ccsds_generator if pkt.apid == apid_of_interest]
        print(f"Found {len(list_comp_packets)} packets with APID {apid_of_interest}")

        # Using a python filter function
        binary_data.seek(0)
        ccsds_generator = ccsds.ccsds_generator(binary_data)
        filtered_packets = filter(lambda pkt: pkt.apid == apid_of_interest, ccsds_generator)
        print(f"Found {len(list(filtered_packets))} packets with APID {apid_of_interest}")

        # Using a for loop
        binary_data.seek(0)
        ccsds_generator = ccsds.ccsds_generator(binary_data)
        pkt_count = 0
        for packet_bytes in ccsds_generator:
            if packet_bytes.apid == apid_of_interest:
                pkt_count += 1
        print(f"Found {pkt_count} packets with APID {apid_of_interest}")

    # Passing a filter to create_dataset
    ds = create_dataset(
        packet_files=[packet_file],
        xtce_packet_definition=packet_definition,
        parse_bytes_kwargs=dict(root_container_name="CCSDSTelemetryPacket"),
        packet_filter=lambda pkt: pkt.apid == apid_of_interest,
    )

    print(ds)
