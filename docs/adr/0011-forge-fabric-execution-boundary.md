# ADR 0011: Forge/Fabric execution and evidence boundary

- **Status:** Accepted
- **Target:** `0.2.x`

## Context

Forge's earlier distributed-execution roadmap described a Forge-owned coordinator, worker
registry, lease system, heartbeat layer, and generic remote worker protocol. Since that plan was
written, `mncs-fabric` has become the persistent heterogeneous execution substrate for the MNCS
family. It already owns worker inventory, `fleet.refresh`, detached jobs, capability declaration,
availability windows, the work queue, containment reporting, process-tree cancellation, and
bounded artifact transport.

Duplicating those mechanics inside Forge would create two schedulers and two authority stories.

## Decision

Fabric decides where and how an eligible job executes. Forge records and evaluates the meaning of
that execution.

```text
Fabric provides persistent placement and execution.
Forge records and evaluates the meaning of that execution.
Commons provides durable collaborative memory.
The harness provides model-agent execution.
RAVEL performs experimental learning/knowledge curation.
Control composes those services for human and agent operation.
```

Forge consumes execution through the typed `Runner` port. `LocalProcessRunner` remains the default
local adapter. A Fabric-backed runner, when added, must translate substrate facts into the same
`ExecutionSession` / `ExecutionObservation` types. Forge application and domain code must not
import Fabric, schedule workers, store a work queue, refresh inventory, or implement leases.

Forge-specific distributed-evidence requirements remain Forge-owned:

- immutable job/subject/action identity;
- worker, runner, and environment identity binding;
- capability-drift detection at the evidence layer;
- retry/attempt lineage and duplicate-result reconciliation;
- evidence classification;
- reproduction semantics;
- same-operator versus independent execution;
- challenge, freeze, and policy authority.

A local process receipt and a same-operator Fabric worker receipt are both useful provenance
records. Neither establishes independence, protected custody, witnessing, certification, or
governance approval.

## Consequences

Positive consequences:

- Forge can use local or Fabric-backed execution without changing evidence semantics;
- Fabric remains the execution substrate rather than an alternate verifier;
- Commons cannot become an alternate evidence ledger; and
- later sandbox runners can report isolation through the same established-property dimensions.

Costs and risks:

- a Fabric adapter must fail closed when requested containment cannot be established;
- same-operator remote execution can be mistaken for independent evaluation if properties are
  collapsed; and
- Forge must keep the upstream MNCS execution-receipt envelope distinct from its own linkage
  records.

## Required evidence before acceptance

- persisted Forge receipt bindings link action, subject, runner, and optional MNCS envelope
  identities;
- incomplete observations remain `UNKNOWN` and cannot become `PASS`;
- a scripted/in-memory Fabric adapter can satisfy the `Runner` port;
- Forge source does not import `mncs_fabric`; and
- documentation no longer proposes a Forge-owned fleet scheduler.
