"""Module with XTCE models related to SequenceContainers"""

import warnings
from dataclasses import dataclass, field
from typing import Any, Union

from lxml import etree as ElementTree
from lxml.builder import ElementMaker

import space_packet_parser as spp
from space_packet_parser import common
from space_packet_parser.exceptions import ElementNotFoundError
from space_packet_parser.xtce import comparisons, parameter_types, parameters


@dataclass
class ParameterRefEntry(common.Parseable, common.XmlObject):
    """<xtce:ParameterRefEntry>

    Represents a reference to a parameter in an EntryList, with optional conditional inclusion
    and repeat logic.

    Parameters
    ----------
    parameter_ref : str
        Name reference to the Parameter
    include_condition : Optional[comparisons.MatchCriteria]
        Condition for inclusion. If None, parameter is always included.
    repeat_entry : Optional[Any]
        Repeat information. Not currently supported - will raise NotImplementedError during parse.
    """

    parameter_ref: str
    include_condition: Optional[comparisons.MatchCriteria] = None
    repeat_entry: Optional[Any] = None

    def parse(self, packet: spp.SpacePacket, parameter_lookup: dict[str, parameters.Parameter]) -> None:
        """Parse the parameter reference entry, handling conditional inclusion.

        Parameters
        ----------
        packet : spp.SpacePacket
            The packet being parsed
        parameter_lookup : dict[str, parameters.Parameter]
            Dictionary to look up parameter objects by name

        Raises
        ------
        NotImplementedError
            If RepeatEntry is specified
        KeyError
            If the referenced parameter is not found in parameter_lookup
        """
        # Check if repeat_entry is specified
        if self.repeat_entry is not None:
            raise NotImplementedError("RepeatEntry is not currently supported in parsing")

        # Evaluate include condition if it exists
        if self.include_condition is not None:
            if not self.include_condition.evaluate(packet):
                # Condition is False, skip this parameter
                return

        # Parse the parameter
        try:
            parameter = parameter_lookup[self.parameter_ref]
        except KeyError as err:
            raise KeyError(
                f"Parameter '{self.parameter_ref}' referenced in ParameterRefEntry not found in parameter lookup. "
                f"Available parameters: {list(parameter_lookup.keys())}"
            ) from err
        parameter.parse(packet)

    @classmethod
    def from_xml(
        cls,
        element: ElementTree.Element,
        *,
        tree: Optional[ElementTree.ElementTree] = None,
        parameter_lookup: Optional[dict[str, parameters.Parameter]] = None,
        parameter_type_lookup: Optional[dict[str, parameter_types.ParameterType]] = None,
        container_lookup: Optional[dict[str, Any]] = None,
    ) -> "ParameterRefEntry":
        """Create a ParameterRefEntry from an XML element.

        Parameters
        ----------
        element : ElementTree.Element
            The ParameterRefEntry XML element
        tree : Optional[ElementTree.ElementTree]
            Full XTCE tree
        parameter_lookup : Optional[dict[str, parameters.Parameter]]
            Ignored
        parameter_type_lookup : Optional[dict[str, parameter_types.ParameterType]]
            Ignored
        container_lookup : Optional[dict[str, Any]]
            Ignored

        Returns
        -------
        : ParameterRefEntry
        """
        parameter_ref = element.attrib["parameterRef"]

        # Parse optional IncludeCondition
        include_condition = None
        if (include_cond_elem := element.find("IncludeCondition")) is not None:
            # IncludeCondition contains a single MatchCriteria element (Comparison, ComparisonList, or BooleanExpression)
            if (comparison_list_elem := include_cond_elem.find("ComparisonList")) is not None:
                # ComparisonList contains multiple Comparison elements with AND semantics per XTCE spec
                # Note: The existing restriction_criteria uses the same pattern (iterfind("*"))
                # to iterate over Comparison elements in a ComparisonList
                comparisons_list = [
                    comparisons.Comparison.from_xml(comp) for comp in comparison_list_elem.iterfind("*")
                ]
                # LIMITATION: MatchCriteria interface expects a single object, but ComparisonList
                # requires AND logic across multiple comparisons. For now, we only support single
                # comparisons in ComparisonList. Full AND logic would require a new MatchCriteria
                # subclass or modifying include_condition to accept a list of MatchCriteria.
                # This follows the same limitation pattern used in restriction_criteria where
                # multiple MatchCriteria are stored in a list on the SequenceContainer itself.
                if len(comparisons_list) == 1:
                    include_condition = comparisons_list[0]
                else:
                    # For multiple comparisons, warn and use only the first one
                    warnings.warn(
                        f"ComparisonList with {len(comparisons_list)} comparisons in IncludeCondition "
                        f"for parameter '{parameter_ref}'. Only the first comparison will be evaluated. "
                        f"Full AND logic for ComparisonList in IncludeCondition requires architectural "
                        f"changes to support multiple MatchCriteria conditions.",
                        UserWarning,
                    )
                    include_condition = comparisons_list[0] if comparisons_list else None
            elif (comparison_elem := include_cond_elem.find("Comparison")) is not None:
                include_condition = comparisons.Comparison.from_xml(comparison_elem)
            elif (bool_expr_elem := include_cond_elem.find("BooleanExpression")) is not None:
                include_condition = comparisons.BooleanExpression.from_xml(bool_expr_elem)

        # Parse optional RepeatEntry
        repeat_entry = None
        if element.find("RepeatEntry") is not None:
            # We'll store a placeholder to indicate it was present
            repeat_entry = True  # Will cause NotImplementedError during parse

        return cls(
            parameter_ref=parameter_ref,
            include_condition=include_condition,
            repeat_entry=repeat_entry,
        )

    def to_xml(self, *, elmaker: ElementMaker) -> ElementTree.Element:
        """Create a ParameterRefEntry XML element.

        Parameters
        ----------
        elmaker : ElementMaker
            Element factory with predefined namespace

        Returns
        -------
        : ElementTree.Element
        """
        entry = elmaker.ParameterRefEntry(parameterRef=self.parameter_ref)

        if self.include_condition is not None:
            include_cond = elmaker.IncludeCondition(self.include_condition.to_xml(elmaker=elmaker))
            entry.append(include_cond)

        if self.repeat_entry is not None:
            # Placeholder for RepeatEntry serialization
            # Since we don't fully parse it, we can't fully serialize it either
            warnings.warn(
                "RepeatEntry serialization is not fully implemented. "
                "The RepeatEntry element will not be included in the XML output.",
                UserWarning,
            )

        return entry


@dataclass
class SequenceContainer(common.Parseable, common.XmlObject):
    """<xtce:SequenceContainer>

    Parameters
    ----------
    name : str
        Container name
    entry_list : list
        List of Parameter objects
    long_description : str
        Long description of the container
    base_container_name : str
        Name of the base container from which this may inherit if restriction criteria are met.
    restriction_criteria : list
        A list of MatchCriteria elements that evaluate to determine whether the SequenceContainer should
        be included.
    abstract : bool
        True if container has abstract=true attribute. False otherwise.
    inheritors : Optional[list]
        List of SequenceContainer objects that may inherit this one's entry list if their restriction criteria
        are met. Any SequenceContainers with this container as base_container_name should be listed here.
    """

    name: str
    entry_list: list[Union[parameters.Parameter, "SequenceContainer"]]
    short_description: str | None = None
    long_description: str | None = None
    base_container_name: str | None = None
    restriction_criteria: list[comparisons.MatchCriteria] | None = field(default_factory=lambda: [])
    abstract: bool = False
    inheritors: list[str] | None = field(default_factory=lambda: [])

    def __post_init__(self):
        # Handle the explicit None passing for default values
        self.restriction_criteria = self.restriction_criteria or []
        self.inheritors = self.inheritors or []

    def parse(self, packet: spp.SpacePacket) -> None:
        """Parse the entry list of parameters/containers in the order they are expected in the packet.

        This could be recursive if the entry list contains SequenceContainers.
        """
        for entry in self.entry_list:
            if isinstance(entry, ParameterRefEntry):
                # ParameterRefEntry needs parameter_lookup to resolve references
                entry.parse(packet=packet, parameter_lookup=self._parameter_lookup)
            else:
                entry.parse(packet=packet)

    @classmethod
    def from_xml(
        cls,
        element: ElementTree.Element,
        *,
        tree: ElementTree.ElementTree,
        parameter_lookup: dict[str, parameters.Parameter],
        container_lookup: dict[str, Any] | None,
        parameter_type_lookup: dict[str, parameter_types.ParameterType] | None = None,
    ) -> "SequenceContainer":
        """Parses the list of parameters in a SequenceContainer element, recursively parsing nested SequenceContainers
        to build an entry list of parameters that flattens the nested structure to derive a sequential ordering of
        expected parameters for each SequenceContainer. Note that this also stores entry lists for containers that are
        not intended to stand alone.

        Parameters
        ----------
        tree : ElementTree.ElementTree
            Full XTCE tree
        element : ElementTree.Element
            The SequenceContainer element to parse.
        parameter_lookup : dict[str, parameters.Parameter]
            Parameters contained in the entry lists of sequence containers
        container_lookup: Optional[dict[str, SequenceContainer]]
            Containers already parsed, used to sort out duplicate references
        parameter_type_lookup : Optional[dict[str, parameter_types.ParameterType]]
            Ignored.

        Returns
        -------
        : cls
            SequenceContainer containing an entry_list of SequenceContainers and Parameters with ParameterTypes
            in the order expected in a packet.
        """
        entry_list = []  # List to house Parameters and nested SequenceContainers for the current SequenceContainer
        try:
            base_container, restriction_criteria = cls._get_base_container_element(tree, element)
            base_container_name = base_container.attrib["name"]
            if base_container_name not in container_lookup:
                base_sequence_container = cls.from_xml(
                    base_container,
                    tree=tree,
                    parameter_lookup=parameter_lookup,
                    container_lookup=container_lookup,
                )
                container_lookup[base_sequence_container.name] = base_sequence_container
        except ElementNotFoundError:
            base_container_name = None
            restriction_criteria = None

        for entry in element.find("EntryList").iterfind("*"):
            entry_tag_name = ElementTree.QName(entry).localname
            if entry_tag_name == "ParameterRefEntry":
                # Check if this ParameterRefEntry has IncludeCondition or RepeatEntry child elements
                has_include_condition = entry.find("IncludeCondition") is not None
                has_repeat_entry = entry.find("RepeatEntry") is not None

                if has_include_condition or has_repeat_entry:
                    # Create a ParameterRefEntry object to handle conditional/repeated parsing
                    param_ref_entry = ParameterRefEntry.from_xml(entry, tree=tree)
                    entry_list.append(param_ref_entry)
                else:
                    # No special handling needed, use the parameter directly for backward compatibility
                    parameter_name = entry.attrib["parameterRef"]
                    entry_list.append(parameter_lookup[parameter_name])  # KeyError if parameter is not in the lookup

            elif entry_tag_name == "ContainerRefEntry":
                # This container may not have been parsed yet. We need to parse it now so we might as well
                # add it to the container lookup dict.
                if entry.attrib["containerRef"] in container_lookup:
                    nested_container = container_lookup[entry.attrib["containerRef"]]
                else:
                    nested_container_element = cls._get_container_element(tree, name=entry.attrib["containerRef"])
                    nested_container = cls.from_xml(
                        nested_container_element,
                        tree=tree,
                        parameter_lookup=parameter_lookup,
                        container_lookup=container_lookup,
                    )
                    container_lookup[nested_container.name] = nested_container
                entry_list.append(nested_container)
            else:
                warnings.warn(
                    f"Unrecognized entry type '{entry_tag_name}' in EntryList for container "
                    f"'{element.attrib['name']}'. Supported types: ParameterRefEntry, ContainerRefEntry. "
                    f"Skipping this entry.",
                    category=UserWarning,
                )
                continue

        short_description = element.attrib.get("shortDescription", None)

        if (long_description_element := element.find("LongDescription")) is not None:
            long_description = long_description_element.text
        else:
            long_description = None

        container = cls(
            name=element.attrib["name"],
            entry_list=entry_list,
            base_container_name=base_container_name,
            restriction_criteria=restriction_criteria,
            abstract=(element.attrib["abstract"].lower() == "true") if "abstract" in element.attrib else False,
            short_description=short_description,
            long_description=long_description,
        )
        # Store parameter lookup for use during parsing
        container._parameter_lookup = parameter_lookup
        return container

    def to_xml(self, *, elmaker: ElementMaker) -> ElementTree.Element:
        """Create a SequenceContainer XML element

        Parameters
        ----------
        elmaker : ElementMaker
            Element factory with predefined namespace

        Returns
        -------
        : ElementTree.Element
        """
        em = elmaker
        sc_attrib = {"abstract": str(self.abstract).lower(), "name": self.name}
        if self.short_description:
            sc_attrib["shortDescription"] = self.short_description

        sc = em.SequenceContainer(**sc_attrib)

        if self.long_description:
            sc.append(em.LongDescription(self.long_description))

        if (self.restriction_criteria and not self.base_container_name) or (
            not self.restriction_criteria and self.base_container_name
        ):
            raise ValueError(
                "The restriction_criteria and base_container_name must be specified together or not at all."
            )

        if len(self.restriction_criteria) == 1:
            restrictions = self.restriction_criteria[0].to_xml(elmaker=elmaker)
        else:
            restrictions = em.ComparisonList(*(rc.to_xml(elmaker=elmaker) for rc in self.restriction_criteria))

        if self.base_container_name:
            sc.append(
                em.BaseContainer(em.RestrictionCriteria(restrictions), containerRef=self.base_container_name),
            )

        entry_list = em.EntryList()
        for entry in self.entry_list:
            if isinstance(entry, ParameterRefEntry):
                entry_element = entry.to_xml(elmaker=elmaker)
            elif isinstance(entry, parameters.Parameter):
                entry_element = em.ParameterRefEntry(parameterRef=entry.name)
            elif isinstance(entry, SequenceContainer):
                entry_element = em.ContainerRefEntry(containerRef=entry.name)
            else:
                raise ValueError(f"Unrecognized element in EntryList for sequence container {self.name}")
            entry_list.append(entry_element)

        sc.append(entry_list)

        return sc

    @staticmethod
    def _get_container_element(tree: ElementTree.ElementTree, name: str) -> ElementTree.Element:
        """Finds an XTCE container <xtce:SequenceContainer> by name.

        Parameters
        ----------
        name : str
            Name of the container to find

        Returns
        -------
        : ElementTree.Element
        """
        containers = tree.getroot().find("TelemetryMetaData/ContainerSet").findall(f"SequenceContainer[@name='{name}']")
        if len(containers) != 1:
            raise ValueError(
                f"Found {len(containers)} matching container_set with name {name}. "
                f"Container names are expected to exist and be unique."
            )
        return containers[0]

    @staticmethod
    def _get_base_container_element(
        tree: ElementTree.Element, container_element: ElementTree.Element
    ) -> tuple[ElementTree.Element, list[comparisons.MatchCriteria]]:
        """Finds the referenced base container of an existing XTCE container element,
        including its inheritance restrictions.

        Parameters
        ----------
        tree : ElementTree.ElementTree
            Full XML tree object, for finding additional referenced containers if necessary.
        container_element : ElementTree.Element
            The container element for which to find its base container.

        Returns
        -------
        : tuple[ElementTree.Element, list[comparisons.MatchCriteria]]
            The base container element of the input container_element.
            The restriction criteria for the inheritance.
        """
        base_container_element = container_element.find("BaseContainer")
        if base_container_element is None:
            raise ElementNotFoundError(
                f"Container element {container_element} does not have a BaseContainer child element."
            )

        if (restriction_criteria_element := base_container_element.find("RestrictionCriteria")) is not None:
            if (comparison_list_element := restriction_criteria_element.find("ComparisonList")) is not None:
                restrictions = [comparisons.Comparison.from_xml(comp) for comp in comparison_list_element.iterfind("*")]
            elif (comparison_element := restriction_criteria_element.find("Comparison")) is not None:
                restrictions = [comparisons.Comparison.from_xml(comparison_element)]
            elif (boolean_expression_element := restriction_criteria_element.find("BooleanExpression")) is not None:
                restrictions = [comparisons.BooleanExpression.from_xml(boolean_expression_element)]
            elif restriction_criteria_element.find("CustomAlgorithm") is not None:
                raise NotImplementedError(
                    "Detected a CustomAlgorithm in a RestrictionCriteria element. This is not implemented."
                )
            else:
                raise ValueError(
                    "Detected a RestrictionCriteria element containing no "
                    "Comparison, ComparisonList, BooleanExpression or CustomAlgorithm."
                )
            # TODO: Implement NextContainer support inside RestrictionCriteria. This might make the parser much
            #    more complicated.
        else:
            restrictions = []
        return (
            SequenceContainer._get_container_element(tree, base_container_element.attrib["containerRef"]),
            restrictions,
        )

    @staticmethod
    def _is_abstract_container(container_element: ElementTree.Element) -> bool:
        """Determine in a SequenceContainer element is abstract

        Parameters
        ----------
        container_element : ElementTree.Element
            SequenceContainer element to examine

        Returns
        -------
        : bool
            True if SequenceContainer element has the attribute abstract=true. False otherwise.
        """
        if "abstract" in container_element.attrib:
            return container_element.attrib["abstract"].lower() == "true"
        return False
