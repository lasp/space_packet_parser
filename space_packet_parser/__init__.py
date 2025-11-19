"""Space Packet Parser"""

from pathlib import Path

from space_packet_parser.common import SpacePacket
from space_packet_parser.generators import ccsds_generator
from space_packet_parser.xtce.definitions import XtcePacketDefinition
from space_packet_parser.xtce.validation import validate_xtce

__all__ = [
    "ccsds_generator",
    "SpacePacket",
    "XtcePacketDefinition",
    "load_xtce",
    "validate_xtce",
]


def load_xtce(filename: str | Path) -> XtcePacketDefinition:
    """Create an XtcePacketDefinition object from an XTCE XML file

    This is a shortcut for calling XtcePacketDefinition.from_xtce().

    Parameters
    ----------
    filename : Union[str, Path]
        XTCE XML file

    Returns
    -------
    : definitions.XtcePacketDefinition
    """
    return XtcePacketDefinition.from_xtce(filename)
