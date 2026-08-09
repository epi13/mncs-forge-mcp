# Task 9B package-stability evidence

This is operator-controlled local development evidence. It is not conformance evidence,
independent evaluation, protected custody, witnessing, certification, governance approval,
promotion, or sandbox assurance. Task 9B is an increment of the `0.2.0` stability gate; neither
Task 9 nor `0.2.0` is complete.

## Baseline

The baseline was the current `main` after the merged Task 9A increment. Using the repository
`.venv`, `scripts/check.sh` reported 349 passing tests, successful formatting/lint, strict mypy,
sdist/wheel builds, and a clean diff check. The local stability coverage command reported 4,148
statements, 1,270 branches, 85% total coverage, and 349 passing tests. The 25-iteration benchmark
used the existing machine-readable schema and recorded 54 ledger entries on Linux with Python
3.14.6.

## Artifact verification

`scripts/verify-package.py` now builds both artifacts, audits their contents, creates a fresh
temporary virtual environment for each, installs normally with runtime dependencies, runs
`pip check`, and executes from outside the checkout. It verifies that `mncs_forge.__file__` is
under the temporary environment's `site-packages`; an import from the repository or an unrelated
editable checkout fails the check.

The final local run reported:

- wheel: 46 files, both console entry points, packaged license and runtime schemas/resources;
- sdist: 83 archive members, license, README, build metadata, and required schema resources;
- runtime metadata: `filelock`, `jsonschema`, and `mcp`, with no development-only dependency leak;
- packaging metadata: build requirements remain `setuptools>=75` and `wheel`, the wheel declares
  `Requires-Python: >=3.11`, and the `dev` optional extra remains separate;
- `pip check`: passed for both environments;
- installed wheel minimal workflow: provider probe `PASS`, verifier result `PASS`, ledger valid;
- MCP stdio smoke: initialization, tool inventory, project inspection, provider listing, and
  capability-blocker calls succeeded; and
- copied historical state: 14 entries and 12 identities remained intact, one current record was
  appended transactionally for a valid 15-entry mixed ledger, historical ledger bytes and
  immutable files remained unchanged, and future schema `999` was rejected.

The historical check reads supported state through the current installed wheel. There is no frozen
earlier installable package artifact in this repository, so this is not described as a binary
package-to-package upgrade.

## Reproducibility and benchmark telemetry

Two clean local builds were compared semantically: wheel contents were equal for 46 files and
sdist regular-file contents were equal for 76 files. Archive metadata and timestamps are not
claimed byte-for-byte reproducible by this check.

`scripts/compare-benchmarks.py` validates the existing benchmark schema, rejects normative input,
compares matching mean/p50/p95/p99 and setup metrics, reports ledger-count and environment
differences, and emits deterministic JSON or readable text. It does not enforce a latency
threshold.

The baseline/candidate runs used the same Linux/Python 3.14.6 environment and 54 ledger entries.
Candidate minus baseline mean deltas were approximately: ledger verification +1.0%, state
inspection +1.8%, verifier explanation -0.3%, verifier listing -0.7%, verifier matching -13.5%,
and verifier execution -2.7%. Setup time changed from 18.709 ms to 17.802 ms. These are local
telemetry observations, not correctness or performance assurance.

## CI and compatibility

The existing Linux/macOS/Windows × Python 3.11/3.12/3.13 matrix remains intact. Each job keeps
editable source validation, adds `pip check`, builds the package, runs the installed-artifact
verifier against the built artifacts, and uploads the two-iteration benchmark as non-gating
telemetry.

The final normal suite reported 351 passing tests. Branch coverage remained 85% (4,148 statements,
1,270 branches, 472 missed statements, and 268 partial branches); the added release-engineering
tests cover benchmark comparison rather than applying a global threshold. The compatibility
snapshot check passed unchanged. `git diff --check` passed.

The first manual snapshot invocation used the host `python` and failed because that interpreter did
not have the repository's MCP dependency. Re-running through `.venv` passed; this was an environment
invocation error, not a repository compatibility failure.

## Remaining work

Task 9 still needs the reviewed local threat model and any remaining release-gate holes. Task 7
still defers identity-bound execution receipts, sandbox-capable runners, Podman/Forge Cell
execution, and stronger execution authority. None of those claims are made by the local runner or
this package verification increment.
