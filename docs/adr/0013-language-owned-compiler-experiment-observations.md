# ADR 0013: Consume language-owned compiler experiment observations

- **Status:** Accepted
- **Target:** compiler evolution observation boundary

## Context

Forge must support compiler experiment tracking, pass records, IR comparison, regression localization, verification evidence, and language compatibility studies. Defining those artifacts independently in Forge would create a competing compiler schema and allow pass-local status to drift into Forge authority or conformance semantics.

`mncs-language` now emits `mncs:language:compilation-study-result:0.1`, including stage fingerprints, pass execution observations, diagnostics, and unresolved obligations.

## Decision

Forge will consume the language-owned record through an observation-only projection.

The projection:

- requires the exact language contract ID and observation-only interpretation;
- preserves compiler, pipeline, host, target, stage, pass, and obligation identities;
- compares stage fingerprints in language-defined order;
- reports the earliest observed difference and pass-status changes; and
- returns no assurance or conformance status.

This initial decision did not add a compiler record type. [ADR 0014](0014-persistent-compiler-experiment-records.md) supersedes only that persistence deferral: Forge now has a generic observation envelope that stores the exact language-owned record without redefining its compiler schema.

## Consequences

Positive consequences:

- language and Forge contracts cannot silently diverge;
- IR regression localization is available without claiming correctness;
- pass `UNKNOWN` remains visible;
- separate verifier results can later provide assurance; and
- existing Forge record migration and lifecycle authority remain unchanged.

Costs and limits:

- the consumer is pinned to one language contract ID;
- a new language contract requires an explicit consumer update;
- comparison is structural observation, not semantic equivalence; and
- persistence must continue to enforce this observation-only authority boundary.

## Evidence

Tests cover language-contract acceptance, earliest SSA divergence, pass-status changes, rejection of a competing contract ID, and rejection of observation laundering. Comparative Joern analysis records the new consumer methods without adding calls into lifecycle, persistence, promotion, or conformance paths.
