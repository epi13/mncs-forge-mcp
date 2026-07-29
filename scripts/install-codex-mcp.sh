#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail

repository_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
project_config="${1:-"$repository_root/../machine-native-complexity-standard/mncs-forge.toml"}"
project_config="$(realpath "$project_config")"
venv="$repository_root/.venv"
server="$venv/bin/mncs-forge-mcp"

command -v codex >/dev/null
codex --version
codex mcp --help >/dev/null
add_help="$(codex mcp add --help)"
if [[ "$add_help" != *"-- <COMMAND>..."* ]]; then
  echo "Unsupported Codex MCP add syntax; no configuration was changed." >&2
  exit 2
fi
if [[ ! -f "$project_config" ]]; then
  echo "Forge project configuration does not exist: $project_config" >&2
  exit 2
fi

if [[ ! -x "$venv/bin/python" ]]; then
  python3 -m venv "$venv"
fi
"$venv/bin/python" -m pip install -e "$repository_root"

existing="$(mktemp)"
trap 'rm -f "$existing"' EXIT
if codex mcp get mncs-forge --json >"$existing" 2>/dev/null; then
  if ! "$venv/bin/python" - "$existing" "$server" "$project_config" <<'PY'
import json
import sys
value = json.load(open(sys.argv[1], encoding="utf-8"))
transport = value.get("transport", {})
expected_args = ["--config", sys.argv[3], "--mode", "development"]
raise SystemExit(0 if transport.get("command") == sys.argv[2] and transport.get("args") == expected_args else 1)
PY
  then
    echo "Refusing to replace an unrelated existing MCP registration named mncs-forge." >&2
    exit 3
  fi
else
  codex mcp add mncs-forge -- "$server" --config "$project_config" --mode development
fi

codex mcp list
"$venv/bin/mncs-forge" --config "$project_config" doctor >/dev/null
"$venv/bin/python" "$repository_root/scripts/mcp-smoke.py" "$server" "$project_config"
echo "MNCS Forge is registered. Start a new Codex session before expecting tool discovery."
