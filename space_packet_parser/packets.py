import warnings

# Reimport the classes and functions from space_packet_parser.ccsds module
# This is done to maintain backwards compatibility with the old imports
from space_packet_parser.generators.ccsds import *  # noqa: F403

warnings.warn(
    "The space_packet_parser.packets module is deprecated. "
    "The classes and functions in this module have been moved to the space_packet_parser.ccsds module.",
    DeprecationWarning,
    stacklevel=2,
)
