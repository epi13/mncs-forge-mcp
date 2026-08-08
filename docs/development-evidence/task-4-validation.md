# Task 4 validation evidence

This is operator-controlled development telemetry, not conformance, independent custody,
witnessing, certification, governance approval, or promotion evidence.

## Baseline

Baseline revision: merged Task 3 `main` at
`d6c772ab2469586db012566234a0c904d4842e64`.

- `PATH="$PWD/.venv/bin:$PATH" ./scripts/check.sh`: 210 tests passed; sdist and wheel built.
- `python scripts/benchmark-micro-verifiers.py --iterations 25`: 54 ledger entries;
  verifier run mean 43.648 ms (p95 51.384 ms), ledger verify mean 2.440 ms (p95 2.486
  ms), verifier explain mean 7.674 ms (p95 8.052 ms), setup 15.232 ms.

## Transaction fault model and tests

`tests/test_record_store.py` and `tests/test_recovery.py` exercise normal commit, identical and
conflicting duplicate identities, thread and spawned-process writers, explicit child-process exit,
immutable deletion/replacement, malformed journals, stage substitution, wrong ledger predecessor,
stale/corrupt indexes, and stranded verifier actions.

The deterministic failpoint matrix covers:

| Failpoint | Recovery result |
| --- | --- |
| before prepare | complete previous state |
| after record staging | complete previous state |
| after ledger staging | complete previous state |
| after durable `PREPARED` | complete new state |
| after record publication | complete new state |
| before ledger publication | complete new state |
| after ledger publication | complete new state |
| before `COMMITTED` | complete new state |
| after `COMMITTED` | complete new state |
| during index update | complete new state |

Every case reopens storage, verifies immutable/ledger correspondence, and runs recovery a second
time as a no-op. The subprocess test exits with `os._exit(77)` after durable preparation and uses
explicit process completion rather than timing sleeps.

## Joern before/after review

Joern `4.0.583` was available. Both snapshots used the same bounded query:

```bash
joern-parse --language PYTHONSRC <source> --output <task4-cpg>
joern --script scripts/joern/task4-storage-flow.sc --param cpgFile=<task4-cpg>
```

Baseline findings: provider probe, epoch, candidate, workflow result, disposition, freeze,
evaluation, bundle, and verifier `run` paths called both `_write_immutable` and `append`;
`_write_immutable` existed in `engine.py`, and no `commit`, `recover`, or stranded-action recovery
method existed.

Post-edit findings: `_write_immutable` count is zero. Each persisted application writer reports a
`commit` callee, verifier `run` reports `commit`, and `_recover_stranded_verifier_actions` reaches
terminal authorization, `recovered_terminal_unknown_result`, and `commit`. A source search reports
no `ledger.append(...)` in `src/`.

Joern's Python name-only call listing also reports unrelated list/dictionary `.append` operations as
`append` and shows those as callees of some methods. Those are false positives for the storage
question; no stronger receiver-sensitive data-flow result was established. The frontend emitted
CFG order-fallback warnings for Python `try`, `catch`, `continue`, and `break`, so graph evidence
beyond the bounded call-name comparison remains `UNKNOWN`.

## Final benchmark

The final 25-iteration benchmark retained 54 ledger entries and added `state_inspect` telemetry:

| Operation | Mean | p95 | Baseline comparison |
| --- | ---: | ---: | --- |
| verifier run | 51.844 ms | 63.594 ms | +18.8% mean |
| ledger verify | 20.912 ms | 22.040 ms | +757% mean |
| state inspect | 9.540 ms | 9.870 ms | new metric |
| verifier explain | 5.725 ms | 5.980 ms | -25.4% mean |

The ledger-verification increase is expected and material: Task 4 verification now opens, parses,
and compares every immutable companion rather than checking only the JSONL hash chain. That raw
integrity and companion validation was not removed for benchmark appearance. Ordinary repeated
reads reuse typed parsing only while the SHA-256 digest of the complete ledger bytes is unchanged;
the persistent index is validated/rebuildable and never authoritative. Whole-ledger staging also
adds bounded write cost at the current small ledger size. No indexing database or Task 5 service
decomposition was introduced.

## Platform boundary

The suite's core transaction/recovery tests have no Windows skip and run in the repository's
Windows CI matrix. This local run establishes Linux behavior. File contents are synced before
closed-handle `os.replace`; containing directories are synced where exposed. Python/Windows may
not expose equivalent directory `fsync`, so identical physical power-loss durability is not
claimed even though the logical journal recovery protocol is cross-platform.

## Final validation

- `PATH="$PWD/.venv/bin:$PATH" ./scripts/check.sh`: formatting, lint, mypy, 237 tests, sdist,
  and wheel passed.
- Required ledger/store/recovery, state-machine/engine, verifier/hardening,
  records/compatibility, and CLI/MCP/benchmark focused suites passed.
- `tests/test_record_store.py tests/test_recovery.py` passed five consecutive repeated runs.
- The 25-iteration benchmark completed with the measurements above.
- `git diff --check` passed.
