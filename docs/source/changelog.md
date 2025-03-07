# Change Log
This is a log of changes made to the library over time. For planned upcoming changes, please check the GitHub issue
list and release milestones.

## Version Release Notes
Release notes for the `space_packet_parser` library

### v6.0.0 (unreleased)
- *BREAKING*: `XtcePacketDefinition` no longer accepts a file object as input.
  Use `spp.xtce.definitions.XtcePacketDefinition.from_xtce()` or `spp.load_xtce()` instead.
- *BREAKING*: Reorganization of the project into different submodules for more explicit handling
  of imports. There is now an `space_packet_parser.xtce` module with xtce representations separated
  into modules underneath that.
- Add support for creating a packet definition from Python objects and serializing it as XML.
- BUGFIX: Fix kbps calculation in packet generator for showing progress.
- Add support for string and float encoded enumerated lookup parameters.
- Add properties to extract the CCSDS Header items from the ``RawPacketData`` object directly.
  e.g. ``RawPacketData.apid``
- Add a ``create_ccsds_packet`` function that can create a CCSDS Packet
  with the given header items and data. This is useful for creating
  mock packets in testing and experimentation for creating debugging
  streams as needed.
- Add a ``ccsds_packet_generator()`` function that iterates through raw
  bytes and yields individual CCSDS packets.
- Add continuation packet support to the XTCE parsing and packet generation.
  This adds logic to concatenate packet data fields together across successive
  packets (if there was too much data to fit in a single CCSDS packet or it
  was logically better to split by other teams).
  - Add warnings if packets are out of sequence within a given apid.
  - Add ability to remove secondary header bytes from subsequent packets.
    ``definition.packet_generator(data, combine_segmented_packets=True, secondary_header_bytes=4)``
- Add a command line interface (spp) to enable quick and easy access to
  some common tasks and utilities.
- Add function to directly create an `xarray.DataSet` from a packet file and XTCE definition.
  e.g. `space_packet_parser.xarr.create_dataset([packets1, packets2, ...], definition)`
- BUGFIX: update list of allowed float encodings to match XTCE spec
- Add benchmark tests and documentation overview of benchmarks.
- Improve XML namespace handling when parsing and serializing XTCE.
- Package for Anaconda distribution via the `lasp` channel

### v5.0.1 (released)
- BUGFIX: Allow raw_value representation for enums with falsy raw values. Previously these defaulted to the enum label.
- If a packet definition parses too few bits, a UserWarning is now emitted instead of a logger warning.

### v5.0.0 (released)
- *BREAKING*: Main API changed. No need to create separate definition and parser objects any more. Create only a
  definition from your XTCE document and instead of `my_parser.generator`, use `my_packet_definition.packet_generator`.
- *BREAKING*: Removed CSV-based packet definition support. We may indirectly support this in the future via
  a utility for converting CSV definitions to XTCE.
- *BREAKING*: Separated out logical pieces into separate modules rather than everything
  living within the xtcedef module. This means user imports may be different now.
- *BREAKING*: Replace `bitstring` objects with native Python bytes objects
  - Remove dependency on the `bitstring` library
  - Much faster parsing speed
  - Users that are passing `bitstring.ConstBitStream` objects to `generator` will need to pass a
    binary filelike object instead
- *BREAKING*: The ``ParsedDataItem`` class has been removed and the derived values are being returned now.
  The ``raw_value`` is stored as an attribute on the returned object. The other items can be accessed
  through the packet definition object ``my_packet_definition.named_parameters["my_item"].short_description``
- *BREAKING*: The return type of BinaryDataEncoding is now the raw bytes.
  To get the previous behavior you can convert the data to an integer and then format it as a binary string.
  ``f"{int.from_bytes(data, byteorder='big'):0{len(data)*8}b}"``
- *BREAKING*: Removed `word_size` kwarg from packet generator method.
  We expect all binary data to be integer number of bytes.
- *BREAKING*: Changed `packet_generator` kwarg `skip_header_bits` to `skip_header_bytes`.
- Fixed incorrect parsing of StringDataEncoding elements. Raw string values are now returned as byte buffers.
  Derived string values contain python string objects.
- The ``CCSDSPacket`` class is now a dictionary subclass, enabling direct lookup of items from the Packet itself.
- A ``RawPacketData`` class has been added that is a subclass of bytes. It keeps track of the current
  parsing location and enables reading of bit lengths as integers or raw bytes.
- Fix EnumeratedParameterType to handle duplicate labels
- Add error reporting for unsupported and invalid parameter types
- Add support for MIL-1750A floats (32-bit only)

### v4.2.0 (released)
- Parse short and long descriptions of parameters
- Implement equality checking for SequenceContainer objects and Parameter objects
- Include parameter short description and long description in ParsedDataItems
- Add support for AbsoluteTimeParameterType and RelativeTimeParameterType
- Add support for BooleanParameterType
- Drop support for bitstring <4.0.1
- Support BooleanExpression in a ContextCalibrator
- Default read size is changed to a full file read on file-like objects
- Improve error handling for invalid/unsupported parameter types

### v4.1.1 (released)
- Allow Python 3.12

### v4.1.0 (released)
- Bugfix in fill_buffer to allow compatibility with Bitstring 4.1.1
- Add informative error if user tries to parse a TextIO object
- Add documentation of some common issues and add changelog to documentation

### v4.0.2 (released)
- Documentation updates for Read The Docs

### v4.0.1 (released)
- Modify API for `PacketParser.generator` to accept a ConstBitStream or a BufferedReader or a socket
  - This will allow us to keep memory overhead of reading a binary stream to almost zero
- Add examples directory to help users
- Add CITATION.cff
- Add CODE_OF_CONDUCT.md

## Historical Changes (`lasp_packets`)
Changes documented in v3.0 and earlier correspond to development efforts undertaken before this library was
moved to GitHub (it was previously known as `lasp_packets`).
None of the git history is available for these versions as the git history was truncated
in preparation for the move to Github to prevent accidental release of non-public example data which may be
(but probably isn't) present in historical commits.

### v3.0 (released publicly)
- Add a discussion of optimization to the documentation
- Change license to BSD3 and CU copyright
- Add support for Python 3.10 and 3.11
- Remove support for Python 3.6
- Redesign the way the parser interprets the SequenceContainer inheritance structure
  - This allows polymorphic packet structures based on flags in telemetry
  - Previous functionality is preserved
  - csvdef module still uses the legacy flattened_containers representation
- Add Parser.generator kwargs tdocs/source/index.rsto aid in debugging
- Add kwarg to only parse CCSDS headers and skip the user data
- Add optional progress bar that prints to stdout when parsing a packets file.

### v2.1 (released publicly)
- Update documentation on release process

### v2.0 (released internally)
- Add link in readme to v1.2 Aug 2021 of XTCE spec
- Add support for `< xtce:DiscreteLookupList >`
- Add support for `< xtce:Condition >`
- Add support for `< xtce:BooleanExpression >`
- Push the evaluation logic for ParameterTypes down to DataEncodings
- Add option to skip an additional header on each packet
- Modify RestrictionCriteria parser to evaluate MatchCriteria elements
- Add word size as an optional parameter to the parser
- Add an optional header name remapping parameter to the parser
- Add support for BooleanExpression in a RestrictionCriteria element

### v1.3 (released internally)
- Expand version compatibility for python >=3.6, <4

### v1.2 (released internally)
- Remove unnecessary warning about float data types being IEEE formatted.
- Switch package manager to Poetry.
- Add support for instantiating definitions with pathlib.Path objects.

### v1.1.0 (released internally)
- Add support for CSV-based packet definitions (contribution by Michael Chambliss).

### v1.0 (released internally)
- Add support for all parameter types.
- Add support for all data encodings.
- Add support for calibrators and contextual calibrators.
- Add support for variable length strings given by termination characters or preceding length fields.
- Add support for variable length binary data fields in utf-8, utf-16-le, and utf-16-be.
- Add build and release documentation to readme.
