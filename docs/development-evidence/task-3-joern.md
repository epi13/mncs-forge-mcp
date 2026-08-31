# Task 3 Joern development evidence

This is supplemental local development evidence, not MNCS/MNCDS conformance, certification,
independence, or protected custody. Both snapshots used Joern `4.0.583`, the `PYTHONSRC` frontend,
and the same committed bounded query
[`task3-lifecycle-flow.sc`](../../scripts/joern/task3-lifecycle-flow.sc).

## Commands

The baseline was exported from merged `origin/main` commit `3071d2f` into a temporary directory so
it could not observe changing worktree source.

```bash
task3_base_dir=$(mktemp -d /tmp/mncs-forge-task3-baseline.XXXXXX)
git archive origin/main | tar -x -C "$task3_base_dir"
joern-parse --language PYTHONSRC \
  "$task3_base_dir/src" \
  --output /tmp/mncs-forge-task3-baseline.cpg
joern --script scripts/joern/task3-lifecycle-flow.sc \
  --param cpgFile=/tmp/mncs-forge-task3-baseline.cpg

joern-parse --language PYTHONSRC src \
  --output /tmp/mncs-forge-task3-post-final3.cpg
joern --script scripts/joern/task3-lifecycle-flow.sc \
  --param cpgFile=/tmp/mncs-forge-task3-post-final3.cpg
```

## Baseline findings

The focused call/control query found lifecycle authorization in the facade and verifier service:

```text
epoch_begin -> _require_mode, _record_by_id
candidate_register -> _require_mode, _latest_payload, _record_by_id
candidate_disposition -> _require_mode, _record_by_id
candidate_freeze -> _require_mode, _candidate, _records
final_evaluation_run -> _require_mode, _latest_payload, _record_by_id, _verify_freeze
verifier run -> _candidate, _latest_payload, _record_by_id, _verify_freeze,
                terminal_unknown_result
```

There were seven `_require_mode` call sites in `engine.py`. No `authorize_*` transition method
existed. Direct lifecycle reads occurred in epoch, candidate, disposition, freeze, evaluator, and
verifier methods. Joern reported meaningful branching in each path, including 15 `IF` structures
in verifier `_execute` and competing authorization branches in the facade.

## Post-change findings

The repeated query found all lifecycle-mutating facade and verifier entry paths reaching the new
transition service:

```text
epoch_begin -> authorize_epoch_begin
candidate_register -> authorize_candidate_register
development_checks_run -> authorize_development_work
candidate_compare -> authorize_candidate_comparison
candidate_disposition -> authorize_candidate_disposition
candidate_freeze -> authorize_candidate_freeze
final_evaluation_run and _verify_freeze -> authorize_evaluator_entry
evidence_reconcile -> authorize_reconciliation
bundle_build -> authorize_bundle
verifier run -> authorize_development_work or authorize_evaluator_entry,
                then authorize_terminal_result_for_recorded_action
```

The graph found one implementation of each focused `authorize_*` method in
`state_machine.py`. Mode-guard calls for lifecycle operations moved there; the one remaining facade
mode guard is provider probing, which is not a lifecycle transition. Remaining direct workflow
result reads support comparison/reconciliation presentation. Remaining verifier-result reads
support supersession metadata, iterative-overlap labeling, and explanation; terminal append
authorization flows through `authorize_terminal_result_for_recorded_action`. Inspection calls the
same pure authorizers when deriving allowed and blocked operations instead of re-implementing their
rules.

The post graph also shows record writes remaining in `Forge` and `MicroVerifierService`, not moving
into the state machine. This is the intended Task 4 seam rather than a transactional-storage
implementation.

## Failures, frontend gaps, and uncertainty

Both parses completed. Joern emitted Python CFG order-fallback warnings for `try`/`finally`,
`catch`, `break`, and `continue`, plus Java restricted/`Unsafe` API warnings. Python dynamic call
linking produced metaclass-adapter callers and can omit a callee from a method summary even when
the explicit call-site query finds it; for example, the transition-call listing found
`authorize_candidate_comparison`, `authorize_development_work`, `authorize_reconciliation`, and
`authorize_bundle` even where the watched-callee summary did not list them.

The query establishes bounded call/control relationships only. It does not prove runtime record
values, evidence completeness, absence of every authorization bypass, atomic storage, crash
recovery, or concurrency safety. Table-driven tests, legacy-chain verification, strict typing,
and the full repository checks cover those separate development claims. Task 4 storage behavior
remains unimplemented and therefore not established by this evidence.
