#!/usr/bin/env python3
"""Small Provider Protocol 0.1 fixture."""

from __future__ import annotations

import json
import sys


def main() -> int:
    mode = sys.argv[1]
    request = json.loads(sys.stdin.readline())
    if mode == "MALFORMED":
        print("not-json")
        return 0
    if mode == "OVERSIZE":
        print("x" * 100_000)
        return 0
    response = {
        "protocol_version": "0.1",
        "type": "analysis_response",
        "request_id": request["request_id"],
        "provider": {"id": f"fake-{mode.lower()}", "version": "1"},
        "status": mode,
        "summary": f"fixture {mode}",
        "witnesses": [{"location": "candidate/main.py:1"}] if mode == "FAIL" else [],
        "limitations": ["fixture cannot resolve dynamic behavior"] if mode == "UNKNOWN" else [],
        "extensions": {"unsupported": ["dynamic-dispatch"] if mode == "UNKNOWN" else []},
    }
    print(json.dumps(response, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
