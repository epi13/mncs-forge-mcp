# Task 5 pre-refactor Forge responsibility inventory

This inventory describes merged `main` at `edb29da` before the Task 5 source refactor. It is a
compatibility contract and operator-controlled development evidence, not conformance,
independence, protected custody, witnessing, certification, governance approval, or promotion.

## Public facade operations

`R` means read-only and `W` means a transactional `RecordStore.commit`. All operations return
JSON-compatible dictionaries and raise stable `ForgeError` codes.

| Forge operation | Mode / effect | Records read -> written | Lifecycle / execution / identity responsibility | CLI / MCP | Principal errors |
| --- | --- | --- | --- | --- | --- |
| `doctor` | both / R | ledger and immutable companions | verifies storage; resolves declared command paths | both / no tool | ledger errors |
| `project_inspect` | both / R | full lifecycle, probes | projects lifecycle, provider inventory, command versions, verifier declarations | both / both | propagated storage/config errors |
| `state_inspect` | both / R | full lifecycle | constructs `ForgeStateMachine` with current identity/policy observations | both / both | lifecycle/storage/identity errors |
| `provider_list` | both / R | latest probes | resolves executable and current executable identity | both / both | unavailable providers become `UNKNOWN` inventory |
| `provider_probe` | development / W | provider probes -> provider probe | mode guard, executable authority, bounded Provider Protocol capability execution | both / both | `MODE_FORBIDDEN`, `PROVIDER_*`, `COMMAND_*` recorded as `UNKNOWN` |
| `capability_blockers` | both / R | latest probes | compares declared requirements with current recognized probe | both / both | fail-closed `UNKNOWN` blockers |
| `verifier_list` | both / R | none | verifier declaration presentation | both / both | verifier configuration errors |
| `verifier_describe` | both / R | none | one verifier declaration | both / both | `VERIFIER_NOT_DECLARED` |
| `verifier_match` | both / R | none | deterministic bounded capability matching | both / both | input/cost/mode validation errors |
| `verifier_run` | development or evaluator / W | lifecycle, actions/results/freeze -> action and terminal result | delegates the singular action/execution/terminal lifecycle | both / both | lifecycle, binding, execution, protocol errors; execution uncertainty terminates `UNKNOWN` |
| `verifier_batch` | development or evaluator / W | same as `verifier_run` | bounded repeated singular verifier lifecycle | both / both | batch/input errors plus per-verifier results |
| `verifier_explain` | both / R | verifier results and current identities | freshness/supersession explanation | both / both | `RESULT_NOT_FOUND` and freshness errors |
| `epoch_begin` | development / W | epoch lineage -> epoch | authorizes successor; observes authority, baseline, contract and objective identities | both / both | epoch transition codes |
| `candidate_register` | development / W | epoch/candidate lineage -> candidate | observes current candidate/files/objective; validates write/protected boundaries | both / both | `STALE_CANDIDATE`, path errors, candidate transition codes |
| `development_checks_run` | development / W | lifecycle -> workflow results | authorizes project/candidate scope, resolves declared workflows, executes and parses results | both / both | workflow, lifecycle, execution, protocol errors |
| `failure_explain` | both / R | workflow results | presents bounded FAIL/UNKNOWN next-step information | both / both | `RESULT_NOT_FOUND` |
| `candidate_compare` | development / R | candidates and workflow results | authorizes comparability and presents policy-bound comparison | both / both | `COMPARE_INPUT`, candidate/evidence transition codes |
| `candidate_disposition` | development / W | candidate/evidence/dispositions -> disposition | authorizes one terminal selected/rejected disposition | both / two tools | disposition/evidence transition codes |
| `candidate_freeze` | development / W | candidate/evidence/disposition/freeze -> freeze | validates evidence plan, authorizes current selection, observes frozen identities | both / both | freeze/evidence-plan/identity transition codes |
| `final_evaluation_run` | evaluator / W | freeze/candidate/disposition -> evaluations | evaluator-entry authorization, isolated workspace, before/after drift checks, status-only disclosure | both / evaluator-only tool | evaluator/freeze/drift/workflow errors |
| `claim_status` | both / R | configured evidence/output JSON files | classifies structured statuses without granting external authority | both / both | malformed files are ignored, missing remains `UNKNOWN` |
| `claim_blockers` | both / R | same as `claim_status` | maps unresolved claim classes to work/authority boundaries | both / both | unknown claim defaults to `UNKNOWN` |
| `evidence_reconcile` | both / R | lifecycle and workflow results | authorizes scope and derives typed reconciliation; not persisted | both / both | reconciliation transition codes |
| `bundle_build` | mode of declared workflow / W | lifecycle -> bundle | authorizes bundle, executes declared MNCS/MNCDS workflow, persists typed result | both / both | bundle/evaluator/workflow errors |

CLI additionally exposes direct `ledger.verify` and validated config location through intentional
public `forge.ledger` and `forge.config` attributes. MCP resources call the same facade methods as
tools. Task 5 therefore preserves `config`, `mode`, `ledger`, and `record_store` as intentional
compatibility attributes.

## Private responsibilities and current dependency seams

| Responsibility | Current methods | Concrete dependencies / issue |
| --- | --- | --- |
| Startup recovery | `__init__`, `_recover_stranded_verifier_actions` | store recovery and semantic terminal-`UNKNOWN` recovery are coordinated in `Forge` |
| Record reads | `_records`, `_record_by_id`, `_result_records`, `_latest_provider_probe` | direct concrete `Ledger` reads are available to all facade behavior |
| Identity/policy observation | `_authority_paths`, `_candidate_paths`, `_current_*`, `_selection_evidence_policy`, `_evidence_envelopes`, `_current_freeze_bindings` | filesystem hashing and policy parsing are mixed with orchestration |
| Lifecycle projection | `_state_machine`, `_verify_freeze` | one authoritative state machine, but its construction is coupled to the facade |
| Provider execution | `_provider_*`, `_record_provider_probe`, `_command_version` | executable resolution and four direct `run_bounded` call sites |
| Workflow execution | `_workflow`, `_provider_workspace`, `_run_workflow`, `_execution_record` | declared-command resolution, workspace copying, subprocess execution, protocol parsing, and record construction are shared inside the facade |
| Claims | `_structured_statuses`, `_extract_statuses`, `_classify_record` | filesystem evidence reporting is unrelated to lifecycle mutation |
| Micro-verifiers | facade verifier methods plus `MicroVerifierService(ForgeHost)` | each call constructs a service that receives a Forge-shaped host; verifier execution calls `run_bounded` directly |

## Pre-refactor structural and failure observations

- `engine.py` contains 1,623 lines and 42 class method definitions.
- Application writes already use `RecordStore.commit`; no source application path manually pairs
  immutable-file publication with ledger append.
- A single Forge instance constructs one `Ledger` and one `RecordStore`, but verifier facade calls
  construct a fresh `MicroVerifierService` wrapper on every invocation.
- The state machine remains the only transition-rule implementation. Extraction must move its
  construction and calls, not reproduce its policy.
- Provider/workflow/verifier application code directly imports the local subprocess function.
- The verifier service depends on a broad Forge-like protocol with configuration, mode, store,
  records, lifecycle, identity, provider, workspace, and freeze methods.
- CLI and MCP both call the facade, so preserving facade signatures and result dictionaries keeps
  interface dispatch aligned without introducing Task 6's operation registry.

## Baseline validation and telemetry

- `PATH="$PWD/.venv/bin:$PATH" ./scripts/check.sh`: formatting, lint, mypy, all 237 tests,
  sdist, and wheel passed.
- 25-iteration benchmark: ledger verification mean 20.664 ms, state inspection mean 9.473 ms,
  verifier explain mean 5.727 ms, verifier run mean 52.508 ms; 54 ledger entries.
- Joern `4.0.583` parsed the exported baseline with Python CFG order-fallback warnings. The focused
  query found five direct `run_bounded` calls, one `LocalRecordStore` construction, ten facade
  commit sites, two verifier commit sites, and lifecycle authorizer calls in facade/verifier
  orchestration. A first receiver-sensitive query clause failed to compile and was narrowed; Joern
  does not establish absence of dynamic call-backs or runtime dependency cycles.
