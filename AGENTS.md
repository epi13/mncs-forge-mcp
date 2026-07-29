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
- For graph-sensitive source changes, use real Joern analysis before and after the edit and
  report graph findings and limitations.
