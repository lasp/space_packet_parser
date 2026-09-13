# XTCE Document Validation

Space Packet Parser provides comprehensive validation capabilities for XTCE documents to help
ensure they are correct and will work properly for parsing packets. The validation system operates
in three modes: `"schema"`, `"structure"`, and a default mode of `"all"` (both schema and structure
validation).

- **Schema Validation**: Validates the XML document against the in-document referenced XTCE XSD
  schema
- **Structural Validation**: Validates XTCE-specific structure and reference integrity

## Supported XTCE Versions

Space Packet Parser supports **XTCE 1.2 and XTCE 1.3**. Which version a document uses is
determined entirely by the XML namespace URI on its root `SpaceSystem` element, which must match
the `targetNamespace` of the corresponding OMG schema:

| XTCE version | Namespace URI (`xmlns`)                 | Schema URL (`xsi:schemaLocation`)                        |
| ------------ | --------------------------------------- | -------------------------------------------------------- |
| 1.2          | `http://www.omg.org/spec/XTCE/20180204` | <https://www.omg.org/spec/XTCE/20180204/SpaceSystem.xsd> |
| 1.3          | `http://www.omg.org/spec/XTCE/20250214` | <https://www.omg.org/spec/XTCE/20250214/SpaceSystem.xsd> |

```{note}
The `version` attribute on an XTCE `Header` element is *not* the version of the XTCE standard —
per the XSD it is a free-form version descriptor for the document itself. Only the namespace URI
identifies the standard version.
```

The parts of the schema this library reads — parameter types, data encodings, calibrators,
comparisons and sequence containers — are unchanged between XTCE 1.2 and 1.3, so the same
definition parses identically under either version. The library also accepts documents that use a
non-standard namespace URI (many mission definitions do); those simply have no detectable XTCE
version.

Schema validation requires correct namespacing declarations at the top of your XTCE document, e.g.

```xml
<xtce:SpaceSystem name="SpacePacketParser"
                  xmlns:xtce="http://www.omg.org/spec/XTCE/20250214"
                  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                  xsi:schemaLocation="http://www.omg.org/spec/XTCE/20250214
                                      https://www.omg.org/spec/XTCE/20250214/SpaceSystem.xsd">
```

The namespace URI and the schema URL must name the _same_ version. Mixing them (for example, a
1.3 namespace pointing at the 1.2 schema) produces an `INVALID_XTCE_NAMESPACE` error.

The detected version is reported on the validation result as `result.xtce_version`, and by the
`spp validate` CLI as `XTCE version:`. On a definition object it is available as
`XtcePacketDefinition.xtce_standard_version`.

## Choosing a Version When Writing XTCE

Pass `xtce_standard_version` when building a definition, or assign it to convert an existing one:

```python
from space_packet_parser import XtcePacketDefinition, load_xtce

# Build a new definition targeting XTCE 1.3
definition = XtcePacketDefinition(container_set, xtce_standard_version="1.3")

# Or convert a definition read from a 1.2 document
definition = load_xtce("my_xtce_1_2.xml")
definition.xtce_standard_version = "1.3"
definition.write_xml("my_xtce_1_3.xml")
```

Serialized documents name the schema for their own version in `xsi:schemaLocation`, so they
validate without you having to supply an XSD. Definitions built from scratch default to XTCE 1.2,
so that upgrading the library does not silently change the version of documents you write.

```{note}
Converting between versions rewrites namespaces, not element content. One thing to check by hand
is the `units` attribute of a time parameter type's `Encoding` element, which is drawn from a
version-specific enumeration: XTCE 1.2 spells it `picoSeconds`, while 1.3 spells it `picoseconds`
and adds values such as `milliseconds`, `minutes` and `hours`.
```

## Schema Resolution and Network Security

Because an XTCE document's `xsi:schemaLocation` is attacker-controllable when you validate a
document from an untrusted source, schema resolution is deliberately locked down (see the security
advisories addressed in the [changelog](../changelog.md): local file read / CWE-73 and SSRF /
CWE-918). Schema validation resolves a schema in this order:

1. **Bundled schema (offline).** The standard OMG XTCE schemas for every supported version ship
   with the package. A document referencing the 1.2 or 1.3 schema URL from the table above (or the
   `http` variant of either) validates against the bundled copy with **no network request** — this
   is the common case and requires no configuration.
2. **`local_xsd` (trusted).** A schema path you pass explicitly is trusted and opened directly,
   from anywhere on the filesystem (absolute or relative).
3. **Allowlisted download.** Any other `xsi:schemaLocation` URL is fetched **only** if it is an
   `https` URL whose host is on the allowlist (default: `www.omg.org`). URLs pointing at internal
   or link-local addresses (e.g. `169.254.169.254`, `127.0.0.1`) are always rejected.

A **local filesystem path** appearing in a document's `xsi:schemaLocation` is never opened — pass
`local_xsd` instead to validate against a local schema.

Controls (all available on `validate_xtce(...)` and the `spp validate` CLI):

| Option                  | Env var                                      | Default           | Purpose                                                                                                     |
| ----------------------- | -------------------------------------------- | ----------------- | ----------------------------------------------------------------------------------------------------------- |
| `allowed_schema_hosts`  | `SPP_ALLOWED_SCHEMA_HOSTS` (comma-separated) | `{"www.omg.org"}` | Hosts and/or exact URLs a schema download may target.                                                       |
| `allow_insecure_http`   | `SPP_ALLOW_INSECURE_HTTP`                    | `False`           | **Dangerous.** Permit `http` (not just `https`). The host allowlist and internal-address guard still apply. |
| `allow_schema_download` | —                                            | `True`            | When `False`, make no network request (bundled schemas and `local_xsd` only).                               |

To allow an additional mirror while keeping the default, extend the exported constant:

```python
from space_packet_parser import DEFAULT_ALLOWED_SCHEMA_HOSTS, validate_xtce

result = validate_xtce(
    "my_xtce.xml",
    level="schema",
    allowed_schema_hosts=[*DEFAULT_ALLOWED_SCHEMA_HOSTS, "schemas.example.org"],
)
```

## CLI Validation

```shell
# Validate against the schema referenced in the document (bundled/allowlisted)
spp --log-level=DEBUG validate my_xtce.xml --level all

# Validate against a trusted local schema
spp validate my_xtce.xml --local-xsd my_xsd.xsd --level all

# Allow an additional schema host, or disable network access entirely
spp validate my_xtce.xml --allowed-schema-host schemas.example.org
spp validate my_xtce.xml --no-schema-download --local-xsd my_xsd.xsd
```

## Programmatic Validation

```{note}
`validate_xtce` defaults to `raise_on_error=True`, which raises as soon as the document is invalid.
To inspect errors yourself instead of letting them propagate, pass `raise_on_error=False` and read
them off the returned `ValidationResult`, as below.
```

```python
from space_packet_parser import validate_xtce

# Validate an XTCE file against the referenced schema
result = validate_xtce("my_xtce.xml", level="schema", raise_on_error=False)
if result.errors:
    for error in result.errors:
        print(f"Error: {error}")
else:
    print("Document is valid")

# Validate an XTCE document structure to check for
# unused Parameters, ParameterTypes, and nonexistent references
result = validate_xtce("my_xtce.xml", level="structure", raise_on_error=False)
if result.errors:
    for error in result.errors:
        print(f"Error: {error}")
else:
    print("Document is valid")

# Comprehensive validation (both schema and structure)
result = validate_xtce("my_xtce.xml", level="all", raise_on_error=False)
print(f"Validation completed in {result.validation_time_ms:.1f}ms")
if result.errors:
    for error in result.errors:
        print(f"Error: {error}")
else:
    print("Document is valid")
```
