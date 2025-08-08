"""XTCE document validation classes and utilities."""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional, Union
from urllib.parse import urlparse


class ValidationLevel(Enum):
    """Validation levels for XTCE documents."""

    SCHEMA = "schema"
    STRUCTURE = "structure"
    SEMANTIC = "semantic"
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


class SchemaCache:
    """Cache for parsed XSD schemas to improve validation performance."""

    def __init__(self):
        self._schemas: dict[str, Any] = {}
        self._schema_locations: dict[str, str] = {}

    def get_schema(self, schema_url: str):
        """Get cached schema or None if not cached."""
        return self._schemas.get(schema_url)

    def cache_schema(self, schema_url: str, schema_obj: Any, local_path: Optional[str] = None):
        """Cache a parsed schema object."""
        self._schemas[schema_url] = schema_obj
        if local_path:
            self._schema_locations[schema_url] = local_path

    def clear_cache(self):
        """Clear all cached schemas."""
        self._schemas.clear()
        self._schema_locations.clear()


# Global schema cache instance
_global_schema_cache = SchemaCache()


def get_schema_cache() -> SchemaCache:
    """Get the global schema cache instance."""
    return _global_schema_cache


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
    except Exception:
        return False


def is_local_file(path: str) -> bool:
    """Check if a string is a local file path that exists."""
    try:
        return Path(path).is_file()
    except Exception:
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


def load_schema_with_caching(schema_url: str, local_path: Optional[str] = None, timeout: int = 30):
    """Load XSD schema with caching support.

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
        Parsed and cached schema object

    Raises
    ------
    XtceValidationError
        If schema cannot be loaded or parsed
    """
    import socket
    from urllib.error import URLError
    from urllib.request import urlopen

    import lxml.etree as ElementTree

    # Check cache first
    cache = get_schema_cache()
    cached_schema = cache.get_schema(schema_url)
    if cached_schema is not None:
        return cached_schema

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

                # Cache the parsed schema
                cache.cache_schema(schema_url, schema_obj, local_path)

                return schema_obj
            except ElementTree.XMLSyntaxError as e:
                raise XtceValidationError(f"Failed to parse XSD schema from {schema_url}: {e}") from e
            except ElementTree.XMLSchemaError as e:
                raise XtceValidationError(f"Invalid XSD schema from {schema_url}: {e}") from e
        else:
            raise XtceValidationError(f"No content loaded from schema location: {schema_url}")

    except Exception as e:
        if isinstance(e, XtceValidationError):
            raise
        raise XtceValidationError(f"Unexpected error loading schema from {schema_url}: {e}") from e


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
    import time
    from pathlib import Path

    import lxml.etree as ElementTree

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
        except Exception as e:
            result.add_warning(f"Could not determine XTCE version: {e}", "VERSION_UNKNOWN")

        # Load the schema
        try:
            schema = load_schema_with_caching(schema_url, local_schema_path, timeout)
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

        except Exception as e:
            result.add_error(f"Schema validation failed with exception: {e}", "VALIDATION_EXCEPTION")
            return result

    except Exception as e:
        result.add_error(f"Unexpected error during validation: {e}", "UNEXPECTED_ERROR")
        return result

    finally:
        # Record validation time
        result.validation_time_ms = (time.time() - start_time) * 1000

    return result


def validate_xtce_structure(xml_source: Union[str, Path, Any], ns: Optional[dict[str, str]] = None) -> ValidationResult:
    """Validate XTCE document structure and reference integrity.

    This performs structural validation beyond XSD schema validation,
    checking XTCE-specific business rules and reference integrity.

    Parameters
    ----------
    xml_source : Union[str, Path, Any]
        Path to XML file, XML string content, or parsed XML tree/element
    ns : Optional[Dict[str, str]]
        Namespace mapping. If None, will be inferred from XML.

    Returns
    -------
    ValidationResult
        Structural validation results with detailed error reporting
    """
    import time
    from pathlib import Path

    import lxml.etree as ElementTree

    start_time = time.time()
    result = ValidationResult(valid=True, validation_level=ValidationLevel.STRUCTURE)

    try:
        # Parse the XML document if needed
        if isinstance(xml_source, (str, Path)):
            xml_path = Path(xml_source)
            if xml_path.is_file():
                try:
                    xml_tree = ElementTree.parse(str(xml_path))
                    result.add_info(f"Loaded XML document from {xml_path}", "XML_LOADED")
                except ElementTree.XMLSyntaxError as e:
                    result.add_error(f"Failed to parse XML document: {e}", "XML_PARSE_ERROR")
                    return result
            else:
                try:
                    xml_tree = ElementTree.XML(xml_source)
                    result.add_info("Parsed XML content from string", "XML_PARSED")
                except ElementTree.XMLSyntaxError as e:
                    result.add_error(f"Failed to parse XML content: {e}", "XML_PARSE_ERROR")
                    return result
        else:
            xml_tree = xml_source
            result.add_info("Using pre-parsed XML tree", "XML_PRELOADED")

        # Get root element and namespace mapping
        if hasattr(xml_tree, "getroot"):
            root = xml_tree.getroot()
        else:
            root = xml_tree

        if ns is None:
            ns = root.nsmap or {}

        # Helper function to find elements with namespace awareness
        def find_elements(parent, tag):
            """Find elements handling namespaces properly."""
            # Try with XTCE namespace prefix if it exists
            for ns_prefix in ["xtce", None]:
                if ns_prefix and ns_prefix in ns:
                    namespaced_tag = f"{{{ns[ns_prefix]}}}{tag}"
                    elements = parent.findall(f".//{namespaced_tag}")
                    if elements:
                        return elements
                elif ns_prefix is None:
                    # Try without namespace (default namespace or no namespace)
                    elements = parent.findall(f".//{tag}")
                    if elements:
                        return elements
            return []

        # Collect all parameter types, parameters, and containers
        parameter_types = {}
        parameters = {}
        containers = {}

        # Parse parameter types
        for param_type_elem in find_elements(root, "ParameterTypeSet"):
            for child in param_type_elem:
                type_name = child.attrib.get("name")
                if type_name:
                    if type_name in parameter_types:
                        result.add_error(
                            f"Duplicate parameter type name: {type_name}",
                            "DUPLICATE_PARAMETER_TYPE",
                            xpath_location=xml_tree.getpath(child) if hasattr(xml_tree, "getpath") else None,
                        )
                    else:
                        parameter_types[type_name] = child

        result.add_info(f"Found {len(parameter_types)} parameter types", "PARAMETER_TYPES_FOUND")

        # Parse parameters
        for param_set_elem in find_elements(root, "ParameterSet"):
            for param_elem in param_set_elem:
                param_name = param_elem.attrib.get("name")
                if param_name:
                    if param_name in parameters:
                        result.add_error(
                            f"Duplicate parameter name: {param_name}",
                            "DUPLICATE_PARAMETER",
                            xpath_location=xml_tree.getpath(param_elem) if hasattr(xml_tree, "getpath") else None,
                        )
                    else:
                        parameters[param_name] = param_elem

                        # Check parameter type reference
                        param_type_ref = param_elem.attrib.get("parameterTypeRef")
                        if param_type_ref and param_type_ref not in parameter_types:
                            result.add_error(
                                f"Parameter '{param_name}' references unknown parameter type '{param_type_ref}'",
                                "INVALID_PARAMETER_TYPE_REF",
                                xpath_location=xml_tree.getpath(param_elem) if hasattr(xml_tree, "getpath") else None,
                            )

        result.add_info(f"Found {len(parameters)} parameters", "PARAMETERS_FOUND")

        # Parse containers
        for container_set_elem in find_elements(root, "ContainerSet"):
            for container_elem in container_set_elem:
                container_name = container_elem.attrib.get("name")
                if container_name:
                    if container_name in containers:
                        result.add_error(
                            f"Duplicate container name: {container_name}",
                            "DUPLICATE_CONTAINER",
                            xpath_location=xml_tree.getpath(container_elem) if hasattr(xml_tree, "getpath") else None,
                        )
                    else:
                        containers[container_name] = container_elem

        result.add_info(f"Found {len(containers)} containers", "CONTAINERS_FOUND")

        # Validate container structure and references
        inheritance_graph = {}  # For cycle detection

        for container_name, container_elem in containers.items():
            inheritance_graph[container_name] = []

            # Check base container reference using namespace-aware finding
            base_container_elems = find_elements(container_elem, "BaseContainer")
            for base_container_elem in base_container_elems:
                base_ref = base_container_elem.attrib.get("containerRef")
                if base_ref:
                    if base_ref not in containers:
                        result.add_error(
                            f"Container '{container_name}' references unknown base container '{base_ref}'",
                            "INVALID_BASE_CONTAINER_REF",
                            xpath_location=xml_tree.getpath(container_elem) if hasattr(xml_tree, "getpath") else None,
                        )
                    else:
                        inheritance_graph[container_name].append(base_ref)
                    break  # Only need the first BaseContainer

            # Check parameter references in entry lists
            for entry_elem in find_elements(container_elem, "ParameterRefEntry"):
                param_ref = entry_elem.attrib.get("parameterRef")
                if param_ref and param_ref not in parameters:
                    result.add_error(
                        f"Container '{container_name}' references unknown parameter '{param_ref}'",
                        "INVALID_PARAMETER_REF",
                        xpath_location=xml_tree.getpath(entry_elem) if hasattr(xml_tree, "getpath") else None,
                    )

            # Check container references in entry lists
            for entry_elem in find_elements(container_elem, "ContainerRefEntry"):
                container_ref = entry_elem.attrib.get("containerRef")
                if container_ref and container_ref not in containers:
                    result.add_error(
                        f"Container '{container_name}' references unknown container '{container_ref}'",
                        "INVALID_CONTAINER_REF",
                        xpath_location=xml_tree.getpath(entry_elem) if hasattr(xml_tree, "getpath") else None,
                    )

            # Check comparison references in restriction criteria
            for comparison_elem in find_elements(container_elem, "Comparison"):
                param_ref = comparison_elem.attrib.get("parameterRef")
                if param_ref and param_ref not in parameters:
                    result.add_error(
                        f"Container '{container_name}' restriction criteria references unknown parameter '{param_ref}'",
                        "INVALID_COMPARISON_PARAMETER_REF",
                        xpath_location=xml_tree.getpath(comparison_elem) if hasattr(xml_tree, "getpath") else None,
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
        inherited_containers = set()

        for container_name, container_elem in containers.items():
            if container_elem.attrib.get("abstract", "false").lower() == "true":
                abstract_containers.add(container_name)

            # Track which containers are inherited
            for base_container in inheritance_graph[container_name]:
                inherited_containers.add(base_container)

        orphaned_abstract = abstract_containers - inherited_containers
        for orphan in orphaned_abstract:
            result.add_warning(
                f"Abstract container '{orphan}' is not inherited by any container",
                "ORPHANED_ABSTRACT_CONTAINER",
                context={"container": orphan},
            )

        # Validate required XTCE structure elements
        if not parameter_types and not parameters and not containers:
            result.add_warning("Document contains no parameter types, parameters, or containers", "EMPTY_XTCE_DOCUMENT")

        # Check for required CCSDS packet structure
        has_ccsds_structure = False
        for container_name in containers:
            if "ccsds" in container_name.lower() or "packet" in container_name.lower():
                has_ccsds_structure = True
                break

        if not has_ccsds_structure:
            result.add_info(
                "No CCSDS packet structure detected - this may be intentional for non-CCSDS XTCE documents",
                "NO_CCSDS_STRUCTURE",
            )

    except Exception as e:
        result.add_error(f"Unexpected error during structural validation: {e}", "UNEXPECTED_ERROR")
        return result

    finally:
        result.validation_time_ms = (time.time() - start_time) * 1000

    return result


def validate_space_packet_parser_semantics(definition_or_xml) -> ValidationResult:
    """Validate Space Packet Parser specific semantic rules.

    This performs validation of business logic rules specific to how
    Space Packet Parser uses XTCE documents, including CCSDS requirements
    and naming conventions.

    Parameters
    ----------
    definition_or_xml : Union[XtcePacketDefinition, str, Path, Any]
        Either a parsed XtcePacketDefinition object or XML source

    Returns
    -------
    ValidationResult
        Semantic validation results with detailed error reporting
    """
    import time

    start_time = time.time()
    result = ValidationResult(valid=True, validation_level=ValidationLevel.SEMANTIC)

    try:
        # Handle different input types
        if hasattr(definition_or_xml, "containers"):
            # It's already an XtcePacketDefinition object
            definition = definition_or_xml
            result.add_info("Using parsed XtcePacketDefinition object", "DEFINITION_PROVIDED")
        else:
            # Try to parse from XML - this requires importing XtcePacketDefinition
            # We'll do a simplified validation on XML for now to avoid circular imports
            result.add_info("Semantic validation on XML requires parsed definition object", "XML_SEMANTIC_LIMITED")
            return result

        # Validate CCSDS header structure requirements
        required_ccsds_parameters = {
            "VERSION": "VERSION_Type",
            "TYPE": "TYPE_Type",
            "SEC_HDR_FLG": "SEC_HDR_FLG_Type",
            "PKT_APID": "PKT_APID_Type",
            "SEQ_FLGS": "SEQ_FLGS_Type",
            "SRC_SEQ_CTR": "SRC_SEQ_CTR_Type",
            "PKT_LEN": "PKT_LEN_Type",
        }

        # Check for CCSDS parameter presence
        missing_ccsds_params = []
        for param_name, expected_type in required_ccsds_parameters.items():
            if param_name not in definition.parameters:
                missing_ccsds_params.append(param_name)
            else:
                # Check if parameter type matches expected pattern
                param = definition.parameters[param_name]
                actual_type = param.parameter_type.name
                if not actual_type.endswith("_Type"):
                    result.add_warning(
                        f"Parameter '{param_name}' type '{actual_type}' doesn't follow '_Type' naming convention",
                        "PARAMETER_TYPE_NAMING_CONVENTION",
                    )

        if missing_ccsds_params:
            result.add_warning(
                f"Missing recommended CCSDS header parameters: {', '.join(missing_ccsds_params)}",
                "MISSING_CCSDS_PARAMETERS",
                context={"missing_parameters": missing_ccsds_params},
            )
        else:
            result.add_info("All CCSDS header parameters found", "CCSDS_PARAMETERS_COMPLETE")

        # Check for CCSDS container structure
        root_container_candidates = []
        for container_name, container in definition.containers.items():
            if any(keyword in container_name.upper() for keyword in ["CCSDS", "PACKET"]):
                root_container_candidates.append(container_name)

        if not root_container_candidates:
            result.add_warning(
                "No CCSDS packet container found - document may not be suitable for CCSDS packet parsing",
                "NO_CCSDS_CONTAINER",
            )
        else:
            result.add_info(f"Found CCSDS containers: {', '.join(root_container_candidates)}", "CCSDS_CONTAINERS_FOUND")

        # Validate root container configuration
        if definition.root_container_name:
            if definition.root_container_name not in definition.containers:
                result.add_error(
                    f"Configured root container '{definition.root_container_name}' does not exist",
                    "INVALID_ROOT_CONTAINER",
                )
            else:
                root_container = definition.containers[definition.root_container_name]
                if not root_container.abstract:
                    result.add_warning(
                        f"Root container '{definition.root_container_name}' is not abstract - "
                        "this may cause parsing issues",
                        "NON_ABSTRACT_ROOT_CONTAINER",
                    )

        # Check parameter naming conventions
        naming_issues = []
        for param_name in definition.parameters:
            # Check for all caps naming (common CCSDS convention)
            if not param_name.isupper():
                naming_issues.append(f"Parameter '{param_name}' not in uppercase")

            # Check for reasonable length
            if len(param_name) > 32:
                result.add_warning(
                    f"Parameter '{param_name}' has unusually long name ({len(param_name)} chars)", "LONG_PARAMETER_NAME"
                )

        if naming_issues and len(naming_issues) <= 5:  # Don't spam if there are many
            for issue in naming_issues:
                result.add_info(issue, "PARAMETER_NAMING_CONVENTION")
        elif naming_issues:
            result.add_info(f"Found {len(naming_issues)} parameter naming convention issues", "MULTIPLE_NAMING_ISSUES")

        # Check parameter type naming conventions
        type_naming_issues = []
        for type_name in definition.parameter_types:
            if not type_name.endswith("_Type"):
                type_naming_issues.append(f"Parameter type '{type_name}' doesn't end with '_Type'")

        if type_naming_issues and len(type_naming_issues) <= 5:
            for issue in type_naming_issues:
                result.add_info(issue, "TYPE_NAMING_CONVENTION")
        elif type_naming_issues:
            result.add_info(
                f"Found {len(type_naming_issues)} parameter type naming convention issues",
                "MULTIPLE_TYPE_NAMING_ISSUES",
            )

        # Check for secondary header structure
        secondary_header_containers = []
        time_parameters = []

        for container_name in definition.containers:
            if "HEADER" in container_name.upper() and "SECONDARY" in container_name.upper():
                secondary_header_containers.append(container_name)

        for param_name in definition.parameters:
            if any(keyword in param_name.upper() for keyword in ["TIME", "DOY", "MSEC", "USEC"]):
                time_parameters.append(param_name)

        if secondary_header_containers:
            result.add_info(
                f"Found secondary header containers: {', '.join(secondary_header_containers)}", "SECONDARY_HEADER_FOUND"
            )

        if time_parameters:
            result.add_info(f"Found time parameters: {', '.join(time_parameters)}", "TIME_PARAMETERS_FOUND")

        # Check container inheritance depth
        max_inheritance_depth = 0
        inheritance_depths = {}

        def calculate_inheritance_depth(container_name, containers, depths, visited=None):
            """Calculate inheritance depth for a container."""
            if visited is None:
                visited = set()

            if container_name in visited:
                return 0  # Circular reference, already handled in structural validation

            if container_name in depths:
                return depths[container_name]

            visited.add(container_name)
            container = containers.get(container_name)
            if not container:
                depths[container_name] = 0
                return 0

            # Find base container name from the SequenceContainer object
            base_depth = 0
            if hasattr(container, "base_container_name") and container.base_container_name:
                base_depth = calculate_inheritance_depth(container.base_container_name, containers, depths, visited) + 1

            depths[container_name] = base_depth
            visited.remove(container_name)
            return base_depth

        for container_name in definition.containers:
            depth = calculate_inheritance_depth(container_name, definition.containers, inheritance_depths)
            max_inheritance_depth = max(max_inheritance_depth, depth)

        if max_inheritance_depth > 5:
            result.add_warning(
                f"Deep container inheritance detected (max depth: {max_inheritance_depth})",
                "DEEP_INHERITANCE",
                context={"max_depth": max_inheritance_depth},
            )

        # Check for potential performance issues
        total_parameters = len(definition.parameters)
        total_containers = len(definition.containers)

        if total_parameters > 1000:
            result.add_warning(
                f"Large number of parameters ({total_parameters}) may impact parsing performance",
                "LARGE_PARAMETER_COUNT",
            )

        if total_containers > 100:
            result.add_warning(
                f"Large number of containers ({total_containers}) may impact parsing performance",
                "LARGE_CONTAINER_COUNT",
            )

        # Overall assessment
        if result.has_errors:
            result.add_info("Semantic validation found errors that may prevent proper parsing", "SEMANTIC_ERRORS_FOUND")
        elif result.has_warnings:
            result.add_info(
                "Semantic validation found warnings - document should work but may have issues",
                "SEMANTIC_WARNINGS_FOUND",
            )
        else:
            result.add_info("Document passes all semantic validation checks", "SEMANTIC_VALIDATION_PASSED")

    except Exception as e:
        result.add_error(f"Unexpected error during semantic validation: {e}", "UNEXPECTED_ERROR")
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
    schema, structural, or semantic validation based on the level parameter.
    Accepts file paths, XML strings, file-like objects, or in-memory XML trees.

    Parameters
    ----------
    xml_source : Union[str, Path, Any]
        Path to XML file, XML string content, file-like object, or ElementTree
    level : str
        Validation level: "schema", "structure", "semantic", or "all"
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
            f"Invalid validation level '{level}'. Must be one of: schema, structure, semantic, all",
            "INVALID_VALIDATION_LEVEL",
        )
        return result

    if validation_level == ValidationLevel.SCHEMA:
        return validate_xml_against_schema(xml_source, schema_url, local_schema_path, timeout)
    elif validation_level == ValidationLevel.STRUCTURE:
        return validate_xtce_structure(xml_source)
    elif validation_level == ValidationLevel.SEMANTIC:
        # For semantic validation on XML, we need to parse first
        try:
            from space_packet_parser.xtce.definitions import XtcePacketDefinition

            parsed_definition = XtcePacketDefinition.from_xtce(xml_source)
            return validate_space_packet_parser_semantics(parsed_definition)
        except Exception as e:
            result = ValidationResult(valid=False, validation_level=ValidationLevel.SEMANTIC)
            result.add_error(f"Failed to parse XTCE document for semantic validation: {e}", "PARSE_ERROR")
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
            structure_result = validate_xtce_structure(xml_source)
            results.append(structure_result)

            # Semantic validation (requires parsing)
            try:
                from space_packet_parser.xtce.definitions import XtcePacketDefinition

                parsed_definition = XtcePacketDefinition.from_xtce(xml_source)
                semantic_result = validate_space_packet_parser_semantics(parsed_definition)
                results.append(semantic_result)
            except Exception as e:
                semantic_result = ValidationResult(valid=False, validation_level=ValidationLevel.SEMANTIC)
                semantic_result.add_error(f"Failed to parse for semantic validation: {e}", "SEMANTIC_PARSE_ERROR")
                results.append(semantic_result)

        # Combine all results
        combined_result = ValidationResult(valid=True, validation_level=ValidationLevel.ALL)
        combined_result.schema_location = schema_result.schema_location
        combined_result.schema_version = schema_result.schema_version

        total_time = 0
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
