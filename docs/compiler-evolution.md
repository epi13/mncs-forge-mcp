# Compiler evolution observations

Forge consumes compiler study artifacts owned by `mncs-language`; it does not define compiler legality or duplicate the language's compiler schema.

The first supported contract is:

```text
mncs:language:compilation-study-result:0.1
```

The language record carries compiler, pipeline, host, target, stage-fingerprint, pass-execution, diagnostic, and unresolved-obligation information. `mncs_forge.compiler_evolution` projects a bounded immutable observation and compares two observations.

## Supported observation questions

The current comparison answers:

- which semantic, HIR, SSA, selected-SSA, target-plan, and backend fingerprints are equal, different, or missing;
- where the earliest observed stage difference appears;
- which exact pass identities changed recorded status; and
- which unresolved obligation identities were retained by each study.

The canonical order now includes source, lexical tokens, CST, AST, semantic graph, identity map, and validation before HIR/SSA. Additional language-owned stage names are preserved and compared after that order.

## Authority boundary

Compiler evolution uses three distinct questions:

| Layer | Question | Owner |
| --- | --- | --- |
| observation | What happened during this compiler study? | compiler producer and Forge comparison |
| assurance | Was a claimed relation valid under identified evidence and policy? | declared verifier and assurance workflow |
| conformance | Does the artifact satisfy an MNCS profile? | language-owned conformance contract and validator |

A compiler pass observation may contain `PASS`, `FAIL`, or `UNKNOWN`. That value remains pass-local. It is not copied into Forge `assurance_status` or `conformance_status`; comparison returns both as `null`.

Forge rejects a study that changes the contract ID or replaces the required `observation_only_not_assurance_or_conformance` interpretation. This prevents a producer from laundering an observation into a stronger claim through the consumer interface.

## Example

```python
from mncs_forge.compiler_evolution import (
    CompilerExperimentObservation,
    compare_compiler_experiments,
)

baseline = CompilerExperimentObservation.from_language_record(baseline_record)
candidate = CompilerExperimentObservation.from_language_record(candidate_record)
comparison = compare_compiler_experiments(baseline, candidate)
print(comparison.to_json())
```

## Persistent experiment operations

Forge persists the exact language record plus its normalized observation as a version-1 `compiler_experiment` record. It does not copy the language schema into Forge or reinterpret pass-local status.

```bash
mncs-forge --config mncs-forge.toml compiler record "$(mncs source-study identity.mncs)"
mncs-forge --config mncs-forge.toml compiler list
mncs-forge --config mncs-forge.toml compiler compare EXPERIMENT_A EXPERIMENT_B
```

The equivalent MCP tools are `mncs_forge_compiler_experiment_record`, `mncs_forge_compiler_experiments_list`, and `mncs_forge_compiler_experiments_compare`. The list projection is also available at `mncs-forge://compiler/experiments`.

Record identity binds the language contract ID, language record identity, compiler/pipeline/run identities, exact language record, and normalized observation. `recorded_at` is excluded so retrying the same experiment is idempotent. The record schema requires `assurance_status` and `conformance_status` to remain `null` and rejects any interpretation other than observation-only.

## Planned control-plane capabilities

The next integration increments should:

1. bind explicit experiment input-set and language-profile identities once the language record exposes them;
2. attach separate verifier results for translation validation and regression gates;
3. add feature/profile compatibility matrices keyed by language-owned feature identities;
4. retain benchmark observations separately from semantic assurance;
5. run distributed studies through Fabric while preserving compiler-host, build-host, target, and run-environment distinctions; and
6. require an explicit conformance operation before any MNCS conformance claim.

Forge may later search pass orderings, optimization candidates, backend realizations, or validation strategies. The language compiler must still derive obligations and authorize or reject each candidate under language-owned contracts.
