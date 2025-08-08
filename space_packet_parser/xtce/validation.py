"""XTCE document validation classes and utilities."""

import socket
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional, Union
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import urlopen

import lxml.etree as ElementTree

from space_packet_parser.xtce.definitions import XtcePacketDefinition


class ValidationLevel(Enum):
    """Validation levels for XTCE documents."""

    SCHEMA = "schema"
    STRUCTURE = "structure"
    ALL = "all"


class ValidationSeverity(Enum):
    """Severity levels for validation issues."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationError:
    """Represents a validation error or warning."""

    message: str
    severity: ValidationSeverity
    error_code: str
    xpath_location: Optional[str] = None
    line_number: Optional[int] = None
    column_number: Optional[int] = None
    context: Optional[dict[str, Any]] = field(default_factory=dict)

    def __str__(self) -> str:
        """String representation of validation error."""
        location_parts = []
        if self.line_number is not None:
            location_parts.append(f"line {self.line_number}")
        if self.column_number is not None:
            location_parts.append(f"col {self.column_number}")
        if self.xpath_location:
            location_parts.append(f"xpath: {self.xpath_location}")

        location_str = f" ({', '.join(location_parts)})" if location_parts else ""
        return f"{self.severity.value.upper()}: {self.message}{location_str}"


@dataclass
class ValidationResult:
    """Results of XTCE document validation."""

    valid: bool
    validation_level: ValidationLevel
    errors: list[ValidationError] = field(default_factory=list)
    warnings: list[ValidationError] = field(default_factory=list)
    info_messages: list[ValidationError] = field(default_factory=list)
    schema_version: Optional[str] = None
    schema_location: Optional[str] = None
    validation_time_ms: Optional[float] = None

    def __post_init__(self):
        """Post-init processing to categorize errors by severity."""
        # Separate errors by severity if they were passed as a single list
        if hasattr(self, "_all_errors"):
            for error in self._all_errors:
                if error.severity == ValidationSeverity.ERROR:
                    self.errors.append(error)
                elif error.severity == ValidationSeverity.WARNING:
                    self.warnings.append(error)
                else:
                    self.info_messages.append(error)

    @property
    def has_errors(self) -> bool:
        """Check if there are any validation errors."""
        return len(self.errors) > 0

    @property
    def has_warnings(self) -> bool:
        """Check if there are any validation warnings."""
        return len(self.warnings) > 0

    @property
    def total_issues(self) -> int:
        """Total number of validation issues."""
        return len(self.errors) + len(self.warnings) + len(self.info_messages)

    def add_error(
        self,
        message: str,
        error_code: str,
        xpath_location: Optional[str] = None,
        line_number: Optional[int] = None,
        context: Optional[dict[str, Any]] = None,
    ):
        """Add a validation error."""
        error = ValidationError(
            message=message,
            severity=ValidationSeverity.ERROR,
            error_code=error_code,
            xpath_location=xpath_location,
            line_number=line_number,
            context=context or {},
        )
        self.errors.append(error)
        self.valid = False

    def add_warning(
        self,
        message: str,
        error_code: str,
        xpath_location: Optional[str] = None,
        line_number: Optional[int] = None,
        context: Optional[dict[str, Any]] = None,
    ):
        """Add a validation warning."""
        warning = ValidationError(
            message=message,
            severity=ValidationSeverity.WARNING,
            error_code=error_code,
            xpath_location=xpath_location,
            line_number=line_number,
            context=context or {},
        )
        self.warnings.append(warning)

    def add_info(
        self,
        message: str,
        error_code: str,
        xpath_location: Optional[str] = None,
        line_number: Optional[int] = None,
        context: Optional[dict[str, Any]] = None,
    ):
        """Add a validation info message."""
        info = ValidationError(
            message=message,
            severity=ValidationSeverity.INFO,
            error_code=error_code,
            xpath_location=xpath_location,
            line_number=line_number,
            context=context or {},
        )
        self.info_messages.append(info)

    def __str__(self) -> str:
        """String representation of validation result."""
        status = "VALID" if self.valid else "INVALID"
        result = f"Validation Result: {status} ({self.validation_level.value} level)\n"

        if self.errors:
            result += f"\nErrors ({len(self.errors)}):\n"
            for error in self.errors:
                result += f"  {error}\n"

        if self.warnings:
            result += f"\nWarnings ({len(self.warnings)}):\n"
            for warning in self.warnings:
                result += f"  {warning}\n"

        if self.info_messages:
            result += f"\nInfo ({len(self.info_messages)}):\n"
            for info in self.info_messages:
                result += f"  {info}\n"

        return result


class XtceValidationError(Exception):
    """Exception raised during XTCE validation."""

    def __init__(self, message: str, validation_result: Optional[ValidationResult] = None):
        super().__init__(message)
        self.validation_result = validation_result


def is_url(path: str) -> bool:
    """Check if a string is a URL."""
    try:
        result = urlparse(path)
        return bool(result.scheme and result.netloc)
    except (ValueError, AttributeError):
        return False


def is_local_file(path: str) -> bool:
    """Check if a string is a local file path that exists."""
    try:
        return Path(path).is_file()
    except (OSError, ValueError):
        return False


# Default XTCE schema URLs by version
DEFAULT_XTCE_SCHEMAS = {
    "1.0": "https://www.omg.org/spec/XTCE/20180204/SpaceSystem.xsd",
    "1.1": "https://www.omg.org/spec/XTCE/20180204/SpaceSystem.xsd",  # Same as 1.0 for now
}


def get_default_schema_url(version: str = "1.0") -> str:
    """Get default XTCE schema URL for a given version."""
    return DEFAULT_XTCE_SCHEMAS.get(version, DEFAULT_XTCE_SCHEMAS["1.0"])


def extract_schema_location_from_xml(xml_tree, ns: Optional[dict[str, str]] = None) -> Optional[str]:
    """Extract XSD schema location from XML tree with robust namespace handling.

    Parameters
    ----------
    xml_tree : ElementTree.Element or ElementTree.ElementTree
        The XML tree to extract schema location from
    ns : Optional[Dict[str, str]]
        Namespace mapping. If None, will be inferred from the root element.

    Returns
    -------
    Optional[str]
        Schema location URL if found, None otherwise
    """

    # Get the root element
    if hasattr(xml_tree, "getroot"):
        root = xml_tree.getroot()
    else:
        root = xml_tree

    # Use provided namespace mapping or infer from root element
    if ns is None:
        ns = root.nsmap or {}

    # Try to find xsi:schemaLocation attribute using various strategies
    schema_location_value = None

    # Strategy 1: Look for xsi:schemaLocation using xsi namespace
    if "xsi" in ns:
        xsi_ns = ns["xsi"]
        schema_location_key = f"{{{xsi_ns}}}schemaLocation"
        schema_location_value = root.attrib.get(schema_location_key)

    # Strategy 2: Look for schemaLocation without namespace prefix (if xsi is default)
    if schema_location_value is None:
        schema_location_value = root.attrib.get("schemaLocation")

    # Strategy 3: Look for any attribute ending with 'schemaLocation'
    if schema_location_value is None:
        for attr_name in root.attrib:
            if attr_name.endswith("schemaLocation"):
                schema_location_value = root.attrib[attr_name]
                break

    if not schema_location_value:
        return None

    # Parse schemaLocation value (format: "namespace1 schema1 namespace2 schema2")
    pairs = schema_location_value.split()
    if len(pairs) < 2 or len(pairs) % 2 != 0:
        return None

    # Look for XTCE namespace URI in the pairs
    xtce_namespace_uris = [
        "http://www.omg.org/spec/XTCE/20180204",
        "http://www.omg.org/space/xtce",  # Alternative URI sometimes used
    ]

    # Check pairs for XTCE namespace
    for i in range(0, len(pairs), 2):
        namespace_uri = pairs[i]
        schema_url = pairs[i + 1]

        if namespace_uri in xtce_namespace_uris:
            return schema_url

    # If no specific XTCE namespace found, return first schema URL as fallback
    return pairs[1] if len(pairs) >= 2 else None


def extract_xtce_version_from_xml(xml_tree) -> str:
    """Extract XTCE version from XML tree.

    Parameters
    ----------
    xml_tree : ElementTree.Element or ElementTree.ElementTree
        The XML tree to extract version from

    Returns
    -------
    str
        XTCE version string, defaults to "1.0" if not found
    """
    # Get the root element
    if hasattr(xml_tree, "getroot"):
        root = xml_tree.getroot()
    else:
        root = xml_tree

    # Look for version in Header element
    for header in root.iterfind(".//Header"):
        version = header.attrib.get("version")
        if version:
            return version

    # Look for version attribute on root element
    version = root.attrib.get("version")
    if version:
        return version

    # Default version
    return "1.0"


def discover_schema_url(xml_tree, ns: Optional[dict[str, str]] = None, fallback_version: Optional[str] = None) -> str:
    """Discover XSD schema URL from XML document with robust fallbacks.

    Parameters
    ----------
    xml_tree : ElementTree.Element or ElementTree.ElementTree
        The XML tree to discover schema for
    ns : Optional[Dict[str, str]]
        Namespace mapping. If None, will be inferred from the root element.
    fallback_version : Optional[str]
        Version to use for fallback schema. If None, will be extracted from XML.

    Returns
    -------
    str
        Schema URL (either extracted or default fallback)
    """
    # First try to extract from schemaLocation
    schema_url = extract_schema_location_from_xml(xml_tree, ns)
    if schema_url:
        return schema_url

    # Fallback to default schema based on version
    if fallback_version is None:
        fallback_version = extract_xtce_version_from_xml(xml_tree)

    return get_default_schema_url(fallback_version)


def load_schema(schema_url: str, local_path: Optional[str] = None, timeout: int = 30):
    """Load XSD schema.

    Parameters
    ----------
    schema_url : str
        URL or path to the XSD schema
    local_path : Optional[str]
        Local file path to use instead of downloading (for offline use)
    timeout : int
        Timeout in seconds for URL downloads

    Returns
    -------
    XMLSchema object from lxml
        Parsed schema object

    Raises
    ------
    XtceValidationError
        If schema cannot be loaded or parsed
    """
    # Determine how to load the schema
    schema_content = None

    try:
        if local_path and is_local_file(local_path):
            # Load from local file
            with open(local_path, "rb") as f:
                schema_content = f.read()
        elif is_local_file(schema_url):
            # Schema URL is actually a local file path
            with open(schema_url, "rb") as f:
                schema_content = f.read()
        elif is_url(schema_url):
            # Download from URL
            try:
                with urlopen(schema_url, timeout=timeout) as response:  # noqa: S310
                    schema_content = response.read()
            except (URLError, socket.timeout) as e:
                raise XtceValidationError(f"Failed to download schema from {schema_url}: {e}") from e
        else:
            raise XtceValidationError(f"Invalid schema location: {schema_url}")

        # Parse the schema
        if schema_content:
            try:
                schema_tree = ElementTree.XML(schema_content)
                schema_obj = ElementTree.XMLSchema(schema_tree)
                return schema_obj
            except ElementTree.XMLSyntaxError as e:
                raise XtceValidationError(f"Failed to parse XSD schema from {schema_url}: {e}") from e
            except ElementTree.XMLSchemaError as e:
                raise XtceValidationError(f"Invalid XSD schema from {schema_url}: {e}") from e
        else:
            raise XtceValidationError(f"No content loaded from schema location: {schema_url}")

    except XtceValidationError:
        raise
    except OSError as e:
        raise XtceValidationError(f"IO error loading schema from {schema_url}: {e}") from e


def validate_xml_against_schema(
    xml_source: Union[str, Path, Any],
    schema_url: Optional[str] = None,
    local_schema_path: Optional[str] = None,
    timeout: int = 30,
) -> ValidationResult:
    """Validate XML document against XSD schema with comprehensive error reporting.

    Parameters
    ----------
    xml_source : Union[str, Path, Any]
        Path to XML file, XML string content, or parsed XML tree/element
    schema_url : Optional[str]
        Explicit schema URL to use. If None, will be discovered from XML.
    local_schema_path : Optional[str]
        Local path to XSD file to use instead of downloading
    timeout : int
        Timeout in seconds for schema downloads

    Returns
    -------
    ValidationResult
        Comprehensive validation results with errors, warnings, and metadata
    """
    start_time = time.time()
    result = ValidationResult(valid=True, validation_level=ValidationLevel.SCHEMA)

    try:
        # Parse the XML document if needed
        if isinstance(xml_source, (str, Path)):
            xml_path = Path(xml_source)
            if xml_path.is_file():
                # It's a file path
                try:
                    xml_tree = ElementTree.parse(str(xml_path))
                    result.add_info(f"Loaded XML document from {xml_path}", "XML_LOADED")
                except ElementTree.XMLSyntaxError as e:
                    result.add_error(
                        f"Failed to parse XML document: {e}", "XML_PARSE_ERROR", line_number=getattr(e, "lineno", None)
                    )
                    return result
            else:
                # It's XML content as string
                try:
                    xml_tree = ElementTree.XML(xml_source)
                    result.add_info("Parsed XML content from string", "XML_PARSED")
                except ElementTree.XMLSyntaxError as e:
                    result.add_error(
                        f"Failed to parse XML content: {e}", "XML_PARSE_ERROR", line_number=getattr(e, "lineno", None)
                    )
                    return result
        else:
            # Assume it's already a parsed tree/element
            xml_tree = xml_source
            result.add_info("Using pre-parsed XML tree", "XML_PRELOADED")

        # Discover schema URL if not provided
        if schema_url is None:
            schema_url = discover_schema_url(xml_tree)
            result.add_info(f"Discovered schema URL: {schema_url}", "SCHEMA_DISCOVERED")
        else:
            result.add_info(f"Using provided schema URL: {schema_url}", "SCHEMA_PROVIDED")

        result.schema_location = schema_url

        # Extract version information
        try:
            version = extract_xtce_version_from_xml(xml_tree)
            result.schema_version = version
            result.add_info(f"Detected XTCE version: {version}", "VERSION_DETECTED")
        except (AttributeError, ValueError) as e:
            result.add_warning(f"Could not determine XTCE version: {e}", "VERSION_UNKNOWN")

        # Load the schema
        try:
            schema = load_schema(schema_url, local_schema_path, timeout)
            result.add_info("Schema loaded successfully", "SCHEMA_LOADED")
        except XtceValidationError as e:
            result.add_error(str(e), "SCHEMA_LOAD_ERROR")
            return result

        # Perform schema validation
        try:
            # Get the root element if we have an ElementTree
            if hasattr(xml_tree, "getroot"):
                xml_to_validate = xml_tree
            else:
                # Create an ElementTree from the element
                xml_to_validate = ElementTree.ElementTree(xml_tree)

            # Validate the document
            if schema.validate(xml_to_validate):
                result.add_info("Document passed XSD schema validation", "SCHEMA_VALID")
            else:
                result.valid = False

                # Collect detailed validation errors
                for error in schema.error_log:
                    result.add_error(
                        message=str(error.message),
                        error_code="SCHEMA_VALIDATION_ERROR",
                        line_number=error.line,
                        context={
                            "domain": error.domain_name,
                            "type": error.type_name,
                            "level": error.level_name,
                            "filename": error.filename,
                        },
                    )

        except (ElementTree.XMLSchemaError, AttributeError) as e:
            result.add_error(f"Schema validation failed with exception: {e}", "VALIDATION_EXCEPTION")
            return result

    except OSError as e:
        result.add_error(f"IO error during validation: {e}", "IO_ERROR")
        return result

    finally:
        # Record validation time
        result.validation_time_ms = (time.time() - start_time) * 1000

    return result


def validate_xtce_structure(definition: XtcePacketDefinition) -> ValidationResult:
    """Validate XTCE document structure and reference integrity.

    This performs structural validation beyond XSD schema validation,
    checking XTCE-specific business rules and reference integrity.

    Parameters
    ----------
    definition : XtcePacketDefinition
        Parsed XTCE packet definition object

    Returns
    -------
    ValidationResult
        Structural validation results with detailed error reporting
    """
    start_time = time.time()
    result = ValidationResult(valid=True, validation_level=ValidationLevel.STRUCTURE)

    try:
        # Validate parameter type references
        for param_name, param in definition.parameters.items():
            if param.parameter_type.name not in definition.parameter_types:
                result.add_error(
                    f"Parameter '{param_name}' references unknown parameter type '{param.parameter_type.name}'",
                    "INVALID_PARAMETER_TYPE_REF",
                )

        result.add_info(f"Found {len(definition.parameter_types)} parameter types", "PARAMETER_TYPES_FOUND")
        result.add_info(f"Found {len(definition.parameters)} parameters", "PARAMETERS_FOUND")
        result.add_info(f"Found {len(definition.containers)} containers", "CONTAINERS_FOUND")

        # Validate container structure and references
        inheritance_graph = {}  # For cycle detection

        for container_name, container in definition.containers.items():
            inheritance_graph[container_name] = []

            # Check base container reference
            if container.base_container_name:
                if container.base_container_name not in definition.containers:
                    result.add_error(
                        f"Container '{container_name}' references ",
                        f"unknown base container '{container.base_container_name}'",
                        "INVALID_BASE_CONTAINER_REF",
                    )
                else:
                    inheritance_graph[container_name].append(container.base_container_name)

            # Check parameter references in entry lists
            for entry in container.entry_list:
                # Check if it's a Parameter (not a SequenceContainer)
                if hasattr(entry, "name") and hasattr(entry, "parameter_type"):  # It's a Parameter
                    if entry.name not in definition.parameters:
                        result.add_error(
                            f"Container '{container_name}' references unknown parameter '{entry.name}'",
                            "INVALID_PARAMETER_REF",
                        )
                elif hasattr(entry, "name") and not hasattr(entry, "parameter_type"):  # It's a SequenceContainer
                    if entry.name not in definition.containers:
                        result.add_error(
                            f"Container '{container_name}' references unknown container '{entry.name}'",
                            "INVALID_CONTAINER_REF",
                        )

            # Check comparison references in restriction criteria
            if container.restriction_criteria:
                for criteria in container.restriction_criteria:
                    if hasattr(criteria, "parameter_ref"):
                        if criteria.parameter_ref not in definition.parameters:
                            result.add_error(
                                f"Container '{container_name}' restriction criteria references ",
                                f"unknown parameter '{criteria.parameter_ref}'",
                                "INVALID_COMPARISON_PARAMETER_REF",
                            )

        # Check for circular inheritance
        def has_cycle(graph, node, visited, rec_stack):
            """Detect cycles in inheritance graph using DFS."""
            visited[node] = True
            rec_stack[node] = True

            for neighbor in graph.get(node, []):
                if neighbor in graph:  # Only check if neighbor exists
                    if not visited.get(neighbor, False):
                        if has_cycle(graph, neighbor, visited, rec_stack):
                            return True
                    elif rec_stack.get(neighbor, False):
                        return True

            rec_stack[node] = False
            return False

        visited = {}
        rec_stack = {}

        for container in inheritance_graph:
            if not visited.get(container, False):
                if has_cycle(inheritance_graph, container, visited, rec_stack):
                    result.add_error(
                        f"Circular inheritance detected involving container '{container}'",
                        "CIRCULAR_INHERITANCE",
                        context={"inheritance_graph": inheritance_graph},
                    )
                    break

        # Check for orphaned abstract containers
        abstract_containers = set()
        used_containers = set()

        for container_name, container in definition.containers.items():
            if container.abstract:
                abstract_containers.add(container_name)

            # Track which containers are used (via inheritance)
            if container.base_container_name:
                used_containers.add(container.base_container_name)

            # Track which containers are used (via composition/container references)
            for entry in container.entry_list:
                if hasattr(entry, "name") and not hasattr(entry, "parameter_type"):  # It's a SequenceContainer
                    if entry.name in definition.containers:
                        used_containers.add(entry.name)

        orphaned_abstract = abstract_containers - used_containers
        for orphan in orphaned_abstract:
            result.add_warning(
                f"Abstract container '{orphan}' is not used by any container (neither inherited nor referenced)",
                "ORPHANED_ABSTRACT_CONTAINER",
                context={"container": orphan},
            )

        # Validate required XTCE structure elements
        if not definition.parameter_types and not definition.parameters and not definition.containers:
            result.add_warning("Document contains no parameter types, parameters, or containers", "EMPTY_XTCE_DOCUMENT")

    except AttributeError as e:
        result.add_error(f"Structural validation error - missing expected attribute: {e}", "ATTRIBUTE_ERROR")
        return result

    finally:
        result.validation_time_ms = (time.time() - start_time) * 1000

    return result


def validate_document(
    xml_source: Union[str, Path, Any],
    level: str = "schema",
    schema_url: Optional[str] = None,
    local_schema_path: Optional[str] = None,
    timeout: int = 30,
) -> ValidationResult:
    """Validate an XTCE XML document with comprehensive error reporting.

    This is the main validation entry point for XTCE documents. It can perform
    schema or structural validation based on the level parameter.
    Accepts file paths, XML strings, file-like objects, or in-memory XML trees.

    Parameters
    ----------
    xml_source : Union[str, Path, Any]
        Path to XML file, XML string content, file-like object, or ElementTree
    level : str
        Validation level: "schema", "structure", or "all"
    schema_url : Optional[str]
        Explicit schema URL to use. If None, will be discovered from XML.
    local_schema_path : Optional[str]
        Local path to XSD file to use instead of downloading
    timeout : int
        Timeout in seconds for schema downloads

    Returns
    -------
    ValidationResult
        Comprehensive validation results with errors, warnings, and metadata

    Examples
    --------
    >>> result = validate_document("my_xtce.xml")
    >>> if result.valid:
    ...     print("Document is valid!")
    >>> else:
    ...     for error in result.errors:
    ...         print(f"Error: {error}")
    """
    try:
        validation_level = ValidationLevel(level.lower())
    except ValueError:
        # Return an error result for invalid validation level
        result = ValidationResult(valid=False, validation_level=ValidationLevel.SCHEMA)
        result.add_error(
            f"Invalid validation level '{level}'. Must be one of: schema, structure, all",
            "INVALID_VALIDATION_LEVEL",
        )
        return result

    if validation_level == ValidationLevel.SCHEMA:
        return validate_xml_against_schema(xml_source, schema_url, local_schema_path, timeout)
    elif validation_level == ValidationLevel.STRUCTURE:
        # For structural validation on XML, we need to parse first
        try:
            from space_packet_parser.xtce.definitions import XtcePacketDefinition

            parsed_definition = XtcePacketDefinition.from_xtce(xml_source)
            return validate_xtce_structure(parsed_definition)
        except ImportError as e:
            result = ValidationResult(valid=False, validation_level=ValidationLevel.STRUCTURE)
            result.add_error(f"Failed to import XtcePacketDefinition: {e}", "IMPORT_ERROR")
            return result
        except (OSError, ElementTree.XMLSyntaxError) as e:
            result = ValidationResult(valid=False, validation_level=ValidationLevel.STRUCTURE)
            result.add_error(f"Failed to parse XTCE document for structural validation: {e}", "PARSE_ERROR")
            return result
    elif validation_level == ValidationLevel.ALL:
        # Perform all validation levels and combine results
        results = []

        # Schema validation
        schema_result = validate_xml_against_schema(xml_source, schema_url, local_schema_path, timeout)
        results.append(schema_result)

        # Only continue if schema validation passes or we want to check structure anyway
        if schema_result.valid or True:  # Continue even if schema fails
            # Structural validation
            try:
                from space_packet_parser.xtce.definitions import XtcePacketDefinition

                parsed_definition = XtcePacketDefinition.from_xtce(xml_source)
                structure_result = validate_xtce_structure(parsed_definition)
                results.append(structure_result)
            except (ImportError, OSError, ElementTree.XMLSyntaxError) as e:
                structure_result = ValidationResult(valid=False, validation_level=ValidationLevel.STRUCTURE)
                structure_result.add_error(f"Failed to parse for structural validation: {e}", "STRUCTURE_PARSE_ERROR")
                results.append(structure_result)

        # Combine all results
        combined_result = ValidationResult(valid=True, validation_level=ValidationLevel.ALL)
        combined_result.schema_location = schema_result.schema_location
        combined_result.schema_version = schema_result.schema_version

        total_time = 0.0
        for result in results:
            combined_result.errors.extend(result.errors)
            combined_result.warnings.extend(result.warnings)
            combined_result.info_messages.extend(result.info_messages)
            if result.validation_time_ms:
                total_time += result.validation_time_ms

        combined_result.validation_time_ms = total_time
        combined_result.valid = not combined_result.has_errors

        return combined_result

    # This shouldn't be reached, but just in case
    result = ValidationResult(valid=False, validation_level=ValidationLevel.SCHEMA)
    result.add_error(f"Unhandled validation level: {validation_level}", "INTERNAL_ERROR")
    return result
