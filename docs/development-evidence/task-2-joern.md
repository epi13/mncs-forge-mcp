# Task 2 Joern development evidence

This is supplemental local development evidence, not MNCS/MNCDS conformance evidence. The frozen
baseline is merged PR #7 commit `dbf8d652c531996b24e632f53698b84b2a58fc30`. Both snapshots used
Joern `4.0.583`, the `PYTHONSRC` frontend, and the same committed query
[`task2-record-flow.sc`](../../scripts/joern/task2-record-flow.sc).

## Commands

The baseline source was exported from `origin/main` to
`/tmp/mncs-forge-task2-origin-main`; it was not read from the changing worktree.

```bash
joern-parse --language PYTHONSRC \
  /tmp/mncs-forge-task2-origin-main/src \
  --output /tmp/mncs-forge-task2-origin-main.cpg

joern --script scripts/joern/task2-record-flow.sc \
  --param cpgFile=/tmp/mncs-forge-task2-origin-main.cpg

joern-parse --language PYTHONSRC src \
  --output /tmp/mncs-forge-task2-post-final2.cpg

joern --script scripts/joern/task2-record-flow.sc \
  --param cpgFile=/tmp/mncs-forge-task2-post-final2.cpg
```

## Focused baseline snapshot

The baseline query reported these graph relationships:

```text
METHOD|append|count=1|files=ledger.py|callees=_read_unlocked,_verify_records
METHOD|records|count=1|files=ledger.py|callees=_read_unlocked,_verify_records,append
METHOD|_read_unlocked|count=1|files=ledger.py|callers=append,records,verify
METHOD|_read_unlocked_raw|count=0
METHOD|_execution_record|count=1|files=engine.py|callees=local_json_identity
METHOD|run|count=2|files=cli.py,micro_verifiers.py|callees=_write_immutable,append,local_json_identity,terminal_unknown_result
METHOD|_execute|count=1|files=micro_verifiers.py|callees=append,local_json_identity
METHOD|new_record|count=0
METHOD|normalize|count=0
METHOD|normalize_ledger_entry|count=0
METHOD|derive_record_identity|count=0
```

Joern found ten immutable-writer call sites: provider probe, epoch, candidate, development result,
disposition, freeze, evaluation, bundle, verifier action, and verifier result.

## Focused post-change snapshot

The repeated query reported:

```text
METHOD|append|count=1|files=mncs_forge/ledger.py|callees=_read_unlocked_raw,_verify_raw_records,normalize_ledger_entry,to_json
METHOD|records|count=1|files=mncs_forge/ledger.py|callees=_read_unlocked_raw,_verify_raw_records,append,normalize_ledger_entry
METHOD|_read_unlocked|count=0
METHOD|_read_unlocked_raw|count=1|files=mncs_forge/ledger.py|callers=append,records,verify
METHOD|_execution_record|count=1|files=mncs_forge/engine.py|callees=new_record
METHOD|run|count=2|files=mncs_forge/cli.py,mncs_forge/micro_verifiers.py|callees=_write_immutable,append,derive_record_identity,local_json_identity,new_record,terminal_unknown_result
METHOD|_execute|count=1|files=mncs_forge/micro_verifiers.py|callees=append,local_json_identity,new_record,to_json
METHOD|new_record|count=1|files=mncs_forge/records.py|callers=_execute,_execution_record,_record_provider_probe,_run_workflow,candidate_disposition,candidate_freeze,candidate_register,epoch_begin,evidence_reconcile,run|callees=derive_record_identity
METHOD|normalize|count=1|files=mncs_forge/records.py|callers=parse_record|callees=derive_record_identity
METHOD|normalize_ledger_entry|count=1|files=mncs_forge/records.py|callers=append,records
METHOD|derive_record_identity|count=1|files=mncs_forge/records.py|callers=new_record,normalize,run|callees=local_json_identity
```

The same ten immutable-writer categories remained present. Their arguments now flow through typed
records; no persistent writer site disappeared. The ledger read path reaches raw verification
before `normalize_ledger_entry`, while the creation paths reach `new_record`. The verifier graph
still has one `run`/`_execute` lifecycle and retains terminal fallback reachability.

## Failures and uncertainty

Initial exploratory queries failed to compile because of Scala string escaping and an incorrect
filename traversal. They produced no evidence and were replaced by the committed query before the
snapshots above were compared.

Joern emitted CFG fallback warnings for Python `try`/`catch`/`finally`, `break`, and `continue`, plus
Java restricted/`Unsafe` API warnings. Python call linking is approximate: dynamic dispatch creates
metaclass-adapter callers, and common names such as `append` are noisy unless scoped to the ledger
method. The query therefore establishes focused call/control relationships only. It does not prove
runtime data values, authority, evidence status, absence of every dictionary flow, or transactional
storage. Tests and direct codec/ledger verification cover those claims.
