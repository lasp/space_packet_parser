"""Shared plumbing for the benchmark regression gate.

Each benchmark asserts its mean run time against a threshold dict declared next to the
test, through the `assert_within_threshold` fixture. Thresholds are in seconds on a
"nominal" machine and are scaled by `machine_speed_factor`, which times a fixed pure-Python
workload immediately before each benchmark: CI runners for the same job differ in speed
from run to run, the difference is common to every benchmark in the job, and dividing by
it removes most of the run-to-run swing in the means.

The check is enforced only when the SPP_BENCHMARK_GATE environment variable is set, which
the CI gate step does on ubuntu-latest, where the thresholds are calibrated (see
docs/source/developers.md#benchmarks). Otherwise the benchmarks just run and report.
"""

import os
import statistics
import sys
import time

import pytest

# A nominal machine runs `_reference_workload` in exactly this many seconds; the value is a
# round number close to an ubuntu-latest runner at first calibration. Changing it, or the
# workload, rescales every threshold.
NOMINAL_REFERENCE_SECONDS = 0.020
_REFERENCE_REPETITIONS = 11  # the median of these is used, so one GC pause can't skew the factor


class _Field:
    """Small attribute-bearing object, stands in for the parameter/type objects parsing builds."""

    __slots__ = ("name", "value", "width")

    def __init__(self, name, value, width):
        self.name = name
        self.value = value
        self.width = width


def _reference_workload() -> int:
    """Fixed, deterministic, pure-Python work resembling packet parsing.

    Bytes slicing and int conversion, dict lookups keyed by formatted strings, and small
    object creation; no I/O and no C-extension hot loops.
    """
    data = bytes(range(256)) * 256  # 64 KiB
    lookup = {f"param_{i}": i * 7919 % 1009 for i in range(512)}
    total = 0
    fields = []
    pos = 0
    limit = len(data) - 4
    while pos < limit:
        width = (data[pos] & 0x0F) + 1
        raw = int.from_bytes(data[pos : pos + 4], "big") >> (32 - width)
        name = f"param_{raw & 0x1FF}"
        field = _Field(name, raw + lookup[name], width)
        total += field.value
        fields.append(field)
        pos += 3
    total += sum(f.width for f in fields if f.name.endswith("7"))
    return total


@pytest.fixture
def machine_speed_factor(benchmark) -> float:
    """How much slower this machine is right now than the nominal one (1.0 == nominal).

    Recorded in the benchmark's `extra_info` so it appears in `--benchmark-json` output.
    """
    if not benchmark.enabled:  # --benchmark-disable: nothing is timed
        return 1.0
    samples = []
    for _ in range(_REFERENCE_REPETITIONS):
        start = time.perf_counter()
        _reference_workload()
        samples.append(time.perf_counter() - start)
    factor = statistics.median(samples) / NOMINAL_REFERENCE_SECONDS
    benchmark.extra_info["speed_factor"] = factor
    return factor


@pytest.fixture
def assert_within_threshold(benchmark, machine_speed_factor):
    """Callable that fails the test if the benchmark's mean exceeds its scaled threshold.

    `thresholds` maps a Python "major.minor" string to nominal-machine seconds, with a
    required "default" entry. No-op unless SPP_BENCHMARK_GATE is set and benchmarks are enabled.
    """

    def _check(thresholds: dict) -> None:
        if not benchmark.enabled or not os.environ.get("SPP_BENCHMARK_GATE"):
            return
        key = f"{sys.version_info.major}.{sys.version_info.minor}"
        nominal_limit = thresholds.get(key, thresholds["default"])
        limit = nominal_limit * machine_speed_factor
        mean = benchmark.stats.stats.mean
        assert mean <= limit, (
            f"{benchmark.name} mean of {mean:.6f}s exceeded {limit:.6f}s "
            f"(threshold {nominal_limit:.6f}s for Python {key} x machine speed factor {machine_speed_factor:.3f}; "
            f"normalized mean {mean / machine_speed_factor:.6f}s). "
            "See tests/benchmark/conftest.py and docs/source/developers.md#benchmarks."
        )

    return _check
