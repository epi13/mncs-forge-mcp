#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail

repository_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
project_config="${1:-"$repository_root/../machine-native-complexity-standard/mncs-forge.toml"}"
project_config="$(realpath "$project_config")"
server="$repository_root/.venv/bin/mncs-forge-mcp"

test -x "$server"
codex mcp get mncs-forge --json >/dev/null
codex mcp list
"$repository_root/.venv/bin/mncs-forge" --config "$project_config" doctor >/dev/null
"$repository_root/.venv/bin/python" "$repository_root/scripts/mcp-smoke.py" \
  "$server" "$project_config"
