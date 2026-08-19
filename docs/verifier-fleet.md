# Property-oriented verifier fleet

Forge should evolve its existing micro-verifier system as a property-oriented, polyglot verifier
fleet. The goal is not to select one implementation language for verification. The goal is to
select the verification mechanism that best matches the property being checked, while preserving
one bounded Forge evidence contract.

This direction intentionally keeps the independent Rust MNCS validator separate. Normative
validation, structural checks, and portable offline conformance remain distinct from Forge's
iterative development and evaluator evidence. A Haskell, SMT, theorem-prover, graph-analysis, or
runtime verifier is an additional narrow evidence provider, not a replacement validator.

## Design principle

> Choose a verifier implementation according to the property being proven, not according to the
> implementation language of the artifact being verified.

A verifier may be implemented in Rust, Haskell, another functional language, an SMT-backed tool, a
theorem prover, a graph engine, a symbolic executor, a sanitizer, or another purpose-built system.
Forge sees the declared claim and evidence contract rather than treating the backend technology as
the authority.

The stable abstraction remains:

```text
artifact identities + property request + bounded context
                         |
                         v
                declared micro-verifier
                         |
                         v
             PASS | FAIL | UNKNOWN
                         +
       witness / assumptions / limitations
                         +
     verifier/provider/environment identities
```

`UNKNOWN` is a first-class result. A verifier must not manufacture certainty when the claim is
outside its proof domain, when required evidence is unavailable, or when an unsupported construct
is encountered.

## Why Forge owns the verifier fleet

Forge is the natural home for this system because it already owns:

- deterministic verifier discovery and matching;
- bounded Provider Protocol invocation;
- candidate, policy, provider, configuration, and environment identity binding;
- immutable verifier action/result records;
- freshness and lineage semantics;
- development/evaluator separation;
- compact witnesses and explicit limitations; and
- escalation from a small verifier to a larger analyzer.

Forge should not absorb analyzer-specific algorithms. A verifier remains a provider-backed
capability whose authority is limited to its declared claim.

This makes the name **Forge** increasingly literal: it is the place where machine-generated
artifacts are repeatedly formed, heated by tests and counterexamples, struck by narrow
verifications, transformed, and only then allowed to advance with evidence attached.

## Candidate verifier families

The following families are especially suitable for the micro-verifier model.

### Structural and identity verifiers

Likely implementation fit: Rust or another small systems implementation.

Candidate properties include:

- schema validity;
- canonical identity and hash consistency;
- record linkage;
- artifact completeness;
- bounded manifest checks;
- ABI or format constraints; and
- deterministic parser/serializer invariants.

These are generally poor reasons to introduce Haskell when the existing Rust validator or a small
Rust provider can answer them cheaply and portably.

### Semantic-equivalence verifiers

Likely implementation fit: Haskell, SMT-backed functional code, symbolic execution, or a theorem
prover depending on claim strength.

Candidate questions include:

- did an optimization preserve the observable semantics required by the contract?;
- did a lowering step preserve effect behavior?;
- did a rewrite preserve required preconditions and postconditions?;
- did a specialization narrow behavior without expanding the legal state space?; and
- are two normalized bounded expressions equivalent under declared assumptions?

A Haskell provider is attractive here because pure functions, algebraic data types, pattern
matching, and equational reasoning make semantic transformations natural to model and inspect.
The provider can normalize bounded artifacts into a small semantic representation and compare
properties without making Haskell the implementation language of the artifact itself.

### State-machine and lifecycle verifiers

Likely implementation fit: Haskell, model checking, SMT, or a small typed Rust verifier.

Candidate questions include:

- can an invalid state transition occur?;
- can an unverified artifact reach a committed/executable state?;
- does every path to execution traverse required authorization and validation states?;
- can terminal states re-enter mutable execution unexpectedly?; and
- does a transition preserve a declared invariant?

Algebraic data types are particularly useful when the verifier can represent the legal state space
explicitly and reject impossible or undeclared transitions.

### Capability- and authority-flow verifiers

Likely implementation fit: Haskell, graph analysis, Datalog, SMT, Joern-backed analysis, or a
purpose-built Rust graph verifier.

Candidate properties include:

```text
no path: untrusted-input -> secret-store
no delegation path: worker-agent -> controller-admin
all paths: external-input -> execution
           traverse sanitizer AND authorization AND validator
new-capabilities subset-of authorized-capabilities
```

These claims are especially relevant to MNCS because capability exposure is deliberately routed
and minimized. The verifier should reason about an explicit capability/authority graph and return a
compact path witness or counterexample when possible.

### Effect-surface verifiers

Likely implementation fit: Haskell, an MNCS-language semantic checker, compiler IR analysis, or
SMT-backed analysis.

Candidate questions include:

- did a transformation introduce I/O where none was permitted?;
- did a rewrite expand filesystem, network, device, memory, or privilege effects?;
- are all effects represented in the declared contract?; and
- did a supposedly pure transformation remain pure within the modeled semantics?

A useful direction is to compare effect sets before and after transformation rather than merely
checking that both versions compile.

### Resource-bound verifiers

Likely implementation fit: refinement types, SMT, abstract interpretation, symbolic execution, or
runtime measurement depending on whether the claim is static or empirical.

Candidate properties include:

- output size remains within a declared bound;
- memory region access remains within an allocation contract;
- queue growth cannot exceed a modeled maximum;
- recursion or iteration is bounded under declared inputs; and
- privilege/resource acquisition cannot monotonically expand beyond policy.

Refinement-type systems such as Liquid Haskell are worth evaluating for narrow claims where normal
static typing is too weak but a full interactive theorem prover would be excessive.

### Information-flow and security-invariant verifiers

Likely implementation fit: graph analysis, Haskell, taint/data-flow engines, SMT, model checking,
or specialized security analyzers.

Candidate questions include:

- can protected data reach an untrusted output?;
- can a prompt-controlled value reach a tool-authority field?;
- can untrusted content influence executable arguments without passing a required gate?;
- is privilege attenuation preserved across delegation?; and
- did a transformation create a new security-sensitive path?

The verifier result must distinguish a proven bounded property from absence of a discovered path.
If the analysis is incomplete, the correct status is `UNKNOWN`, not `PASS`.

### Provenance-preservation verifiers

Likely implementation fit: Rust for identity mechanics plus Haskell/SMT/theorem-prover providers
for semantic preservation claims.

Machine-native development may transform an artifact repeatedly:

```text
source
  -> semantic IR
  -> optimized IR
  -> specialized IR
  -> lowered representation
  -> executable artifact
```

Each stage can emit evidence describing what property the transformation claims to preserve. Forge
should be able to retain those edges and request narrow verifiers against them. A future verifier
may compose compatible evidence across multiple transformation edges, but composition must never
be assumed merely because every individual stage returned `PASS`.

## Haskell's specific niche

Haskell should be evaluated as one verifier implementation technology where its semantics provide a
real advantage. Good pilot domains are:

1. bounded semantic equivalence over a normalized IR;
2. state-transition invariant checking;
3. capability/authority graph invariants;
4. effect-surface comparison; and
5. small refinement-constrained resource or value properties.

Haskell is not automatically the best choice for:

- raw parsing and schema validation;
- artifact hashing;
- low-level process isolation;
- high-throughput byte scanning;
- platform integration;
- portable standalone normative validation; or
- properties already handled well by the Rust validator.

A Haskell pilot should therefore enter Forge through the same Provider Protocol declaration as any
other micro-verifier. It receives bounded, identity-bound inputs and returns the normal Forge
result envelope. No Haskell-specific authority is added to Forge.

## Proof strength and evidence classes

Verifier technology and proof strength must remain separate concepts. A Haskell implementation is
not inherently a proof, and a Rust implementation is not inherently empirical. Every verifier must
declare the method and strength of its claim.

Useful method classes include:

- `structural-check`;
- `bounded-enumeration`;
- `abstract-interpretation`;
- `graph-proof`;
- `symbolic-proof`;
- `smt-proof`;
- `refinement-proof`;
- `theorem-proof`;
- `runtime-observation`; and
- `differential-check`.

The exact vocabulary can evolve, but Forge should avoid collapsing all successful methods into the
same semantic strength. A bounded enumeration over five inputs and a theorem over the declared
model may both return `PASS`; their assumptions and method remain materially different evidence.

## Overlapping verifier diversity

Critical properties may benefit from independent methods that overlap intentionally:

```text
                    semantic-equivalence
                           |
                +----------+----------+
                |                     |
         Haskell verifier        SMT verifier
                |                     |
                +----------+----------+
                           |
                  reconciliation policy
```

Disagreement is useful information, not an error to hide.

Recommended reconciliation behavior:

- any soundly bound `FAIL` is a blocker for a required property;
- `UNKNOWN` remains unresolved and may trigger escalation;
- multiple `PASS` results increase evidence diversity but do not automatically create a stronger
  normative claim;
- contradictory results preserve all witnesses and identities; and
- Forge policy decides whether a property requires one method, multiple methods, or a stronger
  escalation path.

This provides defense against verifier implementation defects and model mismatches without
creating a vague consensus-voting system.

## Fabric's role

Fabric should not become the verifier authority. Its useful role is execution placement and
capability-aware scheduling for verifier jobs whose requirements differ across workers.

Examples include routing based on:

- installed verifier runtime (`ghc`, SMT solver, theorem prover, graph engine);
- architecture or operating system;
- memory/CPU/GPU requirements;
- trusted execution or containment capability;
- local artifact availability;
- expected cost and latency; and
- evaluator/custody requirements where represented by policy.

Fabric may report that a suitable worker is unavailable. That is an execution/placement fact and
must not be translated into verification `FAIL`. Forge remains responsible for recording the
verifier action, semantic result, evidence classification, identities, freshness, and escalation
meaning.

A future Fabric-backed verifier run should therefore remain conceptually:

```text
Forge chooses the claim and verifier declaration
  -> Runner/Fabric places the declared execution
     -> verifier provider performs the narrow analysis
        -> Fabric returns bounded execution facts
           -> Forge records and interprets the evidence
```

## Escalation ladder

The verifier fleet should prefer the cheapest mechanism capable of answering the property without
pretending that a cheap method is stronger than it is.

A representative ladder is:

```text
structural/identity check
        -> narrow deterministic micro-verifier
        -> graph/refinement/symbolic verifier
        -> SMT/model checker
        -> theorem prover / high-assurance evaluator
        -> runtime or adversarial experiment when static proof is unsuitable
```

Escalation may also occur sideways to an independently implemented verifier for diversity.

## Machine-native direction

The long-term value is not merely a collection of tools. It is a development environment in which
machine-generated changes can request verification at the granularity of the uncertainty that
created them.

An agent should be able to express questions such as:

```text
Did this rewrite expand the effect surface?
Did this optimization preserve the required semantics?
Can this new delegation create a path to controller authority?
Can this state ever reach Execute without Verified?
Does this lowering preserve the original proof obligation?
```

Forge can then match the question to a declared verifier, retain the evidence, and feed a compact
counterexample back into the next machine transformation.

This creates a verification ecology rather than one universal verifier. The architecture should
optimize for many small, composable, independently replaceable specialists whose results remain
explicitly scoped and machine-readable.

## Initial implementation experiments

The direction should be introduced experimentally rather than by rewriting existing components.
Suggested pilots, in order:

1. **Semantic equivalence pilot** — a small Haskell provider over one normalized bounded expression
   or IR family, with explicit unsupported constructs and differential tests against an independent
   reference implementation.
2. **State-transition pilot** — verify a small Forge/Fabric/MNCS lifecycle model and emit a path
   counterexample for illegal reachability.
3. **Capability-flow pilot** — consume an explicit bounded capability graph and prove/reject a small
   set of path invariants.
4. **Method metadata** — extend verifier declarations/results only if experiments show the current
   claim/method fields cannot distinguish proof strength adequately.
5. **Fabric placement experiment** — place a verifier job on a worker by declared runtime/capability
   while preserving the existing Forge Runner/evidence boundary.
6. **Diverse double-check experiment** — run one property through two independently implemented
   verifier methods and study disagreement, cost, and escalation behavior.

Each pilot should be measured against the existing verifier architecture rather than promoted on
language reputation. Keep the component only if it produces better precision, stronger evidence,
lower verification cost, or a useful independent failure mode.

## Non-goals

This direction does not:

- rewrite the Rust MNCS validator in Haskell;
- make Haskell a required MNCS language;
- move scheduling or fleet ownership from Fabric into Forge;
- make Forge the normative MNCS validator;
- treat every `PASS` as a whole-program proof;
- infer proof strength from implementation language;
- require one verifier technology for every language; or
- allow an LLM assertion to stand in for deterministic verification evidence.

The desired end state is a polyglot verification fleet with one consistent Forge evidence model and
clear authority boundaries.
