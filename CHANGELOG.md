# Changelog

## Unreleased

- Streamline the repository entrypoint and add a documentation map and consolidated getting-started
  guide.
- Add a release-level development roadmap and an ordered Codex implementation queue with task
  dependencies, invariants, acceptance criteria, validation commands, and explicit exclusions.
- Add proposed architecture decision records for control-plane composition, versioned persistent
  records, replaceable execution runners, and ledger checkpoint anchoring.
- Expand contributor guidance and add evidence-aware pull request and roadmap-task templates.

## 0.1.0a2

- Add the first machine-native micro-verifier foundation: declared capabilities over existing
  providers/workflows, deterministic matching, bounded single/batch execution, immutable
  action/result lineage, freshness envelopes, CLI/MCP surfaces, examples, and security tests.
- Add provider-neutral configuration for identity/version, argv transport, declared
  capabilities, required/optional status, constructs, limitations, executable identity,
  environment, and last capability probe.
- Add CLI and MCP provider list, explicit bounded probe, and capability-blocker operations.
- Fail closed to UNKNOWN for unavailable, malformed, timed-out, unsupported, or
  identity-drifted providers; do not infer PASS from exit zero alone.
- Add project-scoped development workflows that do not require candidate ledger state.
- Remove final evaluation from the development MCP inventory and demote Joern to an
  explicitly configured optional legacy provider.

## 0.1.0a1

- Initial experimental CLI and stdio MCP server.
- Declared authority, epoch, candidate, evidence, comparison, freeze, evaluation, reconciliation,
  and package workflows.
- Provider Protocol 0.1 integration, EdgeStream example, Codex installer, security boundaries,
  tests, and CI.
