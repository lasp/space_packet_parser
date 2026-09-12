# Variable Length Packet Fields

Flight software engineers often need to downlink data (usually binary blobs) of variable length.
The length of these fields is often specified in a _previous_ telemetry point in the same packet,
and you have to fetch the length by referencing that previous field. In some cases, the length is
implicit and must be computed from the overall packet length instead.

## Explicit Length

The length of the field is carried in an earlier parameter in the same packet, and the field's type
references that parameter.

### Explicit Length Example

Suppose the variable length field is called `SCI_DATA` and is a binary blob (e.g. of compressed
data). The length of this field is specified earlier in the packet in a field called
`SCI_DATA_BYTELEN`, given in number of bytes. To define the type for `SCI_DATA` in XTCE, you could
use the following (snippet):

```xml
<xtce:BinaryParameterType>
    <xtce:BinaryDataEncoding>
        <xtce:SizeInBits>
            <xtce:DynamicValue>
                <xtce:ParameterInstanceRef parameterRef="SCI_DATA_BYTELEN" useCalibratedValue="false"/>
                <xtce:LinearAdjustment intercept="0" slope="8"/>
            </xtce:DynamicValue>
        </xtce:SizeInBits>
    </xtce:BinaryDataEncoding>
</xtce:BinaryParameterType>
```

This tells the parser that the size in bits of data type `SCI_DATA_Type` (the type of `SCI_DATA`)
is the raw value encoded in the parameter `SCI_DATA_BYTELEN`, multiplied by 8 (to convert number of
bytes to number of bits).

## Implicit Length

In some circumstances, flight software teams define a packet field that simply fills up the
"remaining space" in the packet. The length of this field is usually implicit but can be computed
by subtracting the combined length of all fixed length fields in the packet from the total length
of the packet specified in the CCSDS header.

The `PKT_LEN` field is the length of the packet user data, in bytes. This field:

- counts from zero
- does not include the header data (always 6 bytes)

Thus, you can determine the length of your field dynamically from the packet length in the CCSDS
header:

$$len_{var} = 8 \times (len_{packet} + 1) - \sum_n len_{fixed,n}$$

where

- $len_{var}$ is the length, in bits, of the variable length field
- $len_{packet}$ is the packet user data length in bytes (from the CCSDS header)
- $\sum_n len_{fixed,n}$ is the combined length of all fixed length fields in the packet user data

There are some limitations to this. If your flight software team is violating these limitations,
they are making your life extremely difficult, and you have our condolences.

- You can only have a _single_ "remaining packet length" field in a given packet definition.
  Encoding more than one such field makes it impossible to determine the length of the fields.
- All other fields in the packet _must_ be fixed length. There is no way, within XTCE, to
  calculate a dynamic length that is an arbitrary function of multiple previous length specifier
  fields.

### Implicit Length Example

Packet Definition:

```text
"VERSION" : 3 bits
"TYPE" : 1 bits
"SEC_HDR_FLG" : 1 bits
"PKT_APID" : 11 bits
"SEQ_FLGS" : 2 bits
"SRC_SEQ_CTR" : 14 bits
"PKT_LEN" : 16 bits
"SHCOARSE" : 32 bits
"SID" : 8 bits
"SPIN" : 8 bits
"ABORTFLAG" : 1 bits
"STARTDELAY" : 15 bits
"COUNT" : 8 bits
"EVENTDATA": variable length
```

To calculate the length of `EVENTDATA`:

```{math}
len_{var} &= 8 \times (len_{packet} + 1) - (&&len_{SHCOARSE} + len_{SID} + len_{SPIN} + \\
          &                                 &&len_{ABORTFLAG} + len_{STARTDELAY} + len_{COUNT})\\
          &= 8 \times (len_{packet} + 1) - (&&32 + 8 + 8 + 1 + 15 + 8)\\
          &= 8 \times len_{packet} - 64     &&
```

This equation can be implemented in XTCE by referencing the packet length field as follows:

```xml
<xtce:BinaryParameterType name="EVENTDATA_Type" >
    <xtce:BinaryDataEncoding>
        <xtce:SizeInBits>
            <xtce:DynamicValue>
                <xtce:ParameterInstanceRef parameterRef="PKT_LEN"/>
                <xtce:LinearAdjustment intercept="-64" slope="8"/>
            </xtce:DynamicValue>
        </xtce:SizeInBits>
    </xtce:BinaryDataEncoding>
</xtce:BinaryParameterType>
```
