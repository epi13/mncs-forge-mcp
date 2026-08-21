# Forge Evaluation for Concept Reconstruction Experiments

Status: architecture proposal / non-normative

## Purpose

Concept Reconstruction Experiments (CREs) use independent implementations of a fundamental computing concept to pressure-test MNCS Language and the surrounding MNCS tooling. Forge should remain the bounded evaluation/search layer for these studies, not the owner of language meaning, experiment truth, development selection or MNCS conformance.

## Evaluation boundary

For a CRE, Forge may consume exact references to:

- Concept Experiment identity and frozen manifest;
- MNCS Language profile/compiler identity;
- candidate source/artifact identity;
- semantic/HIR/SSA/backend fingerprints;
- Fabric execution receipts and environment identities;
- declared invariants, falsifiers and protected properties;
- verifier/evaluator identities and budgets.

Forge should emit identity-bearing evaluation records that preserve `PASS`, `FAIL` and `UNKNOWN` independently of the generator.

## No self-certification

A candidate generator or experimenter cannot certify its own candidate merely because it can invoke Forge. The evaluator/verifier identity, policy and frozen inputs must be explicit. Candidate search and candidate acceptance remain separate operations.

Useful CRE evaluation dimensions include:

- algebraic or semantic invariant satisfaction;
- compiler-stage agreement/divergence;
- translation-validation outcome;
- first stage of divergence;
- backend/host agreement;
- protected-property preservation;
- unresolved obligations;
- deliberate mutant rejection;
- cost/resource observations where preregistered.

## Failure classification support

Forge may produce evidence useful for classification such as:

- implementation error;
- compiler/lowering divergence;
- verifier/evaluator gap;
- target-specific disagreement;
- unresolved evidence.

Forge should not unilaterally decide that a failure is a language-design defect or specification defect. Those are cross-record attributions that require comparison with language semantics, experiment design and other evidence.

## Family Record Spine

Forge results should remain Forge-native records referenced by the proposed Family Record Spine. Commons may index and relate them; Control may attach them to the Concept Experiment; MNCDS may later cite them as development evidence; MNCS may cite eligible evidence in an assurance case. None of those references rewrite the original Forge result.

At minimum, a CRE evaluation record should be bindable to:

```text
concept_experiment_id
candidate_identity
language_profile
compiler_identity
verifier_identity
evaluator_policy_identity
input_set_identity
Fabric execution refs[]
result = PASS | FAIL | UNKNOWN
unresolved_obligations[]
```

## Blind reconstruction preference

Where practical, CRE candidate generation should begin without exposing the existing implementation body. Forge may later compare the candidate with the current Rust/Python implementation as an oracle, benchmark or invariant source, but the study should distinguish independent reconstruction from transpilation.

## Bootstrap without RAVEL/MNEL

Temporary Harness/Fabric models may act as `experiment-investigator`, `adaptive-experiment-critic` or `skeptic`. Forge should treat their outputs as untrusted proposals/observations until independently checked. They are not RAVEL or MNEL results.

## First CRE

The recommended first study is the MNCS tri-state result lattice. Exhaustively test `PASS`, `UNKNOWN` and `FAIL` combination behavior and properties including commutativity, associativity, idempotence, PASS neutrality and FAIL dominance. Include deliberate incorrect candidates so the evaluation path demonstrates that it can reject plausible-looking implementations.
