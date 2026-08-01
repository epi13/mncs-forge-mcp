"""Shared result redaction for evaluator status-only verifier records."""

from __future__ import annotations


def redact_status_only_result(result: dict[str, object]) -> None:
    """Remove repair-enabling details before identity, recording, or disclosure."""

    envelope = result.get("dependency_envelope")
    envelope_identity = envelope.get("identity") if isinstance(envelope, dict) else None
    result.update(
        {
            "summary": "status-only evaluator verifier result",
            "witnesses": [],
            "assumptions": [],
            "limitations": ["status-only evaluator disclosure withholds repair-enabling details"],
            "unsupported_constructs": [],
            "dependency_envelope": {
                "paths": [],
                "path_identities": {},
                "additional_identities": {},
                "complete": False,
                "identity": envelope_identity,
            },
            "stderr_diagnostic": "",
            "returncode": None,
            "operational_error": None,
        }
    )
