"""Common mixins"""
import datetime as dt
import inspect
import io
import logging
import socket
import time
import warnings
from abc import ABCMeta, abstractmethod
from collections.abc import Iterator
from typing import BinaryIO, Optional, Protocol, Union

import lxml.etree as ElementTree
from lxml.builder import ElementMaker

logger = logging.getLogger(__name__)

class NamespaceAwareElement(ElementTree.ElementBase):
    """Custom element that automatically applies namespace mappings."""

    _nsmap: dict[str, str] = {}  # Class level namespace mapping
    _ns_prefix: Union[str, None] = None  # Class level namespace prefix for adding to Xpaths

    @classmethod
    def element_prefix(cls):
        """Create the XPath element prefix

        Notes
        -----
        If the prefix is None,
        it indicates either an implicit namespace such as `<SpaceSystem xmlns="http://xtce-example-ns-uri"/>`,
        where `nsmap` is `{None: "http://xtce-example-ns-uri", ...}`
        or no namespace awareness, such as `<SpaceSystem/>`,
        where `nsmap` does not contain any reference to a URI or prefix for the XTCE namespace
        (but may contain other namespace mappings).

        If the prefix is anything other than None,
        it must be a string and must be present in the namespace mapping dict and represents a prefixed namespace,
        such as `<xtce:SpaceSystem xmlns:xtce="http://xtce-example-ns-uri"/>`
        where `nsmap` would be `{"xtce": "http://xtce-example-ns-uri", ...}` and `ns_prefix` would be `xtce`.
        """
        if cls._ns_prefix is not None:
            if cls._ns_prefix not in cls._nsmap:
                raise ValueError(f"XTCE namespace prefix {cls._ns_prefix} not found in namespace mapping "
                                 f"{cls._nsmap}. If the namespace prefix is not 'None', it must appear as a key in the "
                                 f"namespace mapping dict.")
            return f"{cls._ns_prefix}:"
        return ""

    @classmethod
    def add_namespace_to_xpath(cls, xpath: str) -> str:
        """
        Adds a namespace prefix to each element in an XPath expression.

        Parameters
        ----------
        xpath : str
            The original XPath expression without namespace prefixes.

        Returns
        -------
        str
            The updated XPath expression with namespace prefixes.
        """
        prefix = cls.element_prefix()
        # Regex to match valid XML element names (avoids matching special characters like `@attr`, `.`, `*`, `()`, `::`)
        xpath_parts = xpath.split('/')
        new_parts = []

        for part in xpath_parts:
            # Skip empty parts (handles leading/trailing slashes)
            if not part:
                new_parts.append('')
                continue

            # Handle special cases (wildcards, functions, attributes, self, parent, axes)
            if part is None or part in {'.', '..', '*'} or part.startswith('@') or '::' in part or '(' in part:
                new_parts.append(part)
            else:
                new_parts.append(f"{prefix}{part}")

        new_path = '/'.join(new_parts)
        return new_path

    def find(self, path, namespaces=None):
        """Override find() to automatically use the stored namespace map."""
        if namespaces is None:
            namespaces = self.get_nsmap()
        return super().find(self.add_namespace_to_xpath(path), namespaces=namespaces)

    def findall(self, path, namespaces=None):
        """Override findall() to automatically use the stored namespace map."""
        if namespaces is None:
            namespaces = self.get_nsmap()
        return super().findall(self.add_namespace_to_xpath(path), namespaces=namespaces)

    def iterfind(self, path, namespaces=None):
        """Override iterfind() to automatically use the stored namespace map."""
        if namespaces is None:
            namespaces = self.get_nsmap()
        return super().iterfind(self.add_namespace_to_xpath(path), namespaces=namespaces)

    @classmethod
    def set_nsmap(cls, nsmap: dict):
        """Store the namespace map for all elements of this type."""
        cls._nsmap = nsmap

    def get_nsmap(self):
        """Retrieve the stored namespace map."""
        return self._nsmap

    @classmethod
    def set_ns_prefix(cls, ns_prefix: Union[str, None]):
        """Store the namespace map for all elements of this type."""
        cls._ns_prefix = ns_prefix

    def get_ns_prefix(self):
        """Retrieve the stored namespace map."""
        return self._ns_prefix


# Common comparable mixin
class AttrComparable(metaclass=ABCMeta):
    """Generic class that provides a notion of equality based on all non-callable, non-dunder attributes"""

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            raise NotImplementedError(f"No method to compare {type(other)} with {self.__class__}")

        compare = inspect.getmembers(self, lambda a: not inspect.isroutine(a))
        compare = [attr[0] for attr in compare
                   if not (attr[0].startswith('__') or attr[0].startswith(f'_{self.__class__.__name__}__'))]
        for attr in compare:
            if getattr(self, attr) != getattr(other, attr):
                print(f'Mismatch was in {attr}. {getattr(self, attr)} != {getattr(other, attr)}')
                return False
        return True


class XmlObject(metaclass=ABCMeta):
    """ABC that requires `to_xml_element` and `from_xml_element` methods for parsing and serializing
    a library object from an XML element object.
    """

    @classmethod
    @abstractmethod
    def from_xml(
            cls,
            element: ElementTree.Element,
            *,
            tree: Optional[ElementTree.ElementTree],
            parameter_lookup: Optional[dict[str, any]],
            parameter_type_lookup: Optional[dict[str, any]],
            container_lookup: Optional[dict[str, any]],
    ) -> 'XmlObject':
        """Create an object from an XML element

        Notes
        -----
        This abstract implementation has a signature that includes all possible parameters to this function
        across our XML object classes in order to satisfy Liskov Substitution. It also makes it clear that you
        _can_ pass this information in to from_xml but depending on the subtype implementation, it may be ignored.

        Parameters
        ----------
        element : ElementTree.Element
            XML element from which to parse the object
        tree: Optional[ElementTree.ElementTree]
            Full XML tree for parsing that requires access to other elements
        parameter_lookup: Optional[dict[str, parameters.ParameterType]]
            Parameters dict for parsing that requires knowledge of existing parameters
        parameter_type_lookup: Optional[dict[str, parameters.ParameterType]]
            Parameter type dict for parsing that requires knowledge of existing parameter types
        container_lookup: Optional[dict[str, parameters.ContainerType]]
            Container type dict for parsing that requires knowledge of existing containers

        Returns
        -------
        : cls
        """
        raise NotImplementedError()

    @abstractmethod
    def to_xml(self, *, elmaker: ElementMaker) -> ElementTree.Element:
        """Create an XML element from the object self

        Parameters
        ----------
        elmaker : ElementMaker
            ElementMaker for creating new XML elements with predefined namespace

        Returns
        -------
        : ElementTree.Element
            XML Element object
        """
        raise NotImplementedError()


class Parseable(Protocol):
    """Defines an object that can be parsed from packet data."""
    def parse(self, packet: "SpacePacket") -> None:
        """Parse this entry from the packet data and add the necessary items to the packet."""



BuiltinDataTypes = Union[bytes, float, int, str]

class _Parameter:
    """Mixin class for storing access to the raw value of a parsed data item.

    The raw value is the closest representation of the data item as it appears in the packet.
    e.g. bytes for binary data, int for integer data, etc. It has not been calibrated or
    adjusted in any way and is an easy way for user's to debug the transformations that
    happened after the fact.

    Notes
    -----
    We need to override the __new__ method to store the raw value of the data item
    on immutable built-in types. So this is just a way of allowing us to inject our
    own attribute into the built-in types.
    """
    def __new__(cls, value: BuiltinDataTypes, raw_value: BuiltinDataTypes = None) -> BuiltinDataTypes:
        obj = super().__new__(cls, value)
        # Default to the same value as the parsed value if it isn't provided
        obj.raw_value = raw_value if raw_value is not None else value
        return obj


class BinaryParameter(_Parameter, bytes):
    """A class to represent a binary data item."""


class BoolParameter(_Parameter, int):
    """A class to represent a parsed boolean data item."""
    # A bool is a subclass of int, so all we are really doing here
    # is making a nice representation using the bool type because
    # bool can't be subclassed directly.
    def __repr__(self) -> str:
        return bool.__repr__(bool(self))


class FloatParameter(_Parameter, float):
    """A class to represent a float data item."""


class IntParameter(_Parameter, int):
    """A class to represent a integer data item."""


class StrParameter(_Parameter, str):
    """A class to represent a string data item."""


ParameterDataTypes = Union[BinaryParameter, BoolParameter, FloatParameter, IntParameter, StrParameter]


class SpacePacket(dict):
    """Packet representing parsed data items.

    Container that stores the binary packet data (bytes) as an instance attribute and the parsed
    data items in a dictionary interface. A ``SpacePacket`` generally begins as an empty dictionary that gets
    filled as the packet is parsed. To access the raw bytes of the packet, use the ``SpacePacket.binary_data``
    attribute.

    Parameters
    ----------
    *args : Mapping or Iterable
        Initial items to store in the packet, passed to the dict() constructor.
    binary_data : bytes, optional
        The binary data for a single packet as a bytes object / subclass. This binary data is stored
        and used for parsing the data items. Internally we are tracking the parsing position within
        this binary_data object and trying to read specific bit ranges from it.
    **kwargs : dict
        Additional packet items to store, passed to the dict() constructor.
    """
    def __init__(self, *args, binary_data: bytes = b"", **kwargs):
        if "raw_data" in kwargs:
            warnings.warn("The 'raw_data' keyword argument is deprecated and will be removed in a future release. "
                          "Use 'binary_data' instead.", DeprecationWarning, stacklevel=2)
            binary_data = kwargs.pop("raw_data")
        self.binary_data = binary_data
        self._parsing_pos = 0
        super().__init__(*args, **kwargs)

    @property
    def header(self) -> dict:
        """The header content of the packet."""
        warnings.warn("The header property is deprecated and will be removed in a future release. "
                      "To access the header fields of a CCSDS packet, use the CCSDSPacketBytes class.",
                      DeprecationWarning, stacklevel=2)
        return dict(list(self.items())[:7])

    @property
    def user_data(self) -> dict:
        """The user data content of the packet."""
        warnings.warn("The user_data property is deprecated and will be removed in a future release. "
                      "To access the user_data fields of a CCSDS packet, use the CCSDSPacketBytes class.",
                      DeprecationWarning, stacklevel=2)
        return dict(list(self.items())[7:])

    @property
    def raw_data(self) -> bytes:
        """The raw binary data of the packet."""
        warnings.warn("The raw_data property is deprecated and will be removed in a future release. "
                      "Use the binary_data property instead.", DeprecationWarning, stacklevel=2)
        return self.binary_data

    def _read_from_binary_as_bytes(self, nbits: int) -> bytes:
        """Read a number of bits from the binary packet data as bytes.

        Reads the minimum number of complete bytes required to
        capture `nbits`. Moves `_parsing_pos` cursor `nbits` forward, even if `nbits` is not an integer number of bytes.

        Parameters
        ----------
        nbits : int
            Number of bits to read

        Returns
        -------
        : bytes
            Raw bytes from the packet data
        """
        if self._parsing_pos + nbits > len(self.binary_data) * 8:
            raise ValueError("Tried to read beyond the end of the packet data. "
                             f"Tried to read {nbits} bits from position {self._parsing_pos} "
                             f"in a packet of length {len(self.binary_data) * 8} bits.")
        if self._parsing_pos % 8 == 0 and nbits % 8 == 0:
            # If the read is byte-aligned, we can just return the bytes directly
            data = self.binary_data[self._parsing_pos//8:self._parsing_pos//8 + (nbits+7) // 8]
            self._parsing_pos += nbits
            return data
        # We are non-byte aligned, so we need to extract the bits and convert to bytes
        bytes_as_int = _extract_bits(self.binary_data, self._parsing_pos, nbits)
        self._parsing_pos += nbits
        return int.to_bytes(bytes_as_int, (nbits + 7) // 8, "big")

    def _read_from_binary_as_int(self, nbits: int) -> int:
        """Read a number of bits from the binary packet data as an integer.

        Parameters
        ----------
        nbits : int
            Number of bits to read

        Returns
        -------
        : int
            Integer representation of the bits read from the packet
        """
        if self._parsing_pos + nbits > len(self.binary_data) * 8:
            raise ValueError("Tried to read beyond the end of the packet data. "
                             f"Tried to read {nbits} bits from position {self._parsing_pos} "
                             f"in a packet of length {len(self.binary_data) * 8} bits.")
        int_data = _extract_bits(self.binary_data, self._parsing_pos, nbits)
        self._parsing_pos += nbits
        return int_data


def fixed_length_generator(
    binary_data: Union[BinaryIO, socket.socket, bytes],
    *,
    packet_length_bytes: int,
    buffer_read_size_bytes: Optional[int] = None,
    show_progress: bool = False,
) -> Iterator[bytes]:
    """A generator that yields fixed-length chunks from binary_data.

    Parameters
    ----------
    binary_data : Union[BinaryIO, socket.socket, bytes]
        Binary data source.
    packet_length_bytes : int
        Number of bytes per packet to yield.
    buffer_read_size_bytes : int, optional
        Number of bytes to read from the source per read.
    show_progress : bool
        If True, prints a status bar.

    Yields
    ------
    bytes
        Fixed-length packet bytes.
    """
    n_bytes_parsed = 0  # Keep track of how many bytes we have parsed
    n_packets_parsed = 0  # Keep track of how many packets we have parsed
    read_buffer, total_length_bytes, read_bytes_from_source, buffer_read_size_bytes = _setup_binary_reader(
        binary_data, buffer_read_size_bytes)
    current_pos = 0  # Keep track of where we are in the buffer
    start_time = time.time_ns()
    while True:
        if total_length_bytes and n_bytes_parsed == total_length_bytes:
            break
        if show_progress:
            _print_progress(current_bytes=n_bytes_parsed, total_bytes=total_length_bytes,
                            start_time_ns=start_time, current_packets=n_packets_parsed)
        if current_pos > 20_000_000:
            # Only trim the buffer after 20 MB read to prevent modifying
            # the bitstream and trimming after every packet
            read_buffer = read_buffer[current_pos:]
            current_pos = 0
        while len(read_buffer) - current_pos < packet_length_bytes:
            result = read_bytes_from_source(buffer_read_size_bytes)
            if not result:
                break
            read_buffer += result
        packet_bytes = read_buffer[current_pos:current_pos + packet_length_bytes]
        current_pos += packet_length_bytes
        n_packets_parsed += 1
        n_bytes_parsed += packet_length_bytes
        yield packet_bytes
    if show_progress:
        _print_progress(current_bytes=n_bytes_parsed, total_bytes=total_length_bytes,
                        start_time_ns=start_time, current_packets=n_packets_parsed,
                        end="\n", log=True)


def _setup_binary_reader(binary_data, buffer_read_size_bytes=None):
    """Helper to set up reading from binary_data (file, socket, bytes). Returns:
    read_buffer, total_length_bytes, read_bytes_from_source, buffer_read_size_bytes
    """
    read_buffer = b""
    # ========
    # Set up the reader based on the type of binary_data
    # ========
    if isinstance(binary_data, io.BufferedIOBase):
        if buffer_read_size_bytes is None:
            # Default to a full read of the file
            buffer_read_size_bytes = -1
        total_length_bytes = binary_data.seek(0, io.SEEK_END)  # This is probably preferable to len
        binary_data.seek(0, 0)
        logger.info(f"Creating packet generator from a filelike object, {binary_data}. "
                    f"Total length is {total_length_bytes} bytes")
        read_bytes_from_source = binary_data.read
    elif isinstance(binary_data, socket.socket):  # It's a socket and we don't know how much data we will get
        logger.info("Creating packet generator to read from a socket. Total length to parse is unknown.")
        total_length_bytes = None  # We don't know how long it is
        if buffer_read_size_bytes is None:
            # Default to 4096 bytes from a socket
            buffer_read_size_bytes = 4096
        read_bytes_from_source = binary_data.recv
    elif isinstance(binary_data, bytes):
        read_buffer = binary_data
        total_length_bytes = len(read_buffer)
        read_bytes_from_source = None  # No data to read, we've filled the read_buffer already
        logger.info(f"Creating packet generator from a bytes object. Total length is {total_length_bytes} bytes")
    elif isinstance(binary_data, io.TextIOWrapper):
        raise OSError("Packet data file opened in TextIO mode. You must open packet data in binary mode.")
    else:
        raise OSError(f"Unrecognized data source: {binary_data}")
    return read_buffer, total_length_bytes, read_bytes_from_source, buffer_read_size_bytes


def _print_progress(
            *,
            current_bytes: int,
            total_bytes: Optional[int],
            start_time_ns: int,
            current_packets: int,
            end: str = '\r',
            log: bool = False
        ):
    """Prints a progress bar, including statistics on parsing rate.

    Parameters
    ----------
    current_bytes : int
        Number of bytes parsed so far.
    total_bytes : Optional[int]
        Number of total bytes to parse, if known. None otherwise.
    current_packets : int
        Number of packets parsed so far.
    start_time_ns : int
        Start time on system clock, in nanoseconds.
    end : str
        Print function end string. Default is `\\r` to create a dynamically updating loading bar.
    log : bool
        If True, log the progress bar at INFO level.
    """
    progress_char = "="
    bar_length = 20

    if total_bytes is not None:  # If we actually have an endpoint (i.e. not using a socket)
        percentage = int((current_bytes / total_bytes) * 100)  # Percent Completed Calculation
        progress = int((bar_length * current_bytes) / total_bytes)  # Progress Done Calculation
    else:
        percentage = "???"
        progress = 0

    # Fast calls initially on Windows can result in a zero elapsed time
    elapsed_ns = max(time.time_ns() - start_time_ns, 1)
    delta = dt.timedelta(microseconds=elapsed_ns / 1E3)
    kbps = int(current_bytes * 8E6 / elapsed_ns)  # 8 bits per byte, 1E9 s per ns, 1E3 bits per kb
    pps = int(current_packets * 1E9 / elapsed_ns)
    info_str = f"[Elapsed: {delta}, " \
               f"Parsed {current_bytes} bytes ({current_packets} packets) " \
               f"at {kbps}kb/s ({pps}pkts/s)]"
    loadbar = f"Progress: [{progress * progress_char:{bar_length}}]{percentage}% {info_str}"
    print(loadbar, end=end)
    if log:
        logger.info(loadbar)


def _extract_bits(data: bytes, start_bit: int, nbits: int):
    """Extract nbits from the data starting from the least significant end.

    If data = 00110101 11001010, start_bit = 2, nbits = 9, then the bits extracted are "110101110".
    Those bits are turned into a Python integer and returned.

    Parameters
    ----------
    data : bytes
        Data to extract bits from
    start_bit : int
        Starting bit location within the data
    nbits : int
        Number of bits to extract

    Returns
    -------
    int
        Extracted bits as an integer
    """
    # Get the bits from the packet data
    # Select the bytes that contain the bits we want.
    start_byte = start_bit // 8  # Byte index containing the start_bit
    start_bit_within_byte = start_bit % 8  # Bit index within the start_byte
    end_byte = start_byte + (start_bit_within_byte + nbits + 7) // 8
    data = data[start_byte:end_byte]  # Chunk of bytes containing the data item we want to parse
    # Convert the bytes to an integer for bitwise operations
    value = int.from_bytes(data, byteorder="big")
    if start_bit_within_byte == 0 and nbits % 8 == 0:
        # If we're extracting whole bytes starting at a byte boundary, we don't need any bitshifting
        # This is faster, especially for large binary chunks
        return value

    # Shift the value to the right to move the LSB of the data item we want to parse
    # to the least significant position, then mask out the number of bits we want to keep
    return (value >> (len(data) * 8 - start_bit_within_byte - nbits)) & (2 ** nbits - 1)
