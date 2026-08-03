# Codex implementation queue: query-driven micro-debugging

This queue implements the architecture and record vocabulary defined in
[`docs/micro-debugging.md`](micro-debugging.md) and
[ADR 0006](adr/0006-query-driven-micro-debugging.md).

The architecture and vocabulary are specification foundations. They do not create runtime
diagnostic sessions, persistent analyzer processes, safe result reuse, or new MCP authority.

Do not implement this queue in one branch. Each task should normally be one focused PR and must
preserve the non-negotiable invariants in [`docs/codex-next-steps.md`](codex-next-steps.md).

## Completed specification foundation

The repository contains:

- architecture, lifecycle, status, identity, disclosure, and escalation rules;
- a six-record vocabulary and cross-record invariants;
- a proposed ADR; and
- this ordered implementation handoff.

The following implementation work remains.

---

## Debug Task 1 — Integrate typed diagnostic records

**Priority:** P1 after central Tasks 2 and 4  
**Target:** `0.2.x`  
**Depends on:** central typed records, migrations, and transactional storage

### Objective

Integrate the six diagnostic record types into the versioned persistent model without creating a
parallel evidence store.

### Required changes

- define frozen typed models for every diagnostic record;
- publish packaged schemas as compatibility snapshots;
- add canonical identity computation and deterministic migration/version dispatch;
- store records transactionally with the ledger;
- add indexes for session, candidate, event, hypothesis, probe, verifier action, and verifier result;
- preserve unknown extension data according to the central record policy; and
- reject unsupported future schema versions.

### Cross-record invariants

- all records in a session bind the same candidate and development epoch;
- every snapshot belongs to the referenced session;
- every hypothesis references existing events in the same session;
- every probe references an existing hypothesis or explicitly records `null`;
- a started/completed probe references exactly one existing verifier action;
- a debug result references exactly one existing verifier result;
- repeated verifier status equals the referenced verifier result status;
- `final_evaluation_reusable` is always false for the initial vocabulary; and
- supersession is explicit rather than historical mutation.

### Acceptance criteria

- schema round trips preserve canonical identities;
- malformed references fail closed;
- old Forge state remains readable;
- interrupted writes cannot leave one side of a diagnostic/verifier link committed alone; and
- no diagnostic record changes the status or authority of an existing verifier result.

---

## Debug Task 2 — Normalize diagnostic events

**Priority:** P1  
**Target:** `0.2.x`  
**Depends on:** Debug Task 1 and the modular application-service boundary

### Objective

Create a bounded event-normalization service for declared compiler, test, runtime, verifier,
analyzer, contract, and human observations.

### Required changes

- define typed normalizer adapters;
- preserve a content identity for the bounded raw diagnostic artifact where available;
- enforce size, count, path, location, text, and related-record limits;
- deduplicate only by explicit normalized identity;
- retain origin, phase, code, severity, location, subject identities, and limitations;
- add redaction hooks before persistence; and
- never infer MNCS/MNCDS status from severity or process exit.

### Acceptance criteria

- equivalent bounded diagnostics normalize deterministically;
- oversized logs are truncated or rejected according to policy with explicit limitations;
- malformed locations and protected paths fail closed;
- compiler exit zero does not suppress recorded warnings/errors;
- compiler exit nonzero does not automatically create verifier `FAIL`; and
- event ingestion does not execute a provider.

---

## Debug Task 3 — Add session and snapshot lifecycle services

**Priority:** P1  
**Target:** `0.2.x`  
**Depends on:** Debug Tasks 1–2, central state machine, runner, and operation registry

### Objective

Open, inspect, invalidate, and close development diagnostic sessions and identity-bound snapshots.

### Required operations

- open a session for the current development epoch and candidate;
- register a snapshot build request through a declared provider workflow;
- inspect snapshot capabilities, coverage, limits, storage class, and freshness;
- invalidate snapshots after material identity changes;
- close or abandon sessions;
- rebuild unavailable or stale ephemeral snapshots; and
- explain why a snapshot is current, stale, unavailable, or unresolved.

### Constraints

- callers cannot choose arbitrary executables, argv, environment, or working directories;
- a session does not grant provider authority absent from configuration;
- closing a session does not promote its evidence;
- a provider daemon is optional and must be managed behind the runner protocol;
- a process identity alone is not a snapshot identity; and
- storage paths remain implementation details rather than caller-controlled record fields.

### Acceptance criteria

- candidate, toolchain, provider, configuration, or material environment drift invalidates by default;
- complete dependency envelopes permit reuse only when every dependency identity is unchanged;
- incomplete impact information remains `UNKNOWN`;
- process crash and restart can rebuild an ephemeral snapshot without changing its declared inputs;
- resource cleanup covers child processes, files, sockets, and temporary workspaces; and
- non-supporting providers report snapshot capability unavailable without pretending success.

---

## Debug Task 4 — Extend provider capabilities for diagnostic queries

**Priority:** P1  
**Target:** `0.2.x`  
**Depends on:** Debug Task 3 and a reviewed Provider Protocol extension proposal

### Objective

Define the smallest provider-neutral protocol extension needed to build/inspect snapshots and answer
bounded probes.

### Required design work

- specify capability discovery for snapshot kinds and probe methods;
- bind every request to session, snapshot, candidate, provider, toolchain, and input identities;
- preserve request IDs and exactly-one-response behavior;
- define bounded progress or readiness only if needed;
- distinguish operational failure from analysis `FAIL`;
- support providers that rebuild state per request;
- support providers that retain state behind a runner;
- define explicit snapshot close/cleanup semantics; and
- retain Provider Protocol 0.1 compatibility for ordinary one-shot verifiers.

### Acceptance criteria

- a provider cannot substitute another snapshot or candidate;
- wrong request, session, or snapshot identities fail closed;
- malformed, multiple, empty, oversized, or timed-out responses produce operational `UNKNOWN`;
- provider identity drift prevents reuse;
- no protocol field accepts a shell command or arbitrary execution settings; and
- one-shot providers remain valid escalation backends.

---

## Debug Task 5 — Add hypothesis and probe application services

**Priority:** P1  
**Target:** `0.2.x`  
**Depends on:** Debug Tasks 1–4 and central operation registry

### Objective

Expose the explicit diagnostic loop without embedding an LLM or automatic repair planner in Forge.

### Required operations

- register and supersede a falsifiable hypothesis;
- list compatible probes through existing deterministic verifier matching;
- request one probe or bounded batch;
- link the probe to its verifier action/result;
- register the hypothesis effect and repair scope;
- explain unresolved uncertainty and available escalation levels; and
- close a hypothesis as supported, refuted, unresolved, or superseded.

### Constraints

- the caller supplies the hypothesis statement and falsification criteria;
- Forge may derive deterministic compatibility and lifecycle metadata only;
- a debug interpretation cannot change the underlying verifier status;
- batch aggregation remains `FAIL > UNKNOWN > PASS` for verifier statuses only;
- hypothesis disposition is not aggregated as conformance; and
- no hidden reasoning transcript is stored.

### Acceptance criteria

- CLI and MCP invoke the same typed handlers;
- mode and authority are checked before execution;
- contradictory result/status links fail closed;
- evaluator mode does not expose repair-capable operations;
- every started probe receives a terminal result or recoverable terminal `UNKNOWN`; and
- interface output stays compact and machine-readable.

---

## Debug Task 6 — Implement safe invalidation and identity-bound reuse

**Priority:** P2  
**Target:** after stable local `0.2.0` boundaries  
**Depends on:** Debug Tasks 1–5 and central result-reuse Task 10

### Objective

Avoid rebuilding unchanged snapshots and rerunning unaffected probes without accepting stale
development evidence.

### Required cache key material

- mode and development epoch;
- candidate and parent lineage;
- session and snapshot construction identities;
- verifier declaration and method;
- provider configuration, executable, and reported identity;
- toolchain and compilation database;
- configuration, policy, contract, reference, and material environment;
- bounded input and question-parameter identities;
- dependency-envelope identities and completeness;
- runner and execution-assurance identities where applicable; and
- disclosure policy.

### Acceptance criteria

- changed material identity prevents reuse;
- absent, deleted, renamed, and generated paths have explicit identities;
- incomplete dependency knowledge prevents optimistic reuse;
- reused results retain original timestamps and receive separate reuse records;
- historical results are never rewritten as current; and
- benchmarks report hit rate and validation cost without presenting speed as conformance.

---

## Debug Task 7 — Build the Clang/LLVM pilot provider

**Priority:** P2  
**Target:** `0.2.x`  
**Depends on:** Debug Tasks 1–5

### Objective

Demonstrate the architecture with one C/C++ provider that amortizes expensive parsing/IR generation
across multiple bounded questions.

### Initial snapshot kinds

- Clang AST/semantic index;
- LLVM IR;
- function-level control-flow;
- dominator and use-definition indexes; and
- ABI/symbol metadata.

### Initial probe methods

- exact symbol binding;
- type and conversion path;
- bounded pointer ownership path;
- dominating definition;
- bounded use-definition path;
- function-level control-flow reachability;
- ABI symbol drift; and
- contract-to-symbol binding.

### Acceptance criteria

- at least six probe methods reuse one snapshot;
- every method has a narrow declared claim, assumptions, limitations, and unsupported cases;
- unsupported C/C++ constructs return `UNKNOWN`;
- witnesses are compact and location-bound;
- results are compared against equivalent direct Clang/LLVM queries;
- process lifetime and cleanup are tested through the runner; and
- the provider remains optional and replaceable.

---

## Debug Task 8 — Benchmark query-driven debugging

**Priority:** P2  
**Target:** after the pilot provider  
**Depends on:** Debug Task 7

### Objective

Measure whether micro-debugging improves latency, output size, repair localization, and repeated-query
cost without hiding accuracy or operational failures.

### Required cohorts

1. one-shot large compiler/analyzer output;
2. repeated one-shot bounded providers;
3. one snapshot with repeated micro probes;
4. incremental affected-scope analysis; and
5. deliberate full-scan escalation.

### Required metrics

- snapshot build time;
- per-probe p50/p95/p99 latency;
- bytes disclosed to the agent;
- provider CPU and memory;
- invalidation/rebuild rate;
- supported, unsupported, and operational `UNKNOWN` counts;
- witness size;
- repair-scope size;
- number of probes before resolution or escalation; and
- result agreement with the reference query.

### Acceptance criteria

- benchmark fixtures and expected query answers are versioned;
- warm and cold measurements are separated;
- failed and unsupported probes remain visible;
- no benchmark result is described as MNCS/MNCDS conformance;
- regressions have explicit thresholds or reviewed explanations; and
- data is sufficient to decide when a full scan is cheaper than continued probing.

---

## Debug Task 9 — Adversarial and disclosure study

**Priority:** P2 before broad adoption  
**Target:** `0.2.x`  
**Depends on:** Debug Tasks 1–8 and Forge Cell runner work where used

### Objective

Test stale-state, identity substitution, malformed witness, resource exhaustion, disclosure, and
provider-lifecycle failures.

### Required cases

- candidate, contract, toolchain, provider, snapshot, and environment substitution;
- false complete dependency envelopes;
- stale snapshot replay;
- verifier status/interpretation contradiction;
- missing action or result links;
- oversized event, witness, value, path, and graph data;
- provider crash, hang, fork, orphan, and output overflow;
- protected-path and evaluator-data disclosure attempts;
- snapshot storage traversal, symlink, special-file, and replacement attacks;
- concurrent session/probe races; and
- full-scan escalation that silently broadens authority or disclosure.

### Acceptance criteria

- every malformed or unavailable case fails closed;
- resource exhaustion receives bounded cleanup;
- evaluator mode cannot read repair witnesses from development sessions;
- Forge Cell assurance remains separate from analysis correctness;
- local operation is not described as independent; and
- the threat model documents the trusted computing base for every pilot backend.

---

## Debug Task 10 — Add MNCS-oriented verifier families

**Priority:** P3  
**Target:** after the architecture and pilot are measured  
**Depends on:** Debug Tasks 1–9

### Objective

Add narrowly scoped probes for MNCS-style development blind spots rather than another broad linter.

### Candidate families

- contract-to-symbol binding;
- invariant preservation;
- generated/reference binding drift;
- assumption consumption;
- proof-obligation coverage;
- `UNKNOWN` propagation;
- evidence dependency invalidation;
- lineage mismatch;
- cross-module claim consistency;
- witness minimization;
- observability loss;
- semantic duplication;
- repair side effects; and
- useful-benefit evidence for added complexity.

Each family must have a declared bounded claim, explicit unsupported cases, compact witnesses,
freshness dependencies, reference fixtures, mutation/adversarial cases, and a reason it is more
useful as a micro probe than as a full scan.
