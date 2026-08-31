"""Typed, fail-closed execution-assurance assessments over receipt bindings.

An assessment separates what an execution environment established from any
functional result the program produced. Requested-but-unestablished properties
remain ``UNKNOWN``; identity contradictions are ``FAIL``; a functional ``PASS``
never implies assurance ``PASS``. Assessments are immutable and append-only;
conflicting assessments are retained side by side.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from ..config import ForgeConfig
from ..errors import ForgeError
from ..ports import RecordCommitter, RecordReader
from ..records import (
    ASSURANCE_REQUEST_PROPERTIES,
    ESTABLISHED_PROPERTY_KEYS,
    ExecutionAssuranceRecord,
    RecordType,
    new_record,
)
from .support import now

AssuranceStatus = Literal["PASS", "FAIL", "UNKNOWN"]

_LAUNDERING_RUNNER_KINDS = frozenset({"local-process"})
_CONTAINER_PROPERTIES = ("filesystem_isolation", "network_isolation", "containerization")


def _binding(records: RecordReader, binding_id: str) -> Mapping[str, object]:
    for entry in reversed(records.records("execution_receipt_binding")):
        payload = entry.payload
        if payload.get("binding_id") == binding_id:
            return payload
    raise ForgeError("RECORD_NOT_FOUND", f"no execution receipt binding for {binding_id}")


def _property_map(binding: Mapping[str, object]) -> Mapping[str, object] | None:
    properties = binding.get("established_properties")
    return properties if isinstance(properties, Mapping) else None


def _structural_contradictions(binding: Mapping[str, object]) -> list[str]:
    """Malformed-binding problems that make any assurance claim unreliable."""

    problems: list[str] = []
    properties = _property_map(binding)
    if properties is None:
        return ["execution receipt binding has no established property map"]
    missing = set(ESTABLISHED_PROPERTY_KEYS) - set(properties)
    if missing:
        problems.append("binding property map is incomplete: " + ", ".join(sorted(missing)))
    if binding.get("receipt_completeness") == "complete" and not isinstance(
        binding.get("mncs_receipt"), Mapping
    ):
        problems.append("complete binding is missing its MNCS execution-receipt envelope")
    return problems


def _laundering_contradiction(binding: Mapping[str, object]) -> str | None:
    """Detect isolation claims that contradict the declared runner kind."""

    properties = _property_map(binding)
    runner_kind = binding.get("runner_kind")
    if properties is None or not isinstance(runner_kind, str):
        return None
    if runner_kind in _LAUNDERING_RUNNER_KINDS:
        for key in _CONTAINER_PROPERTIES:
            if properties.get(key) == "established":
                return (
                    f"{key} is claimed established by a {runner_kind} runner, "
                    "which cannot enforce it"
                )
    return None


def assess_execution_receipt(
    *,
    config: ForgeConfig,
    records: RecordReader,
    record_store: RecordCommitter,
    binding_id: str,
    requested_properties: list[str],
    policy_identity: str | None = None,
) -> dict[str, object]:
    """Assess and persist requested execution-assurance properties fail-closed."""

    if not requested_properties:
        raise ForgeError(
            "ASSURANCE_REQUEST", "requested execution-assurance properties cannot be empty"
        )
    if len(set(requested_properties)) != len(requested_properties):
        raise ForgeError(
            "ASSURANCE_REQUEST", "requested execution-assurance properties must be unique"
        )
    invalid = sorted(set(requested_properties) - ASSURANCE_REQUEST_PROPERTIES)
    if invalid:
        raise ForgeError(
            "ASSURANCE_REQUEST",
            "requested properties outside the declared vocabulary: " + ", ".join(invalid),
        )
    binding = _binding(records, binding_id)
    if binding.get("project_identity") != config.project_identity:
        raise ForgeError(
            "RECORD_MISMATCH",
            "execution receipt binding belongs to a different project",
        )
    properties = _property_map(binding)
    if properties is None:
        raise ForgeError("RECORD_MALFORMED", "execution receipt binding has no property map")

    laundering = _laundering_contradiction(binding)
    reasons: list[str] = [*_structural_contradictions(binding)]
    if laundering is not None:
        reasons.append(laundering)
    unmet: list[str] = []
    for key in requested_properties:
        state = properties.get(key)
        if state == "established":
            continue
        unmet.append(key)
        if state == "not-established":
            reasons.append(f"requested property was not established by the runner: {key}")
        elif state == "unknown":
            reasons.append(f"requested property could not be observed: {key}")
        else:
            reasons.append(f"requested property has an unreadable state: {key}")
    if binding.get("receipt_completeness") != "complete":
        reasons.append(
            "the bound execution is incomplete, so no assurance property can be confirmed"
        )
        unmet.extend(key for key in requested_properties if key not in unmet)

    if laundering is not None:
        status: AssuranceStatus = "FAIL"
    elif unmet or reasons:
        status = "UNKNOWN"
    else:
        status = "PASS"

    record = new_record(
        RecordType.EXECUTION_ASSURANCE,
        {
            "project_identity": config.project_identity,
            "candidate_identity": binding["candidate_identity"],
            "binding_identity": binding_id,
            "action_kind": binding["action_kind"],
            "action_identity": binding["action_identity"],
            "requested_properties": list(requested_properties),
            "unmet_properties": unmet,
            "reasons": reasons,
            "assurance_status": status,
            "policy_identity": policy_identity,
            "assessed_at": now(),
        },
    )
    if not isinstance(record, ExecutionAssuranceRecord):
        raise ForgeError("INTERNAL_RECORD", "execution assurance assessment model is invalid")
    record_store.commit("assessments", "execution_assurance", record)
    return summarize_assessment(record)


def summarize_assessment(record: Mapping[str, object]) -> dict[str, object]:
    return {
        "assessment_id": record.get("assessment_id"),
        "binding_identity": record.get("binding_identity"),
        "candidate_identity": record.get("candidate_identity"),
        "action_kind": record.get("action_kind"),
        "requested_properties": record.get("requested_properties"),
        "unmet_properties": record.get("unmet_properties"),
        "assurance_status": record.get("assurance_status"),
        "reasons": record.get("reasons"),
        "policy_identity": record.get("policy_identity"),
        "assessed_at": record.get("assessed_at"),
        "dominance": "FAIL > UNKNOWN > PASS",
        "note": (
            "Execution assurance is separate from the functional result. A PASS result "
            "never implies assurance PASS, and an unmet requested property remains UNKNOWN."
        ),
    }


def list_assessments(
    records: RecordReader,
    *,
    binding_identity: str | None = None,
    candidate_identity: str | None = None,
) -> dict[str, object]:
    assessments: list[dict[str, object]] = []
    for entry in records.records("execution_assurance"):
        payload = entry.payload
        if binding_identity is not None and payload.get("binding_identity") != binding_identity:
            continue
        if (
            candidate_identity is not None
            and payload.get("candidate_identity") != candidate_identity
        ):
            continue
        assessments.append(summarize_assessment(payload))
    return {
        "assessments": assessments,
        "count": len(assessments),
        "vocabulary": sorted(ASSURANCE_REQUEST_PROPERTIES),
        "disagreement_policy": (
            "Assessments are append-only. Conflicting assessments are retained side by "
            "side rather than overwritten or silently resolved."
        ),
    }
