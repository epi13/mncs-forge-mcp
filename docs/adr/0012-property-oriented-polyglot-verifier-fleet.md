# ADR 0012: Property-oriented polyglot verifier fleet

- **Status:** Proposed
- **Target:** `0.2.x`

## Context

Forge already supports machine-native micro-verifiers as narrow, capability-declared Provider
Protocol methods with bounded inputs, explicit `PASS`/`FAIL`/`UNKNOWN`, immutable evidence records,
and deterministic matching. The architecture deliberately keeps analyzer-specific algorithms out of
Forge and preserves the independent MNCS/MNCDS validators as separate authorities.

The next design question is how Forge should expand verification depth without converging on one
large verifier implementation or requiring every verifier to use the same programming language.
Different verification problems have materially different computational shapes. Structural and
identity checks favor small systems implementations; semantic transformation and state-machine
reasoning benefit from algebraic representations and pure transformations; path and authority
questions may favor graph engines; arithmetic or symbolic constraints may favor SMT; and critical
mathematical claims may justify an interactive theorem prover.

Haskell is specifically interesting for bounded semantic equivalence, state-transition invariants,
effect-surface comparison, capability-flow reasoning, and refinement-constrained properties. Its
use should be driven by those problem characteristics rather than by a desire to replace the Rust
validator or standardize the implementation language of the verifier fleet.

## Decision

Forge will treat micro-verification as a **property-oriented, polyglot verifier fleet**.

The stable authority boundary is the verifier declaration and Forge evidence contract, not the
backend language or analyzer brand.

A verifier backend may use Rust, Haskell, SMT, a theorem prover, a graph engine, symbolic execution,
runtime instrumentation, or another fit-for-purpose mechanism provided that it:

- is declared through the existing provider/verifier authority model;
- accepts only bounded Forge-authorized inputs;
- binds its provider, verifier, configuration, policy, environment, and material identities;
- returns `PASS`, `FAIL`, or `UNKNOWN` with explicit assumptions, limitations, and witnesses;
- does not infer stronger authority from implementation technology;
- preserves development/evaluator separation; and
- fails closed when the claim is outside its supported proof domain.

The independent Rust MNCS validator remains independent. No existing validator is to be rewritten
merely to create language uniformity.

### Preferred verifier-family fit

Initial guidance is:

| Property family | Candidate implementation fit |
| --- | --- |
| schema, identity, record, format | Rust / existing validator |
| bounded semantic equivalence | Haskell / SMT / symbolic / prover |
| state-machine invariants | Haskell / model checker / SMT / typed Rust |
| capability and authority flow | Haskell / graph engine / Datalog / SMT / Joern |
| effect-surface preservation | Haskell / compiler IR analysis / SMT |
| resource/value refinements | refinement types / SMT / abstract interpretation |
| information flow | graph/taint analysis / Haskell / SMT / specialized analyzer |
| critical theorem | theorem prover |
| empirical runtime behavior | bounded runner / sanitizer / experiment |

This table is guidance, not a restriction. Experiments should determine whether a technology earns
its place.

### Haskell pilot

The first Haskell experiments should focus on narrow problems that materially benefit from pure,
algebraic representations:

1. bounded semantic equivalence over a normalized representation;
2. state-transition invariant checking;
3. capability/authority graph invariants; and
4. effect-surface comparison.

Liquid Haskell or a comparable refinement approach may be evaluated later for small resource or
value invariants where ordinary static typing is too weak and a full theorem prover is excessive.

A Haskell provider receives no special Forge authority. It is invoked and recorded exactly like any
other declared micro-verifier.

### Diverse verification

Forge may intentionally run independently implemented verifiers against the same critical property.
Conflicting results are preserved as evidence rather than averaged into a consensus.

A required, soundly bound `FAIL` remains a blocker. `UNKNOWN` remains unresolved and can trigger
escalation. Multiple `PASS` results improve evidence diversity but do not automatically become a
stronger normative claim.

### Fabric boundary

The existing Forge/Fabric execution boundary remains intact.

Fabric may place verifier jobs according to worker capabilities such as installed runtimes,
architecture, memory, containment, solver availability, or execution cost. Fabric reports placement
and execution facts. It does not decide the semantic meaning of a verification result.

Forge chooses the verifier declaration and property, records the evidence and identities, evaluates
freshness and policy impact, and decides whether escalation is required.

## Consequences

Positive consequences:

- verifier technology can be optimized for the property rather than standardized prematurely;
- Haskell can be used where semantic structure is valuable without destabilizing Rust components;
- Forge retains one machine-readable evidence model across heterogeneous tools;
- critical properties can gain implementation diversity and independent failure modes;
- unsupported claims remain explicit `UNKNOWN` rather than being forced through an unsuitable
  verifier; and
- Fabric can route specialized verifier jobs without becoming a second verification authority.

Costs and risks:

- the fleet may accumulate runtimes and toolchain dependencies;
- method strength can be confused with implementation language unless metadata stays explicit;
- two verifiers can disagree because they model different semantics or assumptions;
- evidence composition can become unsound if independent narrow `PASS` results are treated as a
  transitive whole-program proof; and
- distributed placement can be mistaken for independent evaluation if custody and operator identity
  are collapsed.

These risks are addressed by bounded declarations, explicit assumptions/limitations, identity
binding, `UNKNOWN`, existing evidence semantics, and the Forge/Fabric authority boundary.

## Initial experiments before acceptance

This ADR should move to **Accepted** only after representative pilots demonstrate that the design
fits the existing verifier system without introducing a parallel evidence path.

Required experimental evidence should include:

- one Haskell-backed semantic or state-invariant verifier invoked through the Provider Protocol;
- explicit unsupported cases returning `UNKNOWN`;
- differential or adversarial tests against an independent implementation or reference model;
- preserved Forge verifier action/result identities and freshness behavior;
- no change to normative Rust validator authority;
- one documented Fabric placement scenario or adapter test showing that placement facts remain
  distinct from semantic verifier status; and
- a disagreement test in which two verifier methods can produce independently retained evidence.

See [Property-oriented verifier fleet](../verifier-fleet.md) for the detailed direction.
