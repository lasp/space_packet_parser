"""Benchmark test for how fast we can parse a large XTCE definition file"""

import pytest

from space_packet_parser.xtce import definitions

CTIM_XTCE_PARSING_THRESHOLDS_SECONDS = {"default": 0.113}


@pytest.mark.benchmark
def test_benchmark_ctim_xtce_parsing(ctim_test_data_dir, benchmark, assert_within_threshold):
    """Parse a large XTCE document that at one point took several seconds to load.

    The regression gate threshold keeps that from coming back.
    """
    xtce_document = ctim_test_data_dir / "ctim_xtce_v1.xml"
    packet_definition = benchmark(definitions.XtcePacketDefinition.from_xtce, xtce_document)
    print("Number of containers:", len(packet_definition.containers))
    print("Number of parameters:", len(packet_definition.parameters))
    print("Number of parameter types:", len(packet_definition.parameter_types))
    assert_within_threshold(CTIM_XTCE_PARSING_THRESHOLDS_SECONDS)
