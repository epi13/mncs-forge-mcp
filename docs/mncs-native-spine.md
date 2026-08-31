# MNCS-native Forge spine

Forge now carries a small MNCS-native source spine alongside the established
Python compatibility surface. The source modules are an incremental authority
boundary for identity-shaped values, canonical candidate material, typed
candidate validation, and lifecycle transitions; the Python CLI and MCP server
remain the stable integration surface during the migration.

| Module | Responsibility |
| --- | --- |
| `mncs.forge.identity.v1` | Host-supplied 32-byte digest values and equality/zero checks |
| `mncs.forge.serialization.v1` | Versioned candidate material layout and status codes |
| `mncs.forge.records.v1` | Candidate/validation records and fail-closed checks |
| `mncs.forge.lifecycle.v1` | Epoch, evidence, selection, rejection, freeze, and evaluation transitions |
| `mncs.forge.core.v1` | Public entrypoints used by the adapter and service drift fixture |

The canonical candidate material is exactly 71 bytes in this tranche:

```text
kind:1 | schema:1 | status:1 | parent_digest:32 | source_digest:32 | changed_files:4
```

The MNCS source declares field order and widths. Forge’s host adapter materializes
the bytes and computes SHA-256 at the explicit host boundary; the MNCS module does
not pretend to provide cryptography. A missing language checkout, malformed native
response, timeout, or unsupported backend remains a bounded failure/`UNKNOWN`
observation and does not upgrade a Forge record into assurance or conformance.

## Local probe

With sibling checkouts at the workspace root:

```bash
MNCS_LANGUAGE_ROOT=/absolute/path/to/mncs-language \
python -c 'from pathlib import Path; from mncs_forge.mncs_native import NativeForgeAdapter; print(NativeForgeAdapter(Path("/absolute/path/to/mncs-forge-mcp")).execute(Path("/absolute/path/to/mncs-forge-mcp/mncs/forge/core.mncs"), Path("/absolute/path/to/mncs-forge-mcp/examples/execution/native-status-probe.json")).payload)'
```

The adapter invokes `mncs-language` through Forge’s existing bounded, no-shell
runner. It is intentionally not wired into legacy record creation yet: the first
slice establishes explicit identity and lifecycle seams while keeping migration
reversible and preserving the compatibility API.
