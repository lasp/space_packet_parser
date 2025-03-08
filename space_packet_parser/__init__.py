"""Space Packet Parser"""
from pathlib import Path
from typing import Union

from space_packet_parser.ccsds import ccsds_generator
from space_packet_parser.common import Packet
from space_packet_parser.xtce.definitions import XtcePacketDefinition

__all__ = [
    "ccsds_generator",
    "Packet",
    "XtcePacketDefinition",
    "load_xml",
]

def load_xtce(filename: Union[str, Path]) -> XtcePacketDefinition:
    """Create an XtcePacketDefinition object from an XTCE XML file

    Parameters
    ----------
    filename : Union[str, Path]
        XTCE XML file

    Returns
    -------
    : definitions.XtcePacketDefinition
    """
    return XtcePacketDefinition.from_xtce(filename)
