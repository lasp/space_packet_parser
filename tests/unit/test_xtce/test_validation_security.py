"""Security regression tests for XTCE schema validation.

These cover the LFI (CWE-73) and SSRF (CWE-918) advisories: a document-supplied
``xsi:schemaLocation`` is untrusted and must never read arbitrary local files or drive
outbound requests to non-allowlisted / internal hosts. The trusted ``local_xsd`` argument
must remain fully functional, and the standard OMG schema must validate offline via the bundle.
"""

import io
from unittest.mock import Mock, patch

import lxml.etree as ElementTree
import pytest

from space_packet_parser.xtce import validation
from space_packet_parser.xtce.validation import (
    DEFAULT_ALLOWED_SCHEMA_HOSTS,
    XtceValidationError,
    _load_schema,
    validate_xtce,
)


def _doc_with_schema_location(location: str) -> ElementTree._ElementTree:
    """Build an XTCE document tree whose xsi:schemaLocation points at ``location``."""
    xml = (
        '<xtce:SpaceSystem name="Test" xmlns:xtce="http://www.omg.org/spec/XTCE/20180204" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        f'xsi:schemaLocation="http://www.omg.org/spec/XTCE/20180204 {location}"/>'
    )
    return ElementTree.parse(io.StringIO(xml))


def _mock_urlopen_returning(content: bytes):
    """Return a Mock suitable for patching urlopen that yields ``content`` with no Content-Length."""

    class _Resp:
        headers: dict = {}

        def read(self, *args):
            if args:
                return content[: args[0]]
            return content

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    return Mock(side_effect=lambda url, timeout=None: _Resp())


# --------------------------------------------------------------------------------------
# LFI (CWE-73): document-derived local paths must never open a file.
# --------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "location",
    [
        "/etc/hostname",  # absolute POSIX path (the LFI PoC)
        "../../../etc/passwd",  # relative traversal
        "SpaceSystem.xsd",  # bare filename
        "schemas/SpaceSystem.xsd",  # relative path
        "C:\\Windows\\win.ini",  # Windows drive path
        "\\\\server\\share\\schema.xsd",  # UNC path
        "file:///etc/hostname",  # file:// scheme
    ],
)
def test_document_local_path_is_rejected(location):
    """A local filesystem reference in xsi:schemaLocation is rejected (no file is opened)."""
    result = validate_xtce(
        _doc_with_schema_location(location), level="schema", print_results=False, raise_on_error=False
    )
    assert not result.valid
    assert any(e.error_code == "DISALLOWED_SCHEMA_LOCATION" for e in result.errors)


# --------------------------------------------------------------------------------------
# SSRF (CWE-918): document-derived URLs must be allowlisted, https, and non-internal.
# --------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "location",
    [
        "http://169.254.169.254/latest/meta-data/iam/security-credentials/",  # cloud metadata PoC
        "http://127.0.0.1:9998/SSRF_CONFIRMED",  # loopback PoC
        "https://evil.example.com/schema.xsd",  # arbitrary external host
        "ftp://example.com/schema.xsd",  # non-http scheme
    ],
)
def test_document_url_ssrf_is_rejected(location):
    """Metadata/loopback/arbitrary URLs from a document are rejected with no outbound request."""
    with patch("space_packet_parser.xtce.validation.urlopen") as mock_urlopen:
        result = validate_xtce(
            _doc_with_schema_location(location), level="schema", print_results=False, raise_on_error=False
        )
    assert not result.valid
    assert any(e.error_code == "DISALLOWED_SCHEMA_LOCATION" for e in result.errors)
    mock_urlopen.assert_not_called()


def test_internal_ip_blocked_even_when_http_allowed_and_allowlisted():
    """The internal-address guard fires even if http is enabled AND the host is allowlisted."""
    location = "http://169.254.169.254/latest/meta-data/"
    with patch("space_packet_parser.xtce.validation.urlopen") as mock_urlopen:
        result = validate_xtce(
            _doc_with_schema_location(location),
            level="schema",
            print_results=False,
            raise_on_error=False,
            allow_insecure_http=True,
            allowed_schema_hosts=["169.254.169.254"],
        )
    assert not result.valid
    assert any("non-public address" in e.message for e in result.errors)
    mock_urlopen.assert_not_called()


# --------------------------------------------------------------------------------------
# Bundled schema: the standard OMG schema validates offline (no network).
# --------------------------------------------------------------------------------------
def test_standard_document_validates_offline_via_bundle(test_data_dir):
    """A document referencing the OMG schema URL validates from the bundle with no urlopen call."""
    with patch("space_packet_parser.xtce.validation.urlopen") as mock_urlopen:
        result = validate_xtce(
            test_data_dir / "test_xtce.xml", level="schema", print_results=False, raise_on_error=False
        )
    assert result.valid
    assert result.schema_version == "1.2"
    mock_urlopen.assert_not_called()


def test_allow_schema_download_false_still_uses_bundle(test_data_dir):
    """With downloads disabled, the bundled OMG schema is still used."""
    with patch("space_packet_parser.xtce.validation.urlopen") as mock_urlopen:
        result = validate_xtce(
            test_data_dir / "test_xtce.xml",
            level="schema",
            print_results=False,
            raise_on_error=False,
            allow_schema_download=False,
        )
    assert result.valid
    mock_urlopen.assert_not_called()


def test_allow_schema_download_false_blocks_non_bundled_url():
    """With downloads disabled, a non-bundled (but allowlisted) URL is not fetched."""
    location = "https://www.omg.org/spec/XTCE/somethingelse.xsd"
    with patch("space_packet_parser.xtce.validation.urlopen") as mock_urlopen:
        result = validate_xtce(
            _doc_with_schema_location(location),
            level="schema",
            print_results=False,
            raise_on_error=False,
            allow_schema_download=False,
        )
    assert not result.valid
    assert any(e.error_code == "SCHEMA_LOAD_ERROR" for e in result.errors)
    mock_urlopen.assert_not_called()


# --------------------------------------------------------------------------------------
# Allowlist configuration: argument, env var, exact-URL entries, insecure http.
# --------------------------------------------------------------------------------------
def test_custom_host_allowlist_argument_permits_download(test_data_dir, tmp_path):
    """A non-OMG host explicitly added to allowed_schema_hosts is fetched."""
    content = (test_data_dir / "SpaceSystem.xsd").read_bytes()
    location = "https://mirror.example.org/SpaceSystem.xsd"
    with patch("space_packet_parser.xtce.validation._get_cache_dir", return_value=tmp_path):
        with patch("space_packet_parser.xtce.validation.urlopen", _mock_urlopen_returning(content)):
            schema, version = _load_schema(location, allowed_schema_hosts=["mirror.example.org"])
    assert version == "1.2"


def test_exact_url_allowlist_entry(test_data_dir, tmp_path):
    """An exact-URL allowlist entry matches only that URL."""
    content = (test_data_dir / "SpaceSystem.xsd").read_bytes()
    good = "https://mirror.example.org/schemas/SpaceSystem.xsd"
    with patch("space_packet_parser.xtce.validation._get_cache_dir", return_value=tmp_path):
        with patch("space_packet_parser.xtce.validation.urlopen", _mock_urlopen_returning(content)):
            schema, version = _load_schema(good, allowed_schema_hosts=[good])
    assert version == "1.2"

    # A different path on the same host is NOT covered by an exact-URL entry.
    other = "https://mirror.example.org/schemas/Other.xsd"
    with pytest.raises(XtceValidationError, match="not in the allowlist"):
        _load_schema(other, allowed_schema_hosts=[good])


def test_env_var_allowlist(monkeypatch, test_data_dir, tmp_path):
    """SPP_ALLOWED_SCHEMA_HOSTS configures the allowlist when no argument is passed."""
    content = (test_data_dir / "SpaceSystem.xsd").read_bytes()
    location = "https://env-mirror.example.org/SpaceSystem.xsd"
    monkeypatch.setenv("SPP_ALLOWED_SCHEMA_HOSTS", "foo.example, env-mirror.example.org")
    with patch("space_packet_parser.xtce.validation._get_cache_dir", return_value=tmp_path):
        with patch("space_packet_parser.xtce.validation.urlopen", _mock_urlopen_returning(content)):
            schema, version = _load_schema(location)
    assert version == "1.2"


def test_insecure_http_requires_opt_in(test_data_dir, tmp_path):
    """An allowlisted http host is rejected by default but permitted with allow_insecure_http."""
    content = (test_data_dir / "SpaceSystem.xsd").read_bytes()
    location = "http://mirror.example.org/SpaceSystem.xsd"

    # Default: http rejected even though host is allowlisted.
    with pytest.raises(XtceValidationError, match="scheme 'http' is not allowed"):
        _load_schema(location, allowed_schema_hosts=["mirror.example.org"])

    # Opt-in: http permitted.
    with patch("space_packet_parser.xtce.validation._get_cache_dir", return_value=tmp_path):
        with patch("space_packet_parser.xtce.validation.urlopen", _mock_urlopen_returning(content)):
            schema, version = _load_schema(
                location, allowed_schema_hosts=["mirror.example.org"], allow_insecure_http=True
            )
    assert version == "1.2"


def test_env_var_insecure_http(monkeypatch, test_data_dir, tmp_path):
    """SPP_ALLOW_INSECURE_HTTP enables http when the argument is not set."""
    content = (test_data_dir / "SpaceSystem.xsd").read_bytes()
    location = "http://mirror.example.org/SpaceSystem.xsd"
    monkeypatch.setenv("SPP_ALLOW_INSECURE_HTTP", "1")
    with patch("space_packet_parser.xtce.validation._get_cache_dir", return_value=tmp_path):
        with patch("space_packet_parser.xtce.validation.urlopen", _mock_urlopen_returning(content)):
            schema, version = _load_schema(location, allowed_schema_hosts=["mirror.example.org"])
    assert version == "1.2"


def test_default_allowlist_is_omg():
    """Sanity check on the exported default allowlist."""
    assert "www.omg.org" in DEFAULT_ALLOWED_SCHEMA_HOSTS


# --------------------------------------------------------------------------------------
# Cache hardening: only validated schema content is cached; oversized responses rejected.
# --------------------------------------------------------------------------------------
def test_non_schema_response_is_not_cached(tmp_path):
    """A non-XSD response (e.g. an SSRF probe body) errors and is never written to the cache."""
    location = "https://mirror.example.org/SpaceSystem.xsd"
    with patch("space_packet_parser.xtce.validation._get_cache_dir", return_value=tmp_path):
        with patch("space_packet_parser.xtce.validation.urlopen", _mock_urlopen_returning(b"NOT-A-SCHEMA creds=abc")):
            with pytest.raises(XtceValidationError):
                _load_schema(location, allowed_schema_hosts=["mirror.example.org"])
    # Nothing was persisted to the cache directory.
    assert not any((tmp_path / "schemas").glob("*.xsd")) if (tmp_path / "schemas").exists() else True


def test_oversized_schema_rejected(tmp_path, monkeypatch, test_data_dir):
    """A response larger than the size cap is rejected."""
    monkeypatch.setattr(validation, "MAX_SCHEMA_BYTES", 16)
    content = (test_data_dir / "SpaceSystem.xsd").read_bytes()  # far larger than 16 bytes
    location = "https://mirror.example.org/SpaceSystem.xsd"
    with patch("space_packet_parser.xtce.validation._get_cache_dir", return_value=tmp_path):
        with patch("space_packet_parser.xtce.validation.urlopen", _mock_urlopen_returning(content)):
            with pytest.raises(XtceValidationError, match="exceeds the maximum allowed size"):
                _load_schema(location, allowed_schema_hosts=["mirror.example.org"])
