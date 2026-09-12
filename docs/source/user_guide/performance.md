# Optimizing for Performance

The logic evaluated during packet parsing is largely reflective of the XTCE configuration being
used to define packet structures. The more logic in the XTCE, the more logic must be evaluated
during parsing.

## Don't Parse Packets You Don't Need

This is often the largest available win, and it costs nothing in XTCE complexity.

Ground testing commonly produces multiplexed streams containing many APIDs. If you pass every
packet to `parse_bytes()`, each one is parsed against the XTCE definition — including packets you
have no interest in, which may also fail to parse or emit warnings. Filtering on the CCSDS header
first lets the parser skip those bytes entirely.

Reading a header to decide whether to keep a packet is a fixed, very small cost; parsing that
packet is not. How much filtering saves you depends on what fraction of the stream you can discard
_and_ on how expensive the discarded packets would have been to parse. Skipping short fixed-length
packets that hold a single binary blob saves little, because those were cheap anyway. Skipping
large packets full of calibrated, conditionally evaluated fields saves a lot. Filtering is never
slower, so it is worth doing regardless — but measure your own stream rather than assuming a
speedup. See
[Filtering Muxed Packet Streams](../benchmarking.md#filtering-muxed-packet-streams) for a worked
example.

```python
import space_packet_parser as spp

definition = spp.load_xtce("my_xtce_document.xml")

with open("muxed_stream.bin", "rb") as binary_data:
    for packet_bytes in spp.ccsds_generator(binary_data):
        if packet_bytes.apid != 41:
            continue  # Skipped without ever touching the XTCE definition
        packet = definition.parse_bytes(packet_bytes)
```

See [Filtering Packets](generators.md#filtering-packets) for the available approaches, including
the `packet_filter` argument to `create_dataset`.

## Reduce Dynamic Evaluation in Your XTCE

The parser's remaining cost is dominated by work it can only do by inspecting the data in front of
it. Below are some common ways to reduce that and speed up parsing:

1. **Remove `RestrictionCriteria` Elements:** If your packet stream is a single packet structure,
   there is no reason to require the evaluation of a restriction criteria for each packet.
2. **Remove Unnecessary Packet Definitions:** Even in a packet stream with multiple packet
   formats, if you only care about one packet type, you can remove the definitions for the other.
   Wrap each `parse_bytes()` call in a `try`/`except UnrecognizedPacketTypeError` (see
   [Error Handling and Troubleshooting](error_handling.md)) to skip packets for which a valid
   definition cannot be determined, rather than letting the exception propagate and stop parsing.
3. **Reduce Container Inheritance:** A flat container definition structure will evaluate
   restriction criteria faster than a nested structure. Each instance of nesting requires an
   additional `MatchCriteria.evaluate()` call for each packet being parsed.
4. **Reduce Complex Items:** Parameter type definitions that contain calibrators or complex string
   parsing (especially variable length termination character defined strings) add significant
   evaluation logic to the parsing of each parameter, as does any parameter type that is variable
   length. Removing them can speed up parsing.

Note that these are all reductions in _dynamic_ work. Static field count matters far less: a
2825 B packet of mostly-binary-blob parses in about the same time as a 71 B packet with 27 simple
fields. See [Benchmarking](../benchmarking.md) for measured throughput on real mission data and a
breakdown of what actually drives parsing cost.
