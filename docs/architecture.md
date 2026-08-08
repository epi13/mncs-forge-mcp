# Architecture and trust boundaries

Forge controls an agent-facing workflow; it does not decide normative conformance. It separates:

1. Codex interaction over local stdio MCP;
2. deterministic analyzer interaction over MNCS Provider Protocol 0.1;
3. replaceable declared compiler, analyzer, test, mutation, sanitizer, benchmark, and harness
   commands; and
4. public offline MNCS and MNCDS validators.

Forge is orchestration, not analysis. Provider discovery records configured identity,
version, argv/transport, capabilities, required/optional status, availability, constructs,
limitations, executable identity, and the last explicit probe. A recognized capabilities
response can satisfy discovery policy; it is not structural-analysis or conformance PASS.
Missing capability remains UNKNOWN.

Development mode can see declared contracts, references, and development evidence, register
candidates, run declared development workflows, compare candidates under the configured policy,
and write only candidate/generated/output/Forge-state paths. Evaluator mode requires frozen
candidate, evaluator, policy, contract, reference, protected, environment, and evidence-plan
identities. It checks identity drift before and after each run and withholds repair details under
status-only disclosure.

The Forge state directory is `.mncs-forge/`. Epoch, candidate, action, result, selection,
rejection, freeze, evaluation, and bundle records are immutable files plus a locked hash-linked
JSONL ledger. Versioned frozen models form the internal domain boundary; filesystem, ledger, CLI,
MCP, and Provider Protocol boundaries remain JSON-compatible. Supersession and lineage are
explicit. See [Versioned Forge records](record-schemas.md) for schema, identity, and legacy
migration rules.

Project-scoped development workflows may run without candidate ledger state. Their subject
is the declared project identity, and their PASS is limited to the development workflow.
Candidate-scoped evidence keeps its candidate and epoch binding. Final evaluation is
registered only by a separate evaluator-mode MCP process.

Micro-verifiers are capability declarations over the same Provider Protocol workflows, bounded
runner, temporary workspace, freeze checks, immutable record store, and ledger. They do not form a
parallel execution or evidence system. Forge controls matching and invocation; the provider owns
the narrow verification method; offline MNCS/MNCDS validators retain normative result authority.

See [Machine-native micro-verifiers](micro-verifiers.md) for the bounded query flow and freshness
model.
