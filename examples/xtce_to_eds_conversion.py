"""
This example demonstrates converting an in-memory XTCE packet definition (an
`space_packet_parser.xtce.definitions.XtcePacketDefinition` object) into a simplified rendering of the CCSDS
Electronic Data Sheets (EDS) format, described in CCSDS 876.0-B-1 (https://ccsds.org/Pubs/876x0b1.pdf).

This is the mirror image of `csv_to_xtce_conversion.py`, which builds an XTCE definition from a non-XTCE source
format. Here we go the other direction: take a fully built XTCE definition and translate its Parameter, ParameterType,
and SequenceContainer objects into EDS `DataType` and `ContainerDataType` elements.

Notes
-----
This is a demonstration of the *pattern* required to map between the two data models, not a complete or
schema-validated EDS implementation. Notably:

* XTCE calibrators, context-dependent match criteria, restriction criteria, and container inheritance
  do not have a direct 1:1 analog in EDS and are not handled here.
* EDS represents data types once, in a `DataTypeSet`, and containers reference them by name. This is very
  similar to how XTCE ParameterTypes work, which makes the ParameterType -> EDS DataType mapping the most
  natural part of the conversion.
* Real-world EDS documents nest `Package` elements, use `DataSheet`/`PackageFile` root elements, and support
  many more datatype variations (bit fields, alternate arrays, etc.) than are demonstrated here.

See also `eds_to_xtce_conversion.py` for the opposite direction (building an XTCE definition from an EDS file).
"""

from pathlib import Path

from lxml import etree as ElementTree
from lxml.builder import ElementMaker

from space_packet_parser.xtce import definitions, parameter_types

EDS_NS_URI = "http://www.ccsds.org/schema/sois/seds"
EM = ElementMaker(namespace=EDS_NS_URI, nsmap={None: EDS_NS_URI})


def _integer_encoding_to_eds(encoding_name: str) -> str:
    """Map an XTCE IntegerDataEncoding `encoding` attribute value to its closest EDS equivalent."""
    return {
        "unsigned": "unsigned",
        "signed": "twosComplement",
        "twosComplement": "twosComplement",
        "twosCompliment": "twosComplement",  # XTCE's historical (mis-spelled) spelling
    }.get(encoding_name, "unsigned")


def _parameter_type_to_eds_datatype(ptype: parameter_types.ParameterType) -> ElementTree.Element:
    """Convert a single XTCE ParameterType object into an EDS DataType element.

    Parameters
    ----------
    ptype : parameter_types.ParameterType
        The XTCE parameter type to convert.

    Returns
    -------
    : ElementTree.Element
        An EDS <IntegerDataType>, <FloatDataType>, <StringDataType>, or <BinaryDataType> element.
    """
    encoding = ptype.encoding

    if isinstance(ptype, parameter_types.IntegerParameterType):
        return EM.IntegerDataType(
            EM.IntegerDataEncoding(
                sizeInBits=str(encoding.size_in_bits),
                encoding=_integer_encoding_to_eds(encoding.encoding),
            ),
            name=ptype.name,
        )
    if isinstance(ptype, parameter_types.FloatParameterType):
        return EM.FloatDataType(
            EM.FloatDataEncoding(sizeInBits=str(encoding.size_in_bits), encodingAndPrecision=encoding.encoding),
            name=ptype.name,
        )
    if isinstance(ptype, parameter_types.StringParameterType):
        length_bits = encoding.fixed_raw_length
        string_datatype_kwargs = {"name": ptype.name}
        children = [EM.StringDataEncoding(encoding=encoding.encoding)]
        if length_bits is not None:
            children.append(EM.Length(fixedSizeInBits=str(length_bits)))
        return EM.StringDataType(*children, **string_datatype_kwargs)
    if isinstance(ptype, parameter_types.BinaryParameterType):
        # EDS has no first-class "binary blob" type, so we approximate one with a fixed size byte array,
        # which is a reasonably common convention.
        size_bits = getattr(encoding, "fixed_size_in_bits", None)
        attrs = {"name": ptype.name}
        if size_bits is not None:
            attrs["sizeInBits"] = str(size_bits)
        return EM.BinaryDataType(**attrs)

    raise NotImplementedError(f"No EDS conversion has been implemented for parameter type {type(ptype)}")


def xtce_to_eds(xtce_definition: definitions.XtcePacketDefinition, package_name: str = "CCSDS") -> ElementTree._Element:
    """Convert an XtcePacketDefinition object into a simplified EDS XML document.

    Parameters
    ----------
    xtce_definition : definitions.XtcePacketDefinition
        A fully constructed XTCE packet definition object (see `csv_to_xtce_conversion.py` for one way to build one).
    package_name : str
        Name to give the top level EDS <Package> element.

    Returns
    -------
    : ElementTree._Element
        The root <PackageFile> element of the generated EDS document.
    """
    datatype_elements = [_parameter_type_to_eds_datatype(ptype) for ptype in xtce_definition.parameter_types.values()]

    container_elements = []
    for sc in xtce_definition.containers.values():
        entries = [EM.Entry(name=entry.name, type=entry.parameter_type.name) for entry in sc.entry_list]
        container_elements.append(EM.ContainerDataType(EM.EntryList(*entries), name=sc.name))

    package = EM.Package(
        EM.DataTypeSet(*datatype_elements, *container_elements),
        name=package_name,
    )
    return EM.PackageFile(package)


if __name__ == "__main__":
    # Reuse the CSV -> XTCE example to get a fully-populated in-memory XTCE definition object to convert
    from csv_to_xtce_conversion import convert_ccsdspy_to_xtce

    script_dir = Path(__file__).parent.resolve()
    jpss_test_data_dir = script_dir / "../tests/test_data/jpss"
    xtce_definition = convert_ccsdspy_to_xtce(jpss_test_data_dir / "ccsdspy_jpss1_geolocation.csv")

    eds_root = xtce_to_eds(xtce_definition, package_name="JPSS_GEOLOCATION")
    eds_document = ElementTree.ElementTree(eds_root)
    print(ElementTree.tostring(eds_document, pretty_print=True, xml_declaration=True, encoding="utf-8").decode())
