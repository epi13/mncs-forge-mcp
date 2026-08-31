# Codex CLI integration

The installer inspects the locally installed `codex mcp add --help`, uses the supported command,
creates or reuses `.venv`, performs an editable install, refuses to overwrite an unrelated
`mncs-forge` registration, registers the checked-in absolute `scripts/codex-mcp` stdio wrapper,
lists the registration, runs `doctor`, and performs a real MCP initialize/list-tools/inspection
health probe. The default project configuration is the empirical configuration owned by
`mncs-reference-studies`; pass another project configuration explicitly when working on one.

```bash
./scripts/install-codex-mcp.sh
./scripts/verify-codex-mcp.sh
codex mcp get mncs-forge --json
```

The supported registration is equivalent to:

```bash
codex mcp add mncs-forge -- \
  /absolute/forge/scripts/codex-mcp \
  --config /absolute/mncs-reference-studies/mncs-forge.toml --mode development
```

The wrapper does not activate a shell or depend on `$PWD`; it resolves the Forge checkout and
executes `python -m mncs_forge.server` through the checkout's `.venv/bin/python`. This avoids
host-absolute shebangs in generated entry points when the checkout is mounted at `/workspace`
inside the MNCS Control Bubblewrap sandbox. Missing or non-executable environments fail with a
remediation message on stderr. `scripts/mcp-health.py` distinguishes missing config,
missing/start-failing executable, MCP initialization failure, missing required tools, and a
healthy Forge path:

```bash
./scripts/verify-codex-mcp.sh
```

The standards repository intentionally no longer owns a root `mncs-forge.toml`; migration of
empirical studies moved that configuration to `mncs-reference-studies`. A stale reference to
`machine-native-complexity-standard/mncs-forge.toml` causes Forge to exit before MCP initialize.

Start a new Codex session before expecting discovery. Uninstall:

```bash
./scripts/uninstall-codex-mcp.sh
```

The uninstaller removes only a registration whose command resolves to this checkout.

The development registration exposes provider discovery and declared development workflows but
does not expose final evaluation. Start evaluator mode as a separate deliberately configured
stdio process only after freeze; never add evaluator mode to the development registration.
