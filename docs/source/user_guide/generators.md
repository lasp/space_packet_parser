# Packet Bytes Generators

Packet bytes generators are functions that yield individual packets as `bytes` objects (or
subclasses of `bytes`) from a binary data source. Space Packet Parser provides built-in generators
like `ccsds_generator`, `fixed_length_generator`, and `udp_generator`, but you can write custom
generators to parse any packet format you need.

A generator function should accept a binary data source (file-like object, socket, or bytes) and
yield packet bytes one at a time. The built-in generator implementations in
`space_packet_parser/generators/` provide complete examples of how to implement packet bytes
generators. Custom generators allow you to adapt Space Packet Parser to work with any binary
packet format.

While XTCE is commonly used with CCSDS packets, the XTCE standard is not limited to representing
CCSDS packet structures. The CCSDS header information (`VERSION`, `TYPE`, `APID`, etc.) is not
required by XTCE. You can define XTCE packet structures for any binary format and use a custom or
built-in generator to yield those packets for parsing.

## Built-in Generators

### CCSDS Generator

The `ccsds_generator` parses CCSDS Space Packets according to the CCSDS standard. It uses the
packet length field in the CCSDS header to determine packet boundaries and supports features like
segmented packet reassembly.

```python
from space_packet_parser import ccsds_generator, load_xtce

packet_definition = load_xtce("my_ccsds_packets.xml")
for packet_bytes in ccsds_generator(binary_data):
    parsed = packet_definition.parse_bytes(packet_bytes)
    print(parsed)
```

### Fixed Length Generator

The `fixed_length_generator` yields fixed-size chunks from binary data. This is useful for packet
formats where all packets have a known, constant length.

```python
from space_packet_parser import load_xtce
from space_packet_parser.generators import fixed_length_generator

packet_definition = load_xtce("my_fixed_length_packets.xml")
for packet_bytes in fixed_length_generator(binary_data, packet_length_bytes=64):
    parsed = packet_definition.parse_bytes(packet_bytes)
    print(parsed)
```

### UDP Generator

The `udp_generator` parses UDP (User Datagram Protocol) packets from binary data. It reads the UDP
length field from each packet header to determine packet boundaries. The generator yields
`UDPPacketBytes` objects that expose UDP header fields (source port, destination port, length,
checksum) as properties.

```python
from space_packet_parser import udp_generator, load_xtce

packet_definition = load_xtce("my_udp_packets.xml")
for udp_packet in udp_generator(binary_data):
    # Access UDP header fields directly
    print(f"From port {udp_packet.source_port} to port {udp_packet.dest_port}")
    # Parse the packet using XTCE
    parsed = packet_definition.parse_bytes(udp_packet)
    print(parsed)
```

## Writing Custom Generators

A minimal custom generator follows this pattern:

```python
def custom_generator(binary_data, packet_length):
    """Yields fixed-length packets from binary data."""
    while True:
        packet_bytes = binary_data.read(packet_length)
        if not packet_bytes:
            break
        yield packet_bytes
```

For more sophisticated generators that handle multiple input types (files, sockets, bytes) and
provide progress tracking, see the implementations of the built-in generators in
`space_packet_parser/generators/`. These demonstrate best practices like using the
`_setup_binary_reader` utility for handling different data sources and optional progress bars.

## Filtering Packets

For generators that expose packet metadata (like `CCSDSPacketBytes` with its `apid` property), you
can filter packets before parsing to improve performance. See the
[packet filtering example](https://github.com/lasp/space_packet_parser/blob/main/examples/packet_filtering.py)
for a complete, runnable demonstration.
