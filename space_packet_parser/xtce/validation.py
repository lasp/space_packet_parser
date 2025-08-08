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
        return f"ERROR: {self.message}{location_str}"


@dataclass
class ValidationResult:
    """Results of XTCE document validation."""

    valid: bool
    validation_level: ValidationLevel
    errors: list[ValidationError] = field(default_factory=list)
    schema_version: Optional[str] = None
    schema_location: Optional[str] = None
    validation_time_ms: Optional[float] = None

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

    def __init__(self, message: str, validation_result: Optional[ValidationResult] = None):
        super().__init__(message)
        self.validation_result = validation_result


def _fix_known_schema_issues(schema_content: str) -> str:
    """Fix known issues in the official XTCE XSD schema.

    The official OMG XTCE schema references xml:base but doesn't declare
    the xml namespace, causing lxml validation to fail.
    """
    if 'ref="xml:base"' in schema_content:
        import re

        # Remove the problematic reference entirely since it's optional for validation
        schema_content = re.sub(
            r'\s*<attribute\s+ref="xml:base"\s*/>\s*',
            "\n\t\t\t\t<!-- xml:base attribute removed for lxml compatibility -->\n\t\t\t\t",
            schema_content,
        )
        schema_content = re.sub(
            r'\s*<attribute\s+ref="xml:base"></attribute>\s*',
            "\n\t\t\t\t<!-- xml:base attribute removed for lxml compatibility -->\n\t\t\t\t",
            schema_content,
        )
    return schema_content


def _load_schema(schema_url: str, timeout: int = 30) -> tuple[ElementTree.XMLSchema, str]:
    """Load XSD schema from URL

    Parameters
    ----------
    schema_url : str
        URL to the XSD schema
    timeout : int
        Timeout in seconds for URL downloads

    Returns
    -------
    : ElementTree.XMLSchema
        Parsed schema object and its version

    Raises
    ------
    XtceValidationError
        If schema cannot be loaded or parsed
    """
    schema_content = None

    # Try to download from URL
    try:
        parsed_url = urlparse(schema_url)
        if parsed_url.scheme and parsed_url.netloc:
            with urlopen(schema_url, timeout=timeout) as response:  # noqa: S310
                schema_content = response.read()
        else:
            raise XtceValidationError(f"Invalid schema location: {schema_url}")
    except (URLError, socket.timeout) as e:
        raise XtceValidationError(f"Failed to download schema from {schema_url}: {e}") from e

    if not schema_content:
        raise XtceValidationError(f"No content loaded from schema location: {schema_url}")

    # Parse the schema
    try:
        parser = ElementTree.XMLParser(recover=True)
        schema_root_element = ElementTree.XML(schema_content, parser)

        try:
            return ElementTree.XMLSchema(schema_root_element), schema_root_element.get("version", "unknown")
        except ElementTree.XMLSchemaError as e:
            # Try to fix known issues
            content_str = schema_content.decode("utf-8") if isinstance(schema_content, bytes) else schema_content
            fixed_content = _fix_known_schema_issues(content_str)

            if fixed_content != content_str:
                try:
                    schema_root_element = ElementTree.XML(fixed_content.encode("utf-8"), parser)
                    return ElementTree.XMLSchema(schema_root_element), schema_root_element.get("version", "unknown")
                except ElementTree.XMLSchemaError:
                    pass  # Fall through to raise original error

            raise XtceValidationError(f"Invalid XSD schema from {schema_url}: {e}") from e

    except ElementTree.XMLSyntaxError as e:
        raise XtceValidationError(f"Failed to parse XSD schema from {schema_url}: {e}") from e


def _validate_xtce_schema(
    # TODO: Be specific about what types are allowed: string filepath, Path filepath, or direct string input
    xml_tree: ElementTree.ElementTree,
    timeout: int = 30,
) -> ValidationResult:
    """Validate XML document against XSD schema.

    Parameters
    ----------
    xml_tree : ElementTree.ElementTree
        XTCE XML tree object
    timeout : int
        Timeout in seconds for schema downloads

    Returns
    -------
    ValidationResult
        Validation results with errors and warnings
    """
    start_time = time.time()
    result = ValidationResult(valid=True, validation_level=ValidationLevel.SCHEMA)

    try:
        # Get root element
        root = xml_tree.getroot() if hasattr(xml_tree, "getroot") else xml_tree

        # Check for namespace presence
        try:
            # Find schema location
            try:
                schema_location_attr = root.attrib.get("{http://www.w3.org/2001/XMLSchema-instance}schemaLocation")
                schema_location = schema_location_attr.split()[-1]
            except Exception:
                raise XtceValidationError(
                    "No 'xsi' namespace found in document. XTCE documents must declare the 'xsi' "
                    "namespace for schema validation via the 'xsi:schemaLocation' attribute."
                )
        except XtceValidationError as e:
            result.add_error(str(e), "MISSING_NAMESPACE")
            return result

        result.schema_location = schema_location

        # Load the schema
        try:
            schema, version = _load_schema(schema_location, timeout)
        except XtceValidationError as e:
            result.add_error(str(e), "SCHEMA_LOAD_ERROR")
            return result

        # Find the XSD version from the schema root element
        result.schema_version = version

        # Validate the document
        if not schema.validate(xml_tree):
            result.valid = False
            for error in schema.error_log:
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
        result.validation_time_ms = (time.time() - start_time) * 1000

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
        Structural validation results
    """
    start_time = time.time()
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
        result.validation_time_ms = (time.time() - start_time) * 1000

    return result


def validate_xtce(
    xml_source: Union[str, Path, ElementTree.ElementTree],
    level: str = "schema",
    timeout: int = 30,
) -> ValidationResult:
    """Validate an XTCE XML document.

    This is the main validation entry point for XTCE documents. It can perform
    schema or structural validation based on the level parameter.

    Parameters
    ----------
    xml_source : Union[str, Path, ElementTree.ElementTree]
        Path to XML file, XML string content, or ElementTree
    level : str
        Validation level: "schema", "structure", or "all"
    timeout : int
        Timeout in seconds for schema downloads

    Returns
    -------
    ValidationResult
        Validation results with errors, warnings, and metadata
    """
    try:
        validation_level = ValidationLevel(level.lower())
    except ValueError:
        result = ValidationResult(valid=False, validation_level=ValidationLevel.SCHEMA)
        result.add_error(
            f"Invalid validation level '{level}'. Must be one of: schema, structure, all",
            "INVALID_VALIDATION_LEVEL",
        )
        return result

    # Parse XML document into a tree object
    if isinstance(xml_source, ElementTree.ElementTree):
        xml_tree = xml_source
    elif isinstance(xml_source, Path):
        xml_tree = ElementTree.parse(str(xml_source))
    else:
        xml_tree = ElementTree.parse(xml_source)

    if validation_level == ValidationLevel.SCHEMA:
        return _validate_xtce_schema(xml_tree, timeout)

    elif validation_level == ValidationLevel.STRUCTURE:
        return _validate_xtce_structure(xml_tree)

    elif validation_level == ValidationLevel.ALL:
        # Perform both validations
        schema_result = _validate_xtce_schema(xml_tree, timeout)

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

        return combined
