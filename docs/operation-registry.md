# Canonical Forge operation registry

`mncs_forge.operations` is the machine-readable authority for public Forge operation dispatch.
It contains frozen operation definitions and frozen input models; CLI and MCP adapters provide
presentation, normalize input, and call the same `OperationRegistry.invoke` gate.

```text
argparse / FastMCP
        -> OperationRegistry.resolve + invoke
        -> typed registry handler
        -> Forge compatibility facade
        -> application service
        -> ForgeStateMachine / records / ports
        -> local adapters
```

Every definition records a canonical ID, allowed modes, mutation classification, input model,
output contract, authority and lifecycle requirements, disclosure class, interface names, and
intentional exclusions. Registry mode and interface checks happen before a handler. Lifecycle
authorization remains in `ForgeStateMachine`; metadata describes that boundary without
reimplementing it. Durable writes remain application requests to `RecordStore.commit`.

## Interface boundaries

Argparse layout remains hand tuned so existing nesting, flags, defaults, help, result envelopes,
and exit behavior stay stable. Parser leaves are bound to canonical IDs, and registry-owned CLI
bindings convert namespace names and JSON/dependency syntax into typed input models. There is no
second CLI business dispatch table.

FastMCP tools are registered by iterating the registry. Flat generated call signatures preserve
the existing tool names, required fields, defaults, JSON schemas, descriptions, and structured
results. The final-evaluation tool is visible only when constructing an evaluator-mode server.
Other development operations retain their historical evaluator-server visibility but the common
gate rejects their development-only authority before a handler runs.

MCP resources remain presentation/read-model projections and prompts remain static guidance. An
operation-backed resource declares its URI on the corresponding operation and invokes it through
the resource interface gate before selecting any projected field. The static usage guide and five
prompts are not executable Forge operations.

Intentional asymmetries are explicit:

- `project.doctor`, `config.validate`, and `ledger.verify` remain local CLI diagnostics;
- `operations.inventory` is a CLI operation and MCP resource, not an executable MCP tool; and
- final evaluation remains a CLI command whose development invocation fails closed and an MCP
  tool registered only in evaluator mode.

Compiler evolution adds one explicit asymmetry: `compiler.experiments.record` is a development-only mutation, while `compiler.experiments.list` and `compiler.experiments.compare` are read-only local-storage projections available in both server modes. The list operation owns the `mncs-forge://compiler/experiments` resource projection.

## Machine-readable inventory

Run:

```bash
mncs-forge --config mncs-forge.toml operations
```

or read `mncs-forge://operations`. The deterministic version-1 result lists canonical operation
IDs, modes, mutation class, input/output model identifiers, authority/lifecycle metadata,
disclosure, CLI command paths, MCP tool names and visibility, resource projections, and reasons
for intentional exclusions. It excludes Python callables, object representations, memory
addresses, environment values, and descriptive wording from compatibility-sensitive metadata.

The `0.1.0b1` semantic digest also omits the exact explanatory text for an interface exclusion;
tests require every asymmetry to remain explicitly documented, but do not freeze that prose.

The registry changes dispatch consistency only. It does not add evidence authority, execution
assurance, isolation, independent custody, witnessing, certification, promotion, or normative
MNCS/MNCDS conformance.
