"""Module for parsing XTCE xml files to specify packet format"""

import logging
import warnings
from collections.abc import Iterable
from datetime import datetime
from os import PathLike
from pathlib import Path
from typing import TextIO

import lxml.etree as ElementTree
from lxml.builder import ElementMaker

import space_packet_parser as spp
from space_packet_parser import common
from space_packet_parser.exceptions import InvalidParameterTypeError, UnrecognizedPacketTypeError
from space_packet_parser.generators import ccsds
from space_packet_parser.xtce import (
    STANDARD_XTCE_NS_PREFIX,
    STANDARD_XTCE_NSMAP,
    containers,
    parameter_types,
    parameters,
)

logger = logging.getLogger(__name__)

DEFAULT_ROOT_CONTAINER = "CCSDSPacket"

TAG_NAME_TO_PARAMETER_TYPE_OBJECT: dict[str, type[parameter_types.ParameterType]] = {
    "StringParameterType": parameter_types.StringParameterType,
    "IntegerParameterType": parameter_types.IntegerParameterType,
    "FloatParameterType": parameter_types.FloatParameterType,
    "EnumeratedParameterType": parameter_types.EnumeratedParameterType,
    "BinaryParameterType": parameter_types.BinaryParameterType,
    "BooleanParameterType": parameter_types.BooleanParameterType,
    "AbsoluteTimeParameterType": parameter_types.AbsoluteTimeParameterType,
    "RelativeTimeParameterType": parameter_types.RelativeTimeParameterType,
}


class XtcePacketDefinition(common.AttrComparable):
    """Object representation of the XTCE definition of a CCSDS packet object"""

    def __init__(
        self,
        container_set: Iterable[containers.SequenceContainer] | None = None,
        *,
        ns: dict = STANDARD_XTCE_NSMAP,
        xtce_ns_prefix: str = STANDARD_XTCE_NS_PREFIX,
        root_container_name: str = DEFAULT_ROOT_CONTAINER,
        space_system_name: str | None = None,
        validation_status: str = "Unknown",
        xtce_version: str = "1.0",
        date: str | None = None,
    ):
        f"""

        Parameters
        ----------
        container_set : Optional[Iterable[containers.SequenceContainer]]
            Iterable of SequenceContainer objects, containing entry lists of Parameter objects, which contain their
            ParameterTypes. This is effectively the entire XTCE document in one list of objects. Every equivalent
            object in this object and its nested Parameter and ParameterType objects is expected to be the same object
            reference, which also requires all ParameterTypes, Parameters, and SequenceContainers to be unique by name.
            e.g. every Parameter object named `MY_PARAM` must be the same class instance.
        ns : dict
            XML namespace mapping, expected as a dictionary with the keys being namespace labels and
            values being namespace URIs. Default {STANDARD_XTCE_NSMAP}. An empty dictionary indicates no namespace
            awareness, in which case `xtce_ns_prefix` must be None.
        xtce_ns_prefix : str
            XTCE namespace prefix. Default {STANDARD_XTCE_NS_PREFIX}. This is the key for the XTCE namespace in the
            namespace mapping dictionary, `ns` and is used to write XML output when necessary.
        root_container_name : str
            Name of root sequence container (where to start parsing)
        space_system_name : Optional[str]
            Name of space system to encode in XML when serializing.
        validation_status : str
            One of ["Unknown", "Working", "Draft", "Test", "Validated", "Released", "Withdrawn"].
        xtce_version : str
            Default "1.0"
        date: Optional[str]
            Optional header date string.
        """
        if isinstance(container_set, (str, Path)):
            raise TypeError(
                "container_set must be an iterable of SequenceContainer objects. "
                "To instantiate an XtcePacketDefinition from an XTCE XML file, use "
                "XtcePacketDefinition.from_xtce() instead."
            )
        if xtce_ns_prefix is not None and xtce_ns_prefix not in ns:
            raise ValueError(
                f"XTCE namespace prefix {xtce_ns_prefix=} not in namespace mapping {ns=}. If the "
                f"namespace prefix is not 'None', it must appear as a key in the namespace mapping dict."
            )

        self.parameter_types: dict[str, parameter_types.ParameterType] = {}
        self.parameters: dict[str, parameters.Parameter] = {}
        self.containers: dict[str, containers.SequenceContainer] = {}

        def _update_caches(sc: containers.SequenceContainer) -> None:
            """Iterate through a SequenceContainer, updating internal caches with all Parameter, ParameterType,
            and SequenceContainer objects, ensuring that a key (object name) only references a single object.

            Notes
            -----
            This catches cases where, e.g. a Parameter element has been parsed twice, resulting in two Parameter
            objects which are "equal" but not the same memory reference.

            Parameters
            ----------
            sc : containers.SequenceContainer
                The SequenceContainer to iterate through.
            """
            self.containers[sc.name] = sc
            for entry in sc.entry_list:
                if isinstance(entry, containers.SequenceContainer):
                    _update_caches(entry)  # recurse
                elif isinstance(entry, parameters.Parameter):
                    self.parameters[entry.name] = entry
                    self.parameter_types[entry.parameter_type.name] = entry.parameter_type

        # Populate the three caches for easy lookup later.
        if container_set:
            for sequence_container in container_set:
                _update_caches(sequence_container)

        self.ns = ns  # Default ns dict used when creating XML elements
        # If the ns dict exists but xtce_ns_prefix is not in it
        # (including the None key representing a default namespace),
        # we assume the document is using no namespace awareness.
        self.xtce_ns_uri = ns[xtce_ns_prefix] if ns and xtce_ns_prefix in ns else None  # XTCE namespace URI
        self.xtce_ns_prefix = (
            xtce_ns_prefix  # This is basically an alias to the ns URI (not to be confused with the XSD schema URL)
        )
        self.root_container_name = root_container_name
        self.space_system_name = space_system_name
        self.validation_status = validation_status
        self.xtce_version = xtce_version
        self.date = date

    def write_xml(self, filepath: str | Path) -> None:
        """Write out the XTCE XML for this packet definition object to the specified path

        Parameters
        ----------
        filepath : Union[str, Path]
            Location to write this packet definition
        """
        self.to_xml_tree().write(Path(filepath).absolute(), pretty_print=True, xml_declaration=True, encoding="utf-8")

    def to_xml_tree(self) -> ElementTree.ElementTree:
        """Initializes and returns an ElementTree object based on parameter type, parameter, and container information

        Returns
        -------
        : ElementTree.ElementTree
        """
        if self.xtce_ns_uri not in self.ns.values():
            warnings.warn(
                "No XTCE namespace defined. This is invalid per XSD, but will be serialized. "
                "Ensure mydef.xtce_ns_prefix is a key in mydef.ns for valid XTCE output.",
                UserWarning,
            )
        # ElementMaker element factory with predefined namespace and namespace mapping
        # The XTCE namespace actually defines the XTCE elements
        # The ns mapping just affects the serialization of XTCE elements
        # Both can be None, resulting in no namespace awareness
        elmaker = ElementMaker(namespace=self.xtce_ns_uri, nsmap=self.ns)

        space_system_attrib = {}
        if self.space_system_name:
            space_system_attrib["name"] = self.space_system_name

        header_attrib = {
            "date": self.date or datetime.now().isoformat(),
            "version": self.xtce_version,
            "validationStatus": self.validation_status,
        }

        # TODO: Ensure XSI namespace and XSD reference are written to the root element
        tree = ElementTree.ElementTree(
            elmaker.SpaceSystem(
                elmaker.Header(**header_attrib),
                elmaker.TelemetryMetaData(
                    elmaker.ParameterTypeSet(
                        *(ptype.to_xml(elmaker=elmaker) for ptype in self.parameter_types.values()),
                    ),
                    elmaker.ParameterSet(
                        *(param.to_xml(elmaker=elmaker) for param in self.parameters.values()),
                    ),
                    elmaker.ContainerSet(
                        *(sc.to_xml(elmaker=elmaker) for sc in self.containers.values()),
                    ),
                ),
                **space_system_attrib,
            )
        )

        return tree

    @classmethod
    def from_xtce(
        cls,
        xtce_document: str | Path | PathLike | TextIO,
        *,
        root_container_name: str = DEFAULT_ROOT_CONTAINER,
    ) -> "XtcePacketDefinition":
        f"""Instantiate an object representation of a CCSDS packet definition,
        according to a format specified in an XTCE XML document.

        Notes
        -----
        This classmethod first parses the ParameterTypeSet element to build a dict of all ParameterType objects,
        keyed on the name of the parameter type.
        Then it parses the ParameterSet element to build a dict of all named Parameter objects, keyed on the
        name of the parameter.
        Lastly, it parses each SequenceContainer element in ContainerSet element to build a dict of all
        SequenceContainer objects, keyed on the name of the sequence container.
        Extensive checking during parsing ensures that there is only a single object reference for each ParameterType,
        Parameter, and SequenceContainer.

        Parameters
        ----------
        xtce_document : Union[str, PathLike, TextIO]
            Path to XTCE XML document containing packet definition.
        root_container_name : str
            Optional override to the root container name. Default is {DEFAULT_ROOT_CONTAINER}.
        """
        # Define a namespace and prefix aware Element subclass so that we don't have to pass the namespace
        # into every from_xml method
        xtce_element_class = common.NamespaceAwareElement
        xtce_element_lookup = ElementTree.ElementDefaultClassLookup(element=xtce_element_class)
        xtce_parser = ElementTree.XMLParser()
        xtce_parser.set_element_class_lookup(xtce_element_lookup)

        tree = ElementTree.parse(xtce_document, parser=xtce_parser)  # noqa: S320

        space_system = tree.getroot()
        ns = space_system.nsmap

        # Search nsmap dict for the XTCE namespace prefix, if present (may be absent)
        possible_prefixes = [pre for pre, uri in ns.items() if "xtce" in uri.lower()]

        if len(possible_prefixes) == 1:
            # Exactly one namespace (possibly prefixed) that looks like XTCE
            xtce_ns_prefix = possible_prefixes[0]
        elif len(possible_prefixes) == 0:
            # This indicates no namespace is present (no xmlns attribute for XTCE)
            # Some XML documents do not use namespaces at all, which is invalid per the XTCE XSD and will fail XSD validation
            # We make an effort to parse these documents anyway, but warn the user
            xtce_ns_prefix = None
            warnings.warn(
                "No XTCE namespace found in the document. This is invalid per XSD, but will be parsed. "
                "Add an `xmlns` attribute to the root XML element to enable namespace awareness.",
                UserWarning,
            )
        else:
            # If there are multiple namespaces that look like XTCE, we cannot determine which one to use
            raise ValueError(f"Multiple XTCE namespace prefixes found in the document: {possible_prefixes}. ")

        # These change class attributes on the NamespaceAwareElement class,
        # which allow the XTCE parser to correctly handle namespaces when parsing (and serializing) elements later on
        xtce_element_class.set_ns_prefix(xtce_ns_prefix)
        xtce_element_class.set_nsmap(ns)

        header = space_system.find("Header")

        if header is not None:
            date = header.attrib.get("date", None)
        else:
            date = None

        parameter_type_lookup = cls._parse_parameter_type_set(tree)
        parameters_lookup = cls._parse_parameter_set(tree, parameter_type_lookup)
        container_lookup = cls._parse_container_set(tree, parameters_lookup)

        xtce_definition = cls(
            container_set=list(container_lookup.values()),
            ns=ns,
            xtce_ns_prefix=xtce_ns_prefix,
            root_container_name=root_container_name,
            date=date,
            space_system_name=space_system.attrib.get("name", None),
        )

        return xtce_definition

    @staticmethod
    def _parse_container_set(
        tree: ElementTree.Element, parameter_lookup: dict[str, parameters.Parameter]
    ) -> dict[str, containers.SequenceContainer]:
        """Parse the <xtce:ContainerSet> element into a dictionary of SequenceContainer objects

        Parameters
        ----------
        tree : ElementTree.Element
            Full XTCE tree
        parameter_lookup : dict[str, parameters.Parameter]
            Parameters that are contained in container entry lists

        Returns
        -------
        : dict[str, containers.SequenceContainer]
        """
        # This lookup dict is mutated as a side effect by SequenceContainer parsing methods
        container_lookup: dict[str, containers.SequenceContainer] = {}
        container_set_element = tree.getroot().find("TelemetryMetaData/ContainerSet")
        for sequence_container_element in container_set_element.iterfind("*"):
            sequence_container = containers.SequenceContainer.from_xml(
                sequence_container_element,
                tree=tree,
                parameter_lookup=parameter_lookup,
                container_lookup=container_lookup,
            )

            if sequence_container.name not in container_lookup:
                container_lookup[sequence_container.name] = sequence_container
            elif container_lookup[sequence_container.name] == sequence_container:
                continue
            else:
                raise ValueError(
                    f"Found duplicate sequence container name "
                    f"{sequence_container.name} for two non-equal "
                    f"sequence containers. Sequence container names are expected to be unique."
                )

        # Back-populate the list of inheritors for each container
        for name, sc in container_lookup.items():
            if sc.base_container_name:
                container_lookup[sc.base_container_name].inheritors.append(name)

        return container_lookup

    @staticmethod
    def _parse_parameter_type_set(tree: ElementTree.ElementTree) -> dict[str, parameter_types.ParameterType]:
        """Parse the <xtce:ParameterTypeSet> into a dictionary of ParameterType objects

        Parameters
        ----------
        tree : ElementTree.ElementTree
            Full XTCE tree

        Returns
        -------
        : dict[str, parameters.ParameterType]
        """
        parameter_type_dict = {}
        parameter_type_set_element = tree.getroot().find("TelemetryMetaData/ParameterTypeSet")
        for parameter_type_element in parameter_type_set_element.iterfind("*"):
            try:
                parameter_type_class: type[parameter_types.ParameterType] = TAG_NAME_TO_PARAMETER_TYPE_OBJECT[
                    ElementTree.QName(parameter_type_element).localname
                ]
            except KeyError as e:
                if (
                    "ArrayParameterType" in parameter_type_element.tag
                    or "AggregateParameterType" in parameter_type_element.tag
                ):
                    raise NotImplementedError(
                        f"Unsupported parameter type {parameter_type_element.tag}. "
                        "Supporting this parameter type is in the roadmap but has "
                        "not yet been implemented."
                    ) from e
                raise InvalidParameterTypeError(
                    f"Invalid parameter type {parameter_type_element.tag}. "
                    "If you believe this is a valid XTCE parameter type, "
                    "please open a feature request as a Github issue with a "
                    "reference to the XTCE element description for the "
                    "parameter type element."
                ) from e
            parameter_type_object = parameter_type_class.from_xml(parameter_type_element)
            if parameter_type_object.name in parameter_type_dict:
                raise ValueError(
                    f"Found duplicate parameter type {parameter_type_object.name}. "
                    f"Parameter types names are expected to be unique"
                )
            parameter_type_dict[parameter_type_object.name] = parameter_type_object  # Add to cache

        return parameter_type_dict

    @staticmethod
    def _parse_parameter_set(
        tree: ElementTree.ElementTree, parameter_type_lookup: dict[str, parameter_types.ParameterType]
    ) -> dict[str, parameters.Parameter]:
        """Parse an <xtce:ParameterSet> object into a dictionary of Parameter objects

        Parameters
        ----------
        tree : ElementTree.ElementTree
            Full XTCE tree
        parameter_type_lookup : dict[str, parameter_types.ParameterType]
            Parameter types referenced by parameters.

        Returns
        -------
        : dict[str, parameters.Parameter]
        """
        parameter_lookup = {}
        parameter_set_element = tree.getroot().find("TelemetryMetaData/ParameterSet")
        for parameter_element in parameter_set_element.iterfind("*"):
            parameter_object = parameters.Parameter.from_xml(
                parameter_element, parameter_type_lookup=parameter_type_lookup
            )

            if parameter_object.name in parameter_lookup:
                raise ValueError(
                    f"Found duplicate parameter name {parameter_object.name}. Parameters are expected to be unique"
                )

            parameter_lookup[parameter_object.name] = parameter_object  # Add to cache

        return parameter_lookup

    def parse_bytes(self, binary_data: bytes, *, root_container_name: str | None = None) -> spp.SpacePacket:
        """Parse binary packet data according to the self.packet_definition object

        Parameters
        ----------
        binary_data : bytes
            Binary representation of the packet used to get the coming bits and any previously parsed data items to
            infer field lengths.
        root_container_name : Optional[str]
            Default is taken from the XtcePacketDefinition object. Any root container may be specified, but it must
            begin with the definition of a CCSDS header in order to parse correctly.

        Returns
        -------
        SpacePacket
            A SpacePacket object containing header and data attributes.
        """
        packet = spp.SpacePacket(binary_data=binary_data)

        _root_container_name: str = root_container_name or self.root_container_name
        current_container: containers.SequenceContainer = self.containers[_root_container_name]
        while True:
            current_container.parse(packet)

            valid_inheritors = []
            for inheritor_name in current_container.inheritors:
                if all(rc.evaluate(packet) for rc in self.containers[inheritor_name].restriction_criteria):
                    valid_inheritors.append(inheritor_name)

            if len(valid_inheritors) == 1:
                # Set the unique valid inheritor as the next current_container
                current_container = self.containers[valid_inheritors[0]]
                continue

            if len(valid_inheritors) == 0:
                if current_container.abstract:
                    raise UnrecognizedPacketTypeError(
                        f"Detected an abstract container with no valid inheritors by restriction criteria. "
                        f"This might mean this packet type is not accounted for in the provided packet definition. "
                        f"APID={packet['PKT_APID']}.",
                        partial_data=packet,
                    )
                break

            raise UnrecognizedPacketTypeError(
                f"Multiple valid inheritors, {valid_inheritors} are possible for {current_container}.",
                partial_data=packet,
            )
        if packet._parsing_pos != len(packet.binary_data) * 8:
            message = (
                f"Number of bits parsed ({packet._parsing_pos}b) did not match "
                + f"the length of data available ({len(packet.binary_data) * 8}b)."
            )
            if isinstance(packet.binary_data, ccsds.CCSDSPacketBytes):
                # Add in the CCSDS Header printout
                message += f" {packet.binary_data}."
            warnings.warn(message)
        return packet

    def parse_packet(self, packet: spp.SpacePacket, *, root_container_name: str | None = None) -> spp.SpacePacket:
        """Parse binary packet data according to the self.packet_definition object

        Parameters
        ----------
        packet: space_packet_parser.SpacePacket
            Binary representation of the packet used to get the coming bits and any
            previously parsed data items to infer field lengths.
        root_container_name : Optional[str]
            Default is taken from the XtcePacketDefinition object. Any root container may be specified, but it must
            begin with the definition of a CCSDS header in order to parse correctly.

        Returns
        -------
        SpacePacket
            A SpacePacket object containing header and data attributes.
        """
        warnings.warn(
            "parse_packet is deprecated and will be removed in a future release. "
            "Use the parse_bytes method instead, XTCE has no notion of the ccsds standard.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.parse_bytes(packet.binary_data, root_container_name=root_container_name)

    def parse_ccsds_packet(self, packet: spp.SpacePacket, *, root_container_name: str | None = None) -> spp.SpacePacket:
        """Parse binary packet data according to the self.packet_definition object

        Parameters
        ----------
        packet: space_packet_parser.SpacePacket
            Binary representation of the packet used to get the coming bits and any
            previously parsed data items to infer field lengths.
        root_container_name : Optional[str]
            Default is taken from the XtcePacketDefinition object. Any root container may be specified, but it must
            begin with the definition of a CCSDS header in order to parse correctly.

        Returns
        -------
        SpacePacket
            A SpacePacket object containing header and data attributes.
        """
        warnings.warn(
            "parse_ccsds_packet is deprecated and will be removed in a future release. "
            "Use the parse_packet method instead, XTCE has no notion of the ccsds standard.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.parse_packet(packet, root_container_name=root_container_name)
