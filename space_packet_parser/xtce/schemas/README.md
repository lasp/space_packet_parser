# Bundled XTCE schemas

These XSD files are bundled with `space_packet_parser` so that schema validation of XTCE
documents that reference the standard OMG schema works **offline**, with no network request.
Resolving the schema locally (instead of downloading the URL named in a document's
`xsi:schemaLocation`) is both faster and removes the SSRF/LFI attack surface for the common case.

| File                       | XTCE version | `targetNamespace`                       | Upstream source                                          |
| -------------------------- | ------------ | --------------------------------------- | -------------------------------------------------------- |
| `SpaceSystem-20180204.xsd` | 1.2          | `http://www.omg.org/spec/XTCE/20180204` | <https://www.omg.org/spec/XTCE/20180204/SpaceSystem.xsd> |
| `SpaceSystem-20250214.xsd` | 1.3          | `http://www.omg.org/spec/XTCE/20250214` | <https://www.omg.org/spec/XTCE/20250214/SpaceSystem.xsd> |

The filename of each schema is the OMG publication date that appears in its URL and namespace URI,
which is what distinguishes one version of the standard from another.

These schemas are published by the Object Management Group (OMG) and remain under OMG's
copyright and license terms. They are redistributed here **byte for byte** as published; the small
set of lxml-compatibility fixups (see `_fix_known_schema_issues` in `../validation.py`) are applied
at load time and are **not** baked into these files. Whitespace-normalizing pre-commit hooks are
excluded from this directory so that the bundled copies can be checksummed against a fresh download:

| File                       | SHA-256                                                            |
| -------------------------- | ------------------------------------------------------------------ |
| `SpaceSystem-20180204.xsd` | `acc3fafc8f16e6c8993335d27c4a1931b2b7eb0e7d1a57b73e745056ca93060d` |
| `SpaceSystem-20250214.xsd` | `a243cf7ac7d51fae15f985193503326b86602322b13c0e40cc44706ed99921d2` |

To add another version, drop the `.xsd` here and add the version to the registry in
`../__init__.py`: its namespace URI (`XTCE_XMLNS_BY_VERSION`), its canonical schema URL
(`XTCE_XSD_URL_BY_VERSION`), the filename you just added (`BUNDLED_XSD_FILENAME_BY_VERSION`), and
the version itself to `SUPPORTED_XTCE_VERSIONS`. The URL-to-file mapping used at validation time
(`_BUNDLED_SCHEMAS` in `../validation.py`) is derived from that registry, so no change is needed
there.
