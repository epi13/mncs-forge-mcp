# Evidence and identity model

Forge uses `forge-tree-sha256-v1` for a sorted, length-delimited local file inventory and
`forge-json-sha256-v1` for Forge-owned deterministic JSON. These names deliberately do not claim
MNCS RFC 8785 canonical-document identity. Public MNCS commands should produce or verify MNCS
canonical identities.

Every result binds candidate and provider/evaluator identities, method, scope, environment-key
names (never values), duration, `PASS`/`FAIL`/`UNKNOWN`, compact witnesses, limitations,
unsupported constructs, and an output identity. Ledger entries bind sequence, time, kind,
previous hash, payload, and current hash under a file lock.

New persistent records use schema version `"1"` and include their stable record type. Current
record-derived identities include that metadata through an explicit type-specific projection.
Candidate identity remains a project-content identity rather than a record hash. Legacy
unversioned identities retain their historical projections. Raw legacy ledger linkage is verified
before normalization; migration never redefines the old chain. See
[Versioned Forge records](record-schemas.md).

Reconciliation is workflow aggregation, not copied certification logic. It reports required-gate
effects, conflicts, stale identities, limitations, and blockers using
`FAIL > UNKNOWN > PASS`. MNCS implementation and MNCDS development-process results remain separate
offline-validator outputs.

Micro-verifier actions and results use the same immutable state and ledger. They additionally bind
verifier/configuration/policy/environment identities, exact bounded input identities, provider
response identity, and a provider-declared dependency envelope. Freshness is `CURRENT`, `STALE`,
or `UNKNOWN` lineage metadata and is not a conformance status. No verifier result cache is enabled
in the initial implementation.

## Execution observations and MNCS adapter readiness

`LocalProcessRunner.observe()` exposes raw, bounded observations without adding a Forge receipt
record. Complete runs report command/environment identities, lifecycle and termination facts,
bounded stream counts and SHA-256 values, aggregate output, wall duration, and the runner's actual
capabilities. Timeout, start-failure, and output-limit observations retain only what was observed;
unknown totals or complete hashes remain unknown rather than being inferred.

`mncs_forge.mncs_execution_receipt` adapts a complete observation plus caller-supplied subject,
bundle, policy, challenge, and optional placement identities to MNCS's experimental
`mncs-execution-receipt` / `0.1-experimental` envelope. It uses the pinned MNCS schema at commit
`6d6380016e174feaaa774c1cf0931095d24b5280` (schema SHA-256
`f2e1860405052a40b100bead7c27dbe0cc3ac11d03dccca3fcb643b350ecab6e`). The adapter fails closed
when required context or complete stream totals are absent. It does not persist, authorize,
interpret, or promote the receipt; all MNCS claim-boundary fields remain `not-asserted`.
