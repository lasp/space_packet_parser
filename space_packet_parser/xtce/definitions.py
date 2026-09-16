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
    DEFAULT_XTCE_VERSION,
    LEGACY_XTCE_XMLNS_ALIASES,
    STANDARD_XTCE_NS_PREFIX,
    STANDARD_XTCE_NSMAP,
    SUPPORTED_XTCE_VERSIONS,
    TIME_UNITS_BY_VERSION,
    XSI_NS_PREFIX,
    XSI_XMLNS,
    XTCE_VERSION_BY_XMLNS,
    XTCE_XSD_URL_BY_VERSION,
    containers,
    encodings,
    parameter_types,
    parameters,
    xtce_nsmap,
    xtce_uri_for_version,
    xtce_version_from_uri,
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


def _check_writable_xtce_version(version: str) -> None:
    """Raise unless an XTCE version is one this library can write a schema-validatable document for.

    Version *detection* is deliberately more permissive than version *selection*: a document using the
    XTCE 1.1 namespace is reported as 1.1 so that callers can see what they have, but no 1.1 schema is
    bundled, so writing a document that points at one would force a network fetch to validate.

    Parameters
    ----------
    version : str
        XTCE version string being selected as a serialization target.

    Raises
    ------
    ValueError
        If the version is not one of the fully supported versions.
    """
    if version not in SUPPORTED_XTCE_VERSIONS:
        raise ValueError(
            f"Cannot write XTCE version {version!r}. No schema for it is bundled with space_packet_parser, so the "
            f"resulting document could not be schema validated offline. Supported versions for writing are "
            f"{list(SUPPORTED_XTCE_VERSIONS)}."
        )


class XtcePacketDefinition(common.AttrComparable):
    """Object representation of the XTCE definition of a CCSDS packet object"""

    def __init__(
        self,
        container_set: Iterable[containers.SequenceContainer] | None = None,
        *,
        ns: dict | None = None,
        xtce_ns_prefix: str | None = STANDARD_XTCE_NS_PREFIX,
        xtce_standard_version: str | None = None,
        root_container_name: str = DEFAULT_ROOT_CONTAINER,
        space_system_name: str | None = None,
        space_system_type: str | None = None,
        asset_type: str | None = None,
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
        ns : Optional[dict]
            XML namespace mapping, expected as a dictionary with the keys being namespace labels and
            values being namespace URIs. If not given, it is derived from `xtce_standard_version` and
            `xtce_ns_prefix`, defaulting to {STANDARD_XTCE_NSMAP}. An empty dictionary indicates no namespace
            awareness, in which case `xtce_ns_prefix` must be None.
        xtce_ns_prefix : Optional[str]
            XTCE namespace prefix. Default {STANDARD_XTCE_NS_PREFIX}. This is the key for the XTCE namespace in the
            namespace mapping dictionary, `ns` and is used to write XML output when necessary. None binds the XTCE
            namespace as the document default namespace (unprefixed element names).
        xtce_standard_version : Optional[str]
            Version of the XTCE standard this definition is written against, one of
            {SUPPORTED_XTCE_VERSIONS}. This selects the XML namespace URI used when serializing, since the
            namespace URI is what identifies the XTCE version of a document. Mutually exclusive with `ns`:
            passing both raises ValueError, because when `ns` is given the version is inferred from the URI
            it binds to `xtce_ns_prefix`. Defaults to {DEFAULT_XTCE_VERSION}.
        root_container_name : str
            Name of root sequence container (where to start parsing)
        space_system_name : Optional[str]
            Name of space system to encode in XML when serializing.
        space_system_type : Optional[str]
            XTCE 1.3 `SpaceSystem/@systemType`: what part of a space enterprise this SpaceSystem represents,
            one of "asset", "assetGroup", "assetComponent" or "unknown". Added in XTCE 1.3; serializing a
            definition that sets it as XTCE 1.2 drops it, with a warning.
        asset_type : Optional[str]
            XTCE 1.3 `SpaceSystem/@assetType`: a free-form label for the kind of asset. Added in XTCE 1.3;
            treated the same as `space_system_type` when serializing as XTCE 1.2.
        validation_status : str
            One of ["Unknown", "Working", "Draft", "Test", "Validated", "Released", "Withdrawn"].
        xtce_version : str
            Free-form version descriptor for *this document*, written to the `version` attribute of the
            XTCE `Header` element. Per the XTCE XSD this is the document's own version, not the version of
            the XTCE standard; use `xtce_standard_version` for the latter. Default "1.0".
        date: Optional[str]
            Optional header date string.
        """
        if ns is None:
            target_version = xtce_standard_version or DEFAULT_XTCE_VERSION
            _check_writable_xtce_version(target_version)
            ns = xtce_nsmap(target_version, prefix=xtce_ns_prefix)
        elif xtce_standard_version is not None:
            raise ValueError(
                "Pass either ns or xtce_standard_version, not both. When ns is given, the XTCE version is "
                "inferred from the namespace URI it binds to xtce_ns_prefix."
            )
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
        self.space_system_type = space_system_type
        self.asset_type = asset_type
        self.validation_status = validation_status
        self.xtce_version = xtce_version
        self.date = date

    @property
    def xtce_standard_version(self) -> str | None:
        """Version of the XTCE standard this definition uses, as implied by its namespace URI.

        Returns
        -------
        : Optional[str]
            One of the supported XTCE versions ("1.2" or "1.3"), or None if this definition's XTCE
            namespace URI is not a standard OMG XTCE namespace (including the case of a definition
            with no namespace at all). A None value does not prevent parsing or serialization; it
            only means the XTCE version cannot be determined from the document.
        """
        return xtce_version_from_uri(self.xtce_ns_uri)

    @xtce_standard_version.setter
    def xtce_standard_version(self, version: str) -> None:
        """Retarget this definition at a different version of the XTCE standard.

        This rebinds the XTCE namespace URI (and the entry for it in the namespace mapping) to the
        standard URI for the requested version, which is what converts a document from one XTCE
        version to another. Almost all of the telemetry content this library reads and writes is
        identical across XTCE 1.2 and 1.3, so usually nothing else needs to change.

        Notes
        -----
        Element content is not translated, and a few constructs are version-specific:

        - Variable-length strings. XTCE 1.2 requires a declared raw buffer length and XTCE 1.3
          requires a `LeadingSize` or `TerminationChar`. Serializing warns if the definition holds a
          string encoding the target version's schema would reject.
        - Time units. The `units` attribute of a time parameter type's `Encoding` element comes from
          a version-specific enumeration: XTCE 1.2 spells it `picoSeconds`, 1.3 spells it
          `picoseconds` and adds values such as `milliseconds`, `minutes` and `hours`. Serializing
          warns rather than translating the unit, since the value is document content.
        - Name references. Parameter *names* could never contain a space in either version (1.2's
          `NameType` is `[^./:\\[\\] ]+`; 1.3 adds tab to the exclusions). What changed is the
          *reference* patterns: 1.2's single `NameReferenceType` permitted space and tab inside a
          reference path, while 1.3's four reference types exclude both and add `[n]` array
          subscript syntax. A reference containing a space is valid 1.2 but not valid 1.3.

        Parameters
        ----------
        version : str
            XTCE version string, one of the supported XTCE versions ("1.2" or "1.3").

        Raises
        ------
        ValueError
            If the version is unrecognized, or if this definition has no XTCE namespace to rebind.
        """
        _check_writable_xtce_version(version)
        uri = xtce_uri_for_version(version)
        if self.xtce_ns_uri is None:
            raise ValueError(
                "Cannot set xtce_standard_version on a definition with no XTCE namespace. Assign a namespace "
                "mapping to `ns` (and a matching `xtce_ns_prefix`) first."
            )
        if self.xtce_ns_uri not in self.ns.values():
            raise ValueError(
                f"Cannot set xtce_standard_version: this definition's XTCE namespace URI {self.xtce_ns_uri!r} is "
                f"not bound by its namespace mapping {self.ns!r}, so there is nothing to rebind. Assign a "
                f"consistent `ns` and `xtce_ns_uri` first."
            )
        self.ns = {prefix: (uri if u == self.xtce_ns_uri else u) for prefix, u in self.ns.items()}
        self.xtce_ns_uri = uri

    def _warn_on_version_incompatible_encodings(self) -> None:
        """Warn about content that is valid in one XTCE version but not in the version being written.

        Retargeting a definition at another XTCE version rewrites namespaces, not element content, so
        a definition can hold a construct the target version's schema rejects. Two cases actually
        bite:

        - Variable-length strings. XTCE 1.2 requires a declared buffer length (`DynamicValue` or
          `DiscreteLookupList`) and treats `LeadingSize`/`TerminationChar` as optional, while XTCE
          1.3 makes the buffer length optional and requires exactly one of them.
        - Time units. `Encoding/@units` on a time parameter type is drawn from a version-specific
          enumeration, so a unit valid in one version may not exist in the other.

        Either direction can therefore produce a document that fails schema validation. The unit is
        document content, so it is reported rather than translated.
        """
        version = self.xtce_standard_version
        if version not in SUPPORTED_XTCE_VERSIONS:
            return

        self._warn_on_incompatible_string_encodings(version)
        self._warn_on_incompatible_time_units(version)

    def _warn_on_incompatible_time_units(self, version: str) -> None:
        """Warn about time parameter types whose units the target XTCE version does not define.

        Parameters
        ----------
        version : str
            XTCE version being serialized.
        """
        permitted = TIME_UNITS_BY_VERSION[version]
        offenders = {}
        for parameter_type_name, parameter_type in self.parameter_types.items():
            if not isinstance(parameter_type, parameter_types.TimeParameterType):
                continue
            unit = parameter_type.unit
            # Units are optional, and a compound (tuple) unit is not expressible in the enumeration
            # at all, so only a plain string can be checked against it.
            if isinstance(unit, str) and unit not in permitted:
                offenders[parameter_type_name] = unit

        if not offenders:
            return

        warnings.warn(
            f"Serializing as XTCE {version}, but {len(offenders)} time parameter type(s) declare a unit that "
            f"XTCE {version} does not define: "
            f"{ {name: unit for name, unit in sorted(offenders.items())} }. Permitted units are "
            f"{sorted(permitted)}. Note that XTCE 1.2 and 1.3 spell some units differently (1.2 'picoSeconds' "
            f"vs 1.3 'picoseconds'). Unit strings are document content and are written unchanged, so the "
            f"document will be written as-is and will fail schema validation.",
            UserWarning,
        )

    def _warn_on_incompatible_string_encodings(self, version: str) -> None:
        """Warn about variable-length string encodings the target XTCE version's schema rejects.

        Parameters
        ----------
        version : str
            XTCE version being serialized.
        """
        offenders = []
        for parameter_type_name, parameter_type in self.parameter_types.items():
            encoding = getattr(parameter_type, "encoding", None)
            if not isinstance(encoding, encodings.StringDataEncoding) or encoding.fixed_length:
                continue
            has_declared_length = bool(encoding.dynamic_length_reference or encoding.discrete_lookup_length)
            has_delimiter = bool(encoding.leading_length_size or encoding.termination_character)
            if version == "1.3" and not has_delimiter:
                offenders.append(parameter_type_name)
            elif version == "1.2" and not has_declared_length:
                offenders.append(parameter_type_name)

        if not offenders:
            return

        if version == "1.3":
            detail = (
                "XTCE 1.3 requires a LeadingSize or TerminationChar element on a variable-length string, "
                "which these parameter types do not have. Set leading_length_size or termination_character "
                "on their encodings"
            )
        else:
            detail = (
                "XTCE 1.2 requires a DynamicValue or DiscreteLookupList element to declare the raw buffer "
                "length of a variable-length string, which these parameter types do not have. Set "
                "dynamic_length_reference or discrete_lookup_length on their encodings"
            )
        warnings.warn(
            f"Serializing as XTCE {version}, but {len(offenders)} parameter type(s) use a variable-length string "
            f"encoding that XTCE {version} does not allow: {sorted(offenders)}. {detail}, or serialize as the other "
            f"version. The document will be written as-is and will fail schema validation.",
            UserWarning,
        )

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
        self._warn_on_version_incompatible_encodings()

        nsmap = dict(self.ns)
        space_system_attrib = {}
        xtce_ns_uri = self.xtce_ns_uri

        # Documents written by space_packet_parser <= 6.2 carry an https XTCE 1.2 namespace URI that
        # no schema declares. Repair it on the way out rather than writing it back out unusable.
        if xtce_ns_uri in LEGACY_XTCE_XMLNS_ALIASES:
            canonical_uri = xtce_uri_for_version(LEGACY_XTCE_XMLNS_ALIASES[xtce_ns_uri])
            warnings.warn(
                f"XTCE namespace URI {xtce_ns_uri!r} is not the targetNamespace of any XTCE schema; documents "
                f"using it cannot be schema validated. It was written by space_packet_parser 6.2 and earlier. "
                f"Writing the canonical URI {canonical_uri!r} instead.",
                UserWarning,
            )
            nsmap = {prefix: (canonical_uri if u == xtce_ns_uri else u) for prefix, u in nsmap.items()}
            xtce_ns_uri = canonical_uri

        # Point the document at the XSD for the XTCE version implied by its namespace URI, so that
        # a serialized definition is schema-validatable without the reader having to supply an XSD.
        # We only do this for a recognized standard XTCE namespace; for a custom namespace URI we
        # have no schema to name and leave the attribute off.
        xsd_url = XTCE_XSD_URL_BY_VERSION.get(XTCE_VERSION_BY_XMLNS.get(xtce_ns_uri, ""))
        if xsd_url is not None:
            # xsi must be bound in the document in order to write an xsi:schemaLocation attribute.
            if XSI_XMLNS not in nsmap.values():
                nsmap[XSI_NS_PREFIX] = XSI_XMLNS
            space_system_attrib[f"{{{XSI_XMLNS}}}schemaLocation"] = f"{xtce_ns_uri} {xsd_url}"

        # ElementMaker element factory with predefined namespace and namespace mapping
        # The XTCE namespace actually defines the XTCE elements
        # The ns mapping just affects the serialization of XTCE elements
        # Both can be None, resulting in no namespace awareness
        elmaker = ElementMaker(namespace=xtce_ns_uri, nsmap=nsmap)

        if self.space_system_name:
            space_system_attrib["name"] = self.space_system_name

        # systemType and assetType were added to SpaceSystem in XTCE 1.3. Writing them into a 1.2
        # document would make it schema-invalid, so they are dropped there — but not silently, since
        # that loses metadata the source document carried.
        version_specific_attributes = {"systemType": self.space_system_type, "assetType": self.asset_type}
        set_version_specific = {name: value for name, value in version_specific_attributes.items() if value}
        if set_version_specific:
            if XTCE_VERSION_BY_XMLNS.get(xtce_ns_uri) == "1.2":
                warnings.warn(
                    f"Dropping {sorted(set_version_specific)} from the SpaceSystem element: these attributes were "
                    f"added in XTCE 1.3 and do not exist in XTCE 1.2, which this document is being serialized as. "
                    f"Serialize as XTCE 1.3 to keep them.",
                    UserWarning,
                )
            else:
                space_system_attrib.update(set_version_specific)

        header_attrib = {
            "date": self.date or datetime.now().isoformat(),
            "version": self.xtce_version,
            "validationStatus": self.validation_status,
        }

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

        # The XTCE namespace is whichever namespace the root SpaceSystem element is actually in, and
        # its prefix is whichever prefix that element is actually written with. Reading both off the
        # root element rather than guessing from the namespace mapping means any namespace URI works,
        # including the version-specific standard URIs (XTCE 1.2 and 1.3 differ) and the non-standard
        # URIs that real mission documents often use.
        xtce_ns_uri = ElementTree.QName(space_system).namespace
        xtce_ns_prefix = space_system.prefix

        if xtce_ns_uri is None:
            # No namespace is present (no xmlns attribute for XTCE).
            # Some XML documents do not use namespaces at all, which is invalid per the XTCE XSD and will fail XSD validation
            # We make an effort to parse these documents anyway, but warn the user
            warnings.warn(
                "No XTCE namespace found in the document. This is invalid per XSD, but will be parsed. "
                "Add an `xmlns` attribute to the root XML element to enable namespace awareness.",
                UserWarning,
            )
        elif xtce_version_from_uri(xtce_ns_uri) is None:
            logger.info(
                f"XTCE namespace URI {xtce_ns_uri!r} is not a standard OMG XTCE namespace "
                f"(expected one of {sorted(XTCE_VERSION_BY_XMLNS)}), so the XTCE version of this document "
                f"cannot be determined. The document will still be parsed."
            )

        # These change class attributes on the NamespaceAwareElement class,
        # which allow the XTCE parser to correctly handle namespaces when parsing (and serializing) elements later on
        xtce_element_class.set_ns_prefix(xtce_ns_prefix)
        xtce_element_class.set_nsmap(ns)

        header = space_system.find("Header")

        header_attrib = header.attrib if header is not None else {}
        date = header_attrib.get("date", None)
        # Header/@version is the document's own version descriptor, not the XTCE standard version
        # (which is carried by the namespace URI). Carry both header attributes through so that
        # reading a document and writing it back out preserves them.
        document_version = header_attrib.get("version", "1.0")
        validation_status = header_attrib.get("validationStatus", "Unknown")

        parameter_type_lookup = cls._parse_parameter_type_set(tree)
        parameters_lookup = cls._parse_parameter_set(tree, parameter_type_lookup)
        container_lookup = cls._parse_container_set(tree, parameters_lookup)

        xtce_definition = cls(
            container_set=list(container_lookup.values()),
            ns=ns,
            xtce_ns_prefix=xtce_ns_prefix,
            root_container_name=root_container_name,
            date=date,
            xtce_version=document_version,
            validation_status=validation_status,
            space_system_name=space_system.attrib.get("name", None),
            # XTCE 1.3-only root attributes. Absent from a 1.2 document, in which case they stay None
            # and nothing is written back out.
            space_system_type=space_system.attrib.get("systemType", None),
            asset_type=space_system.attrib.get("assetType", None),
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
            Name of the SequenceContainer to begin parsing from. Default is taken from the XtcePacketDefinition
            object, which uses "CCSDSPacket" unless configured otherwise. Any container in the definition may be
            used as the root; it does not need to begin with a CCSDS header, as XTCE has no notion of the CCSDS
            standard. Raises KeyError if the definition contains no container by this name.

        Returns
        -------
        space_packet_parser.SpacePacket
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
                    message = (
                        f"Detected an abstract container ({current_container.name}) with no valid inheritors by "
                        f"restriction criteria. This might mean this packet type is not accounted for in the "
                        f"provided packet definition."
                    )
                    # XTCE has no notion of the CCSDS standard, so a PKT_APID parameter is not guaranteed to exist.
                    # Report the APID when it is available because it is the most useful diagnostic for CCSDS
                    # packets, but never let the error report itself fail on a non-CCSDS definition.
                    if "PKT_APID" in packet:
                        message += f" APID={packet['PKT_APID']}."
                    elif isinstance(packet.binary_data, ccsds.CCSDSPacketBytes):
                        message += f" {packet.binary_data}."
                    raise UnrecognizedPacketTypeError(message, partial_data=packet)
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
            Name of the SequenceContainer to begin parsing from. Default is taken from the XtcePacketDefinition
            object, which uses "CCSDSPacket" unless configured otherwise. Any container in the definition may be
            used as the root; it does not need to begin with a CCSDS header, as XTCE has no notion of the CCSDS
            standard. Raises KeyError if the definition contains no container by this name.

        Returns
        -------
        space_packet_parser.SpacePacket
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
            Name of the SequenceContainer to begin parsing from. Default is taken from the XtcePacketDefinition
            object, which uses "CCSDSPacket" unless configured otherwise. Any container in the definition may be
            used as the root; it does not need to begin with a CCSDS header, as XTCE has no notion of the CCSDS
            standard. Raises KeyError if the definition contains no container by this name.

        Returns
        -------
        space_packet_parser.SpacePacket
            A SpacePacket object containing header and data attributes.
        """
        warnings.warn(
            "parse_ccsds_packet is deprecated and will be removed in a future release. "
            "Use the parse_packet method instead, XTCE has no notion of the ccsds standard.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.parse_packet(packet, root_container_name=root_container_name)
