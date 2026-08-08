# MNCS Forge development roadmap

This roadmap separates low-risk repository maintenance from architectural changes that require
focused implementation, compatibility work, and adversarial testing. It is directional rather
than normative and does not change the claim boundary of Forge or MNCS/MNCDS.

## Current baseline — `0.1.0a2`

The current reference implementation provides:

- local CLI and stdio MCP interfaces;
- project authority and path validation;
- declared workflows and Provider Protocol 0.1 providers;
- bounded machine-native micro-verifiers;
- epoch, candidate, action, result, freeze, and evaluation lineage;
- immutable local record files and a hash-linked JSONL ledger;
- development/evaluator mode separation; and
- Linux, macOS, and Windows CI across Python 3.11 through 3.13.

The baseline remains experimental. The local ledger detects mutation but does not create external
anchoring, protected custody, independent evaluation, witnessing, or governance approval.

## `0.1.0a3` — internal consolidation

Goal: remove hidden implementation behavior and establish stable internal data and lifecycle
boundaries without materially changing the public CLI, MCP, configuration, or Provider Protocol
surfaces.

Required work:

1. completed: replace import-time verifier service substitution with one explicit implementation;
2. completed: introduce versioned internal and persistent record models and deterministic legacy
   migrations;
3. completed: define and test explicit state-transition rules;
4. completed: add transactional record-plus-ledger writes and interrupted-write recovery; and
5. completed: retain compatibility with existing `0.1` configurations and state fixtures.

The core `0.1.0a3` P0 internal-consolidation requirements are complete. The package version remains
unchanged until the repository's release process advances it.

## `0.1.0b1` — modular control plane

Goal: split the central control-plane implementation behind stable interfaces.

Required work:

1. completed: separate domain rules, application services, execution, storage, configuration, and
   interfaces;
2. completed: retain a small public `Forge` facade for compatibility;
3. completed: create one typed operation registry shared by CLI and MCP dispatch;
4. add schema compatibility snapshots and migration tests; and
5. completed: document extension boundaries for providers, verifiers, storage, execution, and
   operations.

Task 5 completed service and dependency decomposition. Task 6 now provides the shared typed
operation registry, deterministic inventory, generated FastMCP tools, registry-bound argparse
dispatch, explicit asymmetries, and compatibility enforcement. The extension boundaries are
documented in [Architecture and trust boundaries](docs/architecture.md), with detailed registry,
provider, storage, and verifier guides. Remaining `0.1.0b1` work is focused on schema/migration
compatibility review. Full runner receipts, sandbox-capable adapters, and execution assurance
remain Task 7.

## `0.2.0` — stable local Forge

Goal: make Forge a dependable local control plane before distributed execution is introduced.

Release criteria:

- no import-order implementation replacement;
- documented record schema and migration policy;
- explicit state machine and transition tests;
- transactional storage and recovery tests;
- replaceable runner and record-store interfaces;
- malformed-protocol, subprocess, ledger, and concurrency adversarial suites;
- wheel installation and upgrade tests;
- stable machine-readable CLI/MCP operation inventory; and
- a reviewed threat model covering the local trust boundary.

## `0.2.x` — execution and evidence adapters

Goal: strengthen the execution environment and evidence anchoring without overstating authority.

Planned adapters:

- local process runner;
- rootless Podman runner;
- optional Docker runner;
- Forge Cell Linux isolation runner;
- SSH or remote-host runner;
- periodic ledger checkpoints;
- detached checkpoint signatures; and
- optional external witness receipts or independently held checkpoint heads.

The Forge Cell specification foundation now includes versioned policy, test-bundle, and execution-
record schemas; offline validation; a fail-closed assurance assessment; reference fixtures; and a
proposed ADR. It does not yet implement an OS sandbox. The implementation queue is maintained in
[docs/codex-forge-cell-next-steps.md](docs/codex-forge-cell-next-steps.md).

Every recorded result must distinguish local validity, execution assurance, external anchoring,
witnessing, protected custody, and independence. A signature or second machine controlled by the
same operator does not establish organizational independence.

## `0.2.x` — query-driven micro-debugging

Goal: let agents use compilers and analyzers as identity-bound query engines instead of depending
primarily on large report dumps.

The specification foundation defines diagnostic sessions, reusable snapshots, normalized events,
falsifiable hypotheses, bounded probes, and diagnostic interpretations that link to the existing
verifier action/result system. It also defines `micro`, `incremental`, and `full-scan` escalation
levels without changing verifier status or evidence authority.

Planned work:

- typed diagnostic records and cross-record validation;
- normalized compiler, test, runtime, verifier, analyzer, contract, and human events;
- identity-bound snapshot lifecycle and invalidation;
- a minimal Provider Protocol extension for snapshot-backed queries;
- agent-facing hypothesis and probe operations through the shared operation registry;
- safe identity-bound snapshot and result reuse;
- a Clang/LLVM pilot provider;
- latency, output-size, repair-localization, and escalation benchmarks; and
- stale-state, substitution, resource, and disclosure adversarial studies.

The architecture is documented in [docs/micro-debugging.md](docs/micro-debugging.md), with the
ordered implementation handoff in
[docs/codex-micro-debugging-next-steps.md](docs/codex-micro-debugging-next-steps.md). Runtime work
depends on the core typed-record, transaction, state-machine, modular-service, operation-registry,
and runner tasks.

## `0.3.x` — intent-aware security verification

Goal: harden machine-native code without treating unfamiliar or non-orthodox implementation
structure as automatic failure, while ensuring declared intent can never waive a failed safety
invariant.

The proposed architecture separates suspicious-pattern routing, local and trust-boundary verifier
results, attack-path composition, freshness, and project workflow disposition. It introduces
identity-bound intentional-deviation and deviation-evaluation records rather than broad scanner
suppression or syntax whitelists.

Planned work:

- versioned records and policy for intentional deviations and their evaluations;
- deterministic routing from bounded suspicion witnesses to required verifier capabilities;
- explicit approval, expiration, scope, and revalidation rules;
- local-invariant, trust-boundary, and compiler-aware verifier pilots;
- compiler, target, IR/object, reference-semantics, and deployment identity binding where material;
- a bounded attack-path composition pilot that cannot rewrite underlying verifier results;
- adversarial tests for forged links, stale declarations, broad whitelists, incomplete dependency
  envelopes, copied exceptions, and attempted `FAIL` suppression;
- agentic repair studies comparing compile/test-only feedback with verifier-guided hardening; and
- recursive-learning controls that preserve complete evidence-backed patterns rather than copying
  unusual syntax outside its verified envelope.

The architecture is documented in
[docs/intent-aware-security-verification.md](docs/intent-aware-security-verification.md) and proposed
by [ADR 0007](docs/adr/0007-intent-aware-security-verification.md). Implementation depends on typed
records, transactional storage, the shared operation registry, micro-verifier capability matching,
query-driven diagnostics, and stable freshness semantics.

## `0.3.0` — distributed Forge

Goal: coordinate bounded jobs across heterogeneous machines while preserving identities,
capability constraints, partial failure, and evidence classification.

Planned components:

- coordinator and worker protocol;
- immutable content-addressed job envelopes;
- worker capability and environment declarations;
- leases, retries, idempotency, and duplicate-result reconciliation;
- artifact transfer identity verification;
- cohort plans for cross-platform and different-performance hosts; and
- explicit separation between replication, public reproduction, witnessing, and independent
  evaluation.

The MCP server remains the agent-facing control plane. It should not become the distributed
scheduler itself.

## `0.3.x` — measured and externally held evaluation

Goal: add stronger assurance backends only after local runner and challenge-bound record behavior is
stable.

Planned work:

- signed, content-addressed test bundles and output manifests;
- fresh challenge-bound execution records and an offline verifier;
- an adversarial Forge Cell mutation, escape, exhaustion, and replay study;
- TPM-backed measured execution;
- one confidential-VM backend with protected-test key release; and
- separately administered evaluator and custody adapters.

These features may make silent local substitution detectable under a declared trust model. They do
not automatically create organizational independence, evaluator competence, governance approval,
or immunity from denial of service.

## Work queue

Implementation order, constraints, acceptance criteria, likely file boundaries, and validation
commands are maintained in [docs/codex-next-steps.md](docs/codex-next-steps.md). Forge Cell work is
expanded in [docs/codex-forge-cell-next-steps.md](docs/codex-forge-cell-next-steps.md), and
micro-debugging work is expanded in
[docs/codex-micro-debugging-next-steps.md](docs/codex-micro-debugging-next-steps.md). Architecture
decisions that affect those tasks are staged under [docs/adr/](docs/adr/).
