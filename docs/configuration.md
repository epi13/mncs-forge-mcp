# Configuration

`mncs-forge.toml` is validated against
[`schemas/mncs-forge-config.schema.json`](../schemas/mncs-forge-config.schema.json). It declares
project identity/root, candidate/generated/contract/reference/evaluator/policy/evidence/protected
paths, output paths, limits, environment allowlist, optional MNCS/MNCDS commands, development and
evaluator authority, selection/objective references, providers, and workflows.

All project paths are relative to the configured root. Absolute paths, `..`, NULs, symlink escape,
and protected/writable overlap are rejected. Every command is a non-empty argument array. Forge
never uses `shell=True` and has no arbitrary shell MCP tool.

Provider workflows must repeat a command declared in `[[providers]]`. Ordinary inspection does
not execute providers. Workflow mode and category are checked on every invocation. Environment
values are inherited only for explicitly allowlisted keys and are never returned by inspection.

See [`examples/minimal`](../examples/minimal) and the
[EdgeStream template](../examples/edgestream/mncs-forge.toml).
