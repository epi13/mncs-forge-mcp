# Task 9A local-stability development evidence

This document records bounded local development evidence for the Task 9A stability-harness
increment. It is not independent assurance, external witnessing, protected custody, certification,
or a completion claim for Task 7 or the `0.2.0` release gate.

## Scope

The harness attacks the real Forge lifecycle projection, Provider Protocol 0.1 parsing and probe
boundary, and raw hash-linked ledger chain. Existing Task 7A local-runner and Task 4 recovery
coverage were audited rather than duplicated. The local runner continues to establish no sandbox,
network isolation, filesystem isolation, independence, or external authority.

## Reproducible commands

```bash
./scripts/check.sh
bash scripts/coverage-local-stability.sh
python scripts/benchmark-micro-verifiers.py --iterations 25
git diff --check
```

The coverage command uses development-only `hypothesis` and `pytest-cov` dependencies, branch
measurement, and a terminal report. It does not impose an arbitrary global threshold.

## Harness design

- Hypothesis generates bounded status sequences and lifecycle operation orderings. Properties
  inspect the implementation's durable history and projection; tests do not implement a second
  lifecycle state machine.
- Provider Protocol fixtures cover framing, UTF-8, multiple/blank lines, JSON shape, protocol
  metadata, status primitives, capabilities, cancellation/health flags, extension arrays, and
  bounded arbitrary JSON. Provider identity completeness remains an application probe concern.
- Ledger mutations cover truncation, missing/reordered entries, duplicate sequence, and broken
  previous-hash links. Existing companion substitution, rehashing, transaction, recovery, index,
  and concurrency tests remain authoritative for those classes.
- The property corpus found and retained a parser regression for unhashable analysis statuses;
  malformed status values now produce stable `PROVIDER_MALFORMED` errors.

## Baseline and interpretation

The pre-harness baseline on the repository-local Python 3.14.6 Linux environment was 307 passing
tests and 85% branch coverage (1,270 branches; 281 partial branches). The final run has 349
passing tests and 85% branch coverage (1,270 branches; 268 partial branches), with missed
statements reduced from 490 to 472. Coverage is used to find policy branches, not as a release
claim.

The 25-iteration benchmark means changed as follows: ledger verification 22.47 ms to 24.38 ms,
state inspection 10.06 ms to 10.88 ms, verifier explanation 6.00 ms to 6.86 ms, verifier listing
0.00323 ms to 0.00317 ms, verifier matching 0.153 ms to 0.166 ms, and verifier execution 57.86 ms
to 62.46 ms. These are small single-host development-telemetry variations after adding test-only
and parser-boundary code; they are not normative performance evidence.

Remaining stability work includes package install/upgrade coverage, dependency and packaging
audit, benchmark trend capture, and a reviewed local threat model. Task 7 execution receipts,
Podman isolation policy, Forge Cell execution, and external evidence authority remain deferred.
