# Bundled XTCE schemas

These XSD files are bundled with `space_packet_parser` so that schema validation of XTCE
documents that reference the standard OMG schema works **offline**, with no network request.
Resolving the schema locally (instead of downloading the URL named in a document's
`xsi:schemaLocation`) is both faster and removes the SSRF/LFI attack surface for the common case.

| File              | XTCE version | `targetNamespace`                       | Upstream source                                          |
| ----------------- | ------------ | --------------------------------------- | -------------------------------------------------------- |
| `SpaceSystem.xsd` | 1.2          | `http://www.omg.org/spec/XTCE/20180204` | <https://www.omg.org/spec/XTCE/20180204/SpaceSystem.xsd> |

These schemas are published by the Object Management Group (OMG) and remain under OMG's
copyright and license terms. They are redistributed here unmodified; the small set of
lxml-compatibility fixups (see `_fix_known_schema_issues` in `../validation.py`) are applied
at load time and are **not** baked into these files.

The mapping from schema URL to bundled file lives in `_BUNDLED_SCHEMAS` in `../validation.py`.
To add another version, drop the `.xsd` here and add an entry keyed on its scheme-insensitive
`host/path`.
