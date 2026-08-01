# MNCS Forge documentation

This directory separates user setup, control-plane concepts, provider integration, security, and
development planning. The root README remains a short project entrypoint.

## Start here

- [Getting started](getting-started.md) — install Forge, validate a project, inspect authority, and
  register the local MCP server.
- [CLI and MCP interfaces](interfaces.md) — complete command, tool, resource, and prompt surface.
- [Configuration](configuration.md) — project paths, authority, workflows, providers, verifiers,
  policies, and limits.

## Concepts and authority

- [Architecture and trust boundaries](architecture.md)
- [Evidence and identity model](evidence-model.md)
- [Security model and residual risks](security.md)
- [Compatibility](compatibility.md)

## Providers and integrations

- [Provider Protocol integration](provider-protocol.md)
- [Machine-native micro-verifiers](micro-verifiers.md)
- [Forge and provider transition](provider-transition.md)
- [EdgeStream integration](edgestream.md)
- [Codex installation details](codex-cli.md)

## Development planning

- [Development roadmap](../ROADMAP.md) — release-level direction and sequencing.
- [Codex implementation queue](codex-next-steps.md) — ordered implementation tasks, constraints,
  acceptance criteria, and validation requirements for coding agents.
- [Architecture decision records](adr/README.md) — proposed decisions that should be resolved
  before the corresponding implementation work lands.

## Documentation rules

Documentation must preserve the same boundaries as the implementation:

- MNCS and MNCDS results remain separate;
- missing or unsupported evidence remains `UNKNOWN`;
- workflow completion alone is not normative conformance;
- local operation does not create independence, protected custody, or governance approval; and
- Forge is not an operating-system or network sandbox unless a future runner explicitly provides
  and records those properties.
