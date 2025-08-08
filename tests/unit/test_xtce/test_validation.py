"""Tests for XTCE validation functionality."""

import io

import lxml.etree as ElementTree
import pytest

from space_packet_parser.xtce.validation import validate_xtce


@pytest.mark.parametrize("xml_file", ["test_xtce.xml", "test_xtce_4byte.xml", "test_xtce_default_namespace.xml"])
def test_schema_validation_valid_document(test_data_dir, xml_file):
    """Test schema validation on valid XTCE documents"""
    result = validate_xtce(test_data_dir / xml_file, level="schema")
    assert result.validation_level.value == "schema"
    # Schema validation might fail due to network issues, but should at least attempt it
    assert result.schema_location is not None
    assert result.schema_version is not None
    # For valid documents, we expect no validation errors if schema loading succeeds
    assert result.valid
    assert len(result.errors) == 0


def test_schema_validation_nonstandard_namespace_string():
    """Test schema validation on XTCE document with non-standard namespace identifier

    Usually the namespace is "http://www.omg.org/spec/XTCE/20180204", but this test uses "http://www.omg.org/spec/xtce"
    """
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

    validate_xtce(io.StringIO(xtce_str), level="schema")


def test_schema_validation_missing_namespace(test_data_dir):
    """Test schema validation fails for document without XTCE namespace"""
    result = validate_xtce(test_data_dir / "test_xtce_no_namespace.xml", level="schema")
    assert result.validation_level.value == "schema"
    assert not result.valid
    assert len(result.errors) > 0

    # Check that the error is specifically about missing namespace
    namespace_error = next((error for error in result.errors if error.error_code == "MISSING_NAMESPACE"), None)
    assert namespace_error is not None
    assert "xsi" in namespace_error.message
    assert "namespace" in namespace_error.message.lower()
    assert "schemaLocation" in namespace_error.message


def test_schema_validation_invalid_header():
    """Test schema validation fails for document with invalid Header element"""
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

    result = validate_xtce(invalid_xtce_str, level="schema")
    assert result.validation_level.value == "schema"
    assert not result.valid


def test_input_types_to_validate(test_data_dir):
    """Test that validate_xtce accepts various input types"""

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
    result = validate_xtce(str(test_data_dir / "test_xtce.xml"), level="schema")
    assert result.validation_level.value == "schema"

    # Test with a Path object
    result = validate_xtce(test_data_dir / "test_xtce.xml", level="schema")
    assert result.validation_level.value == "schema"

    # Test with a file-like object
    with (test_data_dir / "test_xtce.xml").open("r") as file_obj:
        result = validate_xtce(file_obj, level="schema")
        assert result.validation_level.value == "schema"

    # Test with a string input
    result = validate_xtce(io.StringIO(xtce_str), level="schema")

    # Test with a bytes input
    result = validate_xtce(io.BytesIO(xtce_bytes), level="schema")

    # Test with an ElementTree object
    result = validate_xtce(ElementTree.parse(io.StringIO(xtce_str)), level="schema")


@pytest.mark.parametrize("xml_file", ["test_xtce.xml", "test_xtce_4byte.xml", "test_xtce_default_namespace.xml"])
def test_structural_validation_valid_document(test_data_dir, xml_file):
    """Test structural validation on valid XTCE documents"""
    result = validate_xtce(test_data_dir / xml_file, level="structure")
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

    result = validate_xtce(io.StringIO(invalid_xtce), level="structure")
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

    result = validate_xtce(io.StringIO(invalid_xtce), level="structure")
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

    result = validate_xtce(io.StringIO(invalid_xtce), level="structure")
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

    result = validate_xtce(io.StringIO(invalid_xtce), level="structure")
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

    result = validate_xtce(io.StringIO(invalid_xtce), level="structure")
    assert result.validation_level.value == "structure"
    assert not result.valid
    assert len(result.errors) > 0

    # Check that the error is specifically about unused parameter type
    unused_type_error = next((error for error in result.errors if error.error_code == "UNUSED_PARAMETER_TYPE"), None)
    assert unused_type_error is not None
    assert "UNUSED_Type" in unused_type_error.message


def test_validate_xtce_all_mode(test_data_dir):
    """Test validate_xtce with mode='all' on test_xtce.xml"""
    result = validate_xtce(test_data_dir / "test_xtce.xml", level="all")
    assert result.validation_level.value == "all"
    assert result.valid
    assert len(result.errors) == 0

    # Should have schema information
    assert result.schema_location is not None
    assert result.schema_version is not None
