# User Guide

This guide covers Space Packet Parser's features in depth. If you're new to the library, start
with [Getting Started](../getting_started.md) first.

```{toctree}
:maxdepth: 1
:hidden:

generators
packets_and_parameters
xarray
variable_length_fields
xtce_validation
error_handling
sockets
performance
```

- [Packet Bytes Generators](generators.md) — built-in CCSDS, fixed-length, and UDP generators,
  plus how to write your own.
- [Packet and Parameter Objects](packets_and_parameters.md) — what you get back from
  `parse_bytes()`, including numeric calibration, string parsing, enumerated lookups, and boolean
  evaluation.
- [Parsing to Xarray Datasets](xarray.md) — parse packets directly into `xarray.Dataset` objects
  for analysis workflows.
- [Variable Length Packet Fields](variable_length_fields.md) — encoding fields whose length is
  determined by another field, or by the remaining packet length.
- [XTCE Document Validation](xtce_validation.md) — schema and structural validation of XTCE
  documents, including network security controls for schema resolution.
- [Error Handling and Troubleshooting](error_handling.md) — handling unrecognized packets and
  diagnosing common XTCE definition mistakes.
- [Parsing from a Socket](sockets.md) — using the packet generator with streaming binary sources.
- [Optimizing for Performance](performance.md) — tips for speeding up packet parsing.
