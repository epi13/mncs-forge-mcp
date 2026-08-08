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

## Control-plane composition

`Forge` is the stable compatibility and composition facade used by both existing interfaces. It
constructs one shared ledger, transactional store, lifecycle context, project observer, and bounded
command executor, then delegates public behavior to cohesive application services:

```text
CLI / MCP
    -> typed operation registry and common invocation gate
    -> Forge compatibility facade
    -> project | provider | candidate | workflow | evaluation | evidence | recovery services
    -> typed records and ForgeStateMachine
    -> RecordReader | RecordCommitter | CommandExecutor | ProjectObserver ports
    -> local ledger/store/process/filesystem adapters
```

The incremental package layout keeps stable domain and storage modules such as `records.py`,
`state_machine.py`, `ledger.py`, and `record_store.py` in their established locations. Application
services live under `application/`; inward-facing protocols live in `ports.py`; local execution and
filesystem observation implementations live in `adapters.py`. This avoids compatibility churn
while making dependency direction enforceable.

Application services never receive the `Forge` facade and do not import CLI, MCP, argparse,
`LocalRecordStore`, or the local subprocess function. `MicroVerifierService` remains the one
authoritative verifier lifecycle and receives the same shared ports as other services. CLI and MCP
normalize their existing presentation into frozen operation input models and invoke one validated
registry definition. The registry enforces interface exposure and allowed Forge mode before its
typed facade handler runs; it describes lifecycle and authority requirements without implementing
transition policy. FastMCP tools are generated from registry metadata, while argparse layout stays
hand tuned and registry-bound. Operation-backed MCP resources use the same gate; static resources
and prompts remain presentation. See [Canonical Forge operation registry](operation-registry.md).

## Extension boundaries

Forge extensions attach at explicit inward-facing boundaries:

| Extension | Current boundary | What it does not establish |
| --- | --- | --- |
| Provider | declared Provider Protocol workflow and capability probe | analyzer authority, conformance, or independence |
| Micro-verifier | typed verifier declaration over a declared provider method | a whole-program proof, result cache, or normative validator |
| Application service | focused service with typed ports and shared composition-root dependencies | a replacement lifecycle policy or interface adapter |
| Storage | `RecordReader`/`RecordCommitter` ports implemented by `LocalRecordStore` | external anchoring, custody, witnessing, or remote storage |
| Execution | current `CommandExecutor` port and local adapter | runner receipts, sandbox assurance, containers, SSH, or attestation |
| Public operation | frozen definition in `operations.py` with CLI/MCP/resource metadata | lifecycle authorization, which remains in `ForgeStateMachine` |

The operation registry is the public dispatch extension point; application services are the
behavior extension point; ports are the adapter substitution points. New providers or verifiers
must remain declared and capability-bound. A future Task 7 runner may replace the local execution
adapter only after it records the properties needed for any stronger assurance claim. See
[Provider Protocol integration](provider-protocol.md), [Machine-native micro-verifiers](micro-verifiers.md),
[Transactional local storage](storage.md), and [Canonical Forge operation registry](operation-registry.md)
for the detailed contracts.

`CommandExecutor` is dependency inversion over the existing bounded local process behavior only.
It does not add runner receipts, sandbox assurance, containers, SSH, mount/network policy, or
attestation; those remain Task 7. Likewise, project observation centralizes existing filesystem
identity and workspace behavior without changing identity algorithms or authority semantics.

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

Authorized persistent transitions pass to `RecordStore` only after state-machine approval and
typed record construction. The local store stages the immutable record and replacement ledger,
binds them to the expected ledger predecessor, and publishes them under one exclusive state lock.
Startup recovery resolves prepared transactions before lifecycle projection. A local derived index
is rebuildable acceleration data; the ledger and immutable records remain authoritative. See
[Transactional local storage](storage.md).

`ForgeStateMachine` derives active epoch, candidate lineage/freshness, required-evidence readiness,
terminal disposition, freeze/evaluation/bundle state, and verifier action terminality from one
typed ledger snapshot. It authorizes transitions but does not execute providers or write records.
There is no mutable current-state file. See [Forge lifecycle state machine](lifecycle.md).

Project-scoped development workflows may run without candidate ledger state. Their subject
is the declared project identity, and their PASS is limited to the development workflow.
Candidate-scoped evidence keeps its candidate and epoch binding. Final evaluation is
registered only by a separate evaluator-mode MCP process.

Micro-verifiers are capability declarations over the same Provider Protocol workflows, bounded
command executor, temporary workspace, freeze checks, immutable record store, and ledger. They do
not form a parallel execution or evidence system. Forge controls matching and invocation; the provider owns
the narrow verification method; offline MNCS/MNCDS validators retain normative result authority.

See [Machine-native micro-verifiers](micro-verifiers.md) for the bounded query flow and freshness
model.
