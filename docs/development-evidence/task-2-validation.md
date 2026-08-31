# Task 2 validation record

This is operator-controlled development evidence. It does not establish MNCS/MNCDS conformance,
independence, protected custody, witnessing, certification, or governance approval.

## Baseline

The baseline was merged PR #7 (`dbf8d652c531996b24e632f53698b84b2a58fc30`) with package version
`0.1.0a2`.

```text
PATH="$PWD/.venv/bin:$PATH" ./scripts/check.sh
124 passed

PATH="$PWD/.venv/bin:$PATH" python scripts/benchmark-micro-verifiers.py --iterations 25
verifier_run mean:     41.150486 ms
ledger_verify mean:     2.526645 ms
verifier_explain mean:  3.422112 ms
```

## Final

```text
PATH="$PWD/.venv/bin:$PATH" ./scripts/check.sh
172 passed; formatting, Ruff, mypy, sdist, and wheel checks passed

PATH="$PWD/.venv/bin:$PATH" pytest -q \
  tests/test_ledger.py tests/test_records.py tests/test_compatibility.py
51 passed

PATH="$PWD/.venv/bin:$PATH" pytest -q \
  tests/test_micro_verifiers.py tests/test_verifier_hardening.py
55 passed

PATH="$PWD/.venv/bin:$PATH" python scripts/benchmark-micro-verifiers.py --iterations 25
verifier_run mean:     45.865936 ms
ledger_verify mean:     2.540037 ms
verifier_explain mean:  7.547031 ms

git diff --check
passed
```

Verifier-run mean increased by about 11.5%. Ledger verification was effectively unchanged at
about +0.5%. Explain increased by about 4.1 ms (roughly 2.2x) because a lookup now performs strict
typed parsing and reproduces current record-derived identities rather than returning unchecked
dictionaries. Investigation also found avoidable normalization of unrelated ledger kinds and an
extra raw JSON-tree copy. Removing those costs reduced an intermediate verifier-run mean from
53.64 ms to 45.87 ms and explain from 10.76 ms to 7.55 ms while retaining raw-chain verification
before normalization. Further indexing or a record store is intentionally deferred to the
transactional storage iteration.
