# ADR 0006: Query-driven micro-debugging over the verifier evidence system

- **Status:** Proposed
- **Target:** `0.2.x`

## Context

Forge can match and invoke bounded micro-verifiers, but repeated development debugging may still
depend on large compiler, LLVM, sanitizer, Joern, or test-suite outputs. Those outputs are expensive,
contain irrelevant detail, and provide a weak interface for an agent that needs one precise fact for
its next repair decision.

Large analyzers can often build reusable AST, IR, graph, index, runtime, or test representations.
The missing architecture is a way to bind those representations to candidate identities and ask
small questions without creating a second execution or evidence system.

## Decision

Forge will define query-driven micro-debugging as a development-only layer over existing
micro-verifier actions and results.

The record vocabulary consists of:

- `diagnostic_session`;
- `diagnostic_snapshot`;
- `diagnostic_event`;
- `debug_hypothesis`;
- `debug_probe`; and
- `debug_probe_result`.

A debug probe references a declared verifier and links to the existing `verifier_action` once
execution starts. A debug probe result references the existing `verifier_result`; it may interpret
that result for a hypothesis, repair scope, freshness envelope, and escalation decision, but it
cannot redefine the verifier status.

Providers may create reusable identity-bound snapshots. Snapshot internals remain provider-owned and
may be ephemeral or content-addressed. Forge records provider, toolchain, candidate, input,
configuration, environment, coverage, storage, and dependency identities. Candidate changes
invalidate snapshots by default unless a declared complete dependency envelope proves every material
dependency unchanged.

The cost hierarchy is `micro`, `incremental`, and `full-scan`. Full analyzers remain available as
deliberate escalation paths.

Forge will not contain an LLM planner. An agent or human states hypotheses and requests declared
probes; Forge performs deterministic matching, authority checks, bounded execution, immutable
recording, freshness evaluation, and disclosure.

## Consequences

Positive consequences:

- agents can obtain compact empirical feedback instead of consuming unbounded analyzer reports;
- expensive compiler or graph construction can be amortized across multiple bounded questions;
- hypothesis, evidence, repair scope, and escalation remain explicit;
- existing verifier status, lineage, freshness, and authority semantics remain authoritative; and
- analyzer brands remain replaceable behind declared narrow capabilities.

Costs and risks:

- session and snapshot lifecycle add record and invalidation complexity;
- provider-declared dependency envelopes may be incomplete or wrong;
- persistent provider processes increase resource-management and security review requirements;
- diagnostic interpretation records can contradict their referenced verifier results unless
  cross-record validation fails closed;
- repair-capable context increases disclosure risk; and
- broad scans may still be more efficient when many uncertainties share one representation.

## Required evidence before acceptance

- the six record definitions are integrated into typed versioned models, compatibility snapshots,
  and migrations;
- record-plus-ledger writes are transactional;
- cross-record validation rejects missing, mismatched, duplicated, or contradictory links;
- snapshot invalidation and complete/incomplete dependency-envelope behavior are tested;
- at least one provider demonstrates multiple bounded probes over one identity-bound snapshot;
- benchmarks compare one-shot large output, repeated provider startup, and session-based queries;
- malformed, stale, oversized, timed-out, and provider-drift cases fail closed;
- development/evaluator separation and disclosure tests prevent repair feedback leakage; and
- no result is described as MNCS/MNCDS conformance, independence, or protected custody.
