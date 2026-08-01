# ADR 0002: Versioned persistent record schemas

- **Status:** Proposed
- **Target:** `0.1.0a3`

## Context

Forge treats epochs, candidates, actions, results, freezes, evaluations, and bundles as immutable
evidence records, but much of the internal lifecycle passes unversioned dictionaries. The current
representation is workable for an experiment but provides no explicit migration boundary as the
record model evolves.

A persistent record can outlive the Python implementation that created it. Future Forge versions
must be able to identify, validate, migrate, reject, and reproduce record identities without
silently changing authority or status semantics.

## Decision

Every newly persisted record will include:

- a stable `record_type`;
- a stable `schema_version`;
- the fields required by that record type; and
- an identity derived from its canonical persisted representation where an identity is applicable.

Forge will use frozen typed models internally and JSON-compatible objects only at storage,
Provider Protocol, CLI, and MCP boundaries. A deterministic migration registry will normalize
supported historical records when they are read. Historical files will not be rewritten in place.

Unsupported future versions will fail closed with a specific error and will not be interpreted as
current evidence.

## Consequences

Positive consequences:

- persistent evidence gains an explicit compatibility contract;
- migrations and schema snapshots can be tested;
- identities can be reproduced across versions; and
- internal type checking can replace broad dictionary assumptions.

Costs and risks:

- migration code becomes a permanent maintenance responsibility;
- careless defaults could accidentally broaden authority; and
- identity calculations must use the persisted representation consistently.

## Required evidence before acceptance

- existing committed `0.1` fixtures remain readable;
- unsupported future versions fail closed;
- serialize/parse/serialize round trips preserve canonical identities;
- public schema snapshots cover each record type; and
- migrations never silently convert missing or unknown evidence into `PASS`.
