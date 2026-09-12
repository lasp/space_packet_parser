# Getting Started

## Installation

From PyPI:

```bash
pip install space_packet_parser
```

From Anaconda:

```bash
conda install -c lasp space_packet_parser
```

## The Parsing Workflow

The typical workflow for parsing packets is to

1. **Load a packet definition.** Packet definitions are XTCE configuration documents that describe
   how to parse binary data into Python variables.

   ```python
   definition = spp.load_xtce("/path/to/xtce_definition.xml")
   ```

2. **Iterate over binary data.** You can load binary data from a file all at once, or continually
   read from a socket stream. To parse individual packets, iterate over that binary data to yield
   individual binary packet chunks one at a time. There is a built-in generator for CCSDS packets.
   Other binary packet generators can be used if your packets follow a different protocol from
   CCSDS (see [Packet Bytes Generators](user_guide/generators.md)).

   ```python
   for binary_packet in spp.ccsds_generator("/path/to/packet_file.ccsds"):
       print(binary_packet)
   ```

3. **Parse the binary packet data into a dictionary of parsed items.** With a definition (1) and a
   stream of individual packets (2), you can parse the contents of that binary data into Python
   objects. The packet definition defines a lookup structure based on `Parameter` names, which are
   returned as a Python dictionary of `{ParameterName: value}` items.

   ```python
   packet = definition.parse_bytes(binary_packet)
   print(packet)  # All items within the packet
   print(packet["my_uint8_param"])  # An individual item
   ```

## Quickstart Example

The script below is fully self-contained and copy-paste runnable: it builds a tiny XTCE
definition and a matching binary packet in memory, then parses the packet. It doesn't require
any external files, so it's a good way to confirm your installation works end to end.

```python
"""Self-contained quickstart: define, build, and parse a minimal CCSDS packet."""

import io
import struct

from space_packet_parser import load_xtce

# 1) A minimal XTCE definition, as an inline XML string.
#    It describes the 7 standard CCSDS primary header fields plus two
#    user data fields: an unsigned 16-bit integer and a 32-bit float.
XTCE_DEFINITION = """<?xml version="1.0" encoding="UTF-8"?>
<xtce:SpaceSystem name="QuickstartExample"
                   xmlns:xtce="http://www.omg.org/spec/XTCE/20180204"
                   xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                   xsi:schemaLocation="http://www.omg.org/spec/XTCE/20180204
                                       https://www.omg.org/spec/XTCE/20180204/SpaceSystem.xsd">
  <xtce:TelemetryMetaData>
    <xtce:ParameterTypeSet>
      <xtce:IntegerParameterType name="VERSION_Type" signed="false">
        <xtce:IntegerDataEncoding sizeInBits="3" encoding="unsigned"/>
      </xtce:IntegerParameterType>
      <xtce:IntegerParameterType name="TYPE_Type" signed="false">
        <xtce:IntegerDataEncoding sizeInBits="1" encoding="unsigned"/>
      </xtce:IntegerParameterType>
      <xtce:IntegerParameterType name="SEC_HDR_FLG_Type" signed="false">
        <xtce:IntegerDataEncoding sizeInBits="1" encoding="unsigned"/>
      </xtce:IntegerParameterType>
      <xtce:IntegerParameterType name="PKT_APID_Type" signed="false">
        <xtce:IntegerDataEncoding sizeInBits="11" encoding="unsigned"/>
      </xtce:IntegerParameterType>
      <xtce:IntegerParameterType name="SEQ_FLGS_Type" signed="false">
        <xtce:IntegerDataEncoding sizeInBits="2" encoding="unsigned"/>
      </xtce:IntegerParameterType>
      <xtce:IntegerParameterType name="SRC_SEQ_CTR_Type" signed="false">
        <xtce:IntegerDataEncoding sizeInBits="14" encoding="unsigned"/>
      </xtce:IntegerParameterType>
      <xtce:IntegerParameterType name="PKT_LEN_Type" signed="false">
        <xtce:IntegerDataEncoding sizeInBits="16" encoding="unsigned"/>
      </xtce:IntegerParameterType>
      <xtce:IntegerParameterType name="UINT16_Type" signed="false">
        <xtce:IntegerDataEncoding sizeInBits="16" encoding="unsigned"/>
      </xtce:IntegerParameterType>
      <xtce:FloatParameterType name="FLOAT32_Type">
        <xtce:FloatDataEncoding sizeInBits="32" encoding="IEEE754_1985"/>
      </xtce:FloatParameterType>
    </xtce:ParameterTypeSet>
    <xtce:ParameterSet>
      <xtce:Parameter name="VERSION" parameterTypeRef="VERSION_Type"/>
      <xtce:Parameter name="TYPE" parameterTypeRef="TYPE_Type"/>
      <xtce:Parameter name="SEC_HDR_FLG" parameterTypeRef="SEC_HDR_FLG_Type"/>
      <xtce:Parameter name="PKT_APID" parameterTypeRef="PKT_APID_Type"/>
      <xtce:Parameter name="SEQ_FLGS" parameterTypeRef="SEQ_FLGS_Type"/>
      <xtce:Parameter name="SRC_SEQ_CTR" parameterTypeRef="SRC_SEQ_CTR_Type"/>
      <xtce:Parameter name="PKT_LEN" parameterTypeRef="PKT_LEN_Type"/>
      <xtce:Parameter name="TEMPERATURE_RAW" parameterTypeRef="UINT16_Type"/>
      <xtce:Parameter name="VOLTAGE" parameterTypeRef="FLOAT32_Type"/>
    </xtce:ParameterSet>
    <xtce:ContainerSet>
      <xtce:SequenceContainer name="CCSDSPacket">
        <xtce:EntryList>
          <xtce:ParameterRefEntry parameterRef="VERSION"/>
          <xtce:ParameterRefEntry parameterRef="TYPE"/>
          <xtce:ParameterRefEntry parameterRef="SEC_HDR_FLG"/>
          <xtce:ParameterRefEntry parameterRef="PKT_APID"/>
          <xtce:ParameterRefEntry parameterRef="SEQ_FLGS"/>
          <xtce:ParameterRefEntry parameterRef="SRC_SEQ_CTR"/>
          <xtce:ParameterRefEntry parameterRef="PKT_LEN"/>
          <xtce:ParameterRefEntry parameterRef="TEMPERATURE_RAW"/>
          <xtce:ParameterRefEntry parameterRef="VOLTAGE"/>
        </xtce:EntryList>
      </xtce:SequenceContainer>
    </xtce:ContainerSet>
  </xtce:TelemetryMetaData>
</xtce:SpaceSystem>
"""

# 2) Build a minimal, valid CCSDS packet as raw bytes matching the definition
#    above: a 6-byte primary header followed by 6 bytes of user data
#    (an unsigned 16-bit integer and a 32-bit float).
apid = 100
sequence_count = 42
user_data = struct.pack(">Hf", 1234, 3.25)  # TEMPERATURE_RAW, VOLTAGE
packet_length = len(user_data) - 1  # CCSDS PKT_LEN = (user data bytes) - 1

first_header_word = (0 << 13) | (0 << 12) | (0 << 11) | apid  # VERSION, TYPE, SEC_HDR_FLG, PKT_APID
second_header_word = (0b11 << 14) | sequence_count  # SEQ_FLGS (unsegmented), SRC_SEQ_CTR
header = struct.pack(">HHH", first_header_word, second_header_word, packet_length)
packet_bytes = header + user_data

# 3) Load the XTCE definition and parse the packet.
packet_definition = load_xtce(io.BytesIO(XTCE_DEFINITION.encode("utf-8")))
packet = packet_definition.parse_bytes(packet_bytes)

print(packet)
print(f"Voltage: {packet['VOLTAGE']} V")
```

Running this script prints:

```text
{'VERSION': 0, 'TYPE': 0, 'SEC_HDR_FLG': 0, 'PKT_APID': 100, 'SEQ_FLGS': 3, 'SRC_SEQ_CTR': 42, 'PKT_LEN': 5, 'TEMPERATURE_RAW': 1234, 'VOLTAGE': 3.25}
Voltage: 3.25 V
```

## Working with Your Own Data

In practice, you'll load an XTCE definition and binary packet data from files rather than inline
strings. The snippet below shows that pattern — replace `my_packets.pkts` and
`my_xtce_document.xml` with paths to your own data before running it.

```python
from pathlib import Path
import space_packet_parser as spp

packet_file = Path("my_packets.pkts")
xtce_document = Path("my_xtce_document.xml")

# 1) Load the XTCE packet definition
packet_definition = spp.load_xtce(xtce_document)

# 2) Parse each packet from the binary file
with packet_file.open("rb") as binary_data:
    for packet_bytes in spp.ccsds_generator(binary_data):
        packet = packet_definition.parse_bytes(packet_bytes)
        print(packet["PKT_APID"])  # A single parsed parameter
        print(dict(packet))  # All parsed parameters, as a dict

# You can also introspect the packet definition itself
pt = packet_definition.parameter_types["MY_PARAM_Type"]  # look up a type
p = packet_definition.parameters["MY_PARAM"]  # look up a parameter
sc = packet_definition.containers["SecondaryHeaderContainer"]  # look up a container
# See the API docs for more on the ParameterType, Parameter, and SequenceContainer classes
```

## Next Steps

- Browse the [Examples](examples.md) for runnable, real-world scripts (Xarray datasets, packet
  filtering, socket streaming, and XTCE conversion from CSV).
- Read the [User Guide](user_guide/index.md) for a deeper dive into generators, parameter types,
  XTCE validation, error handling, and performance tuning.
- Try the [in-browser demo](browser_demo.md) to parse packets without installing anything.

We aim to provide examples of common usage patterns. If there's a specific example you'd like to
see, please open a GitHub Issue or Discussion.
