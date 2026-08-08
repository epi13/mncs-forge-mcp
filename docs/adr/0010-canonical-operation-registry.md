# ADR 0010: Canonical typed operation registry

- **Status:** Accepted; implemented in Task 6
- **Target:** `0.1.0b1`

## Context

After Task 5, CLI and MCP both reached the small `Forge` facade, but `cli.py` and `server.py`
independently mapped public names, arguments, modes, and handlers. This duplicated dispatch truth
could drift even though downstream application services and lifecycle rules were shared.

## Decision

Forge uses one validated registry of frozen operation definitions and input models. Each definition
binds a stable ID to a typed handler, mode and mutation policy, authority/lifecycle and disclosure
metadata, output contract, CLI mapping, MCP tool mapping/visibility, resources, and explicit
interface exclusions.

CLI and MCP normalize interface-specific input then call one registry invocation gate. The gate
resolves only registered IDs, verifies interface exposure and active mode before handler execution,
constructs the declared input model, and invokes the facade handler. FastMCP wrappers and schemas
are generated from registry definitions; argparse presentation remains hand tuned but every leaf
is registry-bound.

Resources remain explicit projections and prompts remain guidance. Operation-backed resources use
canonical invocation. Lifecycle decisions remain solely in `ForgeStateMachine`, record persistence
remains solely through `RecordStore`, and concrete execution/filesystem behavior remains behind
Task 5 ports and adapters.

## Consequences

Interface parity, intentional asymmetry, evaluator visibility, mutation classification, and
authority metadata are deterministically auditable. Compatibility tests can detect drift in one
semantic snapshot, while CLI help and MCP schema presentation retain their existing conventions.

The registry adds metadata and pre-handler authorization; it adds no execution isolation, runner
receipt, external custody, anchoring, witnessing, certification, promotion, or normative validator
authority. Task 7 runner work and later feature tracks remain separate.
