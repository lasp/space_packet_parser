# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [6.1.2] - 2026-04-02

### Fixed

- Prevent BinaryParameter truncation in `create_dataset`. [#246](https://github.com/lasp/space_packet_parser/issues/246)

## [6.1.1] - 2026-03-31

### Fixed

- Support lxml 5.2.1. [#236](https://github.com/lasp/space_packet_parser/issues/236)

## [6.1.0] - 2026-01-21

### Added

- Add support for filtering packets in `create_dataset`
- Add warnings if there are leftover bytes from a CCSDS generator

### Changed

- Migrated from Poetry to uv/hatchling for Python project management
- Add support for Python 3.14

### Fixed

- Handle optional secondary headers with CCSDS continuation packets

## [6.0.1] - 2025-11-06

### Fixed

- Incorrect bitshift logic for ccsds generator packet length creation
  in very specific circumstances (only if large data on power of 2 boundary)

## [6.0.0] - 2025-09-04

### Added

- Add validation support for XTCE documents.
- Add support for creating a packet definition from Python objects and serializing it as XML.
- Add support for string and float encoded enumerated lookup parameters.
- Add properties to extract the CCSDS Header items from the `CCSDSPacketBytes` object directly.
  e.g. `CCSDSPacketBytes.apid`
- Add a `create_ccsds_packet` function that can create a CCSDS Packet
  with the given header items and data. This is useful for creating
  mock packets in testing and experimentation for creating debugging
  streams as needed.
- Add a `ccsds_generator()` function that iterates through raw
  bytes and yields individual CCSDS packets.
- Add continuation packet support to the ccsds packet generation.
  This adds logic to concatenate packet data fields together across successive
  packets (if there was too much data to fit in a single CCSDS packet or it
  was logically better to split by other teams).
  - Add warnings if packets are out of sequence within a given apid.
  - Add ability to remove secondary header bytes from subsequent packets.
    `ccsds_generator(data, combine_segmented_packets=True, secondary_header_bytes=4)`
- Add a command line interface (spp) to enable quick and easy access to
  some common tasks and utilities.
- Add function to directly create an `xarray.DataSet` from a packet file and XTCE definition.
  e.g. `space_packet_parser.xarr.create_dataset([packets1, packets2, ...], definition)`
- Add benchmark tests and documentation overview of benchmarks.

### Changed

- _BREAKING_: `XtcePacketDefinition` no longer accepts a file object as input.
  Use `spp.xtce.definitions.XtcePacketDefinition.from_xtce()` or `spp.load_xtce()` instead.
- _BREAKING_: Reorganization of the project into different submodules for more explicit handling
  of imports. There is now an `space_packet_parser.xtce` module with xtce representations separated
  into modules underneath that.
- Improve XML namespace handling when parsing and serializing XTCE.
- Package for Anaconda distribution via the `lasp` channel

### Removed

- _BREAKING_: Removed mid-level abstraction methods `packet_generator()` and `ccsds_packet_generator()`
  from `XtcePacketDefinition`. Use low-level `parse_bytes()` with bytes generators directly, or high-level
  `space_packet_parser.xarr.create_dataset()` for xarray integration.

### Fixed

- Fix kbps calculation in packet generator for showing progress.
- Update list of allowed float encodings to match XTCE spec

## [5.0.1] - 2024-10-08

### Changed

- If a packet definition parses too few bits, a UserWarning is now emitted instead of a logger warning.

### Fixed

- Allow raw_value representation for enums with falsy raw values. Previously these defaulted to the enum label.

## [5.0.0] - 2024-10-03

### Added

- A `RawPacketData` class has been added that is a subclass of bytes. It keeps track of the current
  parsing location and enables reading of bit lengths as integers or raw bytes.
- Add error reporting for unsupported and invalid parameter types
- Add support for MIL-1750A floats (32-bit only)

### Changed

- _BREAKING_: Main API changed. No need to create separate definition and parser objects any more. Create only a
  definition from your XTCE document and instead of `my_parser.generator`, use `my_packet_definition.packet_generator`.
- _BREAKING_: Separated out logical pieces into separate modules rather than everything
  living within the xtcedef module. This means user imports may be different now.
- _BREAKING_: Replace `bitstring` objects with native Python bytes objects
  - Much faster parsing speed
  - Users that are passing `bitstring.ConstBitStream` objects to `generator` will need to pass a
    binary filelike object instead
- _BREAKING_: The `ParsedDataItem` class has been removed and the derived values are being returned now.
  The `raw_value` is stored as an attribute on the returned object. The other items can be accessed
  through the packet definition object `my_packet_definition.named_parameters["my_item"].short_description`
- _BREAKING_: The return type of BinaryDataEncoding is now the raw bytes.
  To get the previous behavior you can convert the data to an integer and then format it as a binary string.
  `f"{int.from_bytes(data, byteorder='big'):0{len(data)*8}b}"`
- _BREAKING_: Changed `packet_generator` kwarg `skip_header_bits` to `skip_header_bytes`.
- The `CCSDSPacket` class is now a dictionary subclass, enabling direct lookup of items from the Packet itself.

### Removed

- _BREAKING_: Removed CSV-based packet definition support. We may indirectly support this in the future via
  a utility for converting CSV definitions to XTCE.
- _BREAKING_: Remove dependency on the `bitstring` library
- _BREAKING_: Removed `word_size` kwarg from packet generator method.
  We expect all binary data to be integer number of bytes.

### Fixed

- Fixed incorrect parsing of StringDataEncoding elements. Raw string values are now returned as byte buffers.
  Derived string values contain python string objects.
- Fix EnumeratedParameterType to handle duplicate labels

## [4.2.0] - 2024-03-05

### Added

- Parse short and long descriptions of parameters
- Include parameter short description and long description in ParsedDataItems
- Add support for AbsoluteTimeParameterType and RelativeTimeParameterType
- Add support for BooleanParameterType
- Support BooleanExpression in a ContextCalibrator

### Changed

- Implement equality checking for SequenceContainer objects and Parameter objects
- Drop support for bitstring <4.0.1
- Default read size is changed to a full file read on file-like objects
- Improve error handling for invalid/unsupported parameter types

## [4.1.1] - 2024-04-01

### Changed

- Allow Python 3.12

## [4.1.0] - 2023-08-31

### Added

- Add informative error if user tries to parse a TextIO object
- Add documentation of some common issues and add changelog to documentation

### Fixed

- Bugfix in fill_buffer to allow compatibility with Bitstring 4.1.1

## [4.0.2] - 2023-03-14

### Changed

- Documentation updates for Read The Docs

## [4.0.1] - 2023-03-10

### Added

- Add examples directory to help users
- Add CITATION.cff
- Add CODE_OF_CONDUCT.md

### Changed

- Modify API for `PacketParser.generator` to accept a ConstBitStream or a BufferedReader or a socket
  - This will allow us to keep memory overhead of reading a binary stream to almost zero

---

## Historical Changes (`lasp_packets`)

Changes documented in v3.0 and earlier correspond to development efforts undertaken before this library was
moved to GitHub (it was previously known as `lasp_packets`).
None of the git history is available for these versions as the git history was truncated
in preparation for the move to Github to prevent accidental release of non-public example data which may be
(but probably isn't) present in historical commits.

## [3.0] - Unknown

### Added

- Add a discussion of optimization to the documentation
- Add support for Python 3.10 and 3.11
- Add Parser.generator kwargs tdocs/source/index.rsto aid in debugging
- Add kwarg to only parse CCSDS headers and skip the user data
- Add optional progress bar that prints to stdout when parsing a packets file.

### Changed

- Change license to BSD3 and CU copyright
- Redesign the way the parser interprets the SequenceContainer inheritance structure
  - This allows polymorphic packet structures based on flags in telemetry
  - Previous functionality is preserved
  - csvdef module still uses the legacy flattened_containers representation

### Removed

- Remove support for Python 3.6

## [2.1] - Unknown

### Changed

- Update documentation on release process

## [2.0] - Unknown

### Added

- Add link in readme to v1.2 Aug 2021 of XTCE spec
- Add support for `< xtce:DiscreteLookupList >`
- Add support for `< xtce:Condition >`
- Add support for `< xtce:BooleanExpression >`
- Add option to skip an additional header on each packet
- Add word size as an optional parameter to the parser
- Add an optional header name remapping parameter to the parser
- Add support for BooleanExpression in a RestrictionCriteria element

### Changed

- Push the evaluation logic for ParameterTypes down to DataEncodings
- Modify RestrictionCriteria parser to evaluate MatchCriteria elements

## [1.3] - Unknown

### Changed

- Expand version compatibility for python >=3.6, <4

## [1.2] - Unknown

### Added

- Add support for instantiating definitions with pathlib.Path objects.

### Changed

- Remove unnecessary warning about float data types being IEEE formatted.
- Switch package manager to Poetry.

## [1.1.0] - Unknown

### Added

- Add support for CSV-based packet definitions (contribution by Michael Chambliss).

## [1.0] - Unknown

### Added

- Add support for all parameter types.
- Add support for all data encodings.
- Add support for calibrators and contextual calibrators.
- Add support for variable length strings given by termination characters or preceding length fields.
- Add support for variable length binary data fields in utf-8, utf-16-le, and utf-16-be.
- Add build and release documentation to readme.

[unreleased]: https://github.com/lasp/space_packet_parser/compare/6.1.1...HEAD
[6.1.1]: https://github.com/lasp/space_packet_parser/compare/6.1.0...6.1.1
[6.1.0]: https://github.com/lasp/space_packet_parser/compare/6.0.1...6.1.0
[6.0.1]: https://github.com/lasp/space_packet_parser/compare/6.0.0...6.0.1
[6.0.0]: https://github.com/lasp/space_packet_parser/compare/5.0.1...6.0.0
[5.0.1]: https://github.com/lasp/space_packet_parser/compare/5.0.0...5.0.1
[5.0.0]: https://github.com/lasp/space_packet_parser/compare/4.2.0...5.0.0
[4.2.0]: https://github.com/lasp/space_packet_parser/compare/4.1.1...4.2.0
[4.1.1]: https://github.com/lasp/space_packet_parser/compare/4.1.0...4.1.1
[4.1.0]: https://github.com/lasp/space_packet_parser/compare/4.0.2...4.1.0
[4.0.2]: https://github.com/lasp/space_packet_parser/compare/4.0.1...4.0.2
[4.0.1]: https://github.com/lasp/space_packet_parser/compare/3.0...4.0.1
[3.0]: https://github.com/lasp/space_packet_parser/compare/2.1...3.0
[2.1]: https://github.com/lasp/space_packet_parser/compare/2.0...2.1
[2.0]: https://github.com/lasp/space_packet_parser/compare/1.3...2.0
[1.3]: https://github.com/lasp/space_packet_parser/compare/1.2...1.3
[1.2]: https://github.com/lasp/space_packet_parser/compare/1.1.0...1.2
[1.1.0]: https://github.com/lasp/space_packet_parser/compare/1.0...1.1.0
[1.0]: https://github.com/lasp/space_packet_parser/releases/tag/1.0
