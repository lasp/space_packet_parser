"""Benchmarking test suite for Space Packet Parser

Each test in this suite tests a specific metric over time
"""

import pytest

from space_packet_parser import generators
from space_packet_parser.xtce import definitions

COMPLEX_XTCE_DEFINITION_PARSING_THRESHOLDS_SECONDS = {"default": 0.0184}


@pytest.mark.benchmark(warmup=True)
def test_benchmark_complex_xtce_definition_parsing(benchmark, suda_test_data_dir, assert_within_threshold):
    """Benchmark the time it takes to parse a specific, relatively complex XTCE packet definition document"""
    definition: definitions.XtcePacketDefinition = benchmark(
        definitions.XtcePacketDefinition.from_xtce, suda_test_data_dir / "suda_combined_science_definition.xml"
    )
    assert len(definition.parameters) == 207
    assert len(definition.parameter_types) == 207
    assert len(definition.containers) == 9
    assert_within_threshold(COMPLEX_XTCE_DEFINITION_PARSING_THRESHOLDS_SECONDS)


# This test's normalized mean depends on the runner hardware class more than the others do,
# so its margin is wider.
SIMPLE_PACKET_PARSING_THRESHOLDS_SECONDS = {"default": 0.8}


@pytest.mark.benchmark
def test_benchmark_simple_packet_parsing(benchmark, jpss_test_data_dir, assert_within_threshold):
    """Benchmark the time it takes to parse 7200 simple JPSS geolocation packets from a flat packet definition"""
    packet_definition = definitions.XtcePacketDefinition.from_xtce(jpss_test_data_dir / "jpss1_geolocation_xtce_v1.xml")
    packet_data = jpss_test_data_dir / "J01_G011_LZ_2021-04-09T00-00-00Z_V01.DAT1"

    # Open reusable filehandler
    packet_fh = packet_data.open("rb")

    try:

        def _parse_all_packets():
            """Re-seek and re-create the generator each call, so this is safe to call repeatedly"""
            packet_fh.seek(0)
            ccsds_generator = generators.ccsds_generator(packet_fh)
            return [packet_definition.parse_bytes(binary_data) for binary_data in ccsds_generator]

        packet_list: list = benchmark(_parse_all_packets)

        # Make sure the result actually makes sense
        assert len(packet_list) == 7200
        assert_within_threshold(SIMPLE_PACKET_PARSING_THRESHOLDS_SECONDS)
    finally:
        # Ensure filehandler is closed
        packet_fh.close()


COMPLEX_PACKET_PARSING_THRESHOLDS_SECONDS = {"default": 0.0104}


@pytest.mark.benchmark
def test_benchmark_complex_packet_parsing(benchmark, idex_test_data_dir, assert_within_threshold):
    """Benchmark the time it takes to parse IDEX packets, which have a polymorphic structure"""
    packet_definition = definitions.XtcePacketDefinition.from_xtce(
        idex_test_data_dir / "idex_combined_science_definition.xml"
    )
    packet_data = idex_test_data_dir / "sciData_2023_052_14_45_05"

    # Open reusable filehandler
    packet_fh = packet_data.open("rb")

    try:

        def _parse_all_packets():
            """Re-seek and re-create the generator each call, so this is safe to call repeatedly"""
            packet_fh.seek(0)
            ccsds_generator = generators.ccsds_generator(packet_fh, show_progress=True)
            return [packet_definition.parse_bytes(binary_data) for binary_data in ccsds_generator]

        packet_list: list = benchmark(_parse_all_packets)

        # Make sure the result actually makes sense
        assert len(packet_list) == 78
        assert_within_threshold(COMPLEX_PACKET_PARSING_THRESHOLDS_SECONDS)
    finally:
        # Ensure filehandler is closed
        packet_fh.close()
