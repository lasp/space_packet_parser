# XTCE and Electronic Data Sheets (EDS): Feasibility of Conversion

This document summarizes an investigation into whether Space Packet Parser should support the CCSDS Electronic
Data Sheets (EDS) format (CCSDS 876.0-B-1, <https://ccsds.org/Pubs/876x0b1.pdf>) as an additional packet
definition source, either by converting XTCE to EDS, converting EDS to XTCE, or both. It accompanies two example
scripts that demonstrate the basic mechanics of converting in each direction:

- [`examples/xtce_to_eds_conversion.py`](https://github.com/lasp/space_packet_parser/blob/main/examples/xtce_to_eds_conversion.py) —
  converts an in-memory `XtcePacketDefinition` object into a simplified EDS XML document.
- [`examples/eds_to_xtce_conversion.py`](https://github.com/lasp/space_packet_parser/blob/main/examples/eds_to_xtce_conversion.py) —
  builds an in-memory `XtcePacketDefinition` from a small, contrived EDS XML document
  (`tests/test_data/eds/contrived_ccsds_packet.xml`) and uses it to parse a packet.

## Background

Both XTCE (CCSDS 660.0) and EDS (CCSDS 876.0) are CCSDS "Blue Book" standards used to describe the structure of
telemetry/command data. Despite solving similar problems, they come from different lineages and have different
primary goals:

- **XTCE** ("XML Telemetric and Command Exchange") is purpose-built for describing the bit-level layout of
  telemetry and command _packets_: parameter types, calibrations, containers with inheritance/restriction
  criteria for identifying packet variants (e.g. APID + subtype), algorithms, and command/telemetry meta-data
  such as alarms. It is the format this library already supports natively via
  `space_packet_parser.xtce.definitions.XtcePacketDefinition`.
- **EDS** ("Electronic Data Sheets") is a more general-purpose data description language, originally derived from
  work on spacecraft on-board software/interface descriptions (its history traces back to NASA's cFE/cFS "EDS"
  tooling). It describes _data types_ (including C-like structs, arrays, bit fields, and enumerations) and can
  describe container/packet layouts, but it is not exclusively about packets — it is also used to describe
  software interfaces, components, and telecommand/telemetry APIs more broadly.

Both formats represent data with a similar two-level model: a set of reusable **data type** definitions and a
set of **container/structure** definitions that reference those data types by name, in order, to describe binary
layout. This structural similarity is what makes basic conversion in either direction possible, and it is the
approach taken by the two example scripts.

## What the examples demonstrate

`xtce_to_eds_conversion.py` iterates over an `XtcePacketDefinition`'s `parameter_types` and `containers` dicts and
maps:

| XTCE construct                                              | EDS construct                                            |
| ----------------------------------------------------------- | -------------------------------------------------------- |
| `IntegerParameterType` + `IntegerDataEncoding`              | `IntegerDataType` + `IntegerDataEncoding`                |
| `FloatParameterType` + `FloatDataEncoding`                  | `FloatDataType` + `FloatDataEncoding`                    |
| `StringParameterType` + `StringDataEncoding` (fixed length) | `StringDataType` + `StringDataEncoding`/`Length`         |
| `BinaryParameterType` + `BinaryDataEncoding` (fixed length) | `BinaryDataType` (approximated; EDS has no exact analog) |
| `SequenceContainer` + ordered `entry_list`                  | `ContainerDataType` + `EntryList`/`Entry`                |

`eds_to_xtce_conversion.py` does the reverse: it walks an EDS `DataTypeSet`, builds an XTCE `ParameterType` for
every scalar EDS data type, then builds `Parameter` and `SequenceContainer` objects for each EDS
`ContainerDataType`/`EntryList`, and finally hands the result to `XtcePacketDefinition` so it can parse packets
immediately — no intermediate XTCE XML file is required, since `XtcePacketDefinition` can be built directly from
Python objects.

Both scripts are intentionally narrow (a handful of scalar types, fixed-length fields, a single, flat container)
in order to focus on the conversion _pattern_ rather than attempting to be complete.

## Feasibility analysis: building a general converter

### Where the mapping is straightforward

- **Scalar numeric/string data types.** Integer, float, and (fixed-length) string types map close to 1:1 between
  the two formats. Byte order, signedness, and IEEE-754 float sizes are represented in both.
- **Flat, ordered containers.** A simple, non-inheriting container with an ordered list of fixed-size scalar
  fields — the most common packet layout — converts cleanly in either direction, as shown by the examples.
- **Reusable named data types.** Both formats separate a "type catalog" from container definitions that
  reference those types by name, so the overall two-pass conversion strategy (types first, then containers)
  works for both directions.

### Where the mapping is lossy or requires design decisions

- **Container inheritance and restriction criteria.** XTCE's `SequenceContainer` supports `BaseContainer` +
  `RestrictionCriteria` for representing packet variants that share a common header/subset of fields and are
  disambiguated by field values (e.g. different payloads by APID or subtype). EDS's container model is closer to
  a flat, single-definition struct and does not have a direct analog for this identification pattern; an EDS-based
  workflow would likely need to declare distinct containers per variant with a separate identification mechanism
  (e.g. EDS interfaces/commands), which XTCE does not need. **This is the single largest source of conversion
  complexity** for real-world (as opposed to contrived) telemetry definitions, since most missions use this
  pattern extensively for packet dispatch (see `contrived_inheritance_structure.xml` in this repo's test data for
  an example of how deep this can get).
- **Calibrators and algorithms.** XTCE's polynomial/spline calibrators and math/custom algorithms have no 1:1 EDS
  analog; EDS has no first-class calibration concept in the way XTCE does (EDS's closer term would be `Range`,
  `Argument` defaults, and derived parameters via `DerivedTypeRef`, none of which express the same conversions).
  Converting these would require lossy approximations or custom extensions.
- **Dynamic/variable-length fields.** XTCE's `DynamicValue`/size-reference-parameter mechanism for
  variable-length strings/binary fields (see `docs/source/user_guide/variable_length_fields.md`) needs an
  equivalent in EDS (`ArrayDataType` with a `DynamicArrayValue`/matching `LengthEntry`, IIRC from the standard);
  the mapping is conceptually possible but not implemented in the example converters here.
- **Binary blobs.** EDS has no dedicated "opaque binary" data type; XTCE's `BinaryParameterType` was approximated
  above with a fixed-size `BinaryDataType`/byte array, which is a reasonable but non-standard convention.
- **Namespaces/packages/components.** EDS documents are organized around `Package`/`PackageFile`/`Component`
  concepts that can span multiple files and describe more than packet structures (interfaces, commands as RPCs,
  etc.), whereas XTCE's `SpaceSystem` hierarchy is narrower and packet-focused. A full converter would need to
  decide how much of the EDS object model to support or ignore.

### Complexity and scope estimate

Based on this investigation, building a _general-purpose, round-trippable_ EDS <-> XTCE converter, supporting the
container inheritance patterns that real missions rely on and the calibration/dynamic-length features Space
Packet Parser already supports for XTCE, would be a substantial undertaking — comparable in scope to building a
second XTCE parser/serializer, since EDS's data type/container richness is comparable to XTCE's, and would need
its own object model (analogous to `space_packet_parser.xtce.parameter_types`/`encodings`/`containers`) plus a
bidirectional mapping layer with well-defined behavior for the lossy cases above.

A narrower, still useful scope is: supporting **parsing only** an EDS document straight to an in-memory XTCE
definition (no EDS _authoring_/serialization), restricted to flat containers and scalar data types, as
demonstrated by `eds_to_xtce_conversion.py`. This would let missions that maintain EDS-based configuration reuse
their existing definitions with Space Packet Parser without needing to migrate to XTCE, provided their packet
structures don't rely on the inheritance-based dispatch pattern discussed above (or a separate lookup step is
used to select the right EDS container/type before parsing).

## Recommendation

Given the complexity of the lossy cases above (especially container inheritance and calibrators), a full,
general-purpose bidirectional converter is not recommended as a near-term addition to this library. Instead, if
EDS support becomes a hard requirement for a supported mission:

1. Start with a read-only "EDS -> in-memory XTCE definition" importer (as demonstrated here), scoped initially to
   flat containers and the scalar data types most commonly used for telemetry.
2. Expand incrementally based on real mission EDS documents, rather than trying to support the full EDS schema
   up front.
3. Treat XTCE -> EDS export as a much lower priority, since Space Packet Parser's primary contract with users is
   parsing (consuming) definitions, not authoring them in other standards' formats.
