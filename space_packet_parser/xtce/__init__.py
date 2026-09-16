"""XTCE module

This module contains Python object representations of XTCE UML/XML models.

It also hosts the registry of XTCE standard versions that ``space_packet_parser`` knows about.
An XTCE document identifies the version of the standard it is written against by the XML
namespace URI on its root ``SpaceSystem`` element (which must match the ``targetNamespace`` of
the corresponding OMG XSD), *not* by any attribute in the document. ``Header/@version`` is a
free-form version descriptor for the document itself, not for the XTCE standard.
"""

from __future__ import annotations

STANDARD_XTCE_NS_PREFIX = "xtce"  # Standard XTCE prefix using in xmlns:prefix="url" attribute

XSI_NS_PREFIX = "xsi"
XSI_XMLNS = "http://www.w3.org/2001/XMLSchema-instance"

# XTCE 1.3 (OMG formal/2025, adopted July 2025)
XTCE_1_3_XSD_URL = "https://www.omg.org/spec/XTCE/20250214/SpaceSystem.xsd"
XTCE_1_3_XMLNS = "http://www.omg.org/spec/XTCE/20250214"

# XTCE 1.2 (OMG formal/2018)
XTCE_1_2_XSD_URL = "https://www.omg.org/spec/XTCE/20180204/SpaceSystem.xsd"
XTCE_1_2_XMLNS = "http://www.omg.org/spec/XTCE/20180204"

# XTCE 1.1 (OMG formal/2008). Note that 1.0 and 1.1 share the pre-1.2 namespace URI, so the
# namespace alone cannot distinguish them. No 1.1 XSD is bundled and 1.1 documents are not
# supported for schema validation; they are listed here only so that version detection can
# report something meaningful.
XTCE_1_1_XSD_URL = "https://www.omg.org/spec/XTCE/20061101/06-11-06.xsd"
XTCE_1_1_XMLNS = "http://www.omg.org/space/xtce"

# Note: There is no XSD available from omg.org for XTCE 1.0

#: XTCE standard versions that this library fully supports: it bundles the OMG XSD for offline
#: schema validation and parses/serializes documents in that version's namespace.
SUPPORTED_XTCE_VERSIONS = ("1.2", "1.3")

#: The most recent XTCE version this library supports.
LATEST_XTCE_VERSION = SUPPORTED_XTCE_VERSIONS[-1]

#: The XTCE version assumed when a version is not otherwise known (e.g. when serializing an
#: ``XtcePacketDefinition`` that was built from scratch rather than read from a document).
#: This remains 1.2 rather than the latest version so that serialized output does not silently
#: change version on upgrade. Pass ``xtce_standard_version`` explicitly to write a different version.
DEFAULT_XTCE_VERSION = "1.2"

#: XTCE standard version -> XML namespace URI (the XSD ``targetNamespace``).
XTCE_XMLNS_BY_VERSION: dict[str, str] = {
    "1.1": XTCE_1_1_XMLNS,
    "1.2": XTCE_1_2_XMLNS,
    "1.3": XTCE_1_3_XMLNS,
}

#: XML namespace URI -> XTCE standard version. Only unambiguous mappings appear here; the
#: pre-1.2 namespace is shared by 1.0 and 1.1 and is reported as 1.1.
XTCE_VERSION_BY_XMLNS: dict[str, str] = {uri: version for version, uri in XTCE_XMLNS_BY_VERSION.items()}

#: Non-canonical namespace URIs that are nonetheless recognized, mapped to the version they mean.
#: ``space_packet_parser`` <= 6.2 serialized documents with an ``https`` XTCE 1.2 namespace URI, which
#: no XTCE schema declares. Such documents are still read as XTCE 1.2, and are normalized to the
#: canonical URI (with a warning) when written back out. These URIs are never *written*.
LEGACY_XTCE_XMLNS_ALIASES: dict[str, str] = {
    "https://www.omg.org/spec/XTCE/20180204": "1.2",
}

#: XTCE standard version -> canonical OMG XSD URL.
XTCE_XSD_URL_BY_VERSION: dict[str, str] = {
    "1.1": XTCE_1_1_XSD_URL,
    "1.2": XTCE_1_2_XSD_URL,
    "1.3": XTCE_1_3_XSD_URL,
}

#: Supported XTCE version -> the values its ``TimeUnitsType`` enumeration permits, which is what a
#: time parameter type's ``Encoding/@units`` attribute must be drawn from. The spellings differ
#: between versions (1.2 ``picoSeconds`` vs 1.3 ``picoseconds``) and 1.3 adds several values, so a
#: unit that is valid in one version may be invalid in the other.
TIME_UNITS_BY_VERSION: dict[str, frozenset[str]] = {
    "1.2": frozenset({"seconds", "picoSeconds", "days", "months", "years"}),
    "1.3": frozenset(
        {
            "seconds",
            "milliseconds",
            "microseconds",
            "nanoseconds",
            "picoseconds",
            "minutes",
            "hours",
            "days",
            "months",
            "years",
        }
    ),
}

#: Supported XTCE version -> filename of the XSD bundled in ``space_packet_parser/xtce/schemas``.
BUNDLED_XSD_FILENAME_BY_VERSION: dict[str, str] = {
    "1.2": "SpaceSystem-20180204.xsd",
    "1.3": "SpaceSystem-20250214.xsd",
}

# Retained for backwards compatibility. XTCE_URI is the namespace URI of the default version.
XTCE_URI = XTCE_XMLNS_BY_VERSION[DEFAULT_XTCE_VERSION]


def xtce_version_from_uri(uri: str | None) -> str | None:
    """Look up the XTCE standard version corresponding to an XML namespace URI.

    Parameters
    ----------
    uri : Optional[str]
        XML namespace URI from the root element of an XTCE document, or None.

    Returns
    -------
    : Optional[str]
        The XTCE version string (e.g. ``"1.3"``) if the URI is a recognized standard XTCE
        namespace, otherwise None. A None return does not mean the document cannot be parsed;
        documents routinely use non-standard namespace URIs.

    Notes
    -----
    A legacy URI from :data:`LEGACY_XTCE_XMLNS_ALIASES` resolves to the version it stands for, so
    that documents written by older versions of this library are still recognized.
    """
    if uri is None:
        return None
    version = XTCE_VERSION_BY_XMLNS.get(uri)
    if version is None:
        version = LEGACY_XTCE_XMLNS_ALIASES.get(uri)
    return version


def xtce_uri_for_version(version: str) -> str:
    """Look up the standard XML namespace URI for an XTCE standard version.

    Parameters
    ----------
    version : str
        XTCE version string, e.g. ``"1.2"`` or ``"1.3"``.

    Returns
    -------
    : str
        The standard namespace URI for that version.

    Raises
    ------
    ValueError
        If the version is not one this library knows about.
    """
    try:
        return XTCE_XMLNS_BY_VERSION[version]
    except KeyError as e:
        raise ValueError(
            f"Unrecognized XTCE version {version!r}. Known versions: {sorted(XTCE_XMLNS_BY_VERSION)}. "
            f"Fully supported versions: {list(SUPPORTED_XTCE_VERSIONS)}."
        ) from e


def xtce_nsmap(
    version: str = DEFAULT_XTCE_VERSION,
    *,
    prefix: str | None = STANDARD_XTCE_NS_PREFIX,
    include_xsi: bool = True,
) -> dict[str | None, str]:
    """Build an lxml namespace mapping for a given XTCE standard version.

    Parameters
    ----------
    version : str
        XTCE version string, e.g. ``"1.2"`` or ``"1.3"``. Default {DEFAULT_XTCE_VERSION}.
    prefix : Optional[str]
        Namespace prefix to bind the XTCE namespace to. None binds it as the default namespace
        (i.e. ``xmlns="..."``, with unprefixed element names).
    include_xsi : bool
        Whether to include the XML Schema instance namespace, which is required in order to
        write an ``xsi:schemaLocation`` attribute. Default True.

    Returns
    -------
    : dict
        Namespace mapping suitable for ``XtcePacketDefinition(ns=...)`` or ``lxml`` element
        factories.
    """
    nsmap: dict[str | None, str] = {prefix: xtce_uri_for_version(version)}
    if include_xsi:
        nsmap[XSI_NS_PREFIX] = XSI_XMLNS
    return nsmap


#: Default namespace mapping used when creating XTCE XML elements from scratch.
STANDARD_XTCE_NSMAP = xtce_nsmap(DEFAULT_XTCE_VERSION)
