# Forge lifecycle state machine

Forge derives lifecycle state from the typed records in the verified append-only ledger. There is
no mutable current-state file and no persistent lifecycle-summary record:

```text
typed append-only ledger history
  -> deterministic lifecycle projection
  -> current identities and readiness
  -> allowed operations and stable blockers
```

`ForgeStateMachine` is the single transition authority. `Forge` still creates records, invokes
providers, observes filesystem identities, and writes the ledger. CLI and MCP state inspection
both call `Forge.state_inspect`; neither adapter implements lifecycle policy.

The state machine projects the bounded lifecycle event material through the MNCS-owned lifecycle
module when native execution is selected. That projection owns epoch/candidate parentage,
evidence dominance, disposition, freeze/evaluation sequencing, freshness, and the compact stage;
Forge retains persistence, record identity production, authority checks, evidence envelopes, and
bundle semantics. Covered mutations also require a bounded language-owned preflight before
authorization returns. An unavailable runtime uses the explicit compatibility path, while a
selected native adapter that times out, returns malformed data, or disagrees with the expected
transition blocks the operation.

Evidence reconciliation uses the native reconciliation kernel when native mode
is selected. It receives opaque category identities and bounded status slots,
then returns per-category counts/conflict flags and the aggregate technical
status. Forge reconstructs the presentation layer from its own records and
keeps category names, record identities, unsupported-construct disclosure,
persistence, and rights outside the MNCS ABI. The native envelope is bounded
to 16 categories with 8 observations each; oversized or malformed input is a
fail-closed `UNKNOWN` condition, never a truncated compatibility result. The
compatibility classifier is reserved for `off` mode or unavailable runtimes.

## Projected dimensions and stages

The projection keeps these dimensions separate:

- active, superseded, or ambiguous epoch lineage;
- active-epoch candidate lineage and content freshness;
- required candidate-evidence readiness;
- one terminal candidate disposition;
- freeze presence, selection binding, and current identity drift;
- evaluator result presence;
- reconciliation availability as a deterministic, non-persistent derived view;
- bundle result presence; and
- verifier actions with or without a terminal result.

The overall `stage` is a compact classification: `no_epoch`, `epoch_active`,
`candidate_registered`, `evidence_incomplete`, `candidate_ready`, `candidate_selected`,
`candidate_rejected`, `candidate_frozen`, `evaluation_complete`, `bundle_complete`, or
`ambiguous_history`. It does not replace the dimensions above. Historical ambiguity is reported as
a limitation and blocks prospective lifecycle mutation; it does not rewrite or reject readable
legacy records.

## Prospective transition rules

| Transition | Required current state |
| --- | --- |
| begin first epoch | development mode; no parent |
| begin successor epoch | development mode; parent is exactly the active epoch |
| register first candidate | development mode; active epoch; current epoch authority; no parent |
| register successor candidate | same active epoch; parent is exactly the current candidate; new content identity |
| refresh candidate | development mode; an active-epoch candidate exists; no-op when current, otherwise register a successor whose parent is the stale current candidate |
| run project check | development mode; no epoch or candidate required |
| run candidate check/verifier | development mode; current, fresh active-epoch candidate |
| select candidate | development mode; current candidate; no disposition; complete, current, comparable required PASS evidence |
| reject candidate | development mode; current candidate; no disposition |
| freeze candidate | development mode; current selected candidate; current authority and policy; still-ready evidence; valid evidence plan |
| enter evaluator | evaluator mode; current coherent freeze and selection; frozen candidate and authority identities unchanged |
| record verifier terminal result | referenced action exists; action has no result; mode/candidate/freeze bindings match |
| reconcile evidence | unambiguous history; explicit or projected current candidate; project results are not candidate evidence |
| build bundle | current candidate in development mode, or valid evaluator entry in evaluator mode |

The first candidate of a successor epoch does not inherit across epochs. Cross-epoch candidate
ancestry remains fail-closed until a future schema and explicit semantics authorize it. A frozen
epoch requires a successor epoch before more candidate registration.

## Evidence readiness

The selection policy JSON declares required evidence through a non-empty `required_workflows` or
legacy-compatible `required` list. Readiness matches candidate-scoped workflow names and, for
future policy use, verifier IDs. Project-scoped results use a `project:` subject identity and never
satisfy candidate requirements.

For each requirement, inspection reports present record identities, missing evidence, `UNKNOWN`,
`FAIL`, stale evidence, and non-comparable evidence. Status remains `PASS`/`FAIL`/`UNKNOWN`; readiness
is a separate Boolean decision. A set of observed PASS records is not complete unless every
declared requirement is present and current. Workflow evidence compares the recorded and current
allowlisted environment-key envelope. Verifier evidence also compares its bound environment and
policy identities; unavailable bindings remain non-comparable rather than being inferred ready.
Without an explicit evidence-supersession rule, all matching records remain in the envelope and
status dominance is `FAIL > UNKNOWN > PASS`.

## Stable transition errors

Established codes such as `MODE_FORBIDDEN`, `NO_ACTIVE_EPOCH`, `STALE_CANDIDATE`, `STALE_BASELINE`,
`NO_FREEZE`, and `FREEZE_DRIFT` remain in use. More specific Task 3 codes include:

- epoch: `EPOCH_PARENT_REQUIRED`, `EPOCH_PARENT_INVALID`, `EPOCH_SUPERSEDED`,
  `EPOCH_LINEAGE_CONFLICT`, `EPOCH_FROZEN`;
- candidate: `CANDIDATE_PARENT_REQUIRED`, `CANDIDATE_PARENT_INVALID`,
  `CANDIDATE_LINEAGE_CONFLICT`, `CANDIDATE_NOT_CURRENT`;
- evidence: `EVIDENCE_PLAN_INVALID`, `EVIDENCE_INCOMPLETE`, `EVIDENCE_UNKNOWN`,
  `EVIDENCE_FAILED`, `EVIDENCE_STALE`, `EVIDENCE_NOT_COMPARABLE`;
- disposition/freeze: `CANDIDATE_ALREADY_DISPOSED`, `CANDIDATE_REJECTED`,
  `FREEZE_NOT_SELECTED`, `FREEZE_ALREADY_EXISTS`, `FREEZE_AUTHORITY_STALE`,
  `FREEZE_SELECTION_STALE`, `FREEZE_EVIDENCE_PLAN_INVALID`;
- evaluator: `EVALUATOR_CANDIDATE_MISMATCH`, `FREEZE_SUPERSEDED`; and
- verifier terminality: `ACTION_NOT_RECORDED`, `ACTION_ALREADY_TERMINATED`,
  `ACTION_BINDING_MISMATCH`.

Inspection exposes these codes under `blocked_operations`; errors do not depend only on prose.

## Inspection interfaces

Use either interface:

```bash
mncs-forge --config mncs-forge.toml state
```

```text
mncs_forge_state_inspect
mncs-forge://state/lifecycle
```

The JSON-compatible result contains `stage`, `mode`, `epoch`, `candidate`, `evidence`,
`disposition`, `freeze`, `evaluation`, `reconciliation`, `bundle`, `allowed_operations`,
`blocked_operations`, and `limitations`. Reconciliation is computed on request and is not a
persistent event, so inspection reports its derivability but never claims that an invocation is in
history. `project_inspect` embeds the same projection under `lifecycle`.

## Storage boundary

Authorization and projection are deterministic, but record-file and ledger writes are still two
non-transactional operations. A process interruption can therefore expose the Task 4 recovery
seam. Task 3 does not add journals, prepared/committed states, indexes, checkpoints, or crash
recovery. Terminal-result authorization prevents a second verifier result prospectively; Task 4
must make action/result and record/ledger storage atomic and recoverable.
