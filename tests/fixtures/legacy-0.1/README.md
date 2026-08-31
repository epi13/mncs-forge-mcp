# Immutable pre-Task-2 Forge state

This fixture was generated from merged PR #7 at
`dbf8d652c531996b24e632f53698b84b2a58fc30`, before adding record metadata or
changing any persistent writer. The real Forge lifecycle produced provider probing, an epoch, two
candidates, `FAIL`/`UNKNOWN`/`PASS` workflow results, rejection and selection dispositions, a
verifier action/result pair, freeze, final evaluation, reconciliation output, and bundle output.

`complete-state/ledger.jsonl` and `complete-state/records/` are historical bytes and must not be
regenerated during tests. The reconciliation file is retained separately because reconciliation
was an interface-only derived object in `0.1.0a2`. There was no persistent general workflow-action
record in that version.

`SHA256SUMS` freezes the fixture corpus. Updating a digest is a deliberate compatibility-contract
change, not routine test maintenance.
