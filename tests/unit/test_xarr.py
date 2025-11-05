"""Tests for the xarr.py extras module"""

import io
import struct

import pytest

from space_packet_parser import xarr
from space_packet_parser.generators.fixed_length import fixed_length_generator
from space_packet_parser.xtce import calibrators, containers, definitions, encodings, parameter_types, parameters

np = pytest.importorskip("numpy", reason="numpy is not available")


@pytest.fixture
def data_type_packet_definition():
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


@pytest.fixture
def fixed_length_packet_definition():
    """Reusable packet definition with UINT8_FIELD, STRING_FIELD, INT32_FIELD (8 bytes total)"""
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
    return definitions.XtcePacketDefinition(container_set=container_set)


@pytest.fixture
def fixed_length_test_packets():
    """Three standard 8-byte test packets with known values

    Returns
    -------
    tuple
        (packet1_data, packet2_data, packet3_data, binary_data) where:
        - packet1: UINT8=0x42, STRING="ABC", INT32=12345
        - packet2: UINT8=0x55, STRING="XYZ", INT32=67890
        - packet3: UINT8=0xFF, STRING="123", INT32=-99999
        - binary_data: All three packets concatenated
    """
    packet1_data = struct.pack(">B3si", 0x42, b"ABC", 12345)
    packet2_data = struct.pack(">B3si", 0x55, b"XYZ", 67890)
    packet3_data = struct.pack(">B3si", 0xFF, b"123", -99999)
    binary_data = packet1_data + packet2_data + packet3_data
    return packet1_data, packet2_data, packet3_data, binary_data


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
def test_minimum_numpy_dtype(data_type_packet_definition, pname, use_raw_value, expected_dtype):
    """Test finding the minimum numpy data type for a parameter"""
    assert xarr._get_minimum_numpy_datatype(pname, data_type_packet_definition, use_raw_value) == expected_dtype


def test_create_dataset_with_custom_generator(tmp_path, fixed_length_packet_definition, fixed_length_test_packets):
    """Test creating a dataset with a custom packet generator for non-CCSDS packets"""
    _, _, _, binary_data = fixed_length_test_packets

    # Write test packets to a temporary file
    test_file = tmp_path / "test_packets.bin"
    with open(test_file, "wb") as f:
        f.write(binary_data)

    # Create dataset using a custom fixed-length generator
    datasets = xarr.create_dataset(
        test_file,
        fixed_length_packet_definition,
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


def test_create_dataset_with_packet_filter(tmp_path, fixed_length_packet_definition, fixed_length_test_packets):
    """Test filtering packets with packet_filter parameter using raw byte inspection"""
    _, _, _, binary_data = fixed_length_test_packets

    # Write to a temporary file
    test_file = tmp_path / "test_packets_filtered.bin"
    with open(test_file, "wb") as f:
        f.write(binary_data)

    # Create dataset with a packet filter that passes packets 1 and 2, but not packet 3
    # Filter: first byte == 0x42 (packet 1) OR second byte == ord('X') (packet 2)
    # Packet 1: first byte = 0x42, second byte = ord('A') = 65
    # Packet 2: first byte = 0x55, second byte = ord('X') = 88
    # Packet 3: first byte = 0xFF, second byte = ord('1') = 49
    datasets = xarr.create_dataset(
        test_file,
        fixed_length_packet_definition,
        packet_bytes_generator=fixed_length_generator,
        generator_kwargs={"packet_length_bytes": 8},
        parse_bytes_kwargs={"root_container_name": "FIXED_LENGTH_CONTAINER"},
        packet_filter=lambda pkt: pkt[0] == 0x42 or pkt[1] == ord("X"),
    )

    # Verify we only got 2 packets (packet 3 was filtered out)
    assert len(datasets) == 1
    dataset = list(datasets.values())[0]
    assert len(dataset.packet) == 2

    # Verify that only packets 1 and 2 are present (packet 3 excluded)
    assert list(dataset["UINT8_FIELD"].values) == [0x42, 0x55]
    assert list(dataset["STRING_FIELD"].values) == ["ABC", "XYZ"]
    assert list(dataset["INT32_FIELD"].values) == [12345, 67890]


def test_create_dataset_with_file_like_objects(tmp_path, fixed_length_packet_definition, fixed_length_test_packets):
    """Test creating a dataset with file-like objects instead of file paths"""
    packet1, packet2, packet3, test_data = fixed_length_test_packets

    # Test with single file-like object (simulating file opened in "rb" mode)
    test_data_file = tmp_path / "test_data.bin"
    with open(test_data_file, "wb") as f:
        f.write(test_data)

    with open(test_data_file, "rb") as fh:
        datasets = xarr.create_dataset(
            fh,
            fixed_length_packet_definition,
            packet_bytes_generator=fixed_length_generator,
            generator_kwargs={"packet_length_bytes": 8},
            parse_bytes_kwargs={"root_container_name": "FIXED_LENGTH_CONTAINER"},
        )

    assert len(datasets) == 1
    dataset = list(datasets.values())[0]
    assert len(dataset.packet) == 3
    assert list(dataset["UINT8_FIELD"].values) == [0x42, 0x55, 0xFF]
    assert list(dataset["STRING_FIELD"].values) == ["ABC", "XYZ", "123"]
    assert list(dataset["INT32_FIELD"].values) == [12345, 67890, -99999]

    # Test with iterable of file-like objects
    file_obj1 = io.BytesIO(packet1 + packet2)
    file_obj2 = io.BytesIO(packet3)

    datasets = xarr.create_dataset(
        [file_obj1, file_obj2],
        fixed_length_packet_definition,
        packet_bytes_generator=fixed_length_generator,
        generator_kwargs={"packet_length_bytes": 8},
        parse_bytes_kwargs={"root_container_name": "FIXED_LENGTH_CONTAINER"},
    )

    assert len(datasets) == 1
    dataset = list(datasets.values())[0]
    assert len(dataset.packet) == 3
    assert list(dataset["UINT8_FIELD"].values) == [0x42, 0x55, 0xFF]
    assert list(dataset["STRING_FIELD"].values) == ["ABC", "XYZ", "123"]
    assert list(dataset["INT32_FIELD"].values) == [12345, 67890, -99999]


def test_create_dataset_with_mixed_file_types(tmp_path, fixed_length_packet_definition, fixed_length_test_packets):
    """Test creating a dataset with mixed file paths and file-like objects"""
    packet1, packet2, packet3, _ = fixed_length_test_packets

    # Create a test file
    test_file = tmp_path / "test_packets.dat"
    with open(test_file, "wb") as f:
        f.write(packet1 + packet2)

    # Create a file-like object
    file_obj = io.BytesIO(packet3)

    # Test with mixed types
    datasets = xarr.create_dataset(
        [test_file, file_obj],
        fixed_length_packet_definition,
        packet_bytes_generator=fixed_length_generator,
        generator_kwargs={"packet_length_bytes": 8},
        parse_bytes_kwargs={"root_container_name": "FIXED_LENGTH_CONTAINER"},
    )

    assert len(datasets) == 1
    dataset = list(datasets.values())[0]
    assert len(dataset.packet) == 3
    assert list(dataset["UINT8_FIELD"].values) == [0x42, 0x55, 0xFF]
    assert list(dataset["STRING_FIELD"].values) == ["ABC", "XYZ", "123"]
    assert list(dataset["INT32_FIELD"].values) == [12345, 67890, -99999]


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


def test_create_dataset_with_pathlike_xtce(tmp_path, fixed_length_packet_definition, fixed_length_test_packets):
    """Test that XTCE definitions can be provided as PathLike objects (e.g., from cloudpathlib)"""
    import os

    # Create a custom PathLike class to simulate cloudpathlib's AnyPath
    class CustomPathLike(os.PathLike):
        """Simulates a PathLike object similar to cloudpathlib.AnyPath"""

        def __init__(self, path):
            self._path = path

        def __fspath__(self):
            return str(self._path)

    _, _, _, binary_data = fixed_length_test_packets

    # Write test packets to a temporary file
    test_file = tmp_path / "test_packets.bin"
    with open(test_file, "wb") as f:
        f.write(binary_data)

    # Wrap the packet definition fixture as PathLike (not needed here since we use the fixture directly)
    # But we can test with PathLike packet files
    pathlike_packet_file = CustomPathLike(test_file)

    # Create dataset using a PathLike packet file
    datasets = xarr.create_dataset(
        pathlike_packet_file,
        fixed_length_packet_definition,
        packet_bytes_generator=fixed_length_generator,
        generator_kwargs={"packet_length_bytes": 8},
        parse_bytes_kwargs={"root_container_name": "FIXED_LENGTH_CONTAINER"},
    )

    # Verify the dataset was created correctly
    assert len(datasets) == 1
    dataset = list(datasets.values())[0]
    assert len(dataset.packet) == 3
    assert list(dataset["UINT8_FIELD"].values) == [0x42, 0x55, 0xFF]
    assert list(dataset["STRING_FIELD"].values) == ["ABC", "XYZ", "123"]
    assert list(dataset["INT32_FIELD"].values) == [12345, 67890, -99999]
