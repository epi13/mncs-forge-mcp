# ADR 0001: Explicit control-plane composition

- **Status:** Accepted; implemented in Tasks 1 and 5
- **Target:** `0.1.0a3` and `0.1.0b1`

## Context

Before the first `0.1.0a3` consolidation task, Forge exposed a useful public facade, but
control-plane responsibilities were concentrated in the `Forge` class and the verifier lifecycle
was hardened through import-time class replacement. Import order therefore participated in
implementation selection, and the base and hardened verifier services duplicated important
control flow. The verifier portion of this decision is now implemented; the broader control-plane
composition remains staged work.

Hidden implementation substitution is difficult to reason about, test, extend, and preserve across
packaging and future plugin boundaries.

## Decision

Forge will use explicit composition:

- one normal verifier implementation will replace import-time service substitution;
- `Forge` will remain a small public compatibility facade;
- domain rules and application services will be constructed explicitly;
- storage and execution will be injected through typed protocols; and
- CLI and MCP adapters will invoke application operations rather than implement policy.

The implemented dependency direction is:

```text
interfaces -> application services -> domain rules -> adapter protocols -> concrete adapters
```

Domain modules must not depend on FastMCP, argparse, TOML parsing, subprocess primitives, or
concrete filesystem storage.

## Consequences

Positive consequences:

- implementation selection is visible and deterministic;
- state and authority rules become independently testable;
- storage, runners, and distributed execution gain stable seams; and
- CLI/MCP compatibility can be retained through the facade.

Costs and risks:

- the refactor must be staged to avoid public interface drift;
- compatibility tests are required before moving responsibilities; and
- premature file movement without real dependency boundaries would add churn without solving the
  architectural problem.

## Required evidence before acceptance

- no package import mutates a public service binding;
- direct and package-first import orders produce identical behavior;
- the verifier lifecycle has one authoritative implementation;
- `Forge` delegates to explicit services; and
- import-boundary tests prevent domain-to-interface dependency inversion.

## Implementation evidence

Task 1 removed import-time verifier substitution and retained one `MicroVerifierService`. Task 5
reduced `Forge` to construction, intentional compatibility helpers, and delegation; introduced
cohesive application services; and added typed record, execution, identity/workspace-observation,
and verifier-catalog ports with local adapters at the composition root. The verifier service no
longer receives a Forge-shaped host. Repository-owned architecture tests reject upward imports,
service constructors accepting `Forge`, direct service calls to `run_bounded`, concrete local-store
construction in services, storage bypasses, and cycles among the new application modules.

CLI and MCP still use the same facade and retain their existing hand-written dispatch. A unified
operation registry remains the separate Task 6 decision; full replaceable runner semantics remain
Task 7.
