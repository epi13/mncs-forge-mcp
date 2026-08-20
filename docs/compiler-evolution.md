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

Additional language-owned stage names are preserved and compared after the canonical stage order.

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

The caller may store the original language record or the projection under an existing Forge workflow result `extensions` object. Extensions remain non-normative: Forge persistence does not convert them into lifecycle authority, independent evidence, or conformance.

## Planned control-plane capabilities

The next integration increments should:

1. register language compilation studies as project-scoped workflow observations;
2. bind compiler experiment inputs, language profile, compiler/pipeline, target, and environment identities;
3. persist language-owned pass records and comparison outputs in extensions without schema duplication;
4. attach separate verifier results for translation validation and regression gates;
5. add feature/profile compatibility matrices keyed by language-owned feature identities;
6. retain benchmark observations separately from semantic assurance;
7. run distributed studies through Fabric while preserving compiler-host, build-host, target, and run-environment distinctions; and
8. require an explicit conformance operation before any MNCS conformance claim.

Forge may later search pass orderings, optimization candidates, backend realizations, or validation strategies. The language compiler must still derive obligations and authorize or reject each candidate under language-owned contracts.
