# MNCS-native Forge spine

Forge now carries a packaged MNCS-native source spine alongside the established
Python compatibility surface. The source modules are an incremental authority
boundary for identity-shaped values, canonical candidate material, typed
candidate validation, lifecycle projection, and bounded technical evidence
reconciliation; the Python CLI and MCP server
remain the stable integration surface during the migration. Forge invokes the
lifecycle module for both bounded history projection and covered transition
preflight.

| Module | Responsibility |
| --- | --- |
| `mncs.forge.identity.v1` | Host-supplied 32-byte digest values and equality/zero checks |
| `mncs.forge.serialization.v1` | Versioned candidate material layout and status codes |
| `mncs.forge.records.v1` | Candidate/validation records and fail-closed checks |
| `mncs.forge.lifecycle.v1` | Epoch/candidate lineage, evidence, disposition, freeze, evaluation, freshness, and stage projection |
| `mncs.forge.reconciliation.v1` | Bounded per-category status counts, conflict classification, unsupported-count accounting, and aggregate technical status |
| `mncs.forge.core.v1` | Public entrypoints used by the adapter and service drift fixture |

The authoritative Forge source files are package data under
`src/mncs_forge/resources/native/forge/`; installed wheels and sdists expose the
same files through `importlib.resources`. A release or CI lane may set
`MNCS_FORGE_NATIVE_MODE=off|prefer|required` (or configure `[native].mode`).
`off` disables selection, `prefer` selects the packaged runtime when available,
and `required` fails closed before startup when it is unavailable. Project
inspection exposes the selected/available/reason status.

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
python -c 'from pathlib import Path; from mncs_forge.mncs_native import NativeForgeAdapter; a=NativeForgeAdapter(Path("/absolute/path/to/mncs-forge-mcp")); print(a.execute(a.native_source, Path("/absolute/path/to/mncs-forge-mcp/examples/execution/native-status-probe.json")).payload)'
```

The adapter invokes `mncs-language` through Forge’s existing bounded, no-shell
runner. First-epoch creation, first-candidate registration, candidate disposition,
and candidate freeze are preflighted against the typed lifecycle kernel before
their legacy-compatible records are committed. Forge-specific record persistence,
identity production, evidence envelopes, evaluator custody, and bundle semantics
remain in the host boundary. A missing language checkout retains the explicit
compatibility path; an available but malformed, timed-out, or semantically
mismatching native result fails closed.

Evidence reconciliation now crosses the same typed boundary. Forge supplies
opaque category digests plus up to eight status observations per category and
receives typed category summaries and an aggregate status. Category labels,
record identities, unsupported-construct presentation, persistence, and
authority remain host concerns. The 16-category/8-observation limits are
explicit; native mode never truncates an oversized envelope or treats malformed
input as a compatibility success. Compatibility classification remains only
for explicit `off` mode or unavailable language runtimes.

The pure preflight/projection caches are keyed by the native contract, full
packaged Forge source content, language library/compiler/runtime content, exact
CLI command, and semantic inputs. They do not persist evidence or lifecycle
authority and never rely on source mtime alone. The projection input is a fixed
32-event typed array; histories outside that declared bound remain
`NATIVE_LIFECYCLE_UNKNOWN` rather than being truncated or guessed.
