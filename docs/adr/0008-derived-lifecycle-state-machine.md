# ADR 0008: Derive lifecycle state from append-only history

- **Status:** Accepted; implemented in Task 3
- **Target:** `0.1.0a3`

## Context

Forge persisted typed immutable records but authorized lifecycle changes through checks scattered
across the facade and verifier service. Latest-record lookup was insufficient for epoch lineage,
terminal dispositions, evidence completeness, current selection, and evaluator-entry coherence.
A mutable current-state document would duplicate and potentially contradict the ledger.

## Decision

Forge uses one `ForgeStateMachine` domain service that consumes one typed ledger snapshot plus
current identity observations. It derives a multidimensional lifecycle projection, authorizes
prospective transitions with stable specific errors, and explains legal next operations and
blockers.

Append-only records remain authoritative. No persistent lifecycle-summary event is introduced.
Historical records are projected without applying prospective creation rules retroactively;
ambiguous history is exposed as a limitation instead of being rewritten.

The state machine owns transition decisions. The `Forge` facade retains execution, record
construction, identity observation, and storage responsibilities. CLI and MCP call the facade's
same inspection method.

## Consequences

Positive consequences:

- epoch and candidate lineage, evidence readiness, disposition terminality, freeze coherence,
  evaluator entry, and verifier terminality are inspectable in one place;
- project-scoped development checks remain independent of candidate state;
- lifecycle errors are stable interface data; and
- Task 4 has a clear boundary around authorized-but-not-yet-atomic record/ledger writes.

Costs and limits:

- ordinary projection currently reads the verified ledger without an index;
- unavailable freshness/comparability bindings remain blockers rather than inferred PASS; and
- storage interruption and concurrent commit recovery remain unresolved until Task 4.

## Acceptance evidence

- table-driven valid and invalid transition tests;
- per-stage inspection assertions and CLI/MCP parity;
- legacy fixture projection without rewriting historical bytes;
- focused Joern before/after call/control queries; and
- full repository validation and micro-verifier benchmark comparison.
