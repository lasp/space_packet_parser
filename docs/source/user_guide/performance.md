# Optimizing for Performance

The logic evaluated during packet parsing is largely reflective of the XTCE configuration being
used to define packet structures. The more logic in the XTCE, the more logic must be evaluated
during parsing. Below are some common ways to reduce complexity and speed up parsing:

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

For measured throughput numbers on real mission data, see [Benchmarking](../benchmarking.md).
