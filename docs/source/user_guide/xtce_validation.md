# XTCE Document Validation

Space Packet Parser provides comprehensive validation capabilities for XTCE documents to help
ensure they are correct and will work properly for parsing packets. The validation system operates
in three modes: `"schema"`, `"structure"`, and a default mode of `"all"` (both schema and structure
validation).

- **Schema Validation**: Validates the XML document against the in-document referenced XTCE XSD
  schema
- **Structural Validation**: Validates XTCE-specific structure and reference integrity

Schema validation requires correct namespacing declarations at the top of your XTCE document, e.g.

```xml
<xtce:SpaceSystem name="SpacePacketParser"
                  xmlns:xtce="http://www.omg.org/spec/XTCE/20180204"
                  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                  xsi:schemaLocation="http://www.omg.org/spec/XTCE/20180204
                                      https://www.omg.org/spec/XTCE/20180204/SpaceSystem.xsd">
```

## Schema Resolution and Network Security

Because an XTCE document's `xsi:schemaLocation` is attacker-controllable when you validate a
document from an untrusted source, schema resolution is deliberately locked down (see the security
advisories addressed in the [changelog](../changelog.md): local file read / CWE-73 and SSRF /
CWE-918). Schema validation resolves a schema in this order:

1. **Bundled schema (offline).** The standard OMG XTCE schema ships with the package. A document
   referencing `https://www.omg.org/spec/XTCE/20180204/SpaceSystem.xsd` (or the `http` variant)
   validates against the bundled copy with **no network request** — this is the common case and
   requires no configuration.
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

```python
from space_packet_parser import validate_xtce

# Validate an XTCE file against the referenced schema
result = validate_xtce("my_xtce.xml", level="schema")
if result.errors:
    for error in result.errors:
        print(f"Error: {error}")
else:
    print("Document is valid")

# Validate an XTCE document structure to check for
# unused Parameters, ParameterTypes, and nonexistent references
result = validate_xtce("my_xtce.xml", level="structure")
if result.errors:
    for error in result.errors:
        print(f"Error: {error}")
else:
    print("Document is valid")

# Comprehensive validation (both schema and structure)
result = validate_xtce("my_xtce.xml", level="all")
print(f"Validation completed in {result.validation_time_ms:.1f}ms")
if result.errors:
    for error in result.errors:
        print(f"Error: {error}")
else:
    print("Document is valid")
```
