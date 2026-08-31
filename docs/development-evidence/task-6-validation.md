# Task 6 validation evidence

This is operator-controlled development telemetry, not MNCS/MNCDS conformance, independent
evaluation, protected custody, witnessing, certification, governance approval, or promotion.

## Baseline

Baseline revision: merged Task 5 `main` at
`800c23e3becd3c6d0259cb887c1e2fbe7292ae18`.

- `PATH="$PWD/.venv/bin:$PATH" ./scripts/check.sh`: formatting, lint, strict mypy, 247
  tests, sdist, and wheel passed.
- The development MCP server exposed 23 tools and the evaluator server exposed the same inventory
  plus final evaluation. The CLI exposed 27 command leaves.
- The 25-iteration benchmark used 54 ledger entries. Means were 21.225 ms for ledger verify,
  9.340 ms for state inspect, 5.526 ms for verifier explain, and 52.692 ms for verifier run.
- The complete pre-refactor compatibility mapping is in
  [Task 6 dispatch inventory](task-6-dispatch-inventory.md).

## Implemented registry

`operations.py` defines 28 deterministic canonical operations, frozen typed inputs, output
contracts, allowed modes, mutation classes, authority/lifecycle and disclosure metadata, CLI
bindings, MCP tool names/visibility, resources, and exclusion reasons. The additional operation is
the requested machine-readable inventory, exposed as `mncs-forge operations` and
`mncs-forge://operations`.

Argparse retains its command hierarchy and parsing conventions but all 28 leaves bind to registry
IDs and normalize through registry-owned bindings. FastMCP iterates the registry to register 23
development tools or 24 evaluator tools. Generated wrappers preserve the historical callable names
so all baseline tool names and semantic input schemas remain identical. An isolated before/after
comparison found equal development and evaluator ordered tool contracts, including names,
descriptions, input schemas, and output schemas.

MCP resources remain explicit projections. Nine operation-backed baseline resources and the new
inventory resource invoke through the resource gate; the static usage resource and five prompts
remain presentation/guidance. CLI-only diagnostics and resource-only inventory exposure carry
explicit exclusion reasons.

## Architecture and compatibility enforcement

Focused tests cover registry uniqueness/order, callable handlers, frozen input construction,
deterministic inventory serialization, a semantic inventory digest, complete CLI/MCP mappings,
mode and evaluator visibility, mutation metadata, duplicate IDs/names, undocumented asymmetry,
malformed input, interface rejection, pre-handler mode rejection, shared handler invocation, and
continued state-machine authorization. Argparse-tree inspection proves every leaf maps to exactly
one registry definition. In-process FastMCP tests verify both mode inventories, representative
schemas, and structured results; the existing stdio edge-stream tests remain unchanged.

Architecture tests reject direct Forge business calls in `cli.py`/`server.py`, multiple FastMCP
tool registration sites, registry imports of interfaces or concrete adapters, storage/execution/
filesystem identity calls, transition authorization, application dependency inversion, and new
cycles. Application persistence remains through `RecordStore`, and lifecycle policy remains in
`ForgeStateMachine`.

## Joern before/after review

Joern `4.0.583` parsed baseline and final source with the same bounded query:

```bash
joern-parse --language PYTHONSRC <source> --output <task6-cpg>
joern --script scripts/joern/task6-operation-dispatch.sc --param cpgFile=<task6-cpg>
```

The baseline query found 20 direct matched business calls in `cli.py` (excluding four facade method
references) and 33 in `server.py` across tools/resources. The final query found one registry
`invoke` call in CLI and two in MCP (tool and resource adapters), with 25 facade business calls
centralized in typed registry handlers. Existing provider/state-machine defensive mode checks
remain downstream; the common registry gate is visible at all three adapter entry points.

Joern emitted its known Python CFG order-fallback warnings for `try`, `catch`, `continue`, and
`break`. The query establishes bounded static call placement only. Dynamic wrapper schemas,
pre-handler ordering, compatibility, and lifecycle preservation rely on executable tests rather
than graph inference.

## Final validation

- `PATH="$PWD/.venv/bin:$PATH" ./scripts/check.sh`: formatting, lint, strict mypy, 267 tests,
  sdist, and wheel passed.
- Required CLI, MCP, registry, architecture, edge-stream, lifecycle, recovery, ledger, verifier,
  record, and compatibility suites passed.
- An isolated environment installed the built project and ran the minimal `inspect` smoke test.
- Development/evaluator FastMCP construction produced 23/24 tools with only final evaluation added
  in evaluator mode.
- `python -m build` and `git diff --check` passed.

The final 25-iteration benchmark retained 54 ledger entries:

| Operation | Baseline mean | Final mean | Difference |
| --- | ---: | ---: | ---: |
| ledger verify | 21.225 ms | 21.128 ms | -0.46% |
| state inspect | 9.340 ms | 9.170 ms | -1.82% |
| verifier explain | 5.526 ms | 5.586 ms | +1.09% |
| verifier run | 52.692 ms | 52.136 ms | -1.06% |

These small single-host changes are development noise and were not optimized around. Integrity or
validation checks were not removed.

## Intentionally deferred

Task 7 runner receipts and alternate/sandbox-capable adapters remain deferred, as do Forge Cell
runtime isolation, external anchoring, distributed execution, micro-debugging runtime,
intent-aware security runtime, and caching. The registry changes dispatch consistency only; it
does not change evidence authority, execution assurance, custody, witnessing, promotion, or
normative MNCS/MNCDS validation.
