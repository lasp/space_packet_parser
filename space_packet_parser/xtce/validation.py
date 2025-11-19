"""XTCE document validation classes and utilities."""

import hashlib
import logging
import os
import platform
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import urlopen

import lxml.etree as ElementTree

logger = logging.getLogger(__name__)


class ValidationLevel(Enum):
    """Validation levels for XTCE documents."""

    SCHEMA = "schema"  # Validated against XSD
    STRUCTURE = "structure"  # Validated against XTCE-specific non-schema rules
    ALL = "all"  # Both


@dataclass
class ValidationError:
    """Represents a validation error or warning."""

    message: str
    error_code: str
    xpath_location: str | None = None
    line_number: int | None = None
    column_number: int | None = None
    context: dict[str, Any] | None = field(default_factory=dict)

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
        return f"{self.error_code}: {self.message}{location_str}"


@dataclass
class ValidationResult:
    """Results of XTCE document validation."""

    valid: bool
    validation_level: ValidationLevel
    errors: list[ValidationError] = field(default_factory=list)
    schema_version: str | None = None
    schema_location: str | None = None
    validation_time_ms: float | None = None

    def __bool__(self):
        return self.valid and not self.errors

    def add_error(
        self,
        message: str,
        error_code: str,
        xpath_location: str | None = None,
        line_number: int | None = None,
        context: dict[str, Any] | None = None,
    ):
        """Add a validation error."""
        error = ValidationError(
            message=message,
            error_code=error_code,
            xpath_location=xpath_location,
            line_number=line_number,
            context=context or {},
        )
        self.errors.append(error)
        self.valid = False

    def __str__(self) -> str:
        """String representation of validation result."""
        status = "VALID" if self.valid else "INVALID"
        result = f"Validation Result: {status} ({self.validation_level.value} level)\n"

        if self.errors:
            result += f"\nErrors ({len(self.errors)}):\n"
            for error in self.errors:
                result += f"  {error}\n"

        return result


class XtceValidationError(Exception):
    """Exception raised during XTCE validation."""

    def __init__(self, message: str, validation_result: ValidationResult | None = None):
        super().__init__(message)
        self.validation_result = validation_result


def _get_cache_dir() -> Path:
    """Get cross-platform cache directory for space_packet_parser."""
    system = platform.system()
    home = Path.home()

    if system == "Linux" or system.startswith("CYGWIN"):
        # Respect XDG_CACHE_HOME if set, otherwise use ~/.cache
        cache_home = os.environ.get("XDG_CACHE_HOME")
        if cache_home:
            return Path(cache_home) / "space_packet_parser"
        return home / ".cache" / "space_packet_parser"

    elif system == "Darwin":  # macOS
        return home / "Library" / "Caches" / "space_packet_parser"

    elif system == "Windows":
        # Prefer LOCALAPPDATA, fall back to APPDATA
        local_appdata = os.environ.get("LOCALAPPDATA")
        if local_appdata:
            return Path(local_appdata) / "space_packet_parser" / "Cache"
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "space_packet_parser" / "Cache"
        # Final fallback
        return home / "AppData" / "Local" / "space_packet_parser" / "Cache"

    else:
        # Unknown platform, use generic fallback
        return home / ".space_packet_parser_cache"


def _get_cache_path(schema_url: str) -> Path:
    """Get cache file path for a schema URL using SHA-256 hash."""
    cache_dir = _get_cache_dir() / "schemas"
    url_hash = hashlib.sha256(schema_url.encode("utf-8")).hexdigest()
    return cache_dir / f"{url_hash}.xsd"


def _read_from_cache(cache_path: Path) -> bytes | None:
    """Read cached schema content, return None if not found or unreadable."""
    try:
        if cache_path.exists():
            return cache_path.read_bytes()
    except OSError as e:
        logger.debug(f"Failed to read from cache {cache_path}: {e}")
    return None


def _write_to_cache(cache_path: Path, content: bytes) -> None:
    """Write content to cache, creating directories as needed."""
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_bytes(content)
        logger.debug(f"Cached schema to {cache_path}")
    except OSError as e:
        logger.warning(f"Failed to write schema to cache {cache_path}: {e}")


def _fix_known_schema_issues(schema_content: bytes) -> bytes:
    """Fix known issues in the official XTCE XSD schema.

    The official OMG XTCE schema references xml:base but doesn't declare
    the xml namespace, causing lxml validation to fail.

    Parameters
    ----------
    schema_content : bytes
        The schema content as bytes

    Returns
    -------
    bytes
        The fixed schema content as bytes
    """
    # Decode to string for regex processing
    content_str = schema_content.decode("utf-8")

    if 'ref="xml:base"' in content_str:
        import re

        # Remove the problematic reference entirely since it's optional for validation
        content_str = re.sub(
            r'\s*<attribute\s+ref="xml:base"\s*/>\s*',
            "\n\t\t\t\t<!-- xml:base attribute removed for lxml compatibility -->\n\t\t\t\t",
            content_str,
        )
        content_str = re.sub(
            r'\s*<attribute\s+ref="xml:base"></attribute>\s*',
            "\n\t\t\t\t<!-- xml:base attribute removed for lxml compatibility -->\n\t\t\t\t",
            content_str,
        )

    # Return as bytes
    return content_str.encode("utf-8")


def _load_schema(schema_location: str | Path, timeout: int = 30) -> tuple[ElementTree.XMLSchema, str]:
    """Load XSD schema from URL or local path

    Parameters
    ----------
    schema_location : Union[str, Path]
        URL or local path to the XSD schema document
    timeout : int
        Timeout in seconds for URL downloads

    Returns
    -------
    : tuple[ElementTree.XMLSchema, str]
        Parsed XMLSchema object and version string

    Raises
    ------
    XtceValidationError
        If schema cannot be loaded or parsed
    """

    def _is_http_url(s):
        result = urlparse(s)
        return result if all([result.scheme in ("http", "https"), result.netloc]) else False

    parser = ElementTree.XMLParser(recover=True)

    # If the location is a string that parses as a URL
    if isinstance(schema_location, str) and (_is_http_url(schema_location)):
        # Check cache first
        cache_path = _get_cache_path(schema_location)
        schema_content = _read_from_cache(cache_path)

        if schema_content is None:
            # Cache miss - download from URL
            try:
                with urlopen(schema_location, timeout=timeout) as response:  # noqa: S310
                    schema_content = response.read()
                # Cache the raw downloaded content before any fixes
                _write_to_cache(cache_path, schema_content)
            except (TimeoutError, URLError) as e:
                raise XtceValidationError(f"Failed to download schema from {schema_location}: {e}") from e
        else:
            logger.debug(f"Using cached schema from {cache_path}")
    # Otherwise assume a local filepath
    else:
        with Path(schema_location).open("rb") as sfh:
            schema_content = sfh.read()

    # Fix and parse the schema content
    try:
        schema_root_element = ElementTree.XML(schema_content, parser)
    except ElementTree.XMLSyntaxError as e:
        raise XtceValidationError(f"Failed to parse XSD schema from {schema_location}: {e}") from e

    try:
        return ElementTree.XMLSchema(schema_root_element), schema_root_element.get("version", "unknown")
    except ElementTree.XMLSchemaError as e:
        # Try to fix known issues
        logger.debug("Attempting to fix known XTCE schema problems")
        fixed_content = _fix_known_schema_issues(schema_content)

        if fixed_content != schema_content:
            try:
                schema_root_element = ElementTree.XML(fixed_content, parser)
                return ElementTree.XMLSchema(schema_root_element), schema_root_element.get("version", "unknown")
            except ElementTree.XMLSchemaError:
                pass  # Fall through to raise original error

        raise XtceValidationError(
            f"Invalid XSD schema from {schema_location} (attempted to fix known errors): {e}"
        ) from e


def _find_schema_url(xml_tree: ElementTree.ElementTree) -> str:
    """Find the XSD location from the root attributes of the document

    Parameters
    ----------
    xml_tree : ElementTree.ElementTree
        XML tree of document being validated

    Returns
    -------
    schema_location : str
        URL of XSD
    """
    # Get root element
    root = xml_tree.getroot() if hasattr(xml_tree, "getroot") else xml_tree

    # Find schema location
    try:
        schema_location_attr = root.attrib.get("{http://www.w3.org/2001/XMLSchema-instance}schemaLocation")
        return schema_location_attr.split()[-1]
    except Exception:
        raise XtceValidationError(
            "No 'xsi' namespace found in document. XTCE documents must declare the 'xsi' "
            "namespace for schema validation via the 'xsi:schemaLocation' attribute."
        )


def _validate_xtce_schema(
    xml_tree: ElementTree.ElementTree,
    local_xsd: str | Path | None = None,
    timeout: int = 30,
) -> ValidationResult:
    """Validate XML document against XSD schema.

    Parameters
    ----------
    xml_tree : ElementTree.ElementTree
        XTCE XML tree object
    local_xsd : Optional[Union[str, Path]]
        Optional local schema location. If specified, schema references in root element (or lack thereof) are ignored.
    timeout : int
        Timeout in seconds for schema downloads

    Returns
    -------
    : ValidationResult
        Truthy if result is valid, Falsy otherwise
    """
    start_time = time.perf_counter()
    result = ValidationResult(valid=True, validation_level=ValidationLevel.SCHEMA)

    try:
        if local_xsd:
            # TODO: Load the XSD from local file
            schema_location = str(local_xsd)
        else:
            try:
                # Find the URL of the XSD
                schema_location = _find_schema_url(xml_tree)
            except XtceValidationError as no_schema_location_err:
                result.add_error(message=str(no_schema_location_err), error_code="MISSING_SCHEMA_LOCATION")
                return result

        # Store schema location in result
        result.schema_location = schema_location

        # Load the schema
        try:
            schema, version = _load_schema(schema_location, timeout)
            result.schema_version = version
        except XtceValidationError as e:
            result.add_error(str(e), "SCHEMA_LOAD_ERROR")
            return result

        # Validate the document
        if not schema.validate(xml_tree):
            result.valid = False
            for error in schema.error_log:
                if "No matching global declaration available for the validation root." in error.message:
                    result.add_error(
                        message="Namespace issue detected. Does the `xmlns[:xtce]=<chosen_xtce_uri>` URI on your document root element match the `targetNamespace` URI in your XSD? Typically this is http://www.omg.org/spec/XTCE/20180204.",
                        error_code="INVALID_XTCE_NAMESPACE",
                        context={
                            "nsmap": xml_tree.getroot().nsmap,
                        },
                    )
                result.add_error(
                    message=str(error.message),
                    error_code="SCHEMA_VALIDATION_ERROR",
                    line_number=error.line,
                    context={
                        "domain": error.domain_name,
                        "type": error.type_name,
                        "level": error.level_name,
                    },
                )

    except OSError as e:
        result.add_error(f"IO error during validation: {e}", "IO_ERROR")
    finally:
        result.validation_time_ms = (time.perf_counter() - start_time) * 1000

    return result


def _validate_xtce_structure(xml_tree: ElementTree.ElementTree) -> ValidationResult:
    """Validate XTCE document structure and reference integrity.

    This performs structural validation beyond XSD schema validation,
    checking XTCE-specific business rules and reference integrity.

    Parameters
    ----------
    xml_tree: ElementTree.ElementTree
        Parsed XML tree of the XTCE document

    Returns
    -------
    ValidationResult
        Truthy if result is valid, Falsy otherwise
    """
    start_time = time.perf_counter()
    result = ValidationResult(valid=True, validation_level=ValidationLevel.STRUCTURE)

    try:
        root = xml_tree.getroot() if hasattr(xml_tree, "getroot") else xml_tree

        # Define namespaces for XPath queries
        namespaces = {"xtce": "http://www.omg.org/spec/XTCE/20180204"}

        # Extract all ParameterTypes
        parameter_types = set()
        parameter_type_elements = root.xpath("//xtce:ParameterTypeSet//*[@name]", namespaces=namespaces)
        for elem in parameter_type_elements:
            if elem.tag.endswith("ParameterType"):
                parameter_types.add(elem.get("name"))

        # Extract all Parameters
        parameters = set()
        parameter_elements = root.xpath("//xtce:ParameterSet/xtce:Parameter", namespaces=namespaces)
        for elem in parameter_elements:
            parameters.add(elem.get("name"))

        # Extract all SequenceContainers
        containers = set()
        container_elements = root.xpath("//xtce:ContainerSet/xtce:SequenceContainer", namespaces=namespaces)
        for elem in container_elements:
            containers.add(elem.get("name"))

        # Track which ParameterTypes and Parameters are referenced
        referenced_parameter_types = set()
        referenced_parameters = set()

        # Check Parameter references to ParameterTypes
        for param_elem in parameter_elements:
            param_name = param_elem.get("name")
            param_type_ref = param_elem.get("parameterTypeRef")

            if param_type_ref:
                referenced_parameter_types.add(param_type_ref)
                if param_type_ref not in parameter_types:
                    result.add_error(
                        f"Parameter '{param_name}' references nonexistent ParameterType '{param_type_ref}'",
                        "MISSING_PARAMETER_TYPE_REFERENCE",
                        xpath_location=f"//xtce:Parameter[@name='{param_name}']",
                    )

        # Check ParameterRefEntry references in SequenceContainers
        param_ref_entries = root.xpath("//xtce:ParameterRefEntry", namespaces=namespaces)
        for entry in param_ref_entries:
            param_ref = entry.get("parameterRef")
            if param_ref:
                referenced_parameters.add(param_ref)
                if param_ref not in parameters:
                    result.add_error(
                        f"SequenceContainer references nonexistent Parameter '{param_ref}'",
                        "MISSING_PARAMETER_REFERENCE",
                        xpath_location=f"//xtce:ParameterRefEntry[@parameterRef='{param_ref}']",
                    )

        # Check BaseContainer references to SequenceContainers
        base_containers = root.xpath("//xtce:BaseContainer", namespaces=namespaces)
        for base_container in base_containers:
            container_ref = base_container.get("containerRef")
            if container_ref and container_ref not in containers:
                result.add_error(
                    f"BaseContainer references nonexistent SequenceContainer '{container_ref}'",
                    "MISSING_CONTAINER_REFERENCE",
                    xpath_location=f"//xtce:BaseContainer[@containerRef='{container_ref}']",
                )

        # Check for unused ParameterTypes
        unused_parameter_types = parameter_types - referenced_parameter_types
        for unused_type in unused_parameter_types:
            result.add_error(
                f"ParameterType '{unused_type}' is defined but never used",
                "UNUSED_PARAMETER_TYPE",
                xpath_location=f"//xtce:*[@name='{unused_type}']",
            )

        # Check for unused Parameters
        unused_parameters = parameters - referenced_parameters
        for unused_param in unused_parameters:
            result.add_error(
                f"Parameter '{unused_param}' is defined but never used",
                "UNUSED_PARAMETER",
                xpath_location=f"//xtce:Parameter[@name='{unused_param}']",
            )

    except Exception as e:
        result.add_error(f"Error during structural validation: {e}", "STRUCTURAL_VALIDATION_ERROR")
    finally:
        result.validation_time_ms = (time.perf_counter() - start_time) * 1000

    return result


def validate_xtce(
    xml_source: str | Path | ElementTree.ElementTree,
    level: str = "all",
    timeout: int = 30,
    print_results: bool = True,
    raise_on_error: bool = True,
    local_xsd: str | Path | None = None,
) -> ValidationResult:
    """Validate an XTCE XML document.

    This is the main validation entry point for XTCE documents. It can perform
    schema or structural validation based on the level parameter.

    Parameters
    ----------
    xml_source : Union[str, Path, ElementTree.ElementTree]
        Path to XML file, XML string content, or ElementTree
    level : str
        Validation level: "schema", "structure", or "all". Default "all".
    timeout : int
        Timeout in seconds for schema downloads
    print_results : bool
        Default True. Prints results before returning Truthy or Falsy result.
    raise_on_error : bool
        Default True. If False, returns a ValidationResult object with information about the validation results.
        If True, raises an exception unless the ValidationResult reports valid.
    local_xsd : Optional[str, Path]
        Local path to an XSD for schema validation. If not provided and schema validation is requested,
        XSD is retrieved from schema reference attribute in document root.

    Returns
    -------
    ValidationResult
        Truthy if result is valid, Falsy otherwise
    """
    try:
        validation_level = ValidationLevel(level.lower())
    except ValueError as invalid_level:
        raise ValueError(f"Validation level must be one of {[_.value for _ in ValidationLevel]}") from invalid_level

    # Parse XML document into a tree object
    try:
        if isinstance(xml_source, ElementTree.ElementTree):
            xml_tree = xml_source
        elif isinstance(xml_source, Path):
            xml_tree = ElementTree.parse(str(xml_source))
        else:
            xml_tree = ElementTree.parse(xml_source)
    except Exception as e:
        raise XtceValidationError(
            "Failed to parse XTCE document as valid XML. This indicates malformed XML and is not XTCE specific."
        ) from e

    if validation_level == ValidationLevel.SCHEMA:
        result = _validate_xtce_schema(xml_tree, local_xsd=local_xsd, timeout=timeout)

    elif validation_level == ValidationLevel.STRUCTURE:
        result = _validate_xtce_structure(xml_tree)

    elif validation_level == ValidationLevel.ALL:
        # Perform both validations
        schema_result = _validate_xtce_schema(xml_tree, local_xsd=local_xsd, timeout=timeout)

        # Try structural validation even if schema fails
        structure_result = _validate_xtce_structure(xml_tree)

        # Combine results
        combined = ValidationResult(
            valid=schema_result.valid and structure_result.valid,
            validation_level=ValidationLevel.ALL,
            schema_location=schema_result.schema_location,
            schema_version=schema_result.schema_version,
        )

        combined.errors.extend(schema_result.errors)
        combined.errors.extend(structure_result.errors)

        if schema_result.validation_time_ms and structure_result.validation_time_ms:
            combined.validation_time_ms = schema_result.validation_time_ms + structure_result.validation_time_ms

        result = combined

    if print_results:
        for val_err in result.errors:
            print(val_err)
        print(f"Found {len(result.errors)} validation errors.")
        print(f"Document {'VALID' if result.valid else 'INVALID'}.")

    for val_err in result.errors:
        logger.warning(val_err)
    logger.info(f"Found {len(result.errors)} validation errors.")
    logger.info(f"Document {'VALID' if result.valid else 'INVALID'}.")

    if raise_on_error and ((not result.valid) or result.errors):
        raise XtceValidationError(
            f"Document failed validation with {len(result.errors)} errors. "
            "To examine errors in detail, run validation with raise_on_error=False and examine returned result object."
        )

    return result
