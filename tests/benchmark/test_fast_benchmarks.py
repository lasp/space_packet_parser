"""Fast benchmarks"""

import pytest

import space_packet_parser as spp
from space_packet_parser.xtce import encodings


@pytest.mark.benchmark
def test_benchmark__read_as_int__aligned(benchmark):
    """Benchmark performance of reading byte-aligned ints from a bytes object

    This test essentially makes a packet with a long user data section of alternating ones and zeros
    """
    rounds = 3
    warmup_rounds = 1
    test_byte = b"\x55" * 2  # 01 01 01 01
    n_iterations = 1000
    nbits = 16
    expected_value = int.from_bytes(test_byte, "big")  # 85
    n_test_byte_repeats = ((rounds + warmup_rounds) * n_iterations * nbits // 8) + 1
    raw_packet = spp.SpacePacket(binary_data=test_byte * n_test_byte_repeats)

    value = benchmark.pedantic(
        raw_packet._read_from_binary_as_int,
        args=(nbits,),
        rounds=rounds,
        iterations=n_iterations,
        warmup_rounds=warmup_rounds,
    )

    assert value == expected_value


@pytest.mark.benchmark
def test_benchmark__read_as_int__non_aligned(benchmark):
    """Benchmark performance of reading non-byte-aligned ints from a bytes object

    This test essentially makes a packet with a long user data section of alternating ones and zeros
    """
    rounds = 3
    warmup_rounds = 1
    test_byte = b"\x55" * 3  # 01 01 01 01
    n_iterations = 1000
    nbits = 18
    n_test_byte_repeats = ((rounds + warmup_rounds) * n_iterations * nbits // 8) + 1
    test_data = test_byte * n_test_byte_repeats
    expected_value = 87381  # 01010101 01010101 01

    raw_packet = spp.SpacePacket(binary_data=test_data)

    value = benchmark.pedantic(
        raw_packet._read_from_binary_as_int,
        args=(nbits,),
        rounds=rounds,
        iterations=n_iterations,
        warmup_rounds=warmup_rounds,
    )

    assert value == expected_value


@pytest.mark.benchmark
def test_benchmark__read_as_bytes__aligned(benchmark):
    """Benchmark performance of reading full, aligned, bytes from a bytes object

    This test essentially makes a packet with a long user data section of alternating ones and zeros
    """
    rounds = 3
    warmup_rounds = 1
    test_byte = b"\x55" * 2  # 01 01 01 01
    n_iterations = 1000
    nbits = 16
    expected_value = b"\x55\x55"  # 01010101 01010101
    n_test_byte_repeats = ((rounds + warmup_rounds) * n_iterations * nbits // 8) + 1
    raw_packet = spp.SpacePacket(binary_data=test_byte * n_test_byte_repeats)

    value = benchmark.pedantic(
        raw_packet._read_from_binary_as_bytes,
        args=(nbits,),
        rounds=rounds,
        iterations=n_iterations,
        warmup_rounds=warmup_rounds,
    )

    assert value == expected_value


@pytest.mark.benchmark
def test_benchmark__read_as_bytes__non_aligned_full_bytes(benchmark):
    """Benchmark performance of reading full bytes, not-byte-aligned (offset by 1 bit), from a bytes object

    This test essentially makes a packet with a long user data section of alternating ones and zeros
    """
    rounds = 3
    warmup_rounds = 1
    test_byte = b"\x55" * 2  # 01 01 01 01
    n_iterations = 1000
    nbits = 16
    expected_value = b"\xaa\xaa"  # 10101010 10101010
    n_test_byte_repeats = ((rounds + warmup_rounds) * n_iterations * nbits // 8) + 1
    raw_packet = spp.SpacePacket(binary_data=test_byte * n_test_byte_repeats)
    raw_packet._parsing_pos += 1  # Move cursor to non-aligned position

    value = benchmark.pedantic(
        raw_packet._read_from_binary_as_bytes,
        args=(nbits,),
        rounds=rounds,
        iterations=n_iterations,
        warmup_rounds=warmup_rounds,
    )

    assert value == expected_value


@pytest.mark.benchmark
def test_benchmark__read_as_bytes__partial_bytes(benchmark):
    """Benchmark performance of reading partial bytes from a bytes object, resulting
    in padded values.

    This test essentially makes a packet with a long user data section of alternating ones and zeros
    """
    rounds = 3
    warmup_rounds = 1
    test_byte = b"\x55"  # 01 01 01 01
    n_iterations = 1000
    nbits = 6
    expected_value = b"\x15"  # 00 01 01 01 (MSB padded with 2 bits)
    n_test_byte_repeats = ((rounds + warmup_rounds) * n_iterations * nbits // 8) + 1
    raw_packet = spp.SpacePacket(binary_data=test_byte * n_test_byte_repeats)

    value = benchmark.pedantic(
        raw_packet._read_from_binary_as_bytes,
        args=(nbits,),
        rounds=rounds,
        iterations=n_iterations,
        warmup_rounds=warmup_rounds,
    )

    assert value == expected_value


@pytest.mark.benchmark
def test_benchmark__terminated_string_parsing(benchmark):
    """Benchmark parsing a null-terminated string, which scans the buffer for its terminator

    Finding the terminator is the one part of string parsing whose cost grows with string length, and
    it runs on the XTCE 1.2 path as well as the 1.3 one. It is benchmarked here so that a change to
    the search (for example, replacing the C-level `bytes.find` with a Python loop) shows up as a
    measured regression rather than being noticed in review.
    """
    rounds = 3
    warmup_rounds = 1
    n_iterations = 100
    # A few hundred bytes of content, so the scan does real work.
    content = b"A" * 512
    raw_string_buffer = content + b"\x00"
    encoding = encodings.StringDataEncoding(
        encoding="UTF-8",
        termination_character="00",
        fixed_raw_length=len(raw_string_buffer) * 8,
    )

    def _parse_once():
        """Parse from a fresh packet, since parsing advances the cursor past the string"""
        return encoding.parse_value(spp.SpacePacket(binary_data=raw_string_buffer))

    value = benchmark.pedantic(
        _parse_once,
        rounds=rounds,
        iterations=n_iterations,
        warmup_rounds=warmup_rounds,
    )

    assert value == content.decode("UTF-8")
