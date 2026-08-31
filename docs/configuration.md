# Configuration

`mncs-forge.toml` is validated against
[`schemas/mncs-forge-config.schema.json`](../schemas/mncs-forge-config.schema.json). It declares
project identity/root, candidate/generated/contract/reference/evaluator/policy/evidence/protected
paths, output paths, limits, environment allowlist, optional MNCS/MNCDS commands, development and
evaluator authority, selection/objective references, providers, and workflows.

A provider can declare name, identity/version, argv command, `stdio-jsonl` transport,
capabilities, required/optional status, supported and unsupported constructs, limitations,
expected executable SHA-256 identity, descriptor, allowlisted environment overrides,
`python_packages`, and `module_roots`.

`module_roots` is the named **family module roots** mechanism
(`mncs-forge.family-module-roots.v0.1`). Conventional provider isolation cannot
see undeclared sibling checkouts. A declared root may walk to a sibling under
the workspace parent of the Forge project; Forge resolves it, rejects escapes
and missing directories, injects it into that provider's `PYTHONPATH`, and
records a module-root observation identity on probe/execution evidence. This
is not a silent `sys.path` insertion and is not package attestation.
`python_packages` names importable packages that must be visible through those
roots or the selected interpreter before a probe is treated as available.
`required_capabilities` declares project capability policy. Providers are absent and optional by
default; the configuration never infers a provider from PATH.

Optional `[[verifiers]]` declarations bind a stable verifier ID/version and narrow claim to an
existing Provider Protocol workflow, provider capability/method, category, modes, supported
language/artifact/scope metadata, accepted input kinds, limitations, assumptions, timeout, cost,
matching classes/tags, question-parameter keys, and disclosure. They cannot declare commands or
environment. Verifier category, command, provider, mode, timeout, and disclosure may only retain
or narrow the referenced workflow/provider authority.

Optional `[verifier_limits]` bounds batch count, request bytes, total batch duration, witness,
stderr, and result bytes, changed paths, dependency identities, and question parameters.
Defaults are conservative and existing configurations without verifiers remain valid. See the
[minimal example](../examples/minimal/mncs-forge.toml) and
[micro-verifier guide](micro-verifiers.md).

All project paths are relative to the configured root. Absolute paths, `..`, NULs, symlink escape,
and protected/writable overlap are rejected. Every command is a non-empty argument array. Forge
never uses `shell=True` and has no arbitrary shell MCP tool.

Provider workflows must repeat a command declared in `[[providers]]`. Ordinary inspection does
not execute providers. Workflow mode and category are checked on every invocation. Environment
values are inherited only for explicitly allowlisted keys and are never returned by inspection.
An explicit probe uses the project timeout/output limits, a dedicated temporary working
directory, no shell, strict Provider Protocol framing, and executable/provider identity checks.

Workflows default to `subject = "candidate"`. Project tooling may use `subject = "project"` so
declared checks work in a fresh checkout without mutable candidate ledger state.

See [`examples/minimal`](../examples/minimal) and the
[EdgeStream template](../examples/edgestream/mncs-forge.toml).

The version-1 schema is the explicit compatibility contract; Forge does not introduce a second
configuration-version mechanism for `0.1.0b1`. Unknown sections, missing required fields, and an
unsupported `version` fail with `CONFIG_INVALID`. Malformed TOML also fails with
`CONFIG_INVALID`, while a missing or unreadable file fails with `CONFIG_READ`. Defaults and the
schema's semantic validation digest are frozen by the
[`0.1.0b1` compatibility boundary](compatibility-boundary-0.1.0b1.md).
