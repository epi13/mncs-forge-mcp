# Architecture decision records

Architecture decision records capture choices that materially affect Forge authority, persistent
evidence, execution, or extension boundaries. They are design inputs, not normative MNCS/MNCDS
requirements.

## Status meanings

- **Proposed** — the problem and preferred direction are documented, but implementation may still
  change the decision.
- **Accepted** — the project has approved the decision and implementation should conform to it.
- **Superseded** — a later ADR replaces the decision while preserving historical context.

## Accepted decisions

- [ADR 0001: Explicit control-plane composition](0001-explicit-control-plane-composition.md)
- [ADR 0002: Versioned persistent record schemas](0002-versioned-record-schemas.md)
- [ADR 0003: Replaceable execution runners](0003-replaceable-execution-runners.md)
- [ADR 0008: Derive lifecycle state from append-only history](0008-derived-lifecycle-state-machine.md)
- [ADR 0009: Recoverable local record and ledger commits](0009-recoverable-record-store.md)
- [ADR 0010: Canonical typed operation registry](0010-canonical-operation-registry.md)
- [ADR 0011: Forge/Fabric execution and evidence boundary](0011-forge-fabric-execution-boundary.md)
- [ADR 0013: Consume language-owned compiler experiment observations](0013-language-owned-compiler-experiment-observations.md)
- [ADR 0014: Persist language-owned compiler experiments](0014-persistent-compiler-experiment-records.md)

## Proposed decisions

- [ADR 0004: Ledger checkpoints and external anchoring](0004-ledger-checkpoints-and-anchoring.md)
- [ADR 0005: Forge Cell assurance and challenge-bound attestation](0005-forge-cell-assurance-and-attestation.md)
- [ADR 0006: Query-driven micro-debugging over the verifier evidence system](0006-query-driven-micro-debugging.md)
- [ADR 0007: Intent-aware security verification for non-orthodox code](0007-intent-aware-security-verification.md)
- [ADR 0012: Property-oriented polyglot verifier fleet](0012-property-oriented-polyglot-verifier-fleet.md)

A coding agent should update the relevant ADR from **Proposed** to **Accepted** only when the PR
actually implements and tests the decision or when maintainers approve it independently.
