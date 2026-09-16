"""
This example demonstrates the opposite direction of `xtce_to_eds_conversion.py`: starting from a (contrived, simple)
CCSDS Electronic Data Sheets (EDS) document, described in CCSDS 876.0-B-1 (https://ccsds.org/Pubs/876x0b1.pdf), and
building an in-memory `space_packet_parser.xtce.definitions.XtcePacketDefinition` object that can be used to parse
packets.

This is not a complete or general-purpose EDS parser. It demonstrates the pattern for mapping EDS `DataType` and
`ContainerDataType` elements onto the Space Packet Parser XTCE object model (Parameters, ParameterTypes, and
SequenceContainers), for a small, hand-crafted example EDS file with a single container and a handful of scalar
data types. Real-world EDS documents can be much richer (nested packages, arrays, bit fields, generic types, etc.)
and would need a considerably more complete converter to import in general.

See `tests/test_data/eds/contrived_ccsds_packet.xml` for the example EDS document used here.
"""

import struct
from pathlib import Path

from lxml import etree as ElementTree

from space_packet_parser.xtce import containers, definitions, encodings, parameter_types, parameters

EDS_NS = {"eds": "http://www.ccsds.org/schema/sois/seds"}


def _eds_datatype_to_parameter_type(element: ElementTree.Element) -> parameter_types.ParameterType:
    """Convert a single EDS `*DataType` element into an XTCE ParameterType object.

    Parameters
    ----------
    element : ElementTree.Element
        One of <IntegerDataType>, <FloatDataType>, <StringDataType>, or <BinaryDataType>.

    Returns
    -------
    : parameter_types.ParameterType
    """
    name = element.attrib["name"]
    tag = ElementTree.QName(element).localname

    if tag == "IntegerDataType":
        encoding_element = element.find("eds:IntegerDataEncoding", namespaces=EDS_NS)
        size_in_bits = int(encoding_element.attrib["sizeInBits"])
        eds_encoding = encoding_element.attrib.get("encoding", "unsigned")
        # XTCE only recognizes a specific set of encoding strings, so map the EDS value onto one of those.
        xtce_encoding = "unsigned" if eds_encoding == "unsigned" else "twosComplement"
        return parameter_types.IntegerParameterType(
            name=name,
            encoding=encodings.IntegerDataEncoding(size_in_bits=size_in_bits, encoding=xtce_encoding),
        )

    if tag == "FloatDataType":
        encoding_element = element.find("eds:FloatDataEncoding", namespaces=EDS_NS)
        size_in_bits = int(encoding_element.attrib["sizeInBits"])
        return parameter_types.FloatParameterType(
            name=name, encoding=encodings.FloatDataEncoding(size_in_bits=size_in_bits)
        )

    if tag == "StringDataType":
        length_element = element.find("eds:Length", namespaces=EDS_NS)
        fixed_raw_length = int(length_element.attrib["fixedSizeInBits"])
        return parameter_types.StringParameterType(
            name=name, encoding=encodings.StringDataEncoding(fixed_raw_length=fixed_raw_length)
        )

    if tag == "BinaryDataType":
        size_in_bits = int(element.attrib["sizeInBits"])
        return parameter_types.BinaryParameterType(
            name=name, encoding=encodings.BinaryDataEncoding(fixed_size_in_bits=size_in_bits)
        )

    raise NotImplementedError(f"No XTCE conversion has been implemented for EDS data type <{tag}>")


def eds_to_xtce(eds_path: Path, root_container_name: str) -> definitions.XtcePacketDefinition:
    """Parse a (contrived, simplified) EDS XML document and build an XtcePacketDefinition object from it.

    Parameters
    ----------
    eds_path : Path
        Path to the EDS XML file.
    root_container_name : str
        Name of the EDS <ContainerDataType> to use as the root container when parsing packets.

    Returns
    -------
    : definitions.XtcePacketDefinition
    """
    tree = ElementTree.parse(eds_path)
    root = tree.getroot()

    datatype_set = root.find(".//eds:DataTypeSet", namespaces=EDS_NS)

    # Build every scalar ParameterType first, keyed by name, so container entries can reference them.
    parameter_types_by_name = {}
    for datatype_element in datatype_set:
        tag = ElementTree.QName(datatype_element).localname
        if tag == "ContainerDataType":
            continue  # Containers are handled separately, below, once all ParameterTypes are known.
        parameter_types_by_name[datatype_element.attrib["name"]] = _eds_datatype_to_parameter_type(datatype_element)

    sequence_containers = []
    for container_element in datatype_set.findall("eds:ContainerDataType", namespaces=EDS_NS):
        entry_list_element = container_element.find("eds:EntryList", namespaces=EDS_NS)
        entry_parameters = [
            parameters.Parameter(
                name=entry.attrib["name"], parameter_type=parameter_types_by_name[entry.attrib["type"]]
            )
            for entry in entry_list_element.findall("eds:Entry", namespaces=EDS_NS)
        ]
        sequence_containers.append(
            containers.SequenceContainer(name=container_element.attrib["name"], entry_list=entry_parameters)
        )

    return definitions.XtcePacketDefinition(sequence_containers, root_container_name=root_container_name)


if __name__ == "__main__":
    script_dir = Path(__file__).parent.resolve()
    eds_path = script_dir / "../tests/test_data/eds/contrived_ccsds_packet.xml"

    xtce_definition = eds_to_xtce(eds_path, root_container_name="ContrivedPacket")

    # Build a single, contrived packet matching the ContrivedPacket definition above and parse it to demonstrate
    # that the resulting XtcePacketDefinition object is fully functional.
    header = (0b000_0_0_00000000001).to_bytes(2, byteorder="big") + (0b00_00000000000000).to_bytes(2, byteorder="big")
    packet_length = (0b0000000000000010).to_bytes(2, byteorder="big")  # unused/ignored by this example
    temperature_raw = (-42).to_bytes(2, byteorder="big", signed=True)
    voltage = struct.pack(">f", 3.3)
    mode = b"IDLE"
    binary_data = header + packet_length + temperature_raw + voltage + mode

    packet = xtce_definition.parse_bytes(binary_data)
    print(packet)
