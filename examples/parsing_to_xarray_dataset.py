"""Example of parsing CCSDS packets directly to Xarray Datasets

This example demonstrates how to use the create_dataset function to parse binary
packet data directly into Xarray Datasets. This is useful for analysis and visualization
workflows where you want to work with timeseries telemetry data in a structured format.

The create_dataset function returns a dictionary of Datasets keyed by APID, where each
Dataset contains all parameters from packets with that APID organized as data variables
with a 'packet' dimension.

This example also shows how to filter packets by APID when working with multiplexed
packet streams containing multiple APIDs.
"""

from pathlib import Path

from space_packet_parser.xarr import create_dataset
from space_packet_parser.xtce.definitions import XtcePacketDefinition

if __name__ == "__main__":
    # Get paths to test data relative to this script
    script_dir = Path(__file__).parent.resolve()
    packet_file = script_dir / "../tests/test_data/ctim/ccsds_2021_155_14_39_51"
    packet_definition_file = script_dir / "../tests/test_data/ctim/ctim_xtce_v1.xml"

    # Load the XTCE packet definition
    packet_definition = XtcePacketDefinition.from_xtce(packet_definition_file)

    print("=" * 80)
    print("Example 1: Parse all packets to Datasets")
    print("=" * 80)

    # Parse all packets in the file to Xarray Datasets
    # Returns a dictionary with one Dataset per APID
    datasets = create_dataset(
        packet_files=[packet_file],
        xtce_packet_definition=packet_definition,
        parse_bytes_kwargs={"root_container_name": "CCSDSTelemetryPacket"},
    )

    print(f"\nFound {len(datasets)} unique APIDs in the packet file:")
    for apid, dataset in datasets.items():
        num_packets = dataset.sizes["packet"]
        num_variables = len(dataset.data_vars)
        print(f"  APID {apid}: {num_packets} packets, {num_variables} variables")

    # Examine data from APID 41 (the most common APID in this file)
    if 41 in datasets:
        print(f"\nDataset for APID 41:")
        print(datasets[41])

        print(f"\nVariable names in APID 41:")
        print(list(datasets[41].data_vars.keys()))

        print(f"\nFirst 5 values of 'PKT_APID' variable:")
        print(datasets[41]["PKT_APID"].values[:5])

    print("\n" + "=" * 80)
    print("Example 2: Filter packets by APID")
    print("=" * 80)

    # Often you only care about packets from a specific APID
    # You can filter at the generator level for better performance
    apid_of_interest = 41

    filtered_datasets = create_dataset(
        packet_files=[packet_file],
        xtce_packet_definition=packet_definition,
        parse_bytes_kwargs={"root_container_name": "CCSDSTelemetryPacket"},
        packet_filter=lambda pkt: pkt.apid == apid_of_interest,
    )

    print(f"\nFiltered to only APID {apid_of_interest}")
    print(f"Found {len(filtered_datasets)} APID(s) after filtering")
    print(f"Number of packets: {filtered_datasets[apid_of_interest].sizes['packet']}")

    print("\n" + "=" * 80)
    print("Example 3: Working with Dataset data")
    print("=" * 80)

    # Xarray Datasets provide rich functionality for working with labeled arrays
    if 41 in datasets:
        ds = datasets[41]

        # Access data as numpy arrays
        print(f"\nPacket sequence counter values (first 10):")
        print(ds["SEQ_CTR"].values[:10])

        # Use Xarray's selection and computation features
        print(f"\nSummary statistics for SEQ_CTR:")
        print(f"  Min: {ds['SEQ_CTR'].min().values}")
        print(f"  Max: {ds['SEQ_CTR'].max().values}")
        print(f"  Mean: {ds['SEQ_CTR'].mean().values:.2f}")

        # Datasets can be easily saved to disk in various formats
        # ds.to_netcdf('apid_41_data.nc')  # NetCDF format
        # ds.to_zarr('apid_41_data.zarr')  # Zarr format
        print("\nDatasets can be saved using ds.to_netcdf() or ds.to_zarr()")
