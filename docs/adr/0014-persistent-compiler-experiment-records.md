# ADR 0014: Persist language-owned compiler experiments

- **Status:** Accepted
- **Target:** compiler evolution control plane

## Context

ADR 0013 established a pure observation consumer but deferred durable experiment tracking. Keeping studies only in caller-owned extensions prevents reliable listing, comparison, ledger verification, and cross-version regression workflows. Copying the MNCS language compiler schema into Forge would create a competing contract and risk turning compiler-local status into Forge authority.

## Decision

Forge adds a version-1 `compiler_experiment` record and three canonical operations: record, list, and compare.

The record is a generic observation envelope. It stores the exact `mncs:language:compilation-study-result:0.1` object and its validated normalized projection. Its identity binds the language contract and record identities, compiler/pipeline/run identities, compilation status, exact language record, normalized observation, and fixed observation-only authority fields. Wall-clock `recorded_at` is excluded to make identical retries idempotent.

Recording is development-only and mutating. Listing and comparison are read-only projections over local storage. Neither operation participates in lifecycle selection, promotion, assurance, verifier result, or conformance transitions. Both `assurance_status` and `conformance_status` are required to be `null`.

## Consequences

Positive consequences:

- studies are immutable, ledger-linked, idempotent, inspectable, and comparable;
- CLI, MCP, and resource exposure share one typed operation definition;
- earliest-stage divergence includes the Profile 0.1 frontend stages; and
- Forge consumes the language contract without owning compiler legality.

Costs and limits:

- the consumer remains pinned to one language contract version;
- the exact embedded language record is intentionally duplicated with its projection for auditability;
- local persistence supplies integrity evidence, not independent custody; and
- regression, assurance, and conformance decisions still require separate contracts and operations.

## Evidence

Schema, parser, identity, service, operation-registry, CLI/MCP inventory, ledger, idempotence, comparison, and laundering tests cover the boundary. Comparative Joern analysis checks that persistence reaches only the record store and that comparison remains separate from lifecycle, verifier, disposition, freeze, evaluation, and promotion paths.
