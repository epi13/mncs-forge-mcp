#!/usr/bin/env python3
"""Small Provider Protocol 0.1 fixture."""

from __future__ import annotations

import json
import sys
import time


def main() -> int:
    mode = sys.argv[1]
    request = json.loads(sys.stdin.readline())
    if mode == "TIMEOUT":
        time.sleep(5)
        return 0
    if mode == "MALFORMED":
        print("not-json")
        return 0
    if mode == "OVERSIZE":
        print("x" * 100_000)
        return 0
    identity = "drifted-provider-identity" if mode == "IDENTITY_DRIFT" else f"fake-{mode.lower()}"
    provider = {
        "id": f"fake-{mode.lower()}",
        "name": f"fake-{mode.lower()}",
        "version": "1",
        "identity": identity,
    }
    if request["type"] == "capabilities":
        response = {
            "protocol_version": "0.1",
            "type": "capabilities",
            "provider": provider,
            "analyses": ["bounded-structural"],
            "statuses": ["PASS", "FAIL", "UNKNOWN"],
            "cancellation": False,
            "health_checks": True,
            "extensions": {
                "supported_constructs": ["direct-calls"],
                "unsupported_constructs": ["dynamic-dispatch"],
                "limitations": ["fixture provider"],
            },
        }
        print(json.dumps(response, sort_keys=True, separators=(",", ":")))
        return 0
    response = {
        "protocol_version": "0.1",
        "type": "analysis_response",
        "request_id": request["request_id"],
        "provider": provider,
        "status": "UNKNOWN" if mode == "IDENTITY_DRIFT" else mode,
        "summary": f"fixture {mode}",
        "witnesses": [{"location": "candidate/main.py:1"}] if mode == "FAIL" else [],
        "limitations": ["fixture cannot resolve dynamic behavior"] if mode == "UNKNOWN" else [],
        "extensions": {"unsupported": ["dynamic-dispatch"] if mode == "UNKNOWN" else []},
    }
    print(json.dumps(response, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
