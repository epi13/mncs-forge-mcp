"""Focused policy helpers for micro-verifier execution.

These helpers keep deletion identities, batch parameter envelopes, and terminal
UNKNOWN result construction separate from the core matching and provider runner.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .config import Provider, Verifier
from .identity import content_identity, file_identity
from .paths import resolve_contained
from .serialization import local_json_identity
from .verifier_disclosure import redact_status_only_result

BATCH_SHARED_KEY = "shared"
BATCH_BY_VERIFIER_KEY = "by_verifier"
BATCH_PARAMETER_KEYS = {BATCH_SHARED_KEY, BATCH_BY_VERIFIER_KEY}


def changed_path_identity(root: Path, value: str) -> str:
    """Return a stable identity for an existing, deleted, or renamed path.

    Deleted paths cannot be byte-hashed after the change. Their identity therefore
    binds the canonical path and explicit absent state rather than pretending that
    missing bytes were inspected.
    """

    resolved = resolve_contained(root, value, must_exist=False)
    if resolved.is_file():
        return file_identity(resolved)
    if resolved.exists():
        return content_identity(root, [resolved])
    return local_json_identity({"path": value, "state": "absent"})


def resolve_batch_parameters(
    verifier_ids: list[str],
    value: dict[str, object] | None,
) -> tuple[dict[str, object], dict[str, dict[str, object]]]:
    """Resolve backward-compatible shared or per-verifier question parameters."""

    supplied = value or {}
    if not any(key in supplied for key in BATCH_PARAMETER_KEYS):
        return dict(supplied), {}
    unknown = sorted(set(supplied).difference(BATCH_PARAMETER_KEYS))
    if unknown:
        raise ValueError(
            "batch parameter envelope accepts only shared and by_verifier; unknown: "
            + ", ".join(unknown)
        )
    shared_raw = supplied.get(BATCH_SHARED_KEY, {})
    per_raw = supplied.get(BATCH_BY_VERIFIER_KEY, {})
    if not isinstance(shared_raw, dict) or not isinstance(per_raw, dict):
        raise ValueError("batch shared and by_verifier values must be objects")
    unknown_verifiers = sorted(set(per_raw).difference(verifier_ids))
    if unknown_verifiers:
        raise ValueError(
            "batch parameters reference undeclared batch verifier IDs: "
            + ", ".join(unknown_verifiers)
        )
    per: dict[str, dict[str, object]] = {}
    for verifier_id, raw in per_raw.items():
        if not isinstance(verifier_id, str) or not isinstance(raw, dict):
            raise ValueError("each by_verifier entry must map a verifier ID to an object")
        per[verifier_id] = dict(raw)
    return dict(shared_raw), per


def parameters_for_verifier(
    verifier_id: str,
    shared: Mapping[str, object],
    per_verifier: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    """Merge shared parameters with one verifier's explicit override."""

    result = dict(shared)
    result.update(per_verifier.get(verifier_id, {}))
    return result


def terminal_unknown_result(
    *,
    action: Mapping[str, object],
    verifier: Verifier,
    provider: Provider,
    identities: dict[str, str],
    code: str,
    message: str,
    recorded_at: str,
    duration_seconds: float,
) -> dict[str, object]:
    """Build a terminal UNKNOWN for an action that began but could not finish."""

    result: dict[str, object] = {
        "action_id": action["action_id"],
        "verifier_id": verifier.verifier_id,
        "verifier_version": verifier.version,
        "verifier_identity": identities["verifier_identity"],
        "claim": verifier.claim,
        "category": verifier.category,
        "provider_id": provider.provider_id,
        "provider_configuration_identity": identities["provider_configuration_identity"],
        "provider_executable_identity": None,
        "provider_identity": None,
        "provider_response_identity": None,
        "method": verifier.method,
        "mode": action["mode"],
        "evidence_class": (
            "development_evidence"
            if action["mode"] == "development"
            else "local_evaluator_evidence"
        ),
        "independent_evaluation": False,
        "iterative_development_overlap": False,
        "epoch_identity": action["epoch_identity"],
        "candidate_identity": action["candidate_identity"],
        "candidate_parent_identity": action["candidate_parent_identity"],
        "freeze_identity": action["freeze_identity"],
        "supersedes_output_identity": action["supersedes_output_identity"],
        "input_identities": action["input_identities"],
        "configuration_identity": identities["configuration_identity"],
        "policy_identity": identities["policy_identity"],
        "environment_identity": identities["environment_identity"],
        "status": "UNKNOWN",
        "summary": "verifier action ended without a normal provider result",
        "witnesses": [],
        "assumptions": list(verifier.assumptions),
        "limitations": [
            *verifier.limitations,
            f"terminal operational failure {code}: {message}",
        ],
        "unsupported_constructs": ["interrupted-verifier-action"],
        "dependency_envelope": {
            "paths": [],
            "path_identities": {},
            "additional_identities": {},
            "complete": False,
            "identity": None,
        },
        "duration_seconds": round(duration_seconds, 6),
        "stderr_diagnostic": "",
        "returncode": None,
        "operational_error": {"code": code, "message": message},
        "disclosure": verifier.disclosure,
        "recorded_at": recorded_at,
    }
    if action["mode"] == "evaluator" and verifier.disclosure == "status-only":
        redact_status_only_result(result)
    return result


def unrecorded_batch_unknown(verifier_id: str, code: str, message: str) -> dict[str, Any]:
    """Describe a verifier rejected before an immutable action could be created."""

    return {
        "verifier_id": verifier_id,
        "status": "UNKNOWN",
        "recorded": False,
        "summary": "verifier was rejected before action recording",
        "operational_error": {"code": code, "message": message},
        "limitations": [
            "no verifier_action or verifier_result was created because authority or input "
            "validation failed before execution"
        ],
    }
