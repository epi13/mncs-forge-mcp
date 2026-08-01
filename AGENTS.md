# MNCS Forge agent guidance

- Use Forge for controlled candidate/evidence workflow when a project has a validated
  `mncs-forge.toml`.
- Forge does not replace MNCS or MNCDS offline validation and is not required for conformance.
- Modify candidate or generated files only within the declared paths. Never write to contracts,
  references, evaluators, policies, or protected authorities through Forge.
- Keep MNCS, MNCDS, evidence-class, and promotion statuses separate. Missing or unsupported
  evidence remains `UNKNOWN`; `FAIL` dominates `UNKNOWN`, which dominates `PASS`.
- Final evaluator-mode results are not repair feedback for the same development epoch.
- Do not claim independence, protected custody, witnessing, governance approval, certification,
  or promotion from a local Forge result.
- Use Forge provider discovery and capability blockers to select an appropriate declared
  structural, control-flow, or data-flow provider when a change requires that evidence.
- Joern is one optional legacy provider, not the standard or default. Source reading,
  grep, and line counts are review aids, not substitutes for unavailable structural
  evidence.
- Missing, unsupported, malformed, stale, or unavailable required capability remains
  `UNKNOWN` or a blocker, never `PASS`.
- When comparative graph-sensitive evidence is claimed, use the same provider, method,
  scope, and relevant bounds before and after the change. Preserve historical Joern
  outputs and frozen baselines.
