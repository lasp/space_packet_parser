"""Tests for XTCE validation functionality."""

import io
import tempfile
from pathlib import Path
from unittest.mock import patch

import lxml.etree as ElementTree
import pytest

from space_packet_parser.xtce.validation import _load_schema, validate_xtce


@pytest.fixture
def mock_schema_download(test_data_dir):
    """Mock urlopen to return local XSD content instead of downloading from network."""
    local_xsd_path = test_data_dir / "SpaceSystem.xsd"

    def mock_urlopen(url, timeout=None):
        """Mock urlopen that returns local XSD content."""

        class MockResponse:
            def __init__(self, content):
                self.content = content

            def read(self):
                return self.content

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

        # Read the local XSD file
        with local_xsd_path.open("rb") as f:
            content = f.read()

        return MockResponse(content)

    with patch("space_packet_parser.xtce.validation.urlopen", side_effect=mock_urlopen):
        yield


@pytest.mark.parametrize("xml_file", ["test_xtce.xml", "test_xtce_4byte.xml", "test_xtce_default_namespace.xml"])
def test_schema_validation_valid_document(test_data_dir, xml_file, mock_schema_download):
    """Test schema validation on valid XTCE documents"""
    _ = mock_schema_download  # Used for side effect (mocking urlopen)
    result = validate_xtce(test_data_dir / xml_file, level="schema")
    assert result.validation_level.value == "schema"
    # Schema validation might fail due to network issues, but should at least attempt it
    assert result.schema_location is not None
    assert result.schema_version is not None
    # For valid documents, we expect no validation errors if schema loading succeeds
    assert result.valid
    assert len(result.errors) == 0


def test_schema_validation_nonstandard_namespace_string(mock_schema_download):
    """Test schema validation on XTCE document with non-standard namespace identifier

    Usually the namespace is "http://www.omg.org/spec/XTCE/20180204", but this test uses "http://www.omg.org/spec/xtce"
    """
    _ = mock_schema_download  # Used for side effect (mocking urlopen)
    xtce_str = """<xtce:SpaceSystem name="XTCENamespaceNameChangeTest"
                  xmlns:xtce="http://www.omg.org/spec/xtce"
                  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                  xsi:schemaLocation="http://www.omg.org/spec/xtce
                                      https://www.omg.org/spec/XTCE/20180204/SpaceSystem.xsd">
    <xtce:Header date="2024-03-05T13:36:00MST" version="1.0"/>
    <xtce:TelemetryMetaData>
        <xtce:ParameterTypeSet>
        </xtce:ParameterTypeSet>
        <xtce:ParameterSet>
        </xtce:ParameterSet>
        <xtce:ContainerSet>
        </xtce:ContainerSet>
    </xtce:TelemetryMetaData>
</xtce:SpaceSystem>"""

    validate_xtce(io.StringIO(xtce_str), level="schema", raise_on_error=False)


def test_schema_validation_missing_schema_location(test_data_dir):
    """Test schema validation fails for document without XTCE namespace"""
    result = validate_xtce(test_data_dir / "test_xtce_no_namespace.xml", level="schema", raise_on_error=False)
    assert result.validation_level.value == "schema"
    assert not result.valid
    assert len(result.errors) > 0

    # Check that the error is specifically about missing namespace
    namespace_error = next((error for error in result.errors if error.error_code == "MISSING_SCHEMA_LOCATION"), None)
    assert namespace_error is not None
    assert "xsi" in namespace_error.message
    assert "namespace" in namespace_error.message.lower()
    assert "schemaLocation" in namespace_error.message


def test_schema_validation_invalid_header(mock_schema_download):
    """Test schema validation fails for document with invalid Header element"""
    _ = mock_schema_download  # Used for side effect (mocking urlopen)
    # XTCE document with Header missing required validationStatus attribute
    invalid_xtce = """<xtce:SpaceSystem name="InvalidTest"
                  xmlns:xtce="http://www.omg.org/spec/XTCE/20180204"
                  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                  xsi:schemaLocation="http://www.omg.org/spec/XTCE/20180204
                                      https://www.omg.org/spec/XTCE/20180204/SpaceSystem.xsd">
    <xtce:Header date="2024-03-05T13:36:00MST" version="1.0"/>
    <xtce:TelemetryMetaData>
        <xtce:ParameterTypeSet>
            <xtce:IntegerParameterType name="TEST_Type" signed="false">
                <xtce:IntegerDataEncoding sizeInBits="8" encoding="unsigned"/>
            </xtce:IntegerParameterType>
        </xtce:ParameterTypeSet>
        <xtce:ParameterSet>
            <xtce:Parameter name="TEST_PARAM" parameterTypeRef="TEST_Type"/>
        </xtce:ParameterSet>
        <xtce:ContainerSet>
            <xtce:SequenceContainer name="TEST_CONTAINER">
                <xtce:EntryList>
                    <xtce:ParameterRefEntry parameterRef="TEST_PARAM"/>
                </xtce:EntryList>
            </xtce:SequenceContainer>
        </xtce:ContainerSet>
    </xtce:TelemetryMetaData>
</xtce:SpaceSystem>"""

    invalid_xtce_str = io.StringIO(invalid_xtce)

    result = validate_xtce(invalid_xtce_str, level="schema", raise_on_error=False)
    assert result.validation_level.value == "schema"
    assert not result.valid


def test_input_types_to_validate(test_data_dir, mock_schema_download):
    """Test that validate_xtce accepts various input types"""
    _ = mock_schema_download  # Used for side effect (mocking urlopen)

    xtce_str = """<xtce:SpaceSystem name="XTCEStringTest"
                  xmlns:xtce="http://www.omg.org/spec/XTCE/20180204"
                  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                  xsi:schemaLocation="http://www.omg.org/spec/XTCE/20180204
                                      https://www.omg.org/spec/XTCE/20180204/SpaceSystem.xsd">
    <xtce:Header date="2024-03-05T13:36:00MST" version="1.0"/>
    <xtce:TelemetryMetaData>
        <xtce:ParameterTypeSet>
        </xtce:ParameterTypeSet>
        <xtce:ParameterSet>
        </xtce:ParameterSet>
        <xtce:ContainerSet>
        </xtce:ContainerSet>
    </xtce:TelemetryMetaData>
</xtce:SpaceSystem>"""

    # XTCE string with encoding specified in document
    xtce_bytes = b"""<?xml version='1.0' encoding='UTF-8'?>
<xtce:SpaceSystem name="XTCEBytesTest"
                  xmlns:xtce="http://www.omg.org/spec/XTCE/20180204"
                  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                  xsi:schemaLocation="http://www.omg.org/spec/XTCE/20180204
                                      https://www.omg.org/spec/XTCE/20180204/SpaceSystem.xsd">
    <xtce:Header date="2024-03-05T13:36:00MST" version="1.0"/>
    <xtce:TelemetryMetaData>
        <xtce:ParameterTypeSet>
        </xtce:ParameterTypeSet>
        <xtce:ParameterSet>
        </xtce:ParameterSet>
        <xtce:ContainerSet>
        </xtce:ContainerSet>
    </xtce:TelemetryMetaData>
</xtce:SpaceSystem>"""

    # Test with a string path
    result = validate_xtce(str(test_data_dir / "test_xtce.xml"), level="schema", raise_on_error=False)
    assert result.validation_level.value == "schema"

    # Test with a Path object
    result = validate_xtce(test_data_dir / "test_xtce.xml", level="schema", raise_on_error=False)
    assert result.validation_level.value == "schema"

    # Test with a file-like object
    with (test_data_dir / "test_xtce.xml").open("r") as file_obj:
        result = validate_xtce(file_obj, level="schema", raise_on_error=False)
        assert result.validation_level.value == "schema"

    # Test with a string input
    result = validate_xtce(io.StringIO(xtce_str), level="schema", raise_on_error=False)

    # Test with a bytes input
    result = validate_xtce(io.BytesIO(xtce_bytes), level="schema", raise_on_error=False)

    # Test with an ElementTree object
    result = validate_xtce(ElementTree.parse(io.StringIO(xtce_str)), level="schema", raise_on_error=False)


@pytest.mark.parametrize("xml_file", ["test_xtce.xml", "test_xtce_4byte.xml", "test_xtce_default_namespace.xml"])
def test_structural_validation_valid_document(test_data_dir, xml_file):
    """Test structural validation on valid XTCE documents"""
    result = validate_xtce(test_data_dir / xml_file, level="structure", raise_on_error=False)
    assert result.validation_level.value == "structure"
    assert result.valid
    assert len(result.errors) == 0


def test_structural_validation_parameter_missing_type():
    """Test structural validation fails for Parameter referencing nonexistent ParameterType"""
    invalid_xtce = """<xtce:SpaceSystem name="InvalidTest"
                  xmlns:xtce="http://www.omg.org/spec/XTCE/20180204">
    <xtce:TelemetryMetaData>
        <xtce:ParameterTypeSet>
            <xtce:IntegerParameterType name="VALID_Type" signed="false">
                <xtce:IntegerDataEncoding sizeInBits="8" encoding="unsigned"/>
            </xtce:IntegerParameterType>
        </xtce:ParameterTypeSet>
        <xtce:ParameterSet>
            <xtce:Parameter name="INVALID_PARAM" parameterTypeRef="NONEXISTENT_Type"/>
        </xtce:ParameterSet>
        <xtce:ContainerSet>
        </xtce:ContainerSet>
    </xtce:TelemetryMetaData>
</xtce:SpaceSystem>"""

    result = validate_xtce(io.StringIO(invalid_xtce), level="structure", raise_on_error=False)
    assert result.validation_level.value == "structure"
    assert not result.valid
    assert len(result.errors) > 0

    # Check that the error is specifically about missing parameter type
    missing_type_error = next(
        (error for error in result.errors if error.error_code == "MISSING_PARAMETER_TYPE_REFERENCE"), None
    )
    assert missing_type_error is not None
    assert "INVALID_PARAM" in missing_type_error.message
    assert "NONEXISTENT_Type" in missing_type_error.message


def test_structural_validation_container_missing_parameter():
    """Test structural validation fails for SequenceContainer referencing nonexistent Parameter"""
    invalid_xtce = """<xtce:SpaceSystem name="InvalidTest"
                  xmlns:xtce="http://www.omg.org/spec/XTCE/20180204">
    <xtce:TelemetryMetaData>
        <xtce:ParameterTypeSet>
            <xtce:IntegerParameterType name="VALID_Type" signed="false">
                <xtce:IntegerDataEncoding sizeInBits="8" encoding="unsigned"/>
            </xtce:IntegerParameterType>
        </xtce:ParameterTypeSet>
        <xtce:ParameterSet>
            <xtce:Parameter name="VALID_PARAM" parameterTypeRef="VALID_Type"/>
        </xtce:ParameterSet>
        <xtce:ContainerSet>
            <xtce:SequenceContainer name="TEST_CONTAINER">
                <xtce:EntryList>
                    <xtce:ParameterRefEntry parameterRef="NONEXISTENT_PARAM"/>
                </xtce:EntryList>
            </xtce:SequenceContainer>
        </xtce:ContainerSet>
    </xtce:TelemetryMetaData>
</xtce:SpaceSystem>"""

    result = validate_xtce(io.StringIO(invalid_xtce), level="structure", raise_on_error=False)
    assert result.validation_level.value == "structure"
    assert not result.valid
    assert len(result.errors) > 0

    # Check that the error is specifically about missing parameter reference
    missing_param_error = next(
        (error for error in result.errors if error.error_code == "MISSING_PARAMETER_REFERENCE"), None
    )
    assert missing_param_error is not None
    assert "NONEXISTENT_PARAM" in missing_param_error.message


def test_structural_validation_base_container_missing_container():
    """Test structural validation fails for BaseContainer inheriting nonexistent SequenceContainer"""
    invalid_xtce = """<xtce:SpaceSystem name="InvalidTest"
                  xmlns:xtce="http://www.omg.org/spec/XTCE/20180204">
    <xtce:TelemetryMetaData>
        <xtce:ParameterTypeSet>
        </xtce:ParameterTypeSet>
        <xtce:ParameterSet>
        </xtce:ParameterSet>
        <xtce:ContainerSet>
            <xtce:SequenceContainer name="CHILD_CONTAINER">
                <xtce:EntryList>
                </xtce:EntryList>
                <xtce:BaseContainer containerRef="NONEXISTENT_CONTAINER"/>
            </xtce:SequenceContainer>
        </xtce:ContainerSet>
    </xtce:TelemetryMetaData>
</xtce:SpaceSystem>"""

    result = validate_xtce(io.StringIO(invalid_xtce), level="structure", raise_on_error=False)
    assert not result
    assert result.validation_level.value == "structure"
    assert not result.valid
    assert len(result.errors) > 0

    # Check that the error is specifically about missing container reference
    missing_container_error = next(
        (error for error in result.errors if error.error_code == "MISSING_CONTAINER_REFERENCE"), None
    )
    assert missing_container_error is not None
    assert "NONEXISTENT_CONTAINER" in missing_container_error.message


def test_structural_validation_unused_parameter():
    """Test structural validation detects unused Parameter"""
    invalid_xtce = """<xtce:SpaceSystem name="InvalidTest"
                  xmlns:xtce="http://www.omg.org/spec/XTCE/20180204">
    <xtce:TelemetryMetaData>
        <xtce:ParameterTypeSet>
            <xtce:IntegerParameterType name="TEST_Type" signed="false">
                <xtce:IntegerDataEncoding sizeInBits="8" encoding="unsigned"/>
            </xtce:IntegerParameterType>
        </xtce:ParameterTypeSet>
        <xtce:ParameterSet>
            <xtce:Parameter name="USED_PARAM" parameterTypeRef="TEST_Type"/>
            <xtce:Parameter name="UNUSED_PARAM" parameterTypeRef="TEST_Type"/>
        </xtce:ParameterSet>
        <xtce:ContainerSet>
            <xtce:SequenceContainer name="TEST_CONTAINER">
                <xtce:EntryList>
                    <xtce:ParameterRefEntry parameterRef="USED_PARAM"/>
                </xtce:EntryList>
            </xtce:SequenceContainer>
        </xtce:ContainerSet>
    </xtce:TelemetryMetaData>
</xtce:SpaceSystem>"""

    result = validate_xtce(io.StringIO(invalid_xtce), level="structure", raise_on_error=False)
    assert not result
    assert result.validation_level.value == "structure"
    assert not result.valid
    assert len(result.errors) > 0

    # Check that the error is specifically about unused parameter
    unused_param_error = next((error for error in result.errors if error.error_code == "UNUSED_PARAMETER"), None)
    assert unused_param_error is not None
    assert "UNUSED_PARAM" in unused_param_error.message


def test_structural_validation_unused_parameter_type():
    """Test structural validation detects unused ParameterType"""
    invalid_xtce = """<xtce:SpaceSystem name="InvalidTest"
                  xmlns:xtce="http://www.omg.org/spec/XTCE/20180204">
    <xtce:TelemetryMetaData>
        <xtce:ParameterTypeSet>
            <xtce:IntegerParameterType name="USED_Type" signed="false">
                <xtce:IntegerDataEncoding sizeInBits="8" encoding="unsigned"/>
            </xtce:IntegerParameterType>
            <xtce:IntegerParameterType name="UNUSED_Type" signed="false">
                <xtce:IntegerDataEncoding sizeInBits="8" encoding="unsigned"/>
            </xtce:IntegerParameterType>
        </xtce:ParameterTypeSet>
        <xtce:ParameterSet>
            <xtce:Parameter name="TEST_PARAM" parameterTypeRef="USED_Type"/>
        </xtce:ParameterSet>
        <xtce:ContainerSet>
            <xtce:SequenceContainer name="TEST_CONTAINER">
                <xtce:EntryList>
                    <xtce:ParameterRefEntry parameterRef="TEST_PARAM"/>
                </xtce:EntryList>
            </xtce:SequenceContainer>
        </xtce:ContainerSet>
    </xtce:TelemetryMetaData>
</xtce:SpaceSystem>"""

    result = validate_xtce(io.StringIO(invalid_xtce), level="structure", raise_on_error=False)
    assert result.validation_level.value == "structure"
    assert not result.valid
    assert len(result.errors) > 0

    # Check that the error is specifically about unused parameter type
    unused_type_error = next((error for error in result.errors if error.error_code == "UNUSED_PARAMETER_TYPE"), None)
    assert unused_type_error is not None
    assert "UNUSED_Type" in unused_type_error.message


def test_validate_xtce_all_mode(test_data_dir, mock_schema_download):
    """Test validate_xtce with mode='all' on test_xtce.xml"""
    _ = mock_schema_download  # Used for side effect (mocking urlopen)
    result = validate_xtce(test_data_dir / "test_xtce.xml", level="all")
    assert result.validation_level.value == "all"
    assert result.valid
    assert len(result.errors) == 0

    # Should have schema information
    assert result.schema_location is not None
    assert result.schema_version is not None


def test_schema_validation_with_local_xsd(test_data_dir):
    """Test schema validation using a local XSD file instead of downloading from URL"""
    # Use an existing test XTCE document
    xtce_path = test_data_dir / "test_xtce.xml"
    local_xsd_path = test_data_dir / "SpaceSystem.xsd"

    # Validate using the local XSD
    result = validate_xtce(xtce_path, level="schema", local_xsd=local_xsd_path)

    # Verify validation was performed
    assert result.validation_level.value == "schema"
    assert result.schema_location == str(local_xsd_path)
    assert result.schema_version is not None

    # The document should be valid against the schema
    assert result.valid
    assert len(result.errors) == 0


def test_schema_caching_mechanism(test_data_dir):
    """Test that schema caching works correctly with HTTP URLs."""
    # Read the expected XSD content from the local test file
    local_xsd_path = test_data_dir / "SpaceSystem.xsd"
    expected_content = local_xsd_path.read_bytes()

    # Create a temporary directory for cache testing
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_cache_dir = Path(temp_dir)

        # Mock _get_cache_dir to use our temporary directory
        with patch("space_packet_parser.xtce.validation._get_cache_dir", return_value=temp_cache_dir):
            # Mock urlopen to return the local XSD content and track calls
            with patch("space_packet_parser.xtce.validation.urlopen") as mock_urlopen:
                # Setup mock response
                mock_response = mock_urlopen.return_value.__enter__.return_value
                mock_response.read.return_value = expected_content

                test_url = "https://example.com/test_schema.xsd"

                # First call - should download and cache
                schema1, version1 = _load_schema(test_url)

                # Verify network call was made
                assert mock_urlopen.call_count == 1

                # Verify cache file was created
                from space_packet_parser.xtce.validation import _get_cache_path

                cache_path = _get_cache_path(test_url)
                cache_path = temp_cache_dir / "schemas" / cache_path.name
                assert cache_path.exists()

                # Verify cached content matches expected content
                cached_content = cache_path.read_bytes()
                assert cached_content == expected_content

                # Second call - should use cache (no additional network call)
                schema2, version2 = _load_schema(test_url)

                # Verify no additional network call was made
                assert mock_urlopen.call_count == 1  # Still only 1 call

                # Verify both calls return equivalent results
                assert version1 == version2
                # Both schemas should be XMLSchema objects
                assert isinstance(schema1, ElementTree.XMLSchema)
                assert isinstance(schema2, ElementTree.XMLSchema)
