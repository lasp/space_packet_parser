# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Support XTCE 1.3 (OMG, July 2025) alongside XTCE 1.2. Documents in the XTCE 1.3 namespace
  (`http://www.omg.org/spec/XTCE/20250214`) are parsed, serialized, and schema validated, and the
  OMG 1.3 schema is bundled with the package so validation works offline with no network request.
  Nearly all of the schema this library reads is unchanged between 1.2 and 1.3, so a definition
  generally parses identically under either version; the version-specific constructs are covered by
  the entries below and are documented in the XTCE validation user guide.
  [#184](https://github.com/lasp/space_packet_parser/issues/184)
- Add a registry of supported XTCE versions in `space_packet_parser.xtce`: `SUPPORTED_XTCE_VERSIONS`,
  `LATEST_XTCE_VERSION`, `DEFAULT_XTCE_VERSION`, the per-version namespace URI and schema URL
  mappings, and the `xtce_version_from_uri`, `xtce_uri_for_version`, and `xtce_nsmap` helpers.
- Add `XtcePacketDefinition.xtce_standard_version`, reporting the version of the XTCE standard
  implied by a definition's namespace URI. Assigning to it retargets the definition at another
  version, and the matching `xtce_standard_version` keyword argument selects a version when
  constructing a definition from scratch. Definitions built from scratch continue to default to
  XTCE 1.2 so that upgrading does not silently change the version of documents you write.
- Report the detected XTCE version on validation results as `ValidationResult.xtce_version`, and in
  the `spp validate` CLI output.
- Support the XTCE 1.3 form of a variable-length string, in which the raw buffer length is not
  declared and is instead derived from the string's own delimiter. XTCE 1.2 requires a `DynamicValue`
  or `DiscreteLookupList` and treats `LeadingSize`/`TerminationChar` as optional; XTCE 1.3 inverts
  this, making the declared length optional and one of the delimiters required. Parsing now derives
  the buffer length from a `LeadingSize` (the size tag plus the content length it reports) or a
  `TerminationChar` (up to and including the terminator, bounded by `maxSizeInBits`).
  [#184](https://github.com/lasp/space_packet_parser/issues/184)
- Warn when serializing a definition whose variable-length string encodings are not valid in the
  XTCE version being written, rather than silently producing a document that fails schema validation.
- Preserve the XTCE 1.3 `SpaceSystem` attributes `systemType` and `assetType`, as the new
  `XtcePacketDefinition.space_system_type` and `asset_type` fields and constructor keyword arguments.
  They were previously read past and dropped, so round-tripping a 1.3 document silently replaced them
  with the schema default. Serializing as XTCE 1.2, where the attributes do not exist, drops them with
  a warning.
- Warn when serializing a definition whose time parameter type units the target XTCE version does not
  define, e.g. converting a 1.2 definition using `picoSeconds` to 1.3, which spells it `picoseconds`.
  Units are document content and are written through unchanged rather than translated.
- Add `StringDataEncoding.max_size_in_bits`, read from and written to the `maxSizeInBits` attribute of a
  `Variable` element. It bounds the buffer a leading size tag may declare and how far parsing scans for a
  termination character.

### Changed

- `XtcePacketDefinition(xtce_ns_prefix=None)` now binds the XTCE namespace as the document's default
  namespace (unprefixed element names) rather than producing a document with no namespace at all.
  Pass `ns={}` for the latter.
- Serializing a definition now writes the canonical OMG schema URL in `xsi:schemaLocation`, replacing
  whatever URL the source document named. Anyone pointing documents at an internal schema mirror will
  need to rewrite the attribute after serializing.

### Fixed

- Correct the values of `XTCE_1_2_XMLNS` and `XTCE_1_1_XMLNS`, which did not match the
  `targetNamespace` of the schemas they name, and of `STANDARD_XTCE_NSMAP` and `XTCE_URI`, which are
  derived from them. `XTCE_1_2_XMLNS` used an `https` scheme where the XTCE 1.2 `targetNamespace` is
  `http://www.omg.org/spec/XTCE/20180204`, and `XTCE_1_1_XMLNS` named a URI that no XTCE schema
  declares (XTCE 1.1 uses `http://www.omg.org/space/xtce`). As a result, a definition built from
  scratch and serialized used a namespace URI that no schema recognized, and the document failed
  schema validation. Code that imports these constants, or that string-compares namespace URIs, will
  see the new values; reading documents that use the old URI keeps working, as below.

  Documents written by earlier versions of this library carry the old `https` URI. They are still
  recognized as XTCE 1.2 (see `LEGACY_XTCE_XMLNS_ALIASES`) and are rewritten to the canonical URI,
  with a warning, when serialized — so reading such a document and writing it back out repairs it.

- Make `CITATION.cff` conform to CFF 1.2.0 so citation exports work, and update the
  metadata consistency check to use CFF contacts while keeping package descriptions
  separate from the citation abstract. [#285](https://github.com/lasp/space_packet_parser/issues/285)
- Raise `UnrecognizedPacketTypeError` (with `partial_data` populated) when an abstract container has
  no valid inheritors, even if the definition has no `PKT_APID` parameter. Previously the error
  message was built by subscripting `packet['PKT_APID']`, so definitions that do not use CCSDS
  naming got a `KeyError` from inside the library instead of the documented exception. The message
  still reports the APID when the packet has one. As part of this, `str(CCSDSPacketBytes)` no longer
  raises `IndexError` for inputs shorter than a full six-byte primary header and instead renders the
  bytes it has, so it is safe to use in diagnostic messages.
  [#276](https://github.com/lasp/space_packet_parser/issues/276)
- Make structural validation namespace-aware. Its XPath queries hardcoded the XTCE 1.2 namespace
  URI, so reference-integrity checks silently matched nothing — and therefore reported no errors —
  for documents using any other namespace, including XTCE 1.3, a non-standard namespace URI, or no
  namespace at all.
  [#184](https://github.com/lasp/space_packet_parser/issues/184)
- Emit `BaseContainer` after `EntryList` when serializing a `SequenceContainer`. The XTCE schema
  orders them the other way around (identically in 1.2 and 1.3), so written documents failed schema
  validation. Serialized documents now also declare `xsi:schemaLocation`, pointing at the schema for
  their own XTCE version, so a definition written out by this library is schema-valid as-is.
- Search for a string's termination character on character boundaries rather than byte boundaries in
  fixed-width encodings. In UTF-16BE the terminator `b"\x00\x00"` appears inside
  `b"\x41\x00\x00\x42"`, which is the two characters U+4100 and U+0042 and contains no terminator,
  so such a string previously terminated early and could fail to decode. Variable-width (UTF-8) and
  single-byte encodings are unaffected, and continue to be searched byte by byte.
- Default an omitted `LinearAdjustment` `slope` attribute to 1 rather than 0. The XTCE 1.3 schema
  declares a default of 1 (XTCE 1.2 declares none), so `<LinearAdjustment intercept="8"/>` means
  `f(x) = x + 8`. Defaulting the slope to 0 collapsed the adjustment to a constant, which silently
  produced the wrong length for a dynamically sized string or binary field and corrupted every
  subsequent field in the packet.
- Write the `maxSizeInBits` attribute when serializing a variable-length string. The XTCE schema
  requires it on a `Variable` element in both 1.2 and 1.3, so every variable-length string this
  library wrote previously failed schema validation.
- Bound the XTCE 1.3 leading-size string path by `maxSizeInBits`. The size tag comes from the packet, so
  an oversized tag would consume bytes belonging to later fields instead of being rejected.
- Read an empty `<TerminationChar/>` as the null terminator the XTCE schema declares as its default,
  in both 1.2 and 1.3, rather than treating the delimiter as absent and rejecting a valid C string.
- Refuse to select an XTCE version whose schema is not bundled (e.g. 1.1) as a serialization target.
  Such a document named a schema that could not be resolved offline, so validating it silently fell
  back to a network download. Detecting the version of such a document is unaffected.
- Name the cause in the `INVALID_XTCE_NAMESPACE` error when a document uses the `https` XTCE 1.2
  namespace URI written by `space_packet_parser` 6.2 and earlier, instead of the generic
  "does your namespace match your schema?" message, and say that re-serializing the document repairs it.
- Preserve the XTCE `Header` `version` and `validationStatus` attributes when reading a document, so
  that reading a definition and writing it back out no longer replaces them with defaults.
- Determine a document's XTCE namespace from the namespace of its root element rather than by
  searching the namespace mapping for a URI containing "xtce". Documents that bind more than one
  namespace whose URI contains "xtce" previously raised `ValueError` instead of parsing.

## [6.2.0] - 2026-09-13

### Security

- Fix a local file read vulnerability (CWE-73) and a Server-Side Request Forgery vulnerability
  (CWE-918) in `validate_xtce`. A document-supplied `xsi:schemaLocation` is now treated as
  untrusted: absolute and relative local filesystem paths are rejected (use `local_xsd` for a
  local schema), and schema URLs are fetched only over `https` from an allowlisted host (default
  `www.omg.org`), with requests to internal/link-local addresses (e.g. `169.254.169.254`,
  `127.0.0.1`) always blocked. Downloaded content is size-capped and is written to the cache only
  after it validates as an XSD, so a non-schema response can no longer be persisted to disk.
  [#266](https://github.com/lasp/space_packet_parser/issues/266)

### Added

- Bundle the standard OMG XTCE 1.2 schema with the package so documents referencing it validate
  offline with no network request.
- Add `allowed_schema_hosts`, `allow_insecure_http`, and `allow_schema_download` options to
  `validate_xtce` (and the corresponding `--allowed-schema-host`, `--allow-insecure-http`, and
  `--no-schema-download` flags to `spp validate`). The allowlist may also be set via the
  `SPP_ALLOWED_SCHEMA_HOSTS` environment variable, and insecure http via `SPP_ALLOW_INSECURE_HTTP`.
  The default allowlist is exported as `DEFAULT_ALLOWED_SCHEMA_HOSTS`.
- Support multiple `<xtce:Unit>` elements within an `<xtce:UnitSet>`, so parameter types can declare
  compound units. Applies to every parameter type, both when reading an XTCE document and when
  serializing one back out.
  [#47](https://github.com/lasp/space_packet_parser/issues/47)

### Changed

- Reorganize the user documentation. The single `users.md` page is split into a `Getting Started`
  page (installation, the parsing workflow, and a self-contained runnable quickstart) and a
  `User Guide` section with one page per topic: packet bytes generators, packet and parameter
  objects, xarray datasets, variable length fields, XTCE validation, error handling and
  troubleshooting, socket parsing, and performance tuning. The Sphinx toctree is now defined in
  MyST Markdown rather than reStructuredText, and pages cross-link to one another.
  [#192](https://github.com/lasp/space_packet_parser/issues/192)
- Refresh the benchmarking documentation against the current benchmark suite. All nine benchmarks
  are now covered, including complex (IDEX) packet parsing and XTCE definition load times, which
  were previously unreported. Removes a progress-printing comparison that was not reproducible from
  the committed test suite, and fixes a GitHub-style `[!NOTE]` callout that rendered as literal text
  in the built documentation. Documents packet filtering on muxed streams as a performance lever,
  and corrects the explanation of what drives parsing cost: dynamic evaluation work, not packet
  size or definition-wide parameter count.
- Widen the `unit` attribute of parameter types from `str | None` to `str | tuple[str, ...] | None`.
  An `<xtce:UnitSet>` containing more than one `<xtce:Unit>` previously emitted a warning and joined
  the units into a single space-separated string; it now yields a tuple of the individual unit
  strings. Definitions declaring a single unit are unaffected.
  [#47](https://github.com/lasp/space_packet_parser/issues/47)

### Fixed

- Correct the documented meaning of `root_container_name` on `parse_bytes`, `parse_packet`, and
  `parse_ccsds_packet`. All three stated that a specified root container "must begin with the
  definition of a CCSDS header in order to parse correctly", which is not true — any container in
  the definition may be used as the root, and XTCE has no notion of the CCSDS standard (as the
  deprecated methods' own warnings point out). `"CCSDSPacket"` is the default container name, not a
  structural requirement.
- Remove the duplicated table of contents from the User Guide landing page, and describe the packet
  filtering example on the Examples page alongside the others.
- Fix the navigation sidebar on the in-browser demo page. The demo's standalone HTML document was
  spliced into the middle of the documentation page, so its Materialize stylesheet applied to the
  whole page: `nav { height: 56px; width: 100%; background-color: #ee6e73; position: fixed }` and
  `nav ul li { float: left }` collapsed the theme's `<nav class="wy-nav-side">` sidebar, and the
  demo's `body { display: flex; max-width: 900px }` rule constrained the page layout. The demo is
  now embedded in an iframe, which isolates its styles while leaving the demo itself unchanged.
- Correct several longstanding inaccuracies in the user documentation, surfaced while
  reorganizing it. The Getting Started workflow now imports `space_packet_parser` and opens the
  packet file in binary mode (`ccsds_generator` takes a file-like object, not a path, and raised
  `OSError` as previously written); `udp_generator` is imported from `space_packet_parser.generators`
  rather than the package root, which does not export it; the removed
  `yield_unrecognized_packet_errors` option is no longer referenced; the socket page no longer
  claims `ccsds_generator` yields parsed packets rather than `CCSDSPacketBytes`; `BoolParameter` is
  documented as subclassing `int` rather than `bool` (Python forbids subclassing `bool`, so
  `isinstance(param, bool)` is `False`); and the `validate_xtce` examples pass
  `raise_on_error=False`, without which the documented `result.errors` inspection was unreachable.
- Fix `CLAUDE_CONFIG_DIR` and persist the IPv6 localhost workaround for MCP OAuth in the
  devcontainer configuration.
- `validate_xtce(local_xsd=...)` and `spp validate --local-xsd` again accept absolute paths from
  any working directory (a regression that silently rewrote them to a bare filename in the current
  directory). Schema-fetch failures are now reported with accurate error codes
  (`DISALLOWED_SCHEMA_LOCATION` rather than a misleading `MISSING_SCHEMA_LOCATION`).

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
in preparation for the move to GitHub to prevent accidental release of non-public example data which may be
(but probably isn't) present in historical commits.

## [3.0] - Unknown

### Added

- Add a discussion of optimization to the documentation
- Add support for Python 3.10 and 3.11
- Add Parser.generator kwargs to aid in debugging
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

[unreleased]: https://github.com/lasp/space_packet_parser/compare/6.2.0...HEAD
[6.2.0]: https://github.com/lasp/space_packet_parser/compare/6.1.2...6.2.0
[6.1.2]: https://github.com/lasp/space_packet_parser/compare/6.1.1...6.1.2
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
