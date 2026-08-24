"""XTCE document validation classes and utilities."""

from __future__ import annotations

import hashlib
import ipaddress
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

# Directory holding XSD schemas bundled with the package. Bundled schemas are
# resolved offline (no network request) which is both faster and closes the
# SSRF/LFI surface for the common case of validating against the standard XTCE schema.
_BUNDLED_SCHEMA_DIR = Path(__file__).parent / "schemas"

# Maps a scheme-insensitive "host/path" key to a bundled schema filename. Any
# schemaLocation URL (http or https) whose host+path matches is served from disk.
_BUNDLED_SCHEMAS: dict[str, str] = {
    "www.omg.org/spec/XTCE/20180204/SpaceSystem.xsd": "SpaceSystem.xsd",
}

# Default allowlist of hosts that schema URLs may point at. Exported so callers
# can extend it explicitly, e.g. allowed_schema_hosts=[*DEFAULT_ALLOWED_SCHEMA_HOSTS, "my-mirror"].
DEFAULT_ALLOWED_SCHEMA_HOSTS = frozenset({"www.omg.org"})

# Environment-variable overrides for the schema-fetch policy.
ALLOWED_SCHEMA_HOSTS_ENV_VAR = "SPP_ALLOWED_SCHEMA_HOSTS"
ALLOW_INSECURE_HTTP_ENV_VAR = "SPP_ALLOW_INSECURE_HTTP"

# Hard cap on downloaded schema size to bound memory use and disk writes from a
# hostile or misbehaving host. XTCE schemas are a few hundred KB.
MAX_SCHEMA_BYTES = 10 * 1024 * 1024


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

    def __init__(
        self,
        message: str,
        validation_result: ValidationResult | None = None,
        error_code: str | None = None,
    ):
        super().__init__(message)
        self.validation_result = validation_result
        # Optional machine-readable code so callers (e.g. _validate_xtce_schema) can map
        # the failure onto the correct ValidationResult error_code instead of a generic one.
        self.error_code = error_code


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
    """Write content to cache, creating directories as needed.

    The cache directory and file are created with owner-only permissions so cached schemas are
    not world-readable on shared hosts. The cache filename is a SHA-256 hash of the URL, so no
    user-controlled component reaches the filesystem path (no traversal is possible).
    """
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        cache_path.write_bytes(content)
        try:
            cache_path.chmod(0o600)
        except OSError as e:
            logger.debug(f"Could not set cache file permissions on {cache_path}: {e}")
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


def _resolve_schema_policy(
    allowed_schema_hosts: list[str] | tuple[str, ...] | frozenset[str] | None,
    allow_insecure_http: bool,
) -> tuple[frozenset[str], bool]:
    """Resolve the effective schema-fetch policy from argument, environment, then default.

    The explicit argument wins; otherwise the environment variable is consulted; otherwise the
    built-in default is used. Layers replace (do not merge) so the effective allowlist is always
    whatever the most specific layer specifies.
    """
    if allowed_schema_hosts is not None:
        allowed = frozenset(str(h).strip() for h in allowed_schema_hosts if str(h).strip())
    else:
        env_hosts = os.environ.get(ALLOWED_SCHEMA_HOSTS_ENV_VAR)
        if env_hosts:
            allowed = frozenset(h.strip() for h in env_hosts.split(",") if h.strip())
        else:
            allowed = DEFAULT_ALLOWED_SCHEMA_HOSTS

    if not allow_insecure_http:
        env_http = os.environ.get(ALLOW_INSECURE_HTTP_ENV_VAR, "")
        allow_insecure_http = env_http.strip().lower() in ("1", "true", "yes", "on")

    return allowed, allow_insecure_http


def _bundled_schema_path(schema_location: str) -> Path | None:
    """Return the on-disk path of a bundled schema matching a URL, or None if there is no match.

    Matching is scheme-insensitive (http and https map to the same bundled file) and keyed on host+path.
    """
    parsed = urlparse(schema_location)
    if parsed.scheme not in ("http", "https"):
        return None
    key = f"{parsed.netloc.lower()}{parsed.path}"
    filename = _BUNDLED_SCHEMAS.get(key)
    if filename is None:
        return None
    return _BUNDLED_SCHEMA_DIR / filename


def _reject_internal_host(host: str | None, schema_location: str) -> None:
    """Reject a schema URL whose host is a non-public IP literal (SSRF hardening, CWE-918).

    Only IP literals are inspected here; hostnames are governed by the allowlist. This
    deterministically blocks the metadata-endpoint and loopback PoCs (169.254.169.254, 127.0.0.1)
    which are expressed as literal IPs. A hostname that resolves to an internal address (DNS
    rebinding) is out of scope for this check and is constrained instead by the host allowlist.
    """
    if not host:
        return
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return  # Not an IP literal; the host allowlist is the control for hostnames.
    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
        raise XtceValidationError(
            f"Schema URL host {host} is a non-public address and is not allowed: {schema_location}",
            error_code="DISALLOWED_SCHEMA_LOCATION",
        )


def _normalize_url(url: str) -> str:
    """Normalize a URL for allowlist comparison (lowercase scheme+host, keep path)."""
    parsed = urlparse(url)
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{parsed.path}"


def _url_matches_allowlist(schema_location: str, parsed_host: str | None, allowed_hosts: frozenset[str]) -> bool:
    """Return True if the URL matches an allowlist entry.

    An allowlist entry containing '://' is matched as an exact (normalized) URL; a bare entry is
    matched against the URL's hostname. Matching is exact — never a suffix/substring test.
    """
    host = (parsed_host or "").lower()
    normalized = _normalize_url(schema_location)
    for entry in allowed_hosts:
        entry = entry.strip()
        if not entry:
            continue
        if "://" in entry:
            if _normalize_url(entry) == normalized:
                return True
        elif entry.lower() == host:
            return True
    return False


def _enforce_schema_url_policy(schema_location: str, allowed_hosts: frozenset[str], allow_insecure_http: bool) -> None:
    """Enforce scheme, internal-host, and allowlist policy on an outbound schema URL (CWE-918)."""
    parsed = urlparse(schema_location)
    allowed_schemes = ("https", "http") if allow_insecure_http else ("https",)
    if parsed.scheme not in allowed_schemes:
        allowed_desc = "http or https" if allow_insecure_http else "https"
        raise XtceValidationError(
            f"Schema URL scheme '{parsed.scheme}' is not allowed (only {allowed_desc}): {schema_location}",
            error_code="DISALLOWED_SCHEMA_LOCATION",
        )
    _reject_internal_host(parsed.hostname, schema_location)
    if not _url_matches_allowlist(schema_location, parsed.hostname, allowed_hosts):
        raise XtceValidationError(
            f"Schema URL is not in the allowlist {sorted(allowed_hosts)}: {schema_location}. "
            f"Add the host/URL via allowed_schema_hosts or {ALLOWED_SCHEMA_HOSTS_ENV_VAR}, or pass local_xsd.",
            error_code="DISALLOWED_SCHEMA_LOCATION",
        )


def _parse_schema_content(schema_content: bytes, source: str) -> tuple[ElementTree.XMLSchema, str]:
    """Parse raw XSD bytes into an XMLSchema, applying known-issue fixes if the first parse fails.

    Raises XtceValidationError (error_code SCHEMA_LOAD_ERROR) if the content is not a usable XSD.
    """
    parser = ElementTree.XMLParser(recover=True)
    try:
        schema_root_element = ElementTree.XML(schema_content, parser)
    except ElementTree.XMLSyntaxError as e:
        raise XtceValidationError(
            f"Failed to parse XSD schema from {source}: {e}", error_code="SCHEMA_LOAD_ERROR"
        ) from e

    try:
        return ElementTree.XMLSchema(schema_root_element), schema_root_element.get("version", "unknown")
    except ElementTree.XMLSchemaError as e:
        logger.debug("Attempting to fix known XTCE schema problems")
        fixed_content = _fix_known_schema_issues(schema_content)
        if fixed_content != schema_content:
            try:
                fixed_root = ElementTree.XML(fixed_content, parser)
                return ElementTree.XMLSchema(fixed_root), fixed_root.get("version", "unknown")
            except ElementTree.XMLSchemaError:
                pass  # Fall through to raise the original error
        raise XtceValidationError(
            f"Invalid XSD schema from {source} (attempted to fix known errors): {e}",
            error_code="SCHEMA_LOAD_ERROR",
        ) from e


def _download_schema(schema_location: str, timeout: int) -> tuple[ElementTree.XMLSchema, str]:
    """Download, size-cap, validate, and cache a schema URL that has already passed policy checks.

    The raw downloaded bytes are written to the cache only after they successfully validate as an
    XSD, so a non-schema response (e.g. an SSRF probe body or error page) is never persisted.
    """
    cache_path = _get_cache_path(schema_location)
    cached = _read_from_cache(cache_path)
    if cached is not None:
        logger.debug(f"Using cached schema from {cache_path}")
        return _parse_schema_content(cached, schema_location)

    try:
        with urlopen(schema_location, timeout=timeout) as response:  # noqa: S310
            declared = response.headers.get("Content-Length")
            if declared is not None:
                try:
                    declared_size = int(declared)
                except (ValueError, TypeError):
                    declared_size = None
                if declared_size is not None and declared_size > MAX_SCHEMA_BYTES:
                    raise XtceValidationError(
                        f"Schema at {schema_location} exceeds the maximum allowed size ({MAX_SCHEMA_BYTES} bytes).",
                        error_code="SCHEMA_LOAD_ERROR",
                    )
            # Read one byte past the cap so an oversized body with a missing/incorrect
            # Content-Length is still detected below.
            schema_content = response.read(MAX_SCHEMA_BYTES + 1)
    except (TimeoutError, URLError) as e:
        raise XtceValidationError(
            f"Failed to download schema from {schema_location}: {e}", error_code="SCHEMA_LOAD_ERROR"
        ) from e

    if len(schema_content) > MAX_SCHEMA_BYTES:
        raise XtceValidationError(
            f"Schema at {schema_location} exceeds the maximum allowed size ({MAX_SCHEMA_BYTES} bytes).",
            error_code="SCHEMA_LOAD_ERROR",
        )

    schema, version = _parse_schema_content(schema_content, schema_location)
    # Only cache content that validated as an XSD.
    _write_to_cache(cache_path, schema_content)
    return schema, version


def _load_schema(
    schema_location: str | Path,
    timeout: int = 30,
    *,
    allowed_schema_hosts: list[str] | tuple[str, ...] | frozenset[str] | None = None,
    allow_insecure_http: bool = False,
    allow_schema_download: bool = True,
    trusted: bool = False,
) -> tuple[ElementTree.XMLSchema, str]:
    """Load an XSD schema from a bundled schema, an http(s) URL, or a trusted local path.

    Resolution order:
      1. If ``schema_location`` matches a schema bundled with the package, it is read from disk
         with no network request or policy check (it is a trusted, package-owned file).
      2. If it is an http(s) URL, the SSRF policy (scheme, internal-host, allowlist) is enforced
         and, unless disabled, the schema is downloaded (size-capped) and cached.
      3. If it is a local filesystem path, it is opened only when ``trusted=True`` (i.e. an
         operator-supplied ``local_xsd``); document-derived local paths are refused (CWE-73).

    Parameters
    ----------
    schema_location : Union[str, Path]
        URL or local path to the XSD schema document.
    timeout : int
        Timeout in seconds for URL downloads.
    allowed_schema_hosts : Optional collection of str
        Hosts and/or exact URLs that schema downloads may target. None resolves via environment,
        then the built-in default (``www.omg.org``).
    allow_insecure_http : bool
        If True, permit ``http`` URLs in addition to ``https``. Dangerous; off by default.
    allow_schema_download : bool
        If False, never make a network request (bundled schemas and local paths still work).
    trusted : bool
        If True, a local filesystem path may be opened directly (used for operator-supplied local_xsd).

    Returns
    -------
    : tuple[ElementTree.XMLSchema, str]
        Parsed XMLSchema object and version string.

    Raises
    ------
    XtceValidationError
        If the schema cannot be loaded, is disallowed by policy, or cannot be parsed.
    """
    location = str(schema_location)

    # 1. Bundled schema (offline, no policy needed — it is our own file).
    bundled = _bundled_schema_path(location)
    if bundled is not None:
        try:
            content = bundled.read_bytes()
        except OSError as e:
            raise XtceValidationError(
                f"Failed to read bundled schema {bundled}: {e}", error_code="SCHEMA_LOAD_ERROR"
            ) from e
        return _parse_schema_content(content, location)

    is_url = urlparse(location).scheme in ("http", "https")

    # 2. Remote URL: enforce SSRF policy, then cache/download.
    if is_url:
        if not allow_schema_download:
            raise XtceValidationError(
                f"Schema download is disabled and no bundled schema matches: {location}. "
                "Pass local_xsd, or enable allow_schema_download.",
                error_code="SCHEMA_LOAD_ERROR",
            )
        allowed_hosts, allow_insecure_http = _resolve_schema_policy(allowed_schema_hosts, allow_insecure_http)
        _enforce_schema_url_policy(location, allowed_hosts, allow_insecure_http)
        return _download_schema(location, timeout)

    # 3. Local filesystem path: only trusted (operator-supplied) paths may be opened.
    if not trusted:
        raise XtceValidationError(
            f"Refusing to load a schema from an untrusted local path: {location}. "
            "Document-supplied xsi:schemaLocation must be an allowlisted http(s) URL; "
            "use local_xsd to validate against a local schema.",
            error_code="DISALLOWED_SCHEMA_LOCATION",
        )
    try:
        content = Path(location).read_bytes()
    except OSError as e:
        raise XtceValidationError(
            f"Schema file not found or unreadable: {location}", error_code="SCHEMA_LOAD_ERROR"
        ) from e
    return _parse_schema_content(content, location)


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

    Raises
    ------
    XtceValidationError
        If schema location is invalid or missing
    """
    # Get root element
    root = xml_tree.getroot() if hasattr(xml_tree, "getroot") else xml_tree

    # Find schema location
    try:
        schema_location_attr = root.attrib.get("{http://www.w3.org/2001/XMLSchema-instance}schemaLocation")
        schema_location = schema_location_attr.split()[-1]
    except Exception:
        raise XtceValidationError(
            "No 'xsi' namespace found in document. XTCE documents must declare the 'xsi' "
            "namespace for schema validation via the 'xsi:schemaLocation' attribute.",
            error_code="MISSING_SCHEMA_LOCATION",
        )

    # A document-supplied location is untrusted. Anything that is not an http(s) URL is treated as
    # a local filesystem reference and rejected to prevent local file disclosure (CWE-73). This
    # covers absolute POSIX/Windows/UNC paths, relative paths, bare filenames, and non-http schemes
    # such as file:// and ftp://. Host/scheme allowlist policy is enforced later, at load time,
    # after bundled-schema resolution.
    if urlparse(schema_location).scheme not in ("http", "https"):
        raise XtceValidationError(
            f"xsi:schemaLocation must be an http(s) URL, got: {schema_location!r}. "
            "To validate against a local schema, pass local_xsd explicitly.",
            error_code="DISALLOWED_SCHEMA_LOCATION",
        )

    return schema_location


def _validate_xtce_schema(
    xml_tree: ElementTree.ElementTree,
    local_xsd: str | Path | None = None,
    timeout: int = 30,
    allowed_schema_hosts: list[str] | tuple[str, ...] | frozenset[str] | None = None,
    allow_insecure_http: bool = False,
    allow_schema_download: bool = True,
) -> ValidationResult:
    """Validate XML document against XSD schema.

    Parameters
    ----------
    xml_tree : ElementTree.ElementTree
        XTCE XML tree object
    local_xsd : Optional[Union[str, Path]]
        Optional local schema location. If specified, schema references in root element (or lack thereof) are ignored.
        This is a trusted, caller-supplied path and is opened directly regardless of location.
    timeout : int
        Timeout in seconds for schema downloads
    allowed_schema_hosts : Optional collection of str
        Hosts and/or exact URLs that document-derived schema downloads may target.
    allow_insecure_http : bool
        If True, permit ``http`` schema URLs in addition to ``https``. Dangerous; off by default.
    allow_schema_download : bool
        If True (default), allowlisted schema URLs may be downloaded. If False, only bundled schemas
        and ``local_xsd`` are used.

    Returns
    -------
    : ValidationResult
        Truthy if result is valid, Falsy otherwise
    """
    start_time = time.perf_counter()
    result = ValidationResult(valid=True, validation_level=ValidationLevel.SCHEMA)

    try:
        if local_xsd:
            # local_xsd is trusted, caller-supplied input: open it directly, at whatever path
            # (absolute or relative) the caller provided. No confinement is applied because this
            # is not the attacker-controlled surface (unlike document-derived xsi:schemaLocation).
            schema_location = str(local_xsd)
            trusted = True
        else:
            try:
                # Find the (untrusted) schema URL declared in the document
                schema_location = _find_schema_url(xml_tree)
            except XtceValidationError as no_schema_location_err:
                result.add_error(
                    message=str(no_schema_location_err),
                    error_code=no_schema_location_err.error_code or "MISSING_SCHEMA_LOCATION",
                )
                return result
            trusted = False

        # Store schema location in result
        result.schema_location = schema_location

        # Load the schema
        try:
            schema, version = _load_schema(
                schema_location,
                timeout,
                allowed_schema_hosts=allowed_schema_hosts,
                allow_insecure_http=allow_insecure_http,
                allow_schema_download=allow_schema_download,
                trusted=trusted,
            )
            result.schema_version = version
        except XtceValidationError as e:
            result.add_error(str(e), e.error_code or "SCHEMA_LOAD_ERROR")
            return result

        # Validate the document
        if not schema.validate(xml_tree):
            result.valid = False
            for error in schema.error_log:
                if "No matching global declaration available for the validation root." in error.message:
                    result.add_error(
                        message="Namespace issue detected. Does the `xmlns[:xtce]=<chosen_xtce_uri>` URI on your document root element match the `targetNamespace` URI in your XSD? Typically this is http://www.omg.org/spec/XTCE/20180204",
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
    allowed_schema_hosts: list[str] | tuple[str, ...] | frozenset[str] | None = None,
    allow_insecure_http: bool = False,
    allow_schema_download: bool = True,
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
        XSD is retrieved from schema reference attribute in document root. This is a trusted,
        caller-supplied path and may point anywhere on the filesystem.
    allowed_schema_hosts : Optional collection of str
        Hosts and/or exact URLs that a document-derived ``xsi:schemaLocation`` download may target.
        Entries may be bare hostnames (matched against the URL host) or full URLs (matched exactly).
        Defaults to :data:`DEFAULT_ALLOWED_SCHEMA_HOSTS` (``www.omg.org``); the
        ``SPP_ALLOWED_SCHEMA_HOSTS`` environment variable (comma-separated) is consulted when this
        argument is not provided. Bundled schemas and ``local_xsd`` are not subject to this allowlist.
    allow_insecure_http : bool
        DANGEROUS. If True, permit ``http`` schema URLs in addition to ``https``. This fetches schema
        content over an unauthenticated, tamperable channel and should only be used for trusted
        internal mirrors. The host allowlist and internal-address guard still apply. Off by default;
        may also be enabled via the ``SPP_ALLOW_INSECURE_HTTP`` environment variable.
    allow_schema_download : bool
        Default True. If True, allowlisted schema URLs referenced by the document may be downloaded.
        If False, no network request is made: only schemas bundled with the package or supplied via
        ``local_xsd`` are used.

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
        # In lxml >= 5.2.1 (Cython 3.0), ElementTree.ElementTree is a Cython function
        # rather than a class, which makes isinstance() fail with a TypeError.
        # ElementTree._ElementTree is the actual underlying class and is available in all
        # supported lxml versions.
        if isinstance(xml_source, ElementTree._ElementTree):
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
        result = _validate_xtce_schema(
            xml_tree,
            local_xsd=local_xsd,
            timeout=timeout,
            allowed_schema_hosts=allowed_schema_hosts,
            allow_insecure_http=allow_insecure_http,
            allow_schema_download=allow_schema_download,
        )

    elif validation_level == ValidationLevel.STRUCTURE:
        result = _validate_xtce_structure(xml_tree)

    elif validation_level == ValidationLevel.ALL:
        # Perform both validations
        schema_result = _validate_xtce_schema(
            xml_tree,
            local_xsd=local_xsd,
            timeout=timeout,
            allowed_schema_hosts=allowed_schema_hosts,
            allow_insecure_http=allow_insecure_http,
            allow_schema_download=allow_schema_download,
        )

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
