# Learned micro-model direction for Forge

Forge is moving toward a development architecture in which the amount of evidence available to the system may grow substantially without requiring general-purpose model context to grow at the same rate.

The guiding rule is simple:

> Use the smallest sufficient mechanism, preserve evidence identities, and escalate uncertainty instead of guessing.

This direction complements Forge's existing micro-verifier and query-driven micro-debugging work. It does not replace deterministic verification. Learned micro-models sit upstream of authoritative checks and help decide **what deserves attention**.

## Why Forge needs this

A mature Forge installation can accumulate candidate histories, compiler observations, execution receipts, mutation results, provider health, assurance records, coverage, failures, regressions, and other evidence. Sending all potentially related material to a large reasoning model is both costly and increasingly unreliable as the corpus grows.

The intended architecture makes evidence growth improve specialization rather than cause permanent context growth.

```text
candidate / experiment / change
            |
            v
 deterministic inventory and indexes
            |
            v
 bounded learned specialists
   |        |        |        |
   |        |        |        +--> anomaly / escalation triage
   |        |        +-----------> verifier / mutation selection
   |        +--------------------> evidence retrieval and ranking
   +-----------------------------> change / failure classification
            |
            v
 identity-preserving context packet
            |
        +---+-------------------------+
        |                             |
   inside measured              novel / uncertain /
   operating envelope           conflicting / stale
        |                             |
        v                             v
 bounded continuation          stronger specialist or
                               general reasoning model
        |                             |
        +-------------+---------------+
                      v
           deterministic Forge checks
                      |
                      v
             append-only evidence
```

The large model becomes an escalation mechanism for ambiguity and synthesis rather than the default processor for every stored observation.

## Candidate specialist portfolio

Forge should investigate a portfolio of narrow providers rather than a single small general model.

### Evidence relevance ranker

Given an exact candidate, change inventory, and evidence index, select the smallest high-recall set of historical records likely to matter. Output record identities and scores rather than free-form conclusions.

### Change-family classifier

Classify a bounded change into declared families such as parser/compiler, runtime, ABI/schema, security boundary, documentation, execution substrate, verifier implementation, or unknown. This can drive later routing but cannot authorize it.

### Verifier selector

Rank declared verifier capabilities for expected information value against the candidate and current evidence gaps. Selection remains constrained to the canonical Forge capability registry.

### Failure-signature classifier

Identify known regression families, environment/infrastructure failures, nondeterministic symptoms, cascading failures, or novel signatures. Novelty and low confidence escalate.

### Test prioritizer

Order a bounded set of already permitted tests or probes to maximize useful evidence under a declared budget. It does not redefine the required test set for a formal gate.

### Mutation selector

Choose among registered mutation operators or perturbations based on candidate structure, prior failures, and uncovered assumptions. The provider cannot invent privileged execution actions.

### Disagreement and anomaly triage

Detect unusual divergence among otherwise valid observations, including measurement shifts that a simple PASS/FAIL aggregate would hide.

### Evidence-gap detector

Predict which questions remain unanswered before a stronger reasoning system receives the case. This role should preferentially produce explicit missing-evidence identities or capability classes.

### Result compressor

Construct a compact, identity-preserving machine-readable view of many low-level observations. Generated compression must be distinguishable from source evidence and must never become the evidence itself.

### Escalation predictor

Detect when the current case lies outside all supported operating envelopes and route directly to stronger reasoning rather than wasting several low-confidence stages.

## Relationship to micro-verifiers

Forge must keep these concepts separate.

A learned micro-model may say:

- "these records are probably relevant";
- "these verifiers are likely to be informative";
- "this failure resembles a known family";
- "this case appears novel; escalate."

A verifier may say, under a declared property contract:

- `PASS`;
- `FAIL`; or
- `UNKNOWN`.

The learned component helps Forge spend attention. It does not inherit verifier authority.

## Relationship to MNEL

MNEL is the natural source of the learned-provider lifecycle. Forge should produce the traces and adversarial evidence that make those providers measurable, while MNEL can train, calibrate, compare, and distill candidate specialists.

A long-term family loop is:

```text
verified Forge traces
        |
        v
MNEL training / calibration
        |
        v
candidate micro-provider
        |
        v
Forge offline + shadow evaluation
        |
        v
mutation / adversarial envelope testing
        |
        +---- insufficient ----> retrain / retire
        |
        v
bounded deployment
        |
        v
new measured evidence
        |
        +----------------------> MNEL
```

The same model that proposes a selection does not become the authority that validates that selection.

## Context budget as a first-class measurement

Forge should begin recording context cost alongside execution and verification cost.

Useful measurements include:

- raw candidate evidence available;
- evidence records selected;
- source bytes selected;
- estimated or actual model input tokens;
- context reduction ratio;
- relevant-evidence recall;
- important evidence omitted;
- number and class of escalations;
- larger-model calls avoided;
- latency and compute used by the micro-provider; and
- downstream verifier outcomes.

A provider that saves 95% of tokens while omitting the one record that predicts a regression is not successful. Context reduction is subordinate to evidence preservation and bounded correctness.

## Phased implementation

### Phase 0 — instrumentation

Record context budgets, evidence-selection traces, model-assisted routing decisions, downstream verifier outcomes, and stable identities. Build datasets before introducing learned authority into the path.

### Phase 1 — shadow specialists

Run the first evidence ranker, change classifier, and verifier selector in shadow mode. Their outputs are recorded but do not change the existing path. Compare them with deterministic baselines and stronger reference decisions.

### Phase 2 — bounded context packets

Allow providers that demonstrate acceptable recall and abstention behavior to construct context packets for development-mode reasoning. Preserve a one-command or one-operation path to inspect the omitted source evidence.

### Phase 3 — adaptive specialist portfolio

Use multiple heterogeneous providers with separate operating envelopes. Route by declared capability, health, calibration freshness, cost, and evidence rather than by a single model hierarchy.

### Phase 4 — verified learning loop

Feed eligible traces into MNEL, evaluate proposed replacements or refinements in Forge, and use measured improvements to reduce future context and model calls. Promotion remains explicit and reversible.

## Non-goals

This direction does **not** mean:

- replacing deterministic Forge verifiers with probabilistic verdicts;
- trusting summaries without source identities;
- allowing learned providers to grant permissions or bypass policy;
- making Fabric a semantic router;
- automatically promoting MNEL outputs into production;
- requiring every Forge deployment to use neural models; or
- optimizing token count at the expense of evidence quality.

## Expected outcome

If this direction works, Forge should become more efficient as its evidence base grows. Repeated development patterns will migrate toward tiny, fast specialists, while rare and genuinely difficult cases continue to receive larger-model reasoning.

The goal is not merely lower token use. It is to make **context selection itself an evidence-governed machine-native capability**.
