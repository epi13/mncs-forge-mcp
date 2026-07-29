"""Read-only EdgeStream integration helper used by the example workflow."""

from __future__ import annotations

import json
from pathlib import Path


def inspect(root: Path | None = None) -> dict[str, object]:
    if root is None:
        root = Path.cwd()
    required = [
        "case-studies/edgestream/specification/contract.md",
        "case-studies/edgestream/reference/edgestream_reference.c",
        "case-studies/edgestream/machine/edgestream_generated.c",
        "case-studies/edgestream/preregistration.json",
        "case-studies/edgestream/mncds/development-record.json",
        "case-studies/edgestream/evidence/results/study-summary.json",
    ]
    missing = [value for value in required if not (root / value).is_file()]
    return {
        "status": "PASS" if not missing else "UNKNOWN",
        "method": "read-only-path-inspection",
        "witnesses": [{"visible_file": value} for value in required if value not in missing],
        "limitations": [
            "path visibility is not proof of evidence validity, independence, or protected custody",
            *([f"missing required example path: {value}" for value in missing]),
        ],
        "unsupported_constructs": [
            "independent evaluation",
            "protected holdout",
            "witnessed evidence",
            "governance approval",
        ],
    }


def main() -> int:
    print(json.dumps(inspect(), sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
