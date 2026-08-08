# Task 3 validation evidence

This is operator-controlled development evidence. It does not establish MNCS or MNCDS
conformance, independence, protected custody, witnessing, governance approval, certification, or
promotion.

## Baseline

Task 3 branched from merged `origin/main` commit `3071d2f` (PR #8). The package version remained
`0.1.0a2`, as transactional storage is still an `0.1.0a3` release gate. The clean baseline passed
`./scripts/check.sh` with 172 tests and built both distributions.

The 25-iteration baseline micro-verifier benchmark reported a 46.856061 ms mean and 55.534688 ms
p95 for `verifier_run`.

## Final validation

The prescribed final commands completed successfully:

```text
./scripts/check.sh                                      210 passed; sdist/wheel built
pytest -q tests/test_state_machine.py                   38 passed
pytest -q tests/test_engine.py                          34 passed
pytest -q tests/test_micro_verifiers.py
          tests/test_verifier_hardening.py              55 passed
pytest -q tests/test_records.py tests/test_compatibility.py
          tests/test_ledger.py                          51 passed
pytest -q tests/test_cli_mcp_edgestream.py              4 passed
git diff --check                                       passed
```

The immutable `tests/fixtures/legacy-0.1/` ledger remained readable, hash-valid, identity-stable,
and byte-unchanged under the compatibility and state-machine tests.

## Benchmark comparison

Both runs used the same script, 25 iterations, the local example provider, and a 54-entry ledger.

| Metric | Baseline mean / p95 (ms) | Final mean / p95 (ms) |
| --- | ---: | ---: |
| verifier run | 46.856061 / 55.534688 | 43.673071 / 49.582502 |
| ledger verify | 2.491339 / not retained | 2.638958 / 3.153517 |
| verifier explain | 8.055640 / not retained | 8.025528 / 8.649902 |
| verifier list | 0.003323 / not retained | 0.003321 / 0.005854 |
| verifier match | 0.149009 / not retained | 0.145408 / 0.160897 |

The verifier-run mean was about 6.8% lower than baseline; small differences in the other local
metrics are treated as noise. The benchmark is non-normative and does not establish correctness or
assurance.

## Supplemental graph analysis

Joern `4.0.583` completed the same bounded source/call/control query before and after the change.
The final graph found each lifecycle facade and verifier entry path calling the transition service,
with only provider probing retaining a facade-local mode guard. Python frontend CFG fallback and
dynamic-call limitations remain documented in [Task 3 Joern development evidence](task-3-joern.md);
graph results are supplemental and do not prove absence of every bypass.

## Deferred storage boundary

Authorization still precedes separate immutable-file and ledger writes. No transaction journal,
prepared/committed state, recovery protocol, checkpoint, or concurrency recovery was added. Those
remain Task 4.
