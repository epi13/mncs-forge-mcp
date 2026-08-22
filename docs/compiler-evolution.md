# Compiler evolution observations

Forge consumes compiler study artifacts owned by `mncs-language`; it does not define compiler legality or duplicate the language's compiler schema.

The supported contracts are:

```text
mncs:language:compilation-study-result:0.1
mncs:language:experiment-result:0.1
```

The compilation-study record carries compiler, pipeline, host, target, stage-fingerprint,
pass-execution, diagnostic, and unresolved-obligation information. The experiment result wraps that
study with the exact language experiment definition, realization request, backend capability
manifest, target plan, typed backend artifact, translation-validation results, and bounded execution
observations. `mncs_forge.compiler_evolution` accepts either contract, projects a bounded immutable
observation, and compares two observations without copying the language schema.

## Supported observation questions

The current comparison answers:

- which semantic, HIR, SSA, selected-SSA, target-plan, and backend fingerprints are equal, different, or missing;
- whether the realization request, backend identity, and backend artifact identity are equal,
  different, or absent, while retaining artifact kind and language validator judgements;
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

Forge rejects a study that changes the contract ID or replaces the required interpretation. The
older study must remain `observation_only_not_assurance_or_conformance`; the experiment result must
remain `bounded_language_observation_not_universal_equivalence_or_conformance`. The nested compiler
study is independently checked. This prevents a producer from laundering an observation into a
stronger claim through the consumer interface.

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

Forge persists the exact language record plus its normalized observation as a version-1
`compiler_experiment` record. It does not copy the language schema, reinterpret pass-local or
experiment status, or treat a translation-validator `PASS` as Forge assurance.

```bash
mncs-forge --config mncs-forge.toml compiler record "$(mncs source-study identity.mncs)"
mncs-forge --config mncs-forge.toml compiler list
mncs-forge --config mncs-forge.toml compiler compare EXPERIMENT_A EXPERIMENT_B
```

The equivalent MCP tools are `mncs_forge_compiler_experiment_record`, `mncs_forge_compiler_experiments_list`, and `mncs_forge_compiler_experiments_compare`. The list projection is also available at `mncs-forge://compiler/experiments`.

Record identity binds the language contract ID, language record identity, compiler/pipeline/run
identities, exact language record, and normalized observation. For new experiment results the
projection also retains realization/backend/artifact identities and validator judgements.
`recorded_at` is excluded so retrying the same experiment is idempotent. The record schema requires
`assurance_status` and `conformance_status` to remain `null`.

## Compiler candidate search

Forge can now persist isolated compiler-search candidates without becoming the language authority.

```text
baseline artifact
   → generator/search identity
   → isolated candidate artifact
   → language/compiler obligations
   → independent validator PASS / FAIL / UNKNOWN
   → explicit policy
   → accept / reject / retain unresolved
```

Operations:

```bash
mncs-forge compiler candidate-register ...
mncs-forge compiler candidate-list
mncs-forge compiler candidate-compare LEFT RIGHT
mncs-forge compiler candidate-attach CANDIDATE VALIDATOR JUDGEMENT RELATION
mncs-forge compiler tournament CANDIDATE...
mncs-forge compiler candidate-select CANDIDATE --policy explicit-protected-property-policy
mncs-forge compiler candidate-inspect CANDIDATE
```

A generator cannot certify its own candidate. Benchmark observations are stored separately and cannot authorize a FAIL or required-UNKNOWN candidate. Target envelopes remain explicit; a Linux-only candidate is not globally valid.

## Planned control-plane capabilities

The next integration increments should:

1. expose the already language-bound source/profile/corpus identities as dedicated query dimensions;
2. attach language-owned translation-validation records as first-class freshness-bound evidence rather than projected judgements;
3. add feature/profile compatibility matrices keyed by language-owned feature identities;
4. run distributed studies through Fabric while preserving compiler-host, build-host, target, and run-environment distinctions; and
5. require an explicit conformance operation before any MNCS conformance claim.
