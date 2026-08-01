# Evidence and identity model

Forge uses `forge-tree-sha256-v1` for a sorted, length-delimited local file inventory and
`forge-json-sha256-v1` for Forge-owned deterministic JSON. These names deliberately do not claim
MNCS RFC 8785 canonical-document identity. Public MNCS commands should produce or verify MNCS
canonical identities.

Every result binds candidate and provider/evaluator identities, method, scope, environment-key
names (never values), duration, `PASS`/`FAIL`/`UNKNOWN`, compact witnesses, limitations,
unsupported constructs, and an output identity. Ledger entries bind sequence, time, kind,
previous hash, payload, and current hash under a file lock.

Reconciliation is workflow aggregation, not copied certification logic. It reports required-gate
effects, conflicts, stale identities, limitations, and blockers using
`FAIL > UNKNOWN > PASS`. MNCS implementation and MNCDS development-process results remain separate
offline-validator outputs.

Micro-verifier actions and results use the same immutable state and ledger. They additionally bind
verifier/configuration/policy/environment identities, exact bounded input identities, provider
response identity, and a provider-declared dependency envelope. Freshness is `CURRENT`, `STALE`,
or `UNKNOWN` lineage metadata and is not a conformance status. No verifier result cache is enabled
in the initial implementation.
