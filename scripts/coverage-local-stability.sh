#!/usr/bin/env bash
set -euo pipefail

repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repository_root"

PATH="$repository_root/.venv/bin:$PATH" \
  "$repository_root/.venv/bin/python" -m pytest \
  --cov=mncs_forge \
  --cov-branch \
  --cov-report=term-missing \
  tests "$@"
