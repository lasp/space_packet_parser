"""Extras package that supports generating an `xarray.Dataset` directly"""

# Extras import first since it might fail
try:
    import numpy as np
    import xarray as xr
except ImportError as ie:
    raise ImportError(
        "Failed to import dependencies for xarray extra. Did you install the [xarray] extras package?"
    ) from ie

import collections
import logging
from collections.abc import Callable, Iterable
from os import PathLike
from pathlib import Path
from typing import BinaryIO

from space_packet_parser.exceptions import UnrecognizedPacketTypeError
from space_packet_parser.generators import ccsds_generator
from space_packet_parser.generators.utils import _read_packet_file
from space_packet_parser.xtce import definitions, encodings, parameter_types

logger = logging.getLogger(__name__)

ReadableBinaryPacket = str | Path | PathLike | BinaryIO | bytes


def _min_dtype_for_encoding(data_encoding: encodings.DataEncoding):
    """Find the minimum data type capable of representing an XTCE data encoding.

    This only works for raw values and does not apply to calibrated or otherwise derived values.

    Parameters
    ----------
    data_encoding : encodings.DataEncoding
        The raw data encoding.

    Returns
    -------
    : str
        The numpy dtype string for the minimal representation of the data encoding.
    """
    if isinstance(data_encoding, encodings.IntegerDataEncoding):
        nbits = data_encoding.size_in_bits
        datatype = "int"
        if data_encoding.encoding == "unsigned":
            datatype = "uint"
        if nbits <= 8:
            datatype += "8"
        elif nbits <= 16:
            datatype += "16"
        elif nbits <= 32:
            datatype += "32"
        else:
            datatype += "64"
    elif isinstance(data_encoding, encodings.FloatDataEncoding):
        nbits = data_encoding.size_in_bits
        datatype = "float"
        if nbits == 32:
            datatype += "32"
        else:
            datatype += "64"
    elif isinstance(data_encoding, encodings.BinaryDataEncoding):
        datatype = "bytes"
    elif isinstance(data_encoding, encodings.StringDataEncoding):
        datatype = "str"
    else:
        raise ValueError(f"Unrecognized data encoding type {data_encoding}.")

    return datatype


def _get_minimum_numpy_datatype(
    name: str, definition: definitions.XtcePacketDefinition, use_raw_value: bool = False
) -> str | None:
    """
    Get the minimum datatype for a given variable.

    Parameters
    ----------
    name : str
        The variable name.
    definition : xtce.definitions.XtcePacketDefinition
        The XTCE packet definition. Used to examine data types to infer their niminal numpy representation.
    use_raw_value : bool
        Default False. If True, uses the data type of the raw value for each parameter.

    Returns
    -------
    datatype : Optional[str]
        The minimum numpy dtype for the parameter.
        Returns None to indicate that numpy should use default dtype inference.
    """
    parameter_type = definition.parameters[name].parameter_type
    data_encoding = parameter_type.encoding

    if use_raw_value:
        # If we are using raw values, we can determine the minimal dtype from the parameter data encoding
        return _min_dtype_for_encoding(data_encoding)

    if isinstance(parameter_type, parameter_types.EnumeratedParameterType):
        # Enums are always strings in their derived state
        return "str"

    if isinstance(data_encoding, encodings.NumericDataEncoding):
        if not (data_encoding.context_calibrators is not None or data_encoding.default_calibrator is not None):
            # If there are no calibrators attached to the encoding, then we can proceed as if we're using
            # raw values
            return _min_dtype_for_encoding(data_encoding)
        # If there are calibrators present, we really can't know the size of the resulting values.
        # Let numpy infer the datatype as best it can
        return None

    if isinstance(data_encoding, encodings.BinaryDataEncoding):
        return "bytes"

    if isinstance(data_encoding, encodings.StringDataEncoding):
        return "str"

    raise ValueError(f"Unsupported data encoding: {data_encoding}")


def create_dataset(
    packet_files: ReadableBinaryPacket | Iterable[ReadableBinaryPacket],
    xtce_packet_definition: str | PathLike | definitions.XtcePacketDefinition,
    use_raw_values: bool = False,
    packet_bytes_generator: Callable | None = None,
    generator_kwargs: dict | None = None,
    parse_bytes_kwargs: dict | None = None,
    packet_filter: Callable[[bytes], bool] | None = None,
) -> dict[int, xr.Dataset]:
    """Create a dictionary of xarray Datasets (per APID) from a set of packet files

    Notes
    -----
    This function only handles packet definitions with the same variable structure
    across all packets with the same APID. For example, this cannot be used for polymorphic
    packets whose structure changes based on previously parsed values.
    If you are parsing muxed APID data and wish to filter it, you can either omit the unwanted
    APID packet definitions from your XTCE (fastest) or you can parse everything and
    filter after creation of the Dataset for each APID.

    Parameters
    ----------
    packet_files : Union[str, Path, PathLike, io.BufferedIOBase, io.RawIOBase, bytes, Iterable[Union[str, Path, PathLike, io.BufferedIOBase, io.RawIOBase, bytes]]]
        Packet files or file-like objects opened in binary mode. Accepts file paths (`str`, `Path`, `PathLike`), file-like objects (`io.BufferedIOBase`, `io.RawIOBase`), or raw bytes.
    xtce_packet_definition : Union[str, Path, PathLike, xtce.definitions.XtcePacketDefinition]
        Packet definition for parsing the packet data
    use_raw_values: bool
        Default False. If True, saves parameter raw values to the resulting Dataset.
        e.g. enumerated lookups will be saved as their encoded integer values.
    packet_bytes_generator : Optional[callable]
        The generator function to use for yielding packet bytes. Defaults to
        ccsds.ccsds_generator. Can be set to fixed_length_generator or any
        other generator that yields bytes-like objects.
    generator_kwargs : Optional[dict]
        Keyword arguments passed to the packet bytes generator.
    parse_bytes_kwargs : Optional[dict]
        Keyword arguments passed to `XtcePacketDefinition.parse_bytes()`.
    packet_filter : Optional[Callable[[bytes], bool]]
        Optional function to filter items returned from the packet generator (e.g. `lambda pkt: pkt.apid == 100`)

    Returns
    -------
    : dict[int, xr.Dataset]
        Dataset objects parsed from the iterable of packets, keyed by APID.
    """
    generator_kwargs = generator_kwargs or {}
    parse_bytes_kwargs = parse_bytes_kwargs or {}

    # Default to ccsds_generator if no generator is specified
    if packet_bytes_generator is None:
        packet_bytes_generator = ccsds_generator

    if not isinstance(xtce_packet_definition, definitions.XtcePacketDefinition):
        xtce_packet_definition = definitions.XtcePacketDefinition.from_xtce(xtce_packet_definition)

    if isinstance(packet_files, (str, Path, PathLike, BinaryIO, bytes)):
        packet_files = [packet_files]

    # Set up containers to store our data
    # We are getting a packet file that may contain multiple apids
    # Each apid is expected to contain consistent data fields, so we want to create a
    # dataset per apid.
    # {apid1: dataset1, apid2: dataset2, ...}
    data_dict: dict[int, dict] = {}
    # Also keep track of the datatype mapping for each field
    datatype_mapping: dict[int, dict] = {}
    # Keep track of which variables (keys) are in the dataset
    variable_mapping: dict[int, set] = {}

    def _process_generator(generator):
        """Helper function to process packets from a generator"""
        for binary_data in generator:
            try:
                packet = xtce_packet_definition.parse_bytes(binary_data, **parse_bytes_kwargs)

                # Always skip packets with incomplete parsing (bad packets)
                if packet._parsing_pos != len(packet.binary_data) * 8:
                    logger.debug(
                        "Skipping packet with incomplete parsing: "
                        f"parsed {packet._parsing_pos} bits, expected {len(packet.binary_data) * 8} bits"
                    )
                    continue

            except UnrecognizedPacketTypeError as e:
                # Skip packets that fail to match a concrete packet definition
                logger.debug(f"Unrecognized packet: {e}")
                continue

            # Try to get APID from CCSDS packets, default to 0 for non-CCSDS packets
            try:
                apid = packet.binary_data.apid
            except AttributeError:
                apid = 0

            if apid not in data_dict:
                # This is the first packet for this APID
                data_dict[apid] = collections.defaultdict(list)
                datatype_mapping[apid] = {}
                variable_mapping[apid] = packet.keys()

            if variable_mapping[apid] != packet.keys():
                raise ValueError(
                    f"Packet fields do not match for APID {apid}. This could be "
                    f"due to a conditional (polymorphic) packet definition in the XTCE, while this "
                    f"function currently only supports flat packet definitions."
                    f"\nExpected: {variable_mapping[apid]},\ngot: {list(packet.keys())}"
                )

            for key, value in packet.items():
                if use_raw_values:
                    # Use the derived value if it exists, otherwise use the raw value
                    val = value.raw_value
                else:
                    val = value

                data_dict[apid][key].append(val)
                if key not in datatype_mapping[apid]:
                    # Add this datatype to the mapping
                    datatype_mapping[apid][key] = _get_minimum_numpy_datatype(
                        key, xtce_packet_definition, use_raw_value=use_raw_values
                    )

    for packet_file in packet_files:
        packet_data = _read_packet_file(packet_file)
        generator = packet_bytes_generator(packet_data, **generator_kwargs)
        # Apply optional packet filtering function to generator
        if packet_filter is not None:
            generator = filter(packet_filter, generator)
        _process_generator(generator)

    # Turn the dict into an xarray dataset
    dataset_by_apid = {}

    for apid, data in data_dict.items():
        ds = xr.Dataset(
            data_vars={
                key: (["packet"], np.asarray(list_of_values, dtype=datatype_mapping[apid][key]))
                for key, list_of_values in data.items()
            }
        )

        dataset_by_apid[apid] = ds

    return dataset_by_apid
