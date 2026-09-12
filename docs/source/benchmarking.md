# Benchmarking Performance

Benchmarking packet parsing is challenging because performance is greatly impacted by the
complexity of the packet structures being parsed. There are a few measures by which we can assess
the performance of Space Packet Parser.

```{note}
Throughout the Space Packet Parser repo and documentation space, B/kB means bytes/kilobytes and
b/kb means bits/kilobits.
```

The dominant cost is **dynamic evaluation** — work the parser can only do by inspecting the data
it is currently parsing. Common sources:

- Calibrators and context calibrators
- Enumerated lookups
- Dynamically sized fields (variable length strings, binary blobs sized by another parameter, or
  fields that consume the remaining packet length)
- Polymorphic packet structures, where which container applies is decided by values inside the
  packet
- Deep container inheritance, since each level adds a `RestrictionCriteria` evaluation per packet

Secondary factors:

- Number of fields in a packet (a better predictor of cost than packet size, but not a law — see
  below)
- Presence of large binary blobs (=high kbps, faster parsing, because many bytes are extracted in
  one operation)

For practical advice on making your own parsing faster, see
[Optimizing for Performance](user_guide/performance.md).

## Running the Benchmarks

The benchmark suite lives in `tests/benchmark/` and runs under
[pytest-benchmark](https://pytest-benchmark.readthedocs.io/):

```bash
pytest tests/benchmark/
```

All numbers on this page were measured inside the project devcontainer (Linux, `aarch64`, 6 CPUs
allocated) running on an Apple Silicon M3 Max. Absolute timings will differ on your hardware; the
_relative_ results are the durable part, and those have been stable across machines.

## Full Packet Parsing Performance

### Packets Per Second

This is a metric we are often asked about. Unfortunately, the answer is that it depends on which
packets are being parsed: how many fields are in each packet and how much extra work the parser is
doing to sort out complex packet structures and evaluate calibrators.

### Kilobits Per Second

This metric is often used when discussing data volumes and downlink bandwidths to make sure that a
data processing system can keep up with the data rate from a spacecraft in the time allowed for
processing. This number is also affected by packet structures. It will be high for simple packets
containing large binary blobs and low for complex packets containing many small fields.

### Results

Two datasets are benchmarked, chosen to sit at opposite ends of the complexity spectrum:

| Dataset               | Packets | Total size | Per packet | Structure                                                    |
| --------------------- | ------: | ---------: | ---------: | ------------------------------------------------------------ |
| JPSS-1 geolocation    |    7200 |     511 kB |       71 B | Flat definition, 32-bit floats and integers of various sizes |
| IDEX combined science |      78 |     220 kB |     2825 B | Polymorphic container structure, large binary science blobs  |

Measured throughput:

| Dataset               |   Mean | pkts/s |    kb/s |
| --------------------- | -----: | -----: | ------: |
| JPSS-1 geolocation    | 252 ms | 28,610 |  16,250 |
| IDEX combined science | 2.8 ms | 27,438 | 620,076 |

Across the full spread of rounds, JPSS-1 ranges 21,689–33,051 pkts/s (12,320–18,773 kb/s) and IDEX
ranges 24,548–28,687 pkts/s (554,778–648,309 kb/s).

```
---------------------------------------------------------------------------------------------- benchmark: 2 tests ----------------------------------------------------------------------------------------------
Name (time in ms)                              Min                 Max                Mean             StdDev              Median                IQR            Outliers       OPS            Rounds  Iterations
----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
test_benchmark_complex_packet_parsing       2.7190 (1.0)        3.1774 (1.0)        2.8428 (1.0)       0.1308 (1.0)        2.8005 (1.0)       0.1489 (1.0)           2;2  351.7653 (1.0)          20           1
test_benchmark_simple_packet_parsing      217.8480 (80.12)    331.9612 (104.48)   251.6601 (88.53)    27.3484 (209.07)   250.6220 (89.49)    34.9758 (234.83)        4;1    3.9736 (0.01)         20           1
----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
```

### Why the Two Metrics Diverge

The two datasets above parse at **roughly the same packets per second** (~28k) but differ by a
factor of **38x in kilobits per second**, despite IDEX packets being 40x larger. Bytes per second is
therefore a poor description of what the parser is actually doing.

Adding a third, much more expensive dataset makes the pattern clearer. CTIM APID 41 packets are
_smaller_ than IDEX packets but take **31x longer** to parse:

| Dataset            | B/packet | Fields/packet | us/packet | us/field |
| ------------------ | -------: | ------------: | --------: | -------: |
| JPSS-1 geolocation |       71 |            27 |        35 |     1.29 |
| IDEX science       |     2825 |           107 |        36 |     0.34 |
| CTIM APID 41       |     1018 |          1003 |      1133 |     1.13 |

Packet size predicts almost nothing: JPSS-1 and IDEX differ 40x in bytes and parse in the same
time. Field count is a much better predictor, but it is not a law either — per-field cost still
varies about 4x across these three datasets.

What actually drives the remaining variation is **how much dynamic evaluation each field requires**.
A field with a static encoding and no calibrator is cheap. A field whose length depends on another
parameter's value, whose raw value must be run through a calibrator or an enumerated lookup, or
whose very presence depends on which container matched, is expensive — and the parser cannot know
any of that until it is looking at the data. IDEX gets its low per-field cost because most of its
bytes sit in one large binary blob extracted in a single operation; CTIM pays full price on all
1003 of its fields.

So when sizing a processing system:

- Benchmark **your own XTCE definition against your own packets**. Numbers quoted for someone
  else's packet structure will not transfer.
- Use **packets per second**, not kb/s, unless you also state the packet structure it came from. A
  kb/s figure derived from blob-heavy packets will badly overestimate throughput on field-dense
  ones, and vice versa.
- See [Optimizing for Performance](user_guide/performance.md) for concrete ways to reduce this
  cost.

## Filtering Muxed Packet Streams

Ground testing commonly produces multiplexed streams containing many APIDs. If you hand every
packet in such a stream to `parse_bytes()`, the parser will attempt to parse each one against the
XTCE definition — including the packets you do not want, which may also fail to parse or emit
warnings. Filtering on the CCSDS header first lets the parser skip those bytes entirely.

The difference is not marginal. Reading a packet's header and deciding whether to keep it costs
about **0.45 us**; parsing that packet against the XTCE definition costs about **989 us** — roughly
a **2000x** difference per packet.

Benchmarked against the CTIM muxed test stream (1499 packets across 9 APIDs, 1.3 MB):

| Approach                           | Packets parsed | Median time | Speedup |
| ---------------------------------- | -------------: | ----------: | ------: |
| No filter (parse everything)       |           1499 |     1483 ms |      1x |
| Filter to APID 41 (1147 of 1499)   |           1147 |     1300 ms |    1.1x |
| Filter to APID 20 (6 of 1499)      |              6 |      1.0 ms |   1447x |
| Header read and filter, no parsing |              0 |      0.7 ms |   2188x |

The saving is proportional to the fraction of the stream you can discard. APID 41 is 77% of this
particular stream, so filtering to it saves little. APID 20 is 0.4% of it, and filtering to it is
three orders of magnitude faster than parsing the whole stream.

Filter at the generator, before `parse_bytes()` is called:

```python
import space_packet_parser as spp

definition = spp.load_xtce("ctim_xtce_v1.xml")

with open("muxed_stream.bin", "rb") as binary_data:
    for packet_bytes in spp.ccsds_generator(binary_data):
        if packet_bytes.apid != 41:
            continue  # Skipped without ever touching the XTCE definition
        packet = definition.parse_bytes(packet_bytes)
```

{py:func}`~space_packet_parser.xarr.create_dataset` takes a `packet_filter` callable that does the
same thing:

```python
from space_packet_parser.xarr import create_dataset

datasets = create_dataset(
    packet_files=[packet_file],
    xtce_packet_definition=definition,
    packet_filter=lambda pkt: pkt.apid == 41,
)
```

See [Filtering Packets](user_guide/generators.md#filtering-packets) for more detail.

## XTCE Definition Parsing Performance

Loading an XTCE document is a one-time startup cost paid before any packets are parsed, but it is
not free — for large definitions it can dominate the runtime of a short job.

| Definition            | Size    | Parameters | Containers |   Mean |
| --------------------- | ------- | ---------: | ---------: | -----: |
| SUDA combined science | 147 kB  |        207 |          9 | 4.7 ms |
| CTIM                  | 1668 kB |       9493 |         39 |  37 ms |

```
------------------------------------------------------------------------------------------------ benchmark: 2 tests -----------------------------------------------------------------------------------------------
Name (time in ms)                                      Min                Max               Mean            StdDev             Median               IQR            Outliers       OPS            Rounds  Iterations
-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
test_benchmark_complex_xtce_definition_parsing      4.2101 (1.0)       6.3158 (1.0)       4.7378 (1.0)      0.3787 (1.0)       4.5185 (1.0)      0.6661 (1.0)          76;2  211.0673 (1.0)         255           1
test_benchmark_ctim_xtce_parsing                   35.8261 (8.51)     41.1216 (6.51)     37.0746 (7.83)     1.4418 (3.81)     36.3483 (8.04)     1.8893 (2.84)          4;1   26.9727 (0.13)         25           1
-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
```

Note that the cost is not a simple function of either document size or parameter count: CTIM's
document is ~11x larger than SUDA's and declares ~46x as many parameters, yet takes only ~8x as
long to load. Two definitions are not enough to establish a scaling law, so treat these as
order-of-magnitude figures and measure your own definition if load time matters to you.

The practical advice holds either way: load a definition once and reuse the resulting
{py:class}`~space_packet_parser.xtce.definitions.XtcePacketDefinition` across all the files you
parse, rather than re-reading the XTCE document per file or per process.

## Parsing Individual Values Benchmarking

In addition to the benchmarks discussed above, we also benchmarked the low level operations that
make up most of the parsing work. The parser relies on two fundamental methods:
`_read_from_binary_as_int(nbits)` and `_read_from_binary_as_bytes(nbits)`, each of which is capable
of reading an arbitrary number of bits from a bytes object. That is, the binary data being parsed
need not be byte aligned or even an integer number of bytes. These are not intended to be used by
external users, but are included in the benchmarks because they are fundamental to how fast we can
parse items from binary data.

```
-------------------------------------------------------------------------------------------------------- benchmark: 5 tests -------------------------------------------------------------------------------------------------------
Name (time in ns)                                              Min                 Max                Mean            StdDev              Median                IQR            Outliers  OPS (Mops/s)            Rounds  Iterations
-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
test_benchmark__read_as_bytes__aligned                    275.5710 (1.0)      291.2800 (1.0)      281.1683 (1.0)      8.7737 (3.15)     276.6540 (1.0)      11.7817 (3.04)          1;0        3.5566 (1.0)           3        1000
test_benchmark__read_as_int__aligned                      334.3690 (1.21)     347.5780 (1.19)     339.7300 (1.21)     6.9468 (2.50)     337.2430 (1.22)      9.9067 (2.56)          1;0        2.9435 (0.83)          3        1000
test_benchmark__read_as_int__non_aligned                  426.7950 (1.55)     436.5450 (1.50)     430.9753 (1.53)     5.0213 (1.80)     429.5860 (1.55)      7.3125 (1.89)          1;0        2.3203 (0.65)          3        1000
test_benchmark__read_as_bytes__non_aligned_full_bytes     468.2160 (1.70)     474.1330 (1.63)     470.2993 (1.67)     3.3242 (1.19)     468.5490 (1.69)      4.4378 (1.14)          1;0        2.1263 (0.60)          3        1000
test_benchmark__read_as_bytes__partial_bytes              476.2990 (1.73)     481.4670 (1.65)     479.4803 (1.71)     2.7834 (1.0)      480.6750 (1.74)      3.8760 (1.0)           1;0        2.0856 (0.59)          3        1000
-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

Legend:
  Outliers: 1 Standard Deviation from Mean; 1.5 IQR (InterQuartile Range) from 1st Quartile and 3rd Quartile.
  OPS: Operations Per Second, computed as 1 / Mean
```

The results are as expected:

- The most efficient parsing is byte-aligned parsing of objects that are integer number of bytes in
  length.
- Parsing integers is slower than raw bytes due to the conversion from bytes to int.
- The most expensive operation is parsing a bytes object that is an odd number of bits (e.g. 6
  bits). This is due to the padding operation required to return a bytes object from such a call.
- The only surprise is that non-aligned integers parse faster than non-aligned full bytes. Ironically
  this is due to a check that we perform during byte parsing to return faster if the request _is_
  byte aligned.

This ordering has held consistently across every machine we have benchmarked on, even where the
absolute timings differ substantially.
