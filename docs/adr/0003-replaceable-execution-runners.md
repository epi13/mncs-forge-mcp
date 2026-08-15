# ADR 0003: Replaceable execution runners

- **Status:** Accepted
- **Target:** `0.2.x`

## Context

Forge currently performs bounded local subprocess execution and correctly documents that the
reduced workspace, no-shell invocation, timeouts, and output caps are not an operating-system or
network sandbox. Configured providers retain the ambient permissions of the Forge process.

Future container and Fabric-backed execution must not be added as special cases inside provider or
workflow services. Execution properties also need to become material evidence rather than informal
deployment assumptions. Generic fleet scheduling belongs to `mncs-fabric`; see
[ADR 0011](0011-forge-fabric-execution-boundary.md).

## Decision

Forge will define a typed runner protocol with capability inspection and bounded execution. The
first adapter preserves current behavior as `LocalProcessRunner`. Later adapters may provide
rootless Podman, Docker, or a Fabric-backed runner. Forge does not grow a second worker registry
or scheduler.

Every execution receipt will bind the material properties needed to interpret the result,
including:

- runner implementation and version;
- host, OS, and architecture identity;
- executable and optional container image identity;
- environment identity;
- network policy;
- filesystem and mount policy;
- timeout, output, and termination limits;
- request identity; and
- output and diagnostic identities.

Forge will describe only properties actually enforced and recorded by the selected runner. An
image tag is not an immutable image identity, and a configured executable remains trusted code
unless the runner establishes a stronger boundary.

## Consequences

Positive consequences:

- execution policy becomes replaceable and testable;
- sandbox claims can be evidence-backed;
- local, container, remote, and worker execution share one contract; and
- application services no longer depend directly on subprocess details.

Costs and risks:

- cross-platform process cleanup remains adapter-specific;
- container runtime availability must be reported explicitly; and
- a skipped sandbox test cannot be treated as a sandbox `PASS`.

## Required evidence before acceptance

- all provider and workflow execution passes through the runner protocol;
- local execution retains current bounds and cross-platform behavior;
- runner capabilities are included in material identities and receipts;
- unavailable adapters fail explicitly; and
- security documentation distinguishes every runner's enforced and unenforced properties.
