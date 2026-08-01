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

1. replace import-time verifier service substitution with one explicit implementation;
2. introduce versioned internal and persistent record models;
3. define and test explicit state-transition rules;
4. add transactional record-plus-ledger writes and interrupted-write recovery; and
5. retain compatibility with existing `0.1` configurations and state fixtures.

## `0.1.0b1` — modular control plane

Goal: split the central control-plane implementation behind stable interfaces.

Required work:

1. separate domain rules, application services, execution, storage, configuration, and interfaces;
2. retain a small public `Forge` facade for compatibility;
3. create one typed operation registry shared by CLI and MCP dispatch;
4. add schema compatibility snapshots and migration tests; and
5. document extension boundaries for providers, verifiers, storage, and runners.

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
- SSH or remote-host runner;
- periodic ledger checkpoints;
- detached checkpoint signatures; and
- optional external witness receipts or independently held checkpoint heads.

Every recorded result must distinguish local validity, external anchoring, witnessing, protected
custody, and independence. A signature or second machine controlled by the same operator does not
establish organizational independence.

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

## Work queue

Implementation order, constraints, acceptance criteria, likely file boundaries, and validation
commands are maintained in [docs/codex-next-steps.md](docs/codex-next-steps.md). Architecture
decisions that affect those tasks are staged under [docs/adr/](docs/adr/).
