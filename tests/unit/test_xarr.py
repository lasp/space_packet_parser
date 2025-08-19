"""Tests for the xarr.py extras module"""

import io
import struct

import pytest

from space_packet_parser import xarr
from space_packet_parser.generators.fixed_length import fixed_length_generator
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
                        "I32_TYPE", encoding=encodings.IntegerDataEncoding(size_in_bits=32, encoding="twosComplement")
                    ),
                ),
                parameters.Parameter(
                    "F32_PARAM",
                    parameter_type=parameter_types.FloatParameterType(
                        "F32_TYPE", encoding=encodings.FloatDataEncoding(size_in_bits=32, encoding="IEEE754")
                    ),
                ),
                parameters.Parameter(
                    "CAL_INT_PARAM",
                    parameter_type=parameter_types.IntegerParameterType(
                        "I32_TYPE",
                        encoding=encodings.IntegerDataEncoding(
                            size_in_bits=32,
                            encoding="twosComplement",
                            default_calibrator=calibrators.PolynomialCalibrator(
                                coefficients=[calibrators.PolynomialCoefficient(1, 1)]
                            ),
                        ),
                    ),
                ),
                parameters.Parameter(
                    "BIN_PARAM",
                    parameter_type=parameter_types.BinaryParameterType(
                        "BIN_TYPE", encoding=encodings.BinaryDataEncoding(fixed_size_in_bits=32)
                    ),
                ),
                parameters.Parameter(
                    "INT_ENUM_PARAM",
                    parameter_type=parameter_types.EnumeratedParameterType(
                        "INT_ENUM_TYPE",
                        encoding=encodings.IntegerDataEncoding(size_in_bits=8, encoding="unsigned"),
                        enumeration={"ONE": 1, "TWO": 2},
                    ),
                ),
                parameters.Parameter(
                    "STR_PARAM",
                    parameter_type=parameter_types.StringParameterType(
                        "STR_TYPE", encoding=encodings.StringDataEncoding(fixed_raw_length=32)
                    ),
                ),
            ],
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
    ],
)
def test_minimum_numpy_dtype(test_xtce, pname, use_raw_value, expected_dtype):
    """Test finding the minimum numpy data type for a parameter"""
    assert xarr._get_minimum_numpy_datatype(pname, test_xtce, use_raw_value) == expected_dtype


def test_create_dataset_with_custom_generator(tmp_path):
    """Test creating a dataset with a custom packet generator for non-CCSDS packets"""
    # Create a simple fixed-length packet definition with 3 fields
    container_set = [
        containers.SequenceContainer(
            "FIXED_LENGTH_CONTAINER",
            entry_list=[
                parameters.Parameter(
                    "UINT8_FIELD",
                    parameter_type=parameter_types.IntegerParameterType(
                        "UINT8_TYPE", encoding=encodings.IntegerDataEncoding(size_in_bits=8, encoding="unsigned")
                    ),
                ),
                parameters.Parameter(
                    "STRING_FIELD",
                    parameter_type=parameter_types.StringParameterType(
                        "STRING_TYPE",
                        encoding=encodings.StringDataEncoding(
                            fixed_raw_length=24  # 3 bytes = 24 bits
                        ),
                    ),
                ),
                parameters.Parameter(
                    "INT32_FIELD",
                    parameter_type=parameter_types.IntegerParameterType(
                        "INT32_TYPE", encoding=encodings.IntegerDataEncoding(size_in_bits=32, encoding="twosComplement")
                    ),
                ),
            ],
        )
    ]

    packet_definition = definitions.XtcePacketDefinition(container_set=container_set)

    # Create 3 test packets with known data (8 bytes each)
    packet1_data = struct.pack(">B3si", 0x42, b"ABC", 12345)
    packet2_data = struct.pack(">B3si", 0x55, b"XYZ", 67890)
    packet3_data = struct.pack(">B3si", 0xFF, b"123", -99999)

    # Concatenate packets into binary data
    binary_data = packet1_data + packet2_data + packet3_data

    # Write to a temporary file
    test_file = tmp_path / "test_packets.bin"
    with open(test_file, "wb") as f:
        f.write(binary_data)

    # Create dataset using a custom fixed-length generator
    datasets = xarr.create_dataset(
        test_file,
        packet_definition,
        packet_bytes_generator=fixed_length_generator,
        generator_kwargs={"packet_length_bytes": 8},
        parse_bytes_kwargs={"root_container_name": "FIXED_LENGTH_CONTAINER"},
    )

    # Since these are not CCSDS packets, they won't have an APID
    # The dataset should be keyed by 0 or similar default
    assert len(datasets) == 1
    dataset = list(datasets.values())[0]

    # Check that we have 3 packets
    assert len(dataset.packet) == 3

    # Check the values
    assert list(dataset["UINT8_FIELD"].values) == [0x42, 0x55, 0xFF]
    assert list(dataset["STRING_FIELD"].values) == ["ABC", "XYZ", "123"]
    assert list(dataset["INT32_FIELD"].values) == [12345, 67890, -99999]


def test_create_dataset_with_file_like_objects(tmp_path):
    """Test creating a dataset with file-like objects instead of file paths"""
    # Create a simple fixed-length packet definition
    container_set = [
        containers.SequenceContainer(
            "SIMPLE_CONTAINER",
            entry_list=[
                parameters.Parameter(
                    "FIELD1",
                    parameter_type=parameter_types.IntegerParameterType(
                        "UINT8_TYPE", encoding=encodings.IntegerDataEncoding(size_in_bits=8, encoding="unsigned")
                    ),
                ),
                parameters.Parameter(
                    "FIELD2",
                    parameter_type=parameter_types.IntegerParameterType(
                        "UINT16_TYPE", encoding=encodings.IntegerDataEncoding(size_in_bits=16, encoding="unsigned")
                    ),
                ),
            ],
        )
    ]

    packet_definition = definitions.XtcePacketDefinition(container_set=container_set)

    # Create test data (3 packets, each 3 bytes: 1 byte + 2 bytes)
    packet1 = struct.pack(">BH", 0x10, 0x1234)  # FIELD1=16, FIELD2=4660
    packet2 = struct.pack(">BH", 0x20, 0x5678)  # FIELD1=32, FIELD2=22136
    packet3 = struct.pack(">BH", 0x30, 0x9ABC)  # FIELD1=48, FIELD2=39612
    test_data = packet1 + packet2 + packet3

    # Test with single file-like object (simulating file opened in "rb" mode)
    test_data_file = tmp_path / "test_data.bin"
    with open(test_data_file, "wb") as f:
        f.write(test_data)

    with open(test_data_file, "rb") as fh:
        datasets = xarr.create_dataset(
            fh,
            packet_definition,
            packet_bytes_generator=fixed_length_generator,
            generator_kwargs={"packet_length_bytes": 3},
            parse_bytes_kwargs={"root_container_name": "SIMPLE_CONTAINER"},
        )

    assert len(datasets) == 1
    dataset = list(datasets.values())[0]
    assert len(dataset.packet) == 3
    assert list(dataset["FIELD1"].values) == [16, 32, 48]
    assert list(dataset["FIELD2"].values) == [4660, 22136, 39612]

    # Test with iterable of file-like objects
    file_obj1 = io.BytesIO(packet1 + packet2)
    file_obj2 = io.BytesIO(packet3)

    datasets = xarr.create_dataset(
        [file_obj1, file_obj2],
        packet_definition,
        packet_bytes_generator=fixed_length_generator,
        generator_kwargs={"packet_length_bytes": 3},
        parse_bytes_kwargs={"root_container_name": "SIMPLE_CONTAINER"},
    )

    assert len(datasets) == 1
    dataset = list(datasets.values())[0]
    assert len(dataset.packet) == 3
    assert list(dataset["FIELD1"].values) == [16, 32, 48]
    assert list(dataset["FIELD2"].values) == [4660, 22136, 39612]


def test_create_dataset_with_mixed_file_types(tmp_path):
    """Test creating a dataset with mixed file paths and file-like objects"""
    # Create a simple fixed-length packet definition (reuse from above)
    container_set = [
        containers.SequenceContainer(
            "SIMPLE_CONTAINER",
            entry_list=[
                parameters.Parameter(
                    "FIELD1",
                    parameter_type=parameter_types.IntegerParameterType(
                        "UINT8_TYPE", encoding=encodings.IntegerDataEncoding(size_in_bits=8, encoding="unsigned")
                    ),
                ),
                parameters.Parameter(
                    "FIELD2",
                    parameter_type=parameter_types.IntegerParameterType(
                        "UINT16_TYPE", encoding=encodings.IntegerDataEncoding(size_in_bits=16, encoding="unsigned")
                    ),
                ),
            ],
        )
    ]

    packet_definition = definitions.XtcePacketDefinition(container_set=container_set)

    # Create test data
    packet1 = struct.pack(">BH", 0x10, 0x1234)
    packet2 = struct.pack(">BH", 0x20, 0x5678)
    packet3 = struct.pack(">BH", 0x30, 0x9ABC)

    # Create a test file
    test_file = tmp_path / "test_packets.dat"
    with open(test_file, "wb") as f:
        f.write(packet1 + packet2)

    # Create a file-like object
    file_obj = io.BytesIO(packet3)

    # Test with mixed types
    datasets = xarr.create_dataset(
        [test_file, file_obj],
        packet_definition,
        packet_bytes_generator=fixed_length_generator,
        generator_kwargs={"packet_length_bytes": 3},
        parse_bytes_kwargs={"root_container_name": "SIMPLE_CONTAINER"},
    )

    assert len(datasets) == 1
    dataset = list(datasets.values())[0]
    assert len(dataset.packet) == 3
    assert list(dataset["FIELD1"].values) == [16, 32, 48]
    assert list(dataset["FIELD2"].values) == [4660, 22136, 39612]


def test_create_dataset_with_xtce_file_like_object():
    """Test that XTCE definitions can also be provided as file-like objects"""
    # Create a minimal XTCE document as a string
    xtce_xml = """<xtce:SpaceSystem name="TestSystem" xmlns:xtce="http://www.omg.org/space/xtce">
    <xtce:TelemetryMetaData>
        <xtce:ParameterTypeSet>
            <xtce:IntegerParameterType name="UINT8_TYPE">
                <xtce:IntegerDataEncoding sizeInBits="8" encoding="unsigned"/>
            </xtce:IntegerParameterType>
        </xtce:ParameterTypeSet>
        <xtce:ParameterSet>
            <xtce:Parameter name="TEST_FIELD" parameterTypeRef="UINT8_TYPE"/>
        </xtce:ParameterSet>
        <xtce:ContainerSet>
            <xtce:SequenceContainer name="TEST_CONTAINER">
                <xtce:EntryList>
                    <xtce:ParameterRefEntry parameterRef="TEST_FIELD"/>
                </xtce:EntryList>
            </xtce:SequenceContainer>
        </xtce:ContainerSet>
    </xtce:TelemetryMetaData>
</xtce:SpaceSystem>"""

    # Create XTCE file-like object
    xtce_file_obj = io.StringIO(xtce_xml)

    # Create test packet data
    test_data = struct.pack("B", 0x42)
    packet_file_obj = io.BytesIO(test_data)

    # Test with both XTCE and packet data as file-like objects
    datasets = xarr.create_dataset(
        packet_file_obj,
        xtce_file_obj,
        packet_bytes_generator=fixed_length_generator,
        generator_kwargs={"packet_length_bytes": 1},
        parse_bytes_kwargs={"root_container_name": "TEST_CONTAINER"},
    )

    assert len(datasets) == 1
    dataset = list(datasets.values())[0]
    assert len(dataset.packet) == 1
    assert list(dataset["TEST_FIELD"].values) == [66]
