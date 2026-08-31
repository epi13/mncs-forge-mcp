# ADR 0018: Learned micro-models for bounded context filtering and evidence triage

- **Status:** Accepted
- **Date:** 2026-08-25

## Context

Forge accumulates increasingly rich development evidence: candidate lineage, verifier results, execution receipts, assurance observations, mutations, failures, compiler experiments, provider health, coverage, historical regressions, and other machine-readable records.

That evidence is valuable, but presenting large portions of it to a general-purpose model for every decision creates a scaling failure. As Forge succeeds, the available evidence grows and context selection becomes more expensive. General models should not be used as the default mechanism for repetitive classification, retrieval, ranking, or routing work when a deterministic mechanism or a very small bounded learned provider can perform the task reliably.

MNEL already provides an evidence-governed model for learned micro-providers. Forge should consume the same family concept for its own internal evidence routing while preserving Forge's authority boundaries.

## Decision

Forge will adopt **smallest-sufficient-mechanism** context handling:

1. deterministic rules and indexes first;
2. narrow learned micro-models when deterministic mechanisms are insufficient;
3. specialist or general models only when the lower-cost mechanism abstains or the task is outside its measured operating envelope;
4. deterministic Forge verifiers and policy remain authoritative for declared checks and lifecycle decisions.

Learned micro-models are **non-authoritative proposal components**. They may rank, select, classify, compress, or recommend. They may not grant permissions, establish trust, issue conformance, create protected custody, override evaluator boundaries, promote candidates, or convert diagnostic evidence into a verdict.

A micro-model and a Forge micro-verifier are deliberately distinct:

- a **micro-model** is learned, bounded, and advisory;
- a **micro-verifier** evaluates a declared property under its own explicit contract and may contribute authoritative evidence within that contract.

## Initial Forge micro-model roles

The first useful roles include:

- change-family classification;
- evidence relevance ranking and retrieval;
- verifier selection and ordering;
- test prioritization;
- failure-signature classification;
- mutation selection;
- disagreement and anomaly triage;
- evidence-gap detection;
- bounded result compression into identity-preserving context packets; and
- escalation prediction when a case lies outside known operating envelopes.

Implementations need not all be neural language models. A role may be implemented by a tiny transformer, embedding ranker, tree ensemble, HMM, classifier, or another small learned mechanism when evidence supports that choice.

## Context firewall

Forge will treat these mechanisms as a **context firewall** between the full evidence corpus and expensive reasoning models.

A context packet produced by a micro-model must:

- retain stable identities for every selected source record;
- preserve enough lineage to reproduce the selection;
- record the selector/provider identity and version;
- record confidence, calibration state, and abstention when applicable;
- distinguish retrieved evidence from generated summaries;
- never delete or mutate source evidence; and
- remain inspectable without requiring the micro-model to be trusted as an evaluator.

Lossy summaries may be used for convenience only when the underlying evidence identities remain addressable. A summary is not a substitute for evidence.

## Abstention and operating envelopes

Every learned Forge micro-model must have a declared operating envelope and an explicit abstention path.

Outside that envelope, low confidence, unsupported input families, stale calibration, unhealthy provider state, conflicting evidence, or detected novelty must produce an escalation or `UNKNOWN`-equivalent routing outcome rather than a forced guess.

The design objective is not universal accuracy. It is high precision inside a bounded domain plus reliable escalation outside it.

## Deployment lifecycle

Learned Forge components should progress through:

1. trace collection from existing deterministic and model-assisted workflows;
2. MNEL-compatible training or calibration from eligible verified traces;
3. offline evaluation;
4. Forge shadow deployment with no routing authority;
5. adversarial and mutation-oriented evaluation;
6. bounded live use only for the measured operating envelope; and
7. retirement or rollback when calibration, health, or environment assumptions no longer hold.

No learned provider becomes authoritative merely because it performs well. Promotion into a routing role is separate from evaluator authority.

## Family boundaries

- **MNEL** may train, calibrate, compare, and propose learned micro-providers from eligible evidence.
- **Forge** measures their operating envelopes, performs adversarial evaluation, records their behavior, and may consume them for bounded evidence routing.
- **Harness / Control** may use similar specialists for model and tool routing but retain their own permission and orchestration authority.
- **Fabric** may execute identity-addressed resident providers and report factual capability/residency observations without choosing semantic routes.
- **MNCS Language** may eventually supply typed contracts or constrained structured-generation surfaces where appropriate.

Forge must not silently absorb the authority of those sibling systems.

## Required measurements

At minimum, Forge micro-model experiments should measure where applicable:

- relevant-evidence recall at a bounded context budget;
- false-omission rate for evidence later shown to matter;
- verifier-selection precision and recall;
- abstention and escalation correctness;
- schema/contract validity for structured outputs;
- false-accept or unsafe-routing rate;
- token/context bytes avoided;
- larger-model calls avoided;
- latency and resource cost;
- disagreement with deterministic baselines or stronger reference models; and
- calibration drift over time.

Token reduction alone is never sufficient evidence for deployment.

## Consequences

Forge gains a path to scale evidence volume without requiring model context to grow at the same rate. Mature workloads can become cheaper and more deterministic while novel or ambiguous work still escalates to stronger reasoning systems.

The tradeoff is additional provider lifecycle, calibration, trace, and evaluation machinery. Forge must therefore make learned routing observable and reversible rather than treating it as an invisible optimization.
