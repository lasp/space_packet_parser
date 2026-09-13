"""Tests for the registry of supported XTCE standard versions.

An XTCE document declares which version of the standard it is written against through the XML
namespace URI on its root element, which must equal the ``targetNamespace`` of the matching OMG
XSD. These tests pin the registry to the URIs and schema files that OMG actually publishes.
"""

import lxml.etree as ElementTree
import pytest

from space_packet_parser import xtce


@pytest.mark.parametrize(
    ("version", "expected_uri"),
    [
        ("1.1", "http://www.omg.org/space/xtce"),
        ("1.2", "http://www.omg.org/spec/XTCE/20180204"),
        ("1.3", "http://www.omg.org/spec/XTCE/20250214"),
    ],
)
def test_namespace_uri_for_version(version, expected_uri):
    """The registered namespace URI for each version matches the one OMG publishes"""
    assert xtce.xtce_uri_for_version(version) == expected_uri
    assert xtce.XTCE_XMLNS_BY_VERSION[version] == expected_uri
    assert xtce.xtce_version_from_uri(expected_uri) == version


def test_supported_versions():
    """1.2 and 1.3 are both fully supported, with 1.3 the latest"""
    assert xtce.SUPPORTED_XTCE_VERSIONS == ("1.2", "1.3")
    assert xtce.LATEST_XTCE_VERSION == "1.3"
    # The serialization default stays on 1.2 so that upgrading the library does not silently
    # change the XTCE version of documents a caller writes out.
    assert xtce.DEFAULT_XTCE_VERSION == "1.2"


def test_version_from_unrecognized_uri():
    """A non-standard or absent namespace URI yields no version rather than raising"""
    assert xtce.xtce_version_from_uri(None) is None
    assert xtce.xtce_version_from_uri("http://www.omg.org/spec/xtce") is None
    assert xtce.xtce_version_from_uri("http://www.fake-test.org/space/xtce") is None


def test_uri_for_unrecognized_version():
    """Asking for an unknown version is an error, and the error names the known versions"""
    with pytest.raises(ValueError, match="Unrecognized XTCE version"):
        xtce.xtce_uri_for_version("9.9")


@pytest.mark.parametrize("prefix", ["xtce", "custom", None])
def test_xtce_nsmap(prefix):
    """The namespace mapping binds the requested version's URI to the requested prefix"""
    nsmap = xtce.xtce_nsmap("1.3", prefix=prefix)
    assert nsmap[prefix] == xtce.XTCE_1_3_XMLNS
    assert nsmap[xtce.XSI_NS_PREFIX] == xtce.XSI_XMLNS

    without_xsi = xtce.xtce_nsmap("1.3", prefix=prefix, include_xsi=False)
    assert without_xsi == {prefix: xtce.XTCE_1_3_XMLNS}


def test_standard_nsmap_matches_default_version():
    """The default namespace mapping is the default version's, with the standard prefix"""
    assert xtce.STANDARD_XTCE_NSMAP == {
        xtce.STANDARD_XTCE_NS_PREFIX: xtce.XTCE_XMLNS_BY_VERSION[xtce.DEFAULT_XTCE_VERSION],
        xtce.XSI_NS_PREFIX: xtce.XSI_XMLNS,
    }
    assert xtce.XTCE_URI == xtce.XTCE_XMLNS_BY_VERSION[xtce.DEFAULT_XTCE_VERSION]


@pytest.mark.parametrize("version", xtce.SUPPORTED_XTCE_VERSIONS)
def test_bundled_xsd_matches_registered_version(version, bundled_xsd_path):
    """Each bundled XSD really is the schema for the version it is registered under

    Guards against a schema file being swapped or mislabeled: the file's own ``targetNamespace``
    and ``version`` attributes must agree with the registry.
    """
    path = bundled_xsd_path(version)
    assert path.is_file()
    root = ElementTree.parse(str(path)).getroot()
    assert root.get("targetNamespace") == xtce.xtce_uri_for_version(version)
    assert root.get("version") == version


@pytest.mark.parametrize("version", xtce.SUPPORTED_XTCE_VERSIONS)
def test_every_supported_version_has_a_bundled_schema(version):
    """Supported means the XSD ships with the package, so validation works offline"""
    assert version in xtce.BUNDLED_XSD_FILENAME_BY_VERSION
    assert version in xtce.XTCE_XSD_URL_BY_VERSION
