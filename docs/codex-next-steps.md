# Codex implementation queue

This document is the ordered implementation handoff for coding agents working on MNCS Forge. It
turns the architectural roadmap into bounded pull requests with explicit constraints and
acceptance criteria.

Do not implement the entire queue in one branch. Each numbered task should normally be one focused
pull request, and later tasks should be rebased on the completed earlier work. Preserve existing
public behavior unless the task explicitly authorizes a compatibility change.

## Non-negotiable invariants

Every task must preserve these project rules:

- MNCS implementation results and MNCDS development-process results remain separate;
- status aggregation remains `FAIL > UNKNOWN > PASS`;
- missing, stale, malformed, unavailable, or unsupported evidence remains `UNKNOWN`;
- workflow exit zero alone is not evidence `PASS`;
- Forge does not copy normative MNCS/MNCDS validator decisions;
- development and evaluator authority remain separate;
- final evaluation must not become repair feedback for the same epoch;
- commands remain declared argument arrays with no shell execution;
- caller input cannot select arbitrary executables, argv, environment, or working directories;
- protected and writable paths cannot overlap;
- historical records remain immutable and lineage remains explicit;
- local operation cannot claim independence, protected custody, witnessing, certification, or
  governance approval; and
- Forge is not described as an OS or network sandbox unless a specific runner provides and records
  those properties.

## Standard agent workflow

Before changing code:

1. inspect the current branch and recent merged PRs;
2. run `./scripts/check.sh` and record the baseline result;
3. identify the public CLI, MCP, configuration, record, and Provider Protocol surfaces affected;
4. add regression tests that fail for the targeted architectural problem; and
5. avoid unrelated formatting, renaming, or documentation churn.

Before opening a PR:

```bash
./scripts/check.sh
python scripts/benchmark-micro-verifiers.py --iterations 25
```

Run additional task-specific checks listed below. The benchmark is development evidence only and
must not be described as conformance, independence, or certification.

---

## Task 1 — Consolidate the verifier implementation

**Priority:** P0

**Target:** `0.1.0a3`

**Depends on:** nothing

**Status:** Completed in the verifier-consolidation iteration.

### Objective

Remove the import-time replacement of `MicroVerifierService` with
`HardenedMicroVerifierService`. Produce one explicit verifier implementation that includes the
current deletion-aware identities, terminal-result guarantees, heterogeneous batch parameters,
evaluator redaction, matching, execution, disclosure, and freshness behavior.

### Required changes

- remove mutation of `mncs_forge.micro_verifiers.MicroVerifierService` from package import;
- merge the hardened lifecycle behavior into one normal service implementation or construct the
  service explicitly through `Forge`;
- remove duplicated `run` and `batch` control flow after behavior is consolidated;
- retain focused helper modules for changed-path identity, terminal records, disclosure, and batch
  parameter envelopes where they reduce responsibility;
- make imports deterministic and independent of import order; and
- update tests so they patch or inject the explicit service rather than depending on package import
  side effects.

### Acceptance criteria

- importing `mncs_forge.engine` directly and importing `mncs_forge` first produce the same service
  class and behavior;
- there is no `vars(...)["MicroVerifierService"]` replacement or equivalent monkey-patch;
- every recorded verifier action receives exactly one terminal verifier result after execution has
  begun, including late authority drift and provider failures;
- absent or deleted changed paths retain explicit identities;
- existing directories remain invalid changed-path inputs;
- evaluator `status-only` records are redacted before identity calculation and persistence;
- shared and per-verifier batch parameter envelopes remain unambiguous; and
- existing CLI and MCP verifier tests pass without changing their public output shape except for
  explicitly documented bug fixes.

### Validation

```bash
./scripts/check.sh
pytest -q tests/test_verifier_hardening.py tests/test_micro_verifiers.py
python -c "import mncs_forge.engine; import mncs_forge; print('imports-ok')"
python -c "import mncs_forge; import mncs_forge.engine; print('imports-ok')"
```

### Out of scope

Do not modularize the whole `Forge` engine, introduce new verifier types, add caching, or change
Provider Protocol in this PR.

---

## Task 2 — Add versioned record models and migrations

**Priority:** P0  
**Target:** `0.1.0a3`  
**Depends on:** Task 1

**Status:** Completed in the versioned-record-model iteration.

### Objective

Replace unstructured internal evidence dictionaries with explicit immutable models at the domain
boundary while preserving JSON objects at storage and interface boundaries.

### Required models

At minimum define typed, frozen models for:

- epoch;
- candidate;
- provider probe;
- workflow action and result;
- verifier action and result;
- selection or rejection disposition;
- freeze;
- final evaluation;
- reconciliation result;
- bundle record; and
- ledger entry.

Each persistent payload must identify its `record_type` and `schema_version`. Add a migration
registry that can read the current unversioned `0.1` fixtures and normalize them into the first
versioned model without rewriting historical files in place.

### Constraints

- identities must be computed from the canonical persisted representation, not a lossy in-memory
  form;
- unknown extension keys must either be preserved in an explicit extension object or rejected by a
  documented rule;
- timestamps, identities, and status fields must retain their current semantics;
- migrations must be deterministic and offline; and
- reading an old record must not silently grant authority or convert `UNKNOWN` into `PASS`.

### Acceptance criteria

- new records include stable type and schema-version fields;
- old committed state fixtures still load and verify;
- unsupported future schema versions fail closed with a specific error code;
- serialization round trips produce the same canonical identity;
- mypy no longer requires broad `dict[str, Any]` assumptions through the core lifecycle; and
- schema compatibility snapshots are committed for public record shapes.

### Validation

```bash
./scripts/check.sh
pytest -q tests/test_ledger.py tests/test_records.py tests/test_compatibility.py
```

### Out of scope

Do not relocate every package module in this PR. Establish the models and adapters first.

---

## Task 3 — Formalize the Forge state machine

**Priority:** P0  
**Target:** `0.1.0a3`  
**Depends on:** Task 2

**Status:** Completed in the lifecycle-state-machine iteration.

### Objective

Move lifecycle authorization from scattered method checks into an explicit transition model used
by CLI, MCP, and internal application services.

### Required transitions

Model at least:

```text
no epoch
  -> active development epoch
  -> registered candidate lineage
  -> candidate evidence collected
  -> candidate selected or rejected
  -> selected candidate frozen
  -> evaluator execution
  -> reconciled evaluation and bundle
```

Project-scoped development workflows that intentionally do not require candidate state must remain
separate from candidate-scoped transitions.

### Required invalid-transition tests

- candidate registration without an active epoch;
- candidate identity or parent lineage mismatch;
- selecting a candidate without comparable required evidence;
- selecting and rejecting the same candidate without explicit supersession rules;
- freezing an unselected or rejected candidate;
- evaluator operation without freeze;
- evaluator operation after frozen authority or environment drift;
- development mutation through evaluator mode;
- two terminal results for one action; and
- continuing a closed or superseded epoch as though it were current.

### Acceptance criteria

- one transition service returns stable, specific error codes;
- CLI and MCP operations invoke the same transition rules;
- state inspection can explain the current lifecycle stage and allowed next operations;
- historical state remains append-only rather than being edited in place; and
- property-based or table-driven tests cover all valid and invalid transitions.

### Implementation evidence

Task 3 added a typed append-only-history projection, active epoch and same-epoch candidate lineage,
policy-declared evidence readiness, one terminal disposition, current-selection freeze and
evaluator gates, verifier action terminality, stable transition errors, per-stage inspection, and
shared Forge/CLI/MCP state output. Historical Task 2 fixtures remain readable and are projected
without rewriting or prospective-rule rejection. Transactional writes and recovery remain Task 4.

### Validation

```bash
./scripts/check.sh
pytest -q tests/test_state_machine.py tests/test_engine.py tests/test_cli_mcp_edgestream.py
```

---

## Task 4 — Make record and ledger writes transactional

**Priority:** P0  
**Target:** `0.1.0a3`  
**Depends on:** Tasks 2 and 3

### Objective

Prevent interrupted processes from leaving an immutable record without its ledger entry, a ledger
entry without its immutable record, or an action permanently lacking a recoverable terminal state.

### Required changes

- define a `RecordStore` interface;
- stage immutable payload and ledger entry under the same exclusive transaction boundary;
- use atomic rename and directory/file synchronization where supported;
- add a transaction or recovery journal that can distinguish prepared, committed, and abandoned
  writes;
- recover deterministically after interruption;
- retain file locking and concurrent-writer rejection or serialization; and
- add periodic checkpoints or an index so ordinary reads do not require reparsing unrelated
  payload files.

### Acceptance criteria

- fault-injection tests at every write step recover to either the complete previous state or the
  complete new state;
- no successful action is left without a terminal result after restart;
- concurrent writers cannot create duplicate sequences or broken hash links;
- ledger verification identifies truncated, reordered, replaced, or missing record files; and
- existing `.mncs-forge` fixtures remain readable through the compatibility adapter.

### Validation

```bash
./scripts/check.sh
pytest -q tests/test_ledger.py tests/test_record_store.py tests/test_recovery.py -x
```

Run repeated concurrency and interruption tests on Linux and Windows.

---

## Task 5 — Split the monolithic control plane behind stable services

**Priority:** P1  
**Target:** `0.1.0b1`  
**Depends on:** Tasks 1 through 4

### Objective

Retain `Forge` as a small compatibility facade while moving responsibilities into explicit domain
and application services.

### Intended dependency direction

```text
CLI and MCP adapters
    -> application services
    -> domain models and transition rules
    -> execution and storage interfaces
    -> local adapters
```

The domain layer must not import FastMCP, argparse, TOML parsing, subprocess primitives, or concrete
filesystem storage.

### Suggested service boundaries

- project inspection and claim reporting;
- epochs and candidate lineage;
- provider discovery and probing;
- development workflows;
- micro-verifiers;
- selection and comparison;
- freeze and evaluator execution;
- reconciliation and bundling; and
- storage, execution, identity, and policy adapters.

### Acceptance criteria

- `Forge` delegates rather than implementing all operations;
- circular imports and package-import side effects are absent;
- each application service has a narrow typed constructor;
- storage and execution are injected through protocols;
- public CLI/MCP results remain compatible; and
- the repository layout reflects real dependency boundaries rather than file movement alone.

### Validation

```bash
./scripts/check.sh
python -m pip install .
mncs-forge --config examples/minimal/mncs-forge.toml inspect
```

Add an import-boundary test or static dependency check that prevents domain modules from importing
interface and adapter modules.

---

## Task 6 — Generate CLI and MCP dispatch from one operation registry

**Priority:** P1  
**Target:** `0.1.0b1`  
**Depends on:** Task 5

### Objective

Eliminate independent manual dispatch definitions that can drift between the CLI and MCP server.

### Required operation metadata

Each operation should declare:

- stable operation name;
- allowed mode or modes;
- whether it mutates state;
- input model;
- output model;
- authority or transition requirement;
- disclosure class;
- CLI mapping where applicable; and
- MCP tool registration metadata.

CLI argument presentation may remain hand-tuned, but both interfaces must invoke the same typed
operation handler and permission checks.

### Acceptance criteria

- a generated machine-readable inventory lists every CLI and MCP operation;
- tests fail if a public operation exists in one interface but is unintentionally absent from the
  other;
- evaluator-only operations cannot appear in development MCP inventory;
- mode and mutation metadata are enforced before handler execution;
- documentation tables can be generated or checked from the registry; and
- existing command names and MCP tool names remain compatible.

### Validation

```bash
./scripts/check.sh
pytest -q tests/test_cli.py tests/test_mcp.py tests/test_operation_registry.py
```

---

## Task 7 — Introduce a runner abstraction and sandbox-capable adapters

**Priority:** P2  
**Target:** `0.2.x`  
**Depends on:** Tasks 4 through 6

### Objective

Separate bounded execution policy from the current local subprocess implementation and make
execution properties explicit in evidence records.

### Initial interface

A runner must expose capability inspection and bounded execution. Execution receipts must bind:

- runner type and version;
- host identity, operating system, and architecture;
- executable identity;
- image identity when applicable;
- declared environment identity;
- network policy;
- filesystem and mount policy;
- timeout and output bounds;
- termination behavior;
- request identity; and
- output and diagnostic identities.

### Adapter order

1. extract the current behavior into `LocalProcessRunner` without semantic change;
2. implement a rootless Podman runner with no network and explicit read-only/writable mounts;
3. optionally implement Docker where the same properties can be established; and
4. add an SSH or remote-host runner only after job and receipt identities are stable.

### Acceptance criteria

- provider and workflow services depend on the runner protocol, not `subprocess` directly;
- local behavior remains cross-platform and bounded;
- sandbox claims are derived only from recorded runner capabilities;
- a malicious configured executable is still described as trusted code unless an adapter enforces
  a stronger boundary;
- timeout, output overflow, crash, malformed output, and process-tree cleanup remain explicit; and
- container image tags alone are not accepted as immutable image identities.

### Validation

Run the full suite plus adapter-specific tests. Container tests must skip explicitly when the
runtime is unavailable and must not silently pass as though sandboxing was tested.

---

## Task 8 — Add ledger checkpoints and optional external anchoring

**Priority:** P2  
**Target:** `0.2.x`  
**Depends on:** Task 4

### Objective

Allow local evidence history to be externally anchored or witnessed without conflating those
properties with independence or protected custody.

### Required classifications

The resulting status model must distinguish at least:

- local chain valid;
- checkpoint created;
- externally anchored;
- witnessed;
- protected custody; and
- independently held.

### Required changes

- create periodic checkpoint records containing ledger head, range, algorithm, project identity,
  and material environment identity;
- support detached signatures without making them mandatory for local operation;
- define a receipt format for publishing or witnessing checkpoint heads;
- verify receipts offline;
- preserve multiple receipts from different holders; and
- keep authority classifications explicit and non-transitive.

### Acceptance criteria

- replacing the entire local ledger after a published checkpoint is detectable when the receipt is
  supplied;
- a self-signed checkpoint remains locally controlled rather than independent;
- a second machine controlled by the same operator can establish replication or witnessing only as
  declared, not organizational independence;
- expired, revoked, malformed, or mismatched receipts remain `UNKNOWN` or `FAIL` according to the
  declared verification rule; and
- ordinary Forge operation remains possible without a network service.

---

## Task 9 — Complete the `0.2.0` local-stability gate

**Priority:** P1 after foundational tasks  
**Target:** `0.2.0`  
**Depends on:** Tasks 1 through 7

### Objective

Create a release gate for dependable local operation rather than adding another feature wave.

### Required hardening

- property-based state-machine tests;
- malformed and adversarial Provider Protocol corpus;
- ledger truncation, replacement, reordering, and concurrency corpus;
- subprocess timeout, overflow, crash, and child-process escape tests;
- package wheel install and upgrade tests;
- configuration and record schema compatibility snapshots;
- branch coverage reporting used to find untested policy branches;
- dependency and packaging audit;
- benchmark trend output with non-normative labeling; and
- reviewed local threat model.

### Release criteria

Do not release `0.2.0` while any of the following remain:

- import-order behavior;
- unversioned new persistent records;
- unexplained invalid state transitions;
- non-transactional record/ledger commits;
- interface drift between CLI and MCP;
- execution code coupled directly throughout application services; or
- undocumented migration behavior.

---

## Task 10 — Add safe identity-bound result reuse

**Priority:** P3  
**Target:** after `0.2.0`  
**Depends on:** versioned records, stable runners, and explicit freshness

### Objective

Reduce repeated verifier cost without allowing stale or differently authorized results to be
reused.

### Required cache key material

A reusable result must bind every material identity, including:

- mode;
- candidate and bounded input identities;
- verifier declaration and version;
- provider configuration, executable, and reported identity;
- method;
- policy and contract identities;
- environment and runner identities;
- dependency envelope and completeness;
- disclosure class; and
- applicable freeze identity.

### Acceptance criteria

- any material identity change prevents reuse;
- incomplete dependency information cannot justify reuse across changed candidates;
- evaluator results cannot become development repair feedback;
- cache hits produce explicit reuse records linked to the original result;
- original records remain immutable; and
- cache failure or uncertainty falls back to execution or `UNKNOWN`, never inferred `PASS`.

---

## Task 11 — Design and implement distributed Forge

**Priority:** P3  
**Target:** `0.3.0`  
**Depends on:** stable record, runner, operation, and checkpoint interfaces

### Objective

Coordinate bounded work across heterogeneous machines for cross-platform reproduction,
performance cohorts, scaled RAVEL, and automated MNCS-family testing.

### Architecture constraint

The MCP server remains the agent-facing control plane. Implement a separate coordinator/worker
layer rather than embedding a distributed scheduler inside MCP request handlers.

### Required components

- immutable content-addressed job envelope;
- coordinator state and scheduling policy;
- worker registration and capability declarations;
- runner, provider, toolchain, OS, architecture, and resource constraints;
- leases and heartbeat expiry;
- idempotent execution and retry rules;
- duplicate-result reconciliation;
- artifact transfer with identity verification;
- partial-failure and disconnected-worker recovery;
- cohort plans for faster/slower and heterogeneous hosts; and
- evidence classifications for same-operator reproduction, public reproduction, witnessing,
  protected holdout, and independent evaluation.

### Time and identity rules

- do not rely on synchronized wall clocks for correctness;
- use monotonic local durations plus signed or witnessed receipts where ordering across hosts is
  required;
- bind every result to the exact worker, runner, environment, input, provider, and job identity;
- worker capability drift must invalidate leases or require re-registration; and
- the coordinator must tolerate duplicate delivery without duplicate authoritative state.

### Acceptance criteria

- loss of any one worker does not corrupt coordinator history;
- replaying a job is idempotent and produces linked attempts;
- mismatched artifacts or worker identities are rejected;
- faster and slower cohorts can be compared without treating performance difference as correctness;
- same-operator machines remain explicitly same-operator evidence; and
- distributed execution cannot bypass existing Forge authority, freeze, disclosure, or `UNKNOWN`
rules.

### Recommended first distributed study

Use the committed minimal provider and a non-promotional RAVEL regression workflow across two
machines before attempting a full cluster scheduler. Record capability mismatch, network loss,
retry, duplicate delivery, and environment drift as deliberate test cases.

---

## Agent completion reporting

Every implementation PR should report:

- exact task number and intentionally excluded later tasks;
- public interfaces changed or confirmed unchanged;
- record or configuration migration effects;
- security and claim-boundary effects;
- tests added and commands run;
- benchmark observations with environment and limitations; and
- remaining `UNKNOWN` facts or follow-up work.

A passing local test suite is necessary development evidence. It is not independent verification,
protected custody, MNCS/MNCDS conformance, certification, or promotion.
