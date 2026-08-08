# Changelog

## Unreleased

- Add frozen, typed version-1 models for current Forge records and ledger entries while retaining
  JSON-compatible filesystem, ledger, Provider Protocol, CLI, and MCP boundaries.
- Add deterministic trusted-context migration for immutable unversioned `0.1` state, verifying raw
  historical ledger linkage before normalization and preserving historical identities/statuses.
- Add explicit metadata-bound current identity projections, fail-closed future-version and
  record-context mismatch errors, documented extension policy, immutable legacy fixtures, and a
  Draft 2020-12 public record-schema snapshot.
- Consolidate the hardened micro-verifier lifecycle into the authoritative
  `MicroVerifierService` and remove package-import service replacement.
- Preserve deletion-aware changed-path identities, terminal `UNKNOWN` results, evaluator
  redaction-before-identity, and heterogeneous partial batch behavior under both package import
  orders.
- Fail closed with a recorded, non-sensitive terminal `UNKNOWN` when an unexpected execution
  exception occurs after a verifier action has been recorded.
- Streamline the repository entrypoint and add a documentation map and consolidated getting-started
  guide.
- Add a release-level development roadmap and an ordered Codex implementation queue with task
  dependencies, invariants, acceptance criteria, validation commands, and explicit exclusions.
- Add proposed architecture decision records for control-plane composition, versioned persistent
  records, replaceable execution runners, ledger checkpoint anchoring, and Forge Cell assurance.
- Expand contributor guidance and add evidence-aware pull request and roadmap-task templates.
- Add versioned Forge Cell policy, test-bundle, and execution-record schemas as packaged resources.
- Add offline Forge Cell document validation and fail-closed assurance assessment that keeps test
  results separate from execution assurance.
- Add reference Forge Cell artifacts and tests covering missing isolation, identity substitution,
  challenge replay, contradictory assurance claims, and malformed evidence.
- Add a dedicated Codex queue for Linux isolation, immutable test bundles, challenge-bound
  attestation, adversarial studies, TPM, confidential execution, and external custody.
- Define query-driven micro-debugging architecture, status separation, identity/invalidation
  rules, and a provider-neutral escalation model over the existing verifier evidence system.
- Add a six-record micro-debugging vocabulary, proposed ADR, and ordered implementation queue for
  sessions, snapshots, queries, a Clang/LLVM pilot, benchmarks, and adversarial validation.

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
