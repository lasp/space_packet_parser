"""Tests for the version-dependent parts of XTCE document validation.

Which schema a document resolves to, which version is reported, and how a version mismatch is
diagnosed. Version-agnostic validation behavior (schema resolution policy, structural rules, input
types) lives in `test_validation`; schema validation of 1.3-only constructs lives in
`test_xtce_1_3_features`.
"""

import io

import pytest

from space_packet_parser.xtce import LEGACY_XTCE_XMLNS_ALIASES, XTCE_1_2_XMLNS, XTCE_1_3_XMLNS
from space_packet_parser.xtce.validation import validate_xtce


@pytest.mark.parametrize(
    ("xml_file", "expected_version"),
    [("test_xtce.xml", "1.2"), ("test_xtce_1_3.xml", "1.3")],
)
def test_validation_resolves_bundled_schema_per_version_offline(test_data_dir, xml_file, expected_version):
    """Documents in either supported XTCE version validate offline against their bundled XSD

    ``allow_schema_download=False`` proves no network request is involved: the schema named by the
    document's ``xsi:schemaLocation`` must have been resolved from the copy bundled in the package.
    """
    result = validate_xtce(
        test_data_dir / xml_file,
        level="all",
        print_results=False,
        allow_schema_download=False,
    )
    assert result.valid
    assert result.errors == []
    assert result.schema_version == expected_version
    assert result.xtce_version == expected_version


def test_schema_version_mismatch_is_reported(test_data_dir):
    """A document whose namespace URI does not match its schema's targetNamespace is flagged

    This is the failure mode of pointing a 1.3 document at the 1.2 schema (or vice versa), so the
    error message must name the standard URI for each supported version.
    """
    mismatched = (
        (test_data_dir / "test_xtce_1_3.xml")
        .read_bytes()
        .replace(b"20250214/SpaceSystem.xsd", b"20180204/SpaceSystem.xsd")
    )

    result = validate_xtce(
        io.BytesIO(mismatched),
        level="schema",
        print_results=False,
        raise_on_error=False,
        allow_schema_download=False,
    )
    assert not result.valid
    namespace_error = next(error for error in result.errors if error.error_code == "INVALID_XTCE_NAMESPACE")
    assert XTCE_1_3_XMLNS in namespace_error.message
    assert XTCE_1_2_XMLNS in namespace_error.message
    # The document's own namespace URI is reported so the reader can see which side is wrong.
    assert namespace_error.context["document_xtce_uri"] == XTCE_1_3_XMLNS
    assert result.xtce_version == "1.3"


def test_legacy_namespace_gets_a_specific_hint(test_data_dir):
    """A document with the legacy https 1.2 URI is told what it is and how to repair it

    This URI is not the targetNamespace of any schema, so validation fails with the generic
    "does your xmlns match?" message. That message is useless here, because the answer is that the
    document was written by an older release of this library — which the reader has no way to guess.
    """
    legacy_uri = next(iter(LEGACY_XTCE_XMLNS_ALIASES))
    legacy_document = (
        (test_data_dir / "test_xtce.xml")
        .read_text()
        .replace(f'xmlns:xtce="{XTCE_1_2_XMLNS}"', f'xmlns:xtce="{legacy_uri}"')
    )

    result = validate_xtce(
        io.BytesIO(legacy_document.encode()),
        level="schema",
        print_results=False,
        raise_on_error=False,
        allow_schema_download=False,
    )

    assert not result.valid
    namespace_error = next(error for error in result.errors if error.error_code == "INVALID_XTCE_NAMESPACE")
    assert "space_packet_parser" in namespace_error.message
    assert XTCE_1_2_XMLNS in namespace_error.message
    # It is still recognized as 1.2 despite the unusable URI.
    assert result.xtce_version == "1.2"


def test_non_legacy_wrong_namespace_gets_the_generic_hint(test_data_dir):
    """An arbitrary wrong namespace URI must not be blamed on an old space_packet_parser release"""
    wrong_document = (
        (test_data_dir / "test_xtce.xml")
        .read_text()
        .replace(f'xmlns:xtce="{XTCE_1_2_XMLNS}"', 'xmlns:xtce="http://www.fake-test.org/space/xtce"')
    )

    result = validate_xtce(
        io.BytesIO(wrong_document.encode()),
        level="schema",
        print_results=False,
        raise_on_error=False,
        allow_schema_download=False,
    )

    assert not result.valid
    namespace_error = next(error for error in result.errors if error.error_code == "INVALID_XTCE_NAMESPACE")
    assert "space_packet_parser 6.2" not in namespace_error.message
    assert result.xtce_version is None


@pytest.mark.parametrize(
    "xml_file",
    ["test_xtce.xml", "test_xtce_1_3.xml", "test_xtce_default_namespace.xml", "test_xtce_no_namespace.xml"],
)
def test_structural_validation_is_namespace_agnostic(test_data_dir, xml_file):
    """Structural validation finds references in whatever namespace the document declares

    Previously the XPath queries hardcoded the XTCE 1.2 namespace URI, so a 1.3 document (or one
    with no namespace) matched nothing and vacuously "passed". Breaking a reference must therefore
    produce an error for every namespace style, otherwise the checks are not running at all.
    """
    source = (test_data_dir / xml_file).read_bytes()
    broken = source.replace(b'parameterTypeRef="USEC_Type"', b'parameterTypeRef="NOT_A_REAL_TYPE"', 1)
    assert broken != source, "test fixture no longer contains the parameter reference this test breaks"

    result = validate_xtce(io.BytesIO(broken), level="structure", print_results=False, raise_on_error=False)

    assert not result.valid
    assert any(error.error_code == "MISSING_PARAMETER_TYPE_REFERENCE" for error in result.errors)


@pytest.mark.parametrize(
    ("xml_file", "expected_version"),
    [
        ("test_xtce.xml", "1.2"),
        ("test_xtce_1_3.xml", "1.3"),
        ("test_xtce_no_namespace.xml", None),
    ],
)
def test_structural_validation_reports_xtce_version(test_data_dir, xml_file, expected_version):
    """Structural validation reports the XTCE version implied by the document's namespace URI"""
    result = validate_xtce(test_data_dir / xml_file, level="structure", print_results=False)
    assert result.xtce_version == expected_version
