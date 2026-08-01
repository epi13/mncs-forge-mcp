# Codex CLI integration

The installer inspects the locally installed `codex mcp add --help`, uses the supported command,
creates or reuses `.venv`, performs an editable install, refuses to overwrite an unrelated
`mncs-forge` registration, registers an absolute stdio executable/config path, lists the
registration, runs `doctor`, and performs an MCP initialize/list-tools/inspection smoke.

```bash
./scripts/install-codex-mcp.sh /absolute/project/mncs-forge.toml
./scripts/verify-codex-mcp.sh /absolute/project/mncs-forge.toml
codex mcp get mncs-forge --json
```

The supported registration is equivalent to:

```bash
codex mcp add mncs-forge -- \
  /absolute/forge/.venv/bin/mncs-forge-mcp \
  --config /absolute/project/mncs-forge.toml --mode development
```

Start a new Codex session before expecting discovery. Uninstall:

```bash
./scripts/uninstall-codex-mcp.sh
```

The uninstaller removes only a registration whose command resolves to this checkout.

The development registration exposes provider discovery and declared development workflows but
does not expose final evaluation. Start evaluator mode as a separate deliberately configured
stdio process only after freeze; never add evaluator mode to the development registration.
