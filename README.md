# MNCS Forge MCP

MNCS Forge is an experimental, non-normative Model Context Protocol server and CLI for
machine-native development and evidence control. It makes project authority, candidate lineage,
declared checks, provider capabilities, evidence gaps, selection, freeze, and evaluator-mode
boundaries explicit.

> Forge is not required for MNCS conformance, an accredited certification system, a source of
> independent evaluation or protected custody, or a universal program analyzer.

Version `0.1.0a2` is a reference experiment. Local results do not promote MNCS, MNCDS, RFCs, or
case studies. Status aggregation is `FAIL > UNKNOWN > PASS`; absent, stale, unsupported, or
unavailable evidence remains `UNKNOWN`.

## What Forge does

- exposes one project-scoped control plane through a CLI and local stdio MCP server;
- runs only declared argument-array workflows and Provider Protocol capabilities;
- records epochs, candidates, actions, results, selection, freeze, and evaluation lineage;
- keeps development and evaluator-mode authority separate;
- provides bounded machine-native micro-verifier discovery and execution; and
- delegates normative MNCS and MNCDS decisions to the public offline validators.

```mermaid
flowchart LR
  Codex[Codex / MCP client] --> Forge[Forge control plane]
  Human[CLI user] --> Forge
  Forge --> Providers[Declared providers and harnesses]
  Providers --> Records[Immutable records and local hash-linked ledger]
  Forge --> Records
  Records --> Validators[Offline MNCS / MNCDS validators]
```

Forge is orchestration, not analysis. Joern is an optional legacy provider rather than a default
dependency. Compilers, analyzers, benchmarks, mutation systems, sanitizers, and runtime harnesses
remain replaceable providers.

## Quick start

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
mncs-forge --config examples/minimal/mncs-forge.toml config validate
mncs-forge --config examples/minimal/mncs-forge.toml inspect
```

See [Getting started](docs/getting-started.md) for installation, CLI, MCP registration, and the
minimal controlled workflow.

## Documentation

- [Documentation map](docs/README.md)
- [Architecture and trust boundaries](docs/architecture.md)
- [Security model and residual risks](docs/security.md)
- [Forge Cell execution assurance](docs/forge-cell.md)
- [Configuration](docs/configuration.md)
- [CLI and MCP interfaces](docs/interfaces.md)
- [Canonical operation registry](docs/operation-registry.md)
- [Provider Protocol integration](docs/provider-protocol.md)
- [Machine-native micro-verifiers](docs/micro-verifiers.md)
- [Query-driven micro-debugging](docs/micro-debugging.md)
- [Evidence and identity model](docs/evidence-model.md)
- [Lifecycle state machine](docs/lifecycle.md)
- [Transactional local storage](docs/storage.md)
- [Development roadmap](ROADMAP.md)
- [Codex implementation queue](docs/codex-next-steps.md)
- [Forge Cell Codex queue](docs/codex-forge-cell-next-steps.md)
- [Micro-debugging Codex queue](docs/codex-micro-debugging-next-steps.md)

## Current development priority

The next release should stabilize the internal architecture before adding more verifier types,
distributed execution, or sandbox backends. The verifier lifecycle now has one explicit service,
and persistent evidence now crosses a frozen typed, versioned boundary with deterministic legacy
migration. Explicit state transitions derive from append-only typed history, authorized
record-plus-ledger changes commit through one recoverable local transaction boundary, and the
compatibility facade delegates to explicit services through typed storage, execution, and identity
ports. CLI and MCP dispatch now share one typed operation registry and deterministic interface
inventory. Remaining `0.1.0b1` work reviews schema/migration compatibility and documented extension
boundaries before Task 7 expands runner semantics. Forge Cell schemas and fail-closed assurance
assessment are available as a specification foundation; the actual Linux isolation and attestation
backends remain ordered follow-up work. Query-driven micro-debugging now also has an architecture,
versioned reference vocabulary, and a separate implementation queue; runtime sessions and reusable
analyzer snapshots remain future work after the core typed-record and service boundaries stabilize.

Licensed under Apache-2.0.
