# Task 4 pre-refactor storage and crash inventory

This inventory describes merged `main` at `d6c772a` before Task 4 source edits. It is local
development evidence, not conformance, external custody, witnessing, certification, or promotion.

All application writers use this non-transactional sequence:

```text
construct typed record -> create immutable file with O_EXCL -> fsync file -> separately lock ledger
-> reread and verify chain -> append and fsync one JSONL line
```

The immutable publication holds no ledger lock. A crash after file fsync leaves record-only state;
a ledger failure leaves the same orphan. Concurrent writers serialize only the ledger calculation,
not the preceding immutable publication. Directory entries are not synced.

| Ledger kind | Immutable group | Identity field | Current writer | Locks/order | Principal failure state |
| --- | --- | --- | --- | --- | --- |
| `provider_probe` | `provider-probes` | `output_identity` | `Forge._record_provider_probe` | record `O_EXCL`, then `ledger.lock` | probe file without ledger event |
| `epoch` | `epochs` | `epoch_id` | `Forge.epoch_begin` | record `O_EXCL`, then `ledger.lock` | authorized epoch not projected after restart |
| `candidate` | `candidates` | `candidate_id` | `Forge.candidate_register` | record `O_EXCL`, then `ledger.lock` | candidate file orphan; same content identity may then collide |
| `result` | `results` | `output_identity` | `Forge.development_checks_run` | one split pair per workflow | partial batch and result-only evidence |
| `verifier_action` | `verifier-actions` | `action_id` | `MicroVerifierService.run` | split pair before provider execution | action file orphan or durable action stranded before result |
| `verifier_result` | `verifier-results` | `output_identity` | `MicroVerifierService.run` | split pair after terminal authorization | terminal file without ledger result; later recovery may collide |
| `disposition` | `dispositions` | `disposition_id` | `Forge.candidate_disposition` | record `O_EXCL`, then `ledger.lock` | terminal disposition file not visible to state machine |
| `freeze` | `freezes` | `freeze_id` | `Forge.candidate_freeze` | record `O_EXCL`, then `ledger.lock` | freeze file exists but evaluator sees no freeze event |
| `evaluation` | `evaluations` | `output_identity` | `Forge.final_evaluation_run` | one split pair per workflow | partial evaluator batch or evaluation-only file |
| `bundle` | `bundles` | `output_identity` | `Forge.bundle_build` | record `O_EXCL`, then `ledger.lock` | bundle file without ledger relationship |

`workflow_action` is constructed for execution/request identity but is not persisted.
`reconciliation` remains a deterministic derived interface record. Task 4 must not invent storage
events for either merely for symmetry.

## Failure points and current behavior

| Point | Current durable state after process death |
| --- | --- |
| before immutable create | previous state |
| during immutable write | exclusive path may contain truncated JSON |
| after immutable file fsync | record only; ledger head unchanged |
| before ledger lock/acquisition | record only |
| after ledger verification | record only if append fails |
| during ledger append | potentially truncated last JSONL line |
| after ledger file fsync | new state logically present, but containing-directory durability is not established |

Current startup has no journal scan or recovery authority. `Ledger.verify` authenticates the raw
hash chain but does not compare ledger payloads with immutable record companions. An orphan action
is visible to state inspection but receives no restart-generated terminal `UNKNOWN`.

## Required Task 4 boundary

The state machine must continue to authorize first. A local `RecordStore` must then own one
exclusive storage lock, staging, expected-head binding, publication, recovery, immutable/ledger
cross-verification, and rebuildable index maintenance. Transaction IDs and index offsets remain
local storage metadata and must not enter evidence identities.
