# ADR 0017: Typed, fail-closed execution-assurance assessments

## Status

Accepted (implemented in this iteration).

## Context

Forge records execution observations and receipt bindings, but nothing forced
the distinction between "the program produced result X" and "the execution
environment established properties Y" to be machine-checkable. A functional
workflow `PASS` could be presented as if the surrounding execution were
trustworthy. The Forge Cell specification already defined fail-closed assurance
assessment for its document model; Forge needed the equivalent concept bound to
its own receipt bindings.

## Decision

1. Introduce a versioned `execution_assurance` record that binds one receipt
   binding to a caller-declared set of requested properties drawn from a fixed
   vocabulary (`runner_capability`, `filesystem_isolation`, `network_isolation`,
   `containerization`, `same_operator_execution`).
2. Assessment is fail-closed:
   - a requested property that is `not-established` or unobservable leaves the
     assessment `UNKNOWN`;
   - an incomplete execution (timeout, output limit, crash, unavailable
     receipt) cannot confirm any property;
   - isolation claims that contradict the declared runner kind — for example
     containerization established by a `local-process` runner — are `FAIL`
     laundering attempts;
   - out-of-vocabulary requests are rejected as authority errors rather than
     silently interpreted.
3. A functional result never participates in the assessment. Workflow or
   verifier `PASS` cannot imply assurance `PASS`.
4. Assessments are immutable, append-only records. Conflicting assessments of
   the same binding are retained side by side; later assessments never rewrite
   earlier ones.
5. The existing Forge Cell document validation and assurance-assessment
   library is exposed read-only through `cell.documents.validate` and
   `cell.execution.assess` so agents can evaluate inline policy/execution-record
   documents without persistence.

## Consequences

- Result and assurance are separated at the record, service, registry, CLI,
  MCP, and resource levels.
- Adversarial coverage asserts that copied `PASS` results, forged isolation
  claims, stale vocabulary requests, and incomplete executions cannot produce
  assurance `PASS`.
- The assessment remains local provenance. It does not establish independence,
  custody, witnessing, or conformance, and host root stays inside the trusted
  computing base until Cell Tasks 6–8 introduce measured or externally held
  evidence.
