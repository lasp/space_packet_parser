# Examples

For a minimal, self-contained script you can copy and run immediately, see the
[Quickstart Example](getting_started.md#quickstart-example) in Getting Started.

For more involved, real-world usage patterns, see the
[examples folder on GitHub](https://github.com/lasp/space_packet_parser/tree/main/examples).
Examples on GitHub include:

- [Parsing to Xarray Datasets](https://github.com/lasp/space_packet_parser/blob/main/examples/parsing_to_xarray_dataset.py)
  demonstrating how to parse packets directly to Xarray Datasets for analysis workflows
- [Packet filtering](https://github.com/lasp/space_packet_parser/blob/main/examples/packet_filtering.py)
  showing several ways to filter a multiplexed stream down to a single APID — in a comprehension,
  with `filter()`, in a loop, and via the `packet_filter` argument to `create_dataset`
- [Basic quicklook tool](https://github.com/lasp/space_packet_parser/blob/main/examples/parsing_and_plotting_idex_waveforms_from_socket.py)
  using realtime packet parsing from a streaming socket
- [CSV to XTCE](https://github.com/lasp/space_packet_parser/blob/main/examples/csv_to_xtce_conversion.py)
  packet definition conversion and parsing
- [Parsing non-CCSDS packets](https://github.com/lasp/space_packet_parser/blob/main/examples/parsing_non_ccsds_packets.py)
  defining a custom packet bytes generator that finds packets by a sync marker and a
  packet-defined length field, for a format with no CCSDS header
