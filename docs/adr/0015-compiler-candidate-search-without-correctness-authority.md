# ADR 0015: Compiler candidate search without correctness authority

- Status: accepted
- Date: 2026-08-21

## Context

Forge already persists language-owned compiler-study observations. The next compiler-research need is bounded search over pass/rewrite/backend candidates. Search must not become the authority that decides language correctness.

## Decision

Introduce a `compiler_candidate` record and shared CLI/MCP operations for register/list/compare/attach-validation/tournament/select/inspect.

Candidates must identify baseline and candidate artifacts, generator identity, declared transformation, claimed relation, expected benefit, protected properties, target envelope, and required validation. They remain isolated from the trusted baseline. Generator certification is forbidden. Semantic status is `UNVALIDATED`, `PASS`, `FAIL`, or `UNKNOWN`. Policy may `accept`, `reject`, or `retain_unresolved`.

A FAIL candidate loses even if a benchmark says it is faster. UNKNOWN cannot be selected when the protected property requires validation.

## Consequences

Forge can conduct compiler-search experiments. Language-owned translation validators and compiler obligations remain the legality path. Assurance and conformance fields stay null on search records.
