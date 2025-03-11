"""Tests for the xarr.py extras module"""
import pytest

from space_packet_parser import xarr
from space_packet_parser.xtce import calibrators, containers, definitions, encodings, parameter_types, parameters

np = pytest.importorskip("numpy", reason="numpy is not available")


@pytest.fixture
def test_xtce():
    """Test definition for testing surmising data types"""
    container_set = [
        containers.SequenceContainer(
            "CONTAINER",
            entry_list=[
                parameters.Parameter(
                    "INT32_PARAM",
                    parameter_type=parameter_types.IntegerParameterType(
                        "I32_TYPE",
                        encoding=encodings.IntegerDataEncoding(size_in_bits=32, encoding="twosComplement")
                    )
                ),
                parameters.Parameter(
                    "F32_PARAM",
                    parameter_type=parameter_types.FloatParameterType(
                        "F32_TYPE",
                        encoding=encodings.FloatDataEncoding(size_in_bits=32, encoding="IEEE754")
                    )
                ),
                parameters.Parameter(
                    "CAL_INT_PARAM",
                    parameter_type=parameter_types.IntegerParameterType(
                        "I32_TYPE",
                        encoding=encodings.IntegerDataEncoding(
                            size_in_bits=32,
                            encoding="twosComplement",
                            default_calibrator=calibrators.PolynomialCalibrator(
                                coefficients=[
                                    calibrators.PolynomialCoefficient(1, 1)
                                ]
                            )
                        )
                    )
                ),
                parameters.Parameter(
                    "BIN_PARAM",
                    parameter_type=parameter_types.BinaryParameterType(
                        "BIN_TYPE",
                        encoding=encodings.BinaryDataEncoding(
                            fixed_size_in_bits=32
                        )
                    )
                ),
                parameters.Parameter(
                    "INT_ENUM_PARAM",
                    parameter_type=parameter_types.EnumeratedParameterType(
                        "INT_ENUM_TYPE",
                        encoding=encodings.IntegerDataEncoding(size_in_bits=8, encoding="unsigned"),
                        enumeration={
                            "ONE": 1,
                            "TWO": 2
                        }
                    )
                ),
                parameters.Parameter(
                    "STR_PARAM",
                    parameter_type=parameter_types.StringParameterType(
                        "STR_TYPE",
                        encoding=encodings.StringDataEncoding(
                            fixed_raw_length=32
                        )
                    )
                ),
            ]
        )
    ]
    return definitions.XtcePacketDefinition(container_set=container_set)

@pytest.mark.parametrize(
    ("pname", "use_raw_value", "expected_dtype"),
    [
        ("INT32_PARAM", True, "int32"),
        ("INT32_PARAM", False, "int32"),
        ("F32_PARAM", False, "float32"),
        ("F32_PARAM", True, "float32"),
        ("CAL_INT_PARAM", True, "int32"),
        ("CAL_INT_PARAM", False, None),
        ("BIN_PARAM", True, "bytes"),
        ("BIN_PARAM", False, "bytes"),
        ("INT_ENUM_PARAM", True, "uint8"),
        ("INT_ENUM_PARAM", False, "str"),
        ("STR_PARAM", True, "str"),
        ("STR_PARAM", False, "str"),
    ]
)
def test_minimum_numpy_dtype(test_xtce, pname, use_raw_value, expected_dtype):
    """Test finding the minimum numpy data type for a parameter"""
    assert xarr._get_minimum_numpy_datatype(pname, test_xtce, use_raw_value) == expected_dtype
