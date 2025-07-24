"""Space Packet Parser"""
from collections.abc import Iterable
from pathlib import Path
from typing import Union

from space_packet_parser.xtce.definitions import XtcePacketDefinition


def load_xtce(filename: Union[str, Path]) -> XtcePacketDefinition:
    """Create an XtcePacketDefinition object from an XTCE XML file

    Parameters
    ----------
    filename : Union[str, Path]
        XTCE XML file

    Returns
    -------
    : XtcePacketDefinition
    """
    return XtcePacketDefinition.from_xtce(filename)


def create_packet_list(
        packet_files: Union[str, Path, Iterable[Union[str, Path]]],
        xtce_packet_definition: Union[str, Path, XtcePacketDefinition],
        **packet_generator_kwargs: any
):
    """Directly create a list of Packet objects directly from one or more binary files and an XTCE definition

    Parameters
    ----------
    packet_files : Union[str, Path, Iterable[Union[str, Path]]]
        Packet files
    xtce_packet_definition : Union[str, Path, xtce.definitions.XtcePacketDefinition]
        Packet definition for parsing the packet data
    packet_generator_kwargs : Optional[dict]
        Keyword arguments passed to `XtcePacketDefinition.packet_generator()`

    Returns
    -------
    : list[packets.Packet]
        List of parsed Packet objects. Can be used like a list of dictionaries.
    """
    packet_generator_kwargs = packet_generator_kwargs or {}

    if not isinstance(xtce_packet_definition, XtcePacketDefinition):
        xtce_packet_definition = XtcePacketDefinition.from_xtce(xtce_packet_definition)

    if isinstance(packet_files, (str, Path)):
        packet_files = [packet_files]

    packet_list = []
    for packet_file in packet_files:
        with open(packet_file, "rb") as f:
            packet_list += list(xtce_packet_definition.packet_generator(f, **packet_generator_kwargs))

    return packet_list
