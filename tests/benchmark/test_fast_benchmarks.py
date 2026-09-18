"""Fast benchmarks"""

import pytest

import space_packet_parser as spp

# These use `benchmark.pedantic` with a fixed round count rather than auto-calibrated
# rounds because the packet's read cursor advances on every call, so the input has to be
# sized for a known call count up front.

READ_AS_INT_ALIGNED_THRESHOLDS_SECONDS = {"default": 1.19e-06}


@pytest.mark.benchmark
def test_benchmark__read_as_int__aligned(benchmark, assert_within_threshold):
    """Benchmark performance of reading byte-aligned ints from a bytes object

    This test essentially makes a packet with a long user data section of alternating ones and zeros
    """
    rounds = 1000
    warmup_rounds = 5
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
    assert_within_threshold(READ_AS_INT_ALIGNED_THRESHOLDS_SECONDS)


READ_AS_INT_NON_ALIGNED_THRESHOLDS_SECONDS = {"default": 1.48e-06}


@pytest.mark.benchmark
def test_benchmark__read_as_int__non_aligned(benchmark, assert_within_threshold):
    """Benchmark performance of reading non-byte-aligned ints from a bytes object

    This test essentially makes a packet with a long user data section of alternating ones and zeros
    """
    rounds = 1000
    warmup_rounds = 5
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
    assert_within_threshold(READ_AS_INT_NON_ALIGNED_THRESHOLDS_SECONDS)


READ_AS_BYTES_ALIGNED_THRESHOLDS_SECONDS = {"default": 8.82e-07}


@pytest.mark.benchmark
def test_benchmark__read_as_bytes__aligned(benchmark, assert_within_threshold):
    """Benchmark performance of reading full, aligned, bytes from a bytes object

    This test essentially makes a packet with a long user data section of alternating ones and zeros
    """
    rounds = 1000
    warmup_rounds = 5
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
    assert_within_threshold(READ_AS_BYTES_ALIGNED_THRESHOLDS_SECONDS)


READ_AS_BYTES_NON_ALIGNED_FULL_BYTES_THRESHOLDS_SECONDS = {"default": 1.62e-06}


@pytest.mark.benchmark
def test_benchmark__read_as_bytes__non_aligned_full_bytes(benchmark, assert_within_threshold):
    """Benchmark performance of reading full bytes, not-byte-aligned (offset by 1 bit), from a bytes object

    This test essentially makes a packet with a long user data section of alternating ones and zeros
    """
    rounds = 1000
    warmup_rounds = 5
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
    assert_within_threshold(READ_AS_BYTES_NON_ALIGNED_FULL_BYTES_THRESHOLDS_SECONDS)


READ_AS_BYTES_PARTIAL_BYTES_THRESHOLDS_SECONDS = {"default": 1.59e-06}


@pytest.mark.benchmark
def test_benchmark__read_as_bytes__partial_bytes(benchmark, assert_within_threshold):
    """Benchmark performance of reading partial bytes from a bytes object, resulting
    in padded values.

    This test essentially makes a packet with a long user data section of alternating ones and zeros
    """
    rounds = 1000
    warmup_rounds = 5
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
    assert_within_threshold(READ_AS_BYTES_PARTIAL_BYTES_THRESHOLDS_SECONDS)
