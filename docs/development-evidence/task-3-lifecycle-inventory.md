# Task 3 pre-refactor lifecycle inventory

This inventory describes merged `main` at `3071d2f` before Task 3 source edits. It is local
development evidence, not conformance, certification, independence, or protected custody.

| Operation | Current guard location | Mode | Predecessor / records consulted | Freshness or authority | Records produced | Existing errors |
| --- | --- | --- | --- | --- | --- | --- |
| begin epoch | `Forge.epoch_begin` | development | optional parent merely exists | current authority is captured, not compared to prior epoch | epoch | `MODE_FORBIDDEN`, `RECORD_NOT_FOUND` |
| register candidate | `Forge.candidate_register` | development | latest epoch exists; optional parent merely exists | authority equals epoch; optional expected content identity | candidate | `NO_ACTIVE_EPOCH`, `STALE_BASELINE`, `STALE_CANDIDATE` |
| development check | `Forge.development_checks_run` and `_candidate` | development | candidate subject requires latest/named candidate; project subject requires none | candidate content current; project results use `project:` identity | workflow result | `MODE_FORBIDDEN`, `NO_CANDIDATE`, `STALE_CANDIDATE`, `WORKFLOW_SUBJECT` |
| verifier run | `MicroVerifierService.run` | declared verifier modes | development uses `_candidate`; evaluator independently loads latest freeze | candidate current; evaluator independently invokes `_verify_freeze` | verifier action + one intended terminal result | `VERIFIER_MODE`, `NO_FREEZE`, `STALE_CANDIDATE`, drift/provider codes |
| compare | `Forge.candidate_compare` | unchecked | named candidates merely exist | no candidate freshness or evidence-envelope comparability gate | derived response | `COMPARE_INPUT`, `RECORD_NOT_FOUND` |
| select/reject | `Forge.candidate_disposition` | development | candidate merely exists; all candidate workflow results are aggregated | no required-workflow completeness, current-candidate, lineage, policy-envelope, verifier-freshness, or prior-disposition check | disposition | `MODE_FORBIDDEN`, `INVALID_DISPOSITION`, `SELECTION_BLOCKED` |
| freeze | `Forge.candidate_freeze` | development | `_candidate`; any historical selected disposition for candidate | content current; evidence and current terminal disposition not revalidated; plan path exists | freeze | `MODE_FORBIDDEN`, `STALE_CANDIDATE`, `FREEZE_BLOCKED`, path errors |
| final evaluation | `Forge.final_evaluation_run` | evaluator | latest freeze; referenced candidate exists | `_verify_freeze` before/after; candidate and authority checked during each workflow | final evaluation result(s) | `MODE_FORBIDDEN`, `NO_FREEZE`, `FREEZE_DRIFT`, `EVALUATION_DRIFT` |
| reconcile | `Forge.evidence_reconcile` | unchecked | workflow results, optionally candidate-filtered | no lifecycle or freshness gate; project results included when unfiltered | derived reconciliation | none lifecycle-specific |
| bundle | `Forge.bundle_build` | workflow mode only | `_candidate`; declared bundle category | candidate content current; no freeze/evaluation/disposition coherence | bundle | candidate/workflow/category errors |
| terminal verifier result | `MicroVerifierService.run` | inherited from action | action was just appended in the same call | result fields copy action candidate/freeze; no explicit history uniqueness gate | verifier result | immutable-file `RECORD_EXISTS` incidentally detects identical output only |

## Confirmed policy hazards

- A candidate can be selected and later rejected, or rejected and later selected.
- Repeated selection/rejection creates competing terminal dispositions.
- Freeze searches for any historical selection instead of deriving the current disposition.
- A successor epoch need not identify the current epoch as parent; old epochs can be used as
  arbitrary parents.
- Candidate parent existence is checked without same-active-epoch lineage compatibility.
- Selection treats all records that happened to exist as the evidence envelope and therefore can
  accept one PASS while a policy-required workflow is absent.
- Project-scoped PASS records are excluded only when a candidate ID is explicitly supplied; an
  unfiltered reconciliation includes them.
- Evaluator workflows repeat freeze checks but do not establish that the freeze still belongs to a
  coherent, currently selected candidate history.
- Verifier result uniqueness is an incidental storage outcome rather than a transition rule.
- CLI and MCP both reach `Forge`, but state resources use `project_inspect`'s latest-record view and
  no common lifecycle projection exists.

The refactor uses this inventory to define the lifecycle model; it does not preserve the unsafe
authorization behavior above.
