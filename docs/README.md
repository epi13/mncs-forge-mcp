# MNCS Forge documentation

This directory separates user setup, control-plane concepts, provider integration, security, and
development planning. The root README remains a short project entrypoint.

## Start here

- [Getting started](getting-started.md) — install Forge, validate a project, inspect authority, and
  register the local MCP server.
- [CLI and MCP interfaces](interfaces.md) — complete command, tool, resource, and prompt surface.
- [Canonical operation registry](operation-registry.md) — shared typed dispatch, metadata, and
  machine-readable interface inventory.
- [Configuration](configuration.md) — project paths, authority, workflows, providers, verifiers,
  policies, and limits.

## Concepts and authority

- [Architecture and trust boundaries](architecture.md)
- [Evidence and identity model](evidence-model.md)
- [Versioned record schemas and migration](record-schemas.md)
- [Lifecycle state machine and transition errors](lifecycle.md)
- [Transactional local storage and recovery](storage.md)
- [Security model and residual risks](security.md)
- [Intent-aware security verification](intent-aware-security-verification.md)
- [Forge Cell execution assurance](forge-cell.md)
- [Compatibility](compatibility.md)

## Providers and integrations

- [Provider Protocol integration](provider-protocol.md)
- [Machine-native micro-verifiers](micro-verifiers.md)
- [Query-driven micro-debugging](micro-debugging.md)
- [Forge and provider transition](provider-transition.md)
- [EdgeStream integration](edgestream.md)
- [Codex installation details](codex-cli.md)

## Development planning

- [Development roadmap](../ROADMAP.md) — release-level direction and sequencing.
- [Codex implementation queue](codex-next-steps.md) — ordered implementation tasks, constraints,
  acceptance criteria, and validation requirements for coding agents.
- [Forge Cell Codex queue](codex-forge-cell-next-steps.md) — ordered implementation tasks for Linux
  isolation, immutable test bundles, challenge-bound attestations, adversarial studies, TPM,
  confidential execution, and external custody.
- [Micro-debugging Codex queue](codex-micro-debugging-next-steps.md) — ordered implementation
  tasks for diagnostic records, snapshots, provider queries, a Clang/LLVM pilot, benchmarks, and
  adversarial validation.
- [Architecture decision records](adr/README.md) — accepted decisions for implemented boundaries
  and proposed decisions for future work.
- [Task 3 validation evidence](development-evidence/task-3-validation.md) — baseline, focused/full
  test results, benchmark comparison, graph-analysis limits, and the deferred storage seam.
- [Task 4 validation evidence](development-evidence/task-4-validation.md) — transaction fault
  matrix, recovery/concurrency validation, benchmark comparison, and Joern storage-flow review.
- [Task 5 validation evidence](development-evidence/task-5-validation.md) — application-service
  boundaries, facade compatibility, dependency enforcement, and structural review.
- [Task 6 dispatch inventory](development-evidence/task-6-dispatch-inventory.md) — pre-refactor
  CLI/MCP compatibility mapping and intentional asymmetries.
- [Task 6 validation evidence](development-evidence/task-6-validation.md) — registry design,
  compatibility enforcement, benchmark comparison, and Joern dispatch review.

## Documentation rules

Documentation must preserve the same boundaries as the implementation:

- MNCS and MNCDS results remain separate;
- missing or unsupported evidence remains `UNKNOWN`;
- workflow completion alone is not normative conformance;
- local operation does not create independence, protected custody, or governance approval; and
- Forge is not an operating-system or network sandbox unless a runner explicitly provides and
  records those properties.
