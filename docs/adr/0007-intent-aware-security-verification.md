# ADR 0007: Intent-aware security verification for non-orthodox code

- **Status:** Proposed
- **Target:** `0.3.x`
- **Related:** [MNCS standards proposal PR #57](https://github.com/epi13/machine-native-complexity-standard/pull/57)

## Context

Forge is intended to support machine-native development, including implementations that are useful,
compiler-aware, and less orthodox than ordinary human-oriented source patterns. Generic security
scanners often use convention as a proxy for safety. That is useful for triage, but it creates two
opposite failure modes:

1. unusual code is rejected or rewritten merely because it resembles a risky pattern; and
2. conventional-looking code is accepted even though it violates a real safety invariant.

Forge already provides bounded micro-verifiers, explicit `PASS`/`FAIL`/`UNKNOWN` results, provider
identity, candidate lineage, freshness, and development/evaluator separation. It does not yet define
how a suspicious construct can carry declared intent and stronger evidence without becoming a broad
warning suppression or syntax whitelist.

Security hardening also cannot depend only on a demonstrated exploit chain. A confirmed local or
trust-boundary weakness remains relevant when current reachability is absent or unknown because later
composition, deployment, privilege, or dependency changes can make the weakness exploitable.

The architecture therefore needs to distinguish:

- a confirmed invariant violation;
- a suspicious pattern that requests more evidence;
- declared intentional deviation from an ordinary implementation convention;
- present attack-path reachability and composability; and
- project disposition and repair priority.

These are related facts, but they are not one status.

## Decision

Forge will define intent-aware security verification as a development and evaluation architecture
layered over the existing micro-verifier evidence system.

The governing rules are:

1. **Orthodoxy is a heuristic; invariants are authoritative.**
2. **Suspicion routes work; it does not establish failure.**
3. **Declared intent cannot waive a failed safety property.**
4. **Current exploitability affects priority and composition, not whether a confirmed weakness
   exists.**
5. **Exceptions are bound to semantics, identities, assumptions, and evidence, never to syntax
   alone.**
6. **Forge preserves verifier `PASS`/`FAIL`/`UNKNOWN`; it does not add a fourth verification
   status.**

### Three verification layers

Forge will organize security-oriented verifier capabilities into three composable layers:

- **Local invariants** — memory, arithmetic, lifetime, bounds, resource, parsing, and explicit
  language/compiler semantics.
- **Trust-boundary invariants** — authorization, privilege transitions, secret flow, filesystem,
  process, network, FFI, and validation boundaries.
- **Composition** — reachability, cross-component assumptions, deployment context, attack paths,
  and chains of individually bounded findings.

A composition result may change urgency or disposition, but it cannot convert a local `FAIL` into
`PASS`. Absence of a known chain is not evidence that the local weakness is absent.

### Intentional-deviation records

Forge will introduce a versioned, identity-bound `intentional_deviation` development record. It
will describe at least:

- deviation ID and version;
- candidate and source-region identities;
- construct or technique class;
- intended purpose and expected benefit;
- conventional rule or heuristic being departed from;
- required invariants and verifier IDs;
- compiler, language, target, ABI, optimization, and environment assumptions;
- allowed scope and prohibited uses;
- known failure modes and unsupported constructs;
- required evidence identities;
- dependency and revalidation envelope;
- authoring and approval authority; and
- lifecycle state.

A corresponding `deviation_evaluation` record will bind the declaration to the actual verifier
results, freshness state, policy identity, compiler/output identities where applicable, and a
workflow disposition such as:

- `accepted_with_constraints`;
- `experimental`;
- `rejected`;
- `review_required`; or
- `stale`.

These dispositions are workflow metadata, not MNCS/MNCDS conformance and not verification statuses.
A declaration with missing, unsupported, stale, contradictory, or unavailable required evidence
remains unresolved and cannot be treated as accepted.

### Evidence-backed routing

When a suspicious construct is detected, Forge will deterministically:

1. record the suspicion and its bounded witness;
2. resolve any matching intentional-deviation declaration;
3. match the declaration's required verifier capabilities;
4. execute only explicitly requested and authorized verifiers;
5. preserve each verifier result independently;
6. evaluate declaration completeness and freshness;
7. derive a non-normative workflow disposition; and
8. either permit bounded continuation, require repair, retain `UNKNOWN`, or escalate.

Forge will not infer intent from a comment, automatically invent an exception, or accept a caller
request to ignore a verifier result. An agent may propose a declaration during development, but the
record must pass configured project policy and may require separate approval authority.

### Compiler-aware deviations

For constructs whose safety or benefit depends on compilation, the evidence envelope must bind the
relevant identities, including as applicable:

- compiler and version;
- target triple and ABI;
- optimization and code-generation flags;
- language mode and feature set;
- source, AST, IR, optimized IR, object, or binary identity;
- undefined-behavior and sanitizer results;
- reference-semantics comparison; and
- benchmark or resource evidence.

Intentional reliance on behavior undefined by the declared language/compiler model is not converted
into safety by documenting intent. Such a construct remains rejected or `UNKNOWN` unless the project
controls a lower-level semantic layer that explicitly defines and verifies the operation.

### No broad suppression

Forge will not implement declarations equivalent to:

- "allow computed goto";
- "ignore integer overflow";
- "disable path traversal warning"; or
- "trust this file."

A declaration must instead bind a narrow semantic claim, such as a closed immutable dispatch table,
a verified index bound, a target-specific compiler contract, and the exact artifact/dependency
identities to which the evidence applies.

### Repair and recursive learning

A confirmed weakness should enter an evidence-backed repair loop:

1. preserve the original finding and witness;
2. propose the smallest structural repair or constrained deviation;
3. modify only authorized candidate/generated paths;
4. rerun the failed verifier;
5. run adjacent verifiers selected by declared dependency and threat envelopes;
6. compare behavior, performance, compiler output, and compatibility where material;
7. preserve before/after identities and results; and
8. prevent stale results from justifying the new candidate.

Recursive systems may learn from accepted deviations only as complete evidence-backed patterns. They
must not learn merely that a syntax form was previously accepted. Promotion into reusable project or
network knowledge remains outside Forge's local authority and must preserve MNCS/MNCDS governance,
independence, and evidence boundaries.

## Consequences

Positive consequences:

- Forge can harden code without normalizing every unusual implementation into conventional form;
- agents receive precise evidence about why a construct is safe, unsafe, constrained, or unknown;
- real invariant violations remain actionable even before a coherent exploit chain is known;
- compiler-oriented techniques can be evaluated against the actual declared toolchain and output;
- broad scanner suppressions are replaced with inspectable, fresh, bounded evidence; and
- recurring weaknesses can inform safer APIs, verifier families, and generation constraints.

Costs and risks:

- intentional-deviation records add schema, policy, lifecycle, and approval complexity;
- declarations can become self-justifying if authoring and approval authority are not separated;
- threat models and dependency envelopes may be incomplete;
- compiler and deployment identities increase invalidation frequency and evidence volume;
- composition analysis can be expensive and may remain `UNKNOWN`;
- a low-quality verifier can falsely legitimize a dangerous technique unless provider identity,
  limitations, and adversarial fixtures are preserved; and
- accepted deviations may be copied outside their verified envelope.

## Required evidence before acceptance

- versioned schemas and typed models for `intentional_deviation` and `deviation_evaluation`;
- transactional record-plus-ledger writes and compatibility snapshots;
- deterministic matching from suspicion and declaration to required verifier capabilities;
- tests proving a declaration cannot suppress or overwrite a verifier `FAIL`;
- tests proving missing, stale, unsupported, contradictory, or unavailable evidence remains
  unresolved;
- freshness invalidation for candidate, source region, dependency, verifier, provider, policy,
  compiler, target, environment, and deployment identities;
- policy tests for declaration authoring, approval, evaluator disclosure, and protected paths;
- valid and invalid fixtures for at least one local, one trust-boundary, and one compiler-aware
  deviation;
- adversarial fixtures for broad whitelists, forged evidence links, declaration drift, incomplete
  dependency envelopes, and copied declarations applied outside their scope;
- a bounded composition pilot showing that chain reachability changes disposition without changing
  underlying verifier results;
- documentation that distinguishes verification status, freshness, workflow disposition, severity,
  and MNCS/MNCDS conformance; and
- no claim of certification, global correctness, independence, protected custody, or governance
  approval from a local Forge result.
