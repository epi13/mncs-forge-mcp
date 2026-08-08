# Task 5 validation evidence

This is operator-controlled development telemetry, not MNCS/MNCDS conformance, independent
evaluation, protected custody, witnessing, certification, governance approval, or promotion.

## Baseline

Baseline revision: merged Task 4 `main` at `edb29da70927e1484a636d2a588407430f243b21`.

- `PATH="$PWD/.venv/bin:$PATH" ./scripts/check.sh`: formatting, lint, mypy, 237 tests,
  sdist, and wheel passed.
- The 25-iteration benchmark used 54 ledger entries. Means were 20.664 ms for ledger verify,
  9.473 ms for state inspect, 5.727 ms for verifier explain, and 52.508 ms for verifier run.
- `engine.py` contained 1,623 lines and 42 source-level class method definitions. See the full
  pre-refactor compatibility matrix in
  [Task 5 Forge inventory](task-5-forge-inventory.md).

## Implemented boundaries

`Forge` is a 358-line compatibility/composition facade. One instance shares one `Ledger`, one
transactional `RecordStore`, one `LifecycleContext`, one `LocalProjectObserver`, and one
`LocalCommandExecutor` across project, provider, candidate/selection, development-workflow,
evaluation, evidence/bundle, recovery, and micro-verifier services.

`ports.py` defines narrow structural protocols for verified record reads, transactional commits,
bounded command execution, project/filesystem observation, and verifier catalog presentation. The
local adapter preserves the existing `run_bounded`, filesystem identity, executable resolution,
and copied-workspace behavior. It adds no Task 7 runner receipt, sandbox, container, SSH, network,
mount, or attestation semantics.

`MicroVerifierService` remains singular. It no longer imports or receives `Forge`; it receives the
same records, commit, lifecycle, observation, and execution collaborators as other services.
Startup `RecoveryService` preserves the distinction between storage recovery and terminal
`UNKNOWN` recovery for stranded durable verifier actions.

## Architecture enforcement

`tests/test_architecture.py` parses imports and constructors to reject:

- application-to-CLI, MCP, facade, or concrete-adapter imports;
- domain imports of interfaces or concrete storage/execution adapters;
- a service constructor parameter named `forge`;
- service calls to `run_bounded` or imports of concrete filesystem identity functions;
- application construction of `LocalRecordStore` or direct ledger/immutable write bypasses; and
- statically detectable cycles among the new application modules.

Direct service tests construct `CandidateService` and `ProviderService` without `Forge`, verify
state-machine authorization and transactional commits, and observe execution through an injected
recording executor. Facade characterization tests preserve representative signatures and public
JSON-compatible result structures. Existing engine, state-machine, CLI/MCP, verifier, recovery,
record, ledger, and legacy-compatibility suites remain the broader behavior contract.

## Joern before/after review

Joern `4.0.583` parsed both snapshots with the same bounded query:

```bash
joern-parse --language PYTHONSRC <source> --output <task5-cpg>
joern --script scripts/joern/task5-service-boundaries.sc --param cpgFile=<task5-cpg>
```

The baseline source was exported from `origin/main`; the post source was the final worktree. The
query reported 56 named non-synthetic methods in `engine.py` before and 36 after. Direct
`run_bounded` calls changed from four in `engine.py` plus one in `micro_verifiers.py` to one in
`adapters.py`. `LocalRecordStore` construction remained only in the facade composition root.
`ForgeStateMachine` construction moved from `engine.py` to `application/lifecycle.py`. Record commit
sites moved to their owning application services, while the two verifier action/result commit sites
remained in the singular verifier service.

The first attempted receiver-sensitive service-to-engine query did not compile against this Joern
API and was narrowed to bounded file/method/call-name reporting. Joern also emitted Python CFG
order-fallback warnings for `try`, `catch`, `continue`, and `break`. The graph establishes the
reported static call placement only; runtime dependency absence, behavior equivalence, and storage
correctness rely on architecture, characterization, lifecycle, recovery, and full-suite tests.

## Final validation

- `PATH="$PWD/.venv/bin:$PATH" ./scripts/check.sh`: formatting, lint, strict mypy, 247 tests,
  sdist, and wheel passed.
- Required architecture; state-machine/engine/CLI-MCP; record-store/recovery/ledger;
  micro-verifier/hardening; records/compatibility; service/facade focused suites passed.
- An isolated virtual environment successfully installed `.` and ran
  `mncs-forge --config examples/minimal/mncs-forge.toml inspect`.
- `git diff --check` passed.

The final 25-iteration benchmark retained 54 ledger entries:

| Operation | Baseline mean | Final mean | Difference |
| --- | ---: | ---: | ---: |
| ledger verify | 20.664 ms | 20.862 ms | +0.96% |
| state inspect | 9.473 ms | 9.758 ms | +3.01% |
| verifier explain | 5.727 ms | 5.880 ms | +2.68% |
| verifier run | 52.508 ms | 52.524 ms | +0.03% |

These small single-host differences were not treated as material regressions or optimized around.
The benchmark is non-normative development telemetry using the minimal example provider.

## Intentionally deferred

Task 6's typed operation registry and generated/shared CLI-MCP dispatch were not introduced. Task
7's full runner abstraction, capability receipts, sandbox policies, and alternate execution
backends were not introduced. Record schemas, migrations, lifecycle policy, transactional storage,
legacy fixture bytes, CLI commands, MCP tools/resources, Provider Protocol, evidence precedence,
and authority/claim boundaries are unchanged.
