# Error Handling and Troubleshooting

## Handling UnrecognizedPacketTypeError

When parsing packets, you may encounter situations where packets cannot be parsed successfully.
The low-level API provides direct control over how to handle these cases.

If a packet doesn't match any of the defined packet structures in your XTCE definition, an
`UnrecognizedPacketTypeError` will be raised. You can catch this error to examine the partially
parsed packet data for debugging:

```python
import space_packet_parser as spp
from space_packet_parser.exceptions import UnrecognizedPacketTypeError

packet_definition = spp.load_xtce("my_xtce_document.xml")

with open("my_packets.pkts", "rb") as binary_data:
    for packet_bytes in spp.ccsds_generator(binary_data):
        try:
            packet = packet_definition.parse_bytes(packet_bytes)
            # Process successful packet
            print(f"Successfully parsed packet with APID: {packet.binary_data.apid}")
        except UnrecognizedPacketTypeError as e:
            # Handle unrecognized packet and continue with the next one
            print("Unrecognized packet type")
            print(f"Partial data: {e.partial_data}")  # Contains any successfully parsed fields
            continue
```

`UnrecognizedPacketTypeError.partial_data` contains the fields successfully parsed before the
parser failed to determine the rest of the container structure, which is useful for figuring out
how far it got during development. Wrapping each `parse_bytes()` call in its own `try`/`except`, as
above, lets you skip bad packets and keep processing the rest of the stream.

## Troubleshooting Packet Parsing

Parsing binary packets is error-prone and getting the XTCE definition correct can be a challenge at
first. Most flight software teams can export XTCE from their command and telemetry database, but
these exports usually require some fine-tuning.

`UnrecognizedPacketTypeError`s are raised during parsing of an individual packet when either:

- multiple child containers are valid inheritors of the current sequence container based on
  restriction criteria evaluated against the data parsed so far, or
- no child containers are valid inheritors of the current sequence container based on restriction
  criteria evaluated against the data parsed so far, and the current container is abstract.

### Parser Generator Completes without Yielding a Packet

This can occur if your data file contains only packets that do not match any packet definitions in
your XTCE document and `yield_unrecognized_packet_errors=False` (the default). This could mean that
your data file actually contains only APIDs that are not covered in your packet definition, but
usually it means you have incorrectly defined restriction criteria for `SequenceContainer`
inheritance.

For example, a restriction criteria element that requires an APID which does not exist in the data:

```xml
<xtce:RestrictionCriteria>
    <xtce:Comparison parameterRef="PKT_APID" value="-99" useCalibratedValue="false"/>
</xtce:RestrictionCriteria>
```

### Only Packet Headers are Parsed

If you observe that only packet headers are being parsed but no exceptions are being raised (you
may be seeing a lot of length mismatch warnings if you have logging set up), it likely means that
you have forgotten to set `abstract="true"` on your non-concrete sequence container elements.

For example,

```xml
<xtce:SequenceContainer name="CCSDSPacket">
    <xtce:LongDescription>Super-container for telemetry and command packets</xtce:LongDescription>
    <xtce:EntryList>
        <xtce:ParameterRefEntry parameterRef="VERSION"/>
        <xtce:ParameterRefEntry parameterRef="TYPE"/>
    </xtce:EntryList>
</xtce:SequenceContainer>
```

will parse as a complete packet, containing only `VERSION` and `TYPE`, instead of searching for
inheriting sequence containers. To define the container as abstract, change the first element
opening tag to

```xml
<xtce:SequenceContainer name="CCSDSPacket" abstract="true">
...contents
</xtce:SequenceContainer>
```
