# Development-Pressure Workflow

Status: experimental Forge integration design.

Forge is the bounded execution and comparison layer for MNCDS development pressure. It consumes pressure/capability-gap records, evaluates candidate resolutions against a declared plan, and publishes evidence and unresolved gaps. It does not own the MNCS standard or turn execution into acceptance.

The intended family path is:

`developer -> Forge workflow -> RAVEL adapter -> Fabric public service/controller -> worker`

Forge uses public contracts and exact target identities; it must not reach into private Fabric internals or hidden SSH paths.

## Workflow

1. **Ingest**: validate pressure identity, revision, reproducer, protected properties, and scope.
2. **Localize**: identify the language/compiler/library/runtime/backend/process boundary; preserve UNKNOWN when incomplete.
3. **Propose**: register independently identified candidates.
4. **Freeze**: bind candidate, corpus, evaluator plan, dependency snapshot, and revisions.
5. **Evaluate**: run bounded reference, backend, negative, and compatibility checks.
6. **Compare**: evaluate candidates against the same protected properties.
7. **Publish**: emit identity-bound evidence and, when configured, a Commons record.
8. **Promote or continue**: record selection, rejection, or unresolved work at an explicit authority level.

Suggested surfaces: `forge pressure inspect`, `reproduce`, `propose`, `evaluate`, `compare`, and `publish`. A future `pressure detect` may consume compiler artifacts, but must not scrape human-readable error text.

## Identity, status, and failure

Every run binds pressure/proposal identities, exact repository revisions, compiler/Forge/Fabric/evaluator versions, corpus and input digests, backend/worker identities, policy revisions, and final result/evidence identity. A moved or unfrozen tree is not evidence for the frozen candidate.

Forge preserves the tri-state aggregation `FAIL > UNKNOWN > PASS) for the declared check set. Missing evaluators, unsupported surfaces, stale capability observations, disagreements, and unverifiable artifacts remain UNKNOWN or FAIL according to the obligation; they are never silently PASS.

Negative paths are first-class: malformed pressure, missing reproducer, identity mismatch, post-freeze mutation, unavailable provider, evaluator disagreement, incomplete backend coverage, rejection, and invalidation. A candidate may be selected for an experimental scope while other surfaces remain UNKNOWN. Local checks alone never auto-promote or auto-merge.

## Change sets and publication

Cross-repository work is represented by a ChangeSet. Forge must hold or reject a workflow when participants, contract snapshots, or the assembled final-tree identity are missing. Published evidence identifies workflow, candidate, final tree, checks, raw observations, derived claims, limitations, and unresolved fields. When writing Commons, Forge is an adapter and publisher; it does not rewrite raw receipts.

The first implementation target is a fixture-backed workflow and validator contract.
