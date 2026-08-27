"""Forge-side consumer for identity-bound MNEL specialist shadow results.

Forge intentionally does not import MNEL's model runtime.  It validates the
versioned wire contract, invokes a declared provider through the existing
bounded process boundary, and records measurements that downstream verifier
and policy code can challenge.  The returned object is a shadow observation,
never an evaluator verdict, evidence acceptance, or promotion decision.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .errors import ForgeError
from .execution import run_provider
from .serialization import canonical_bytes

SCHEMA = "mncs-forge-learned-specialist-shadow/0.1"
PROTOCOL = "mnel-recurrent-specialist-provider/0.1"
AUTHORITY = "diagnostic-only"
MAX_ARTIFACT_BYTES = 256 * 1024
MAX_REQUEST_BYTES = 256 * 1024
MAX_RESPONSE_BYTES = 512 * 1024
MAX_QUERIES = 128


class LearnedSpecialistError(ValueError):
    """A malformed, stale, or over-budget learned-specialist exchange."""


def _digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(canonical_bytes(value)).hexdigest()


def _identity(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.startswith("sha256:") or len(value) != 71:
        raise LearnedSpecialistError(f"{label} must be a sha256 identity")
    return value


def _nonempty(value: object, label: str, maximum: int = 512) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise LearnedSpecialistError(f"{label} must be a bounded non-empty string")
    return value


def _reject_authority(value: object) -> None:
    forbidden = {
        "verdict",
        "evaluator_verdict",
        "promotion",
        "promotion_authorized",
        "permission",
        "credentials",
        "trust",
    }
    if isinstance(value, Mapping):
        for key, child in value.items():
            if str(key).lower() in forbidden:
                raise LearnedSpecialistError(f"specialist result contains authority field: {key}")
            _reject_authority(child)
    elif isinstance(value, list):
        for child in value:
            _reject_authority(child)


def validate_artifact(
    artifact: Mapping[str, Any], *, expected_role: str | None = None
) -> dict[str, Any]:
    """Validate the stable MNEL artifact shape without loading its runtime."""

    value = dict(artifact)
    _reject_authority(value)
    if value.get("schema") != "mnel-recurrent-specialist-artifact/0.1":
        raise LearnedSpecialistError("unsupported specialist artifact schema")
    if value.get("provider_abi") != "mnel-specialist-provider-abi/0.1":
        raise LearnedSpecialistError("unsupported specialist provider ABI")
    if expected_role is not None and value.get("target_role") != expected_role:
        raise LearnedSpecialistError("specialist artifact role does not match consumer role")
    for key in (
        "provider_id",
        "target_role",
        "model_identity",
        "generation_identity",
        "calibration_identity",
    ):
        _nonempty(value.get(key), key)
    for key in (
        "model_identity",
        "generation_identity",
        "calibration_identity",
        "training_dataset_identity",
        "training_spec_identity",
        "checkpoint_identity",
    ):
        _identity(value.get(key), key)
    supplied_artifact = value.pop("artifact_identity", None)
    _identity(supplied_artifact, "artifact_identity")
    if _digest(value) != supplied_artifact:
        raise LearnedSpecialistError("specialist artifact identity does not match content")
    envelope = value.get("operating_envelope")
    if not isinstance(envelope, Mapping):
        raise LearnedSpecialistError("specialist operating envelope is missing")
    for key in ("max_iterations", "maximum_context_observations", "maximum_query_abs"):
        if not isinstance(envelope.get(key), int) or envelope[key] < 1:
            raise LearnedSpecialistError(f"operating envelope field is invalid: {key}")
    if envelope["max_iterations"] > 8 or envelope["maximum_context_observations"] > 32:
        raise LearnedSpecialistError("operating envelope exceeds Forge safety ceiling")
    return dict(artifact)


def _validate_response(
    response: Mapping[str, Any], artifact: Mapping[str, Any], request_identity: str
) -> dict[str, Any]:
    value = dict(response)
    _reject_authority(value)
    if value.get("protocol_version") != PROTOCOL or value.get("type") != "inference_response":
        raise LearnedSpecialistError("unsupported specialist inference response")
    if value.get("request_id") != request_identity:
        raise LearnedSpecialistError("specialist response request identity mismatch")
    if value.get("model_identity") != artifact.get("model_identity") or value.get(
        "generation_identity"
    ) != artifact.get("generation_identity"):
        raise LearnedSpecialistError("specialist response artifact identity mismatch")
    if value.get("target_role") != artifact.get("target_role"):
        raise LearnedSpecialistError("specialist response role mismatch")
    results = value.get("results")
    if not isinstance(results, list) or len(results) > MAX_QUERIES:
        raise LearnedSpecialistError("specialist response results are unbounded or malformed")
    supplied = value.pop("response_identity", None)
    _identity(supplied, "response_identity")
    if _digest(value) != supplied:
        raise LearnedSpecialistError("specialist response identity does not match content")
    return dict(response)


def _unknown_shadow(
    *,
    request_identity: str,
    artifact: Mapping[str, Any],
    source_records: Sequence[Mapping[str, Any]],
    reason: str,
    duration_ns: int,
    lineage_identity: str | None,
) -> dict[str, Any]:
    source_ids = [
        str(item.get("record_identity")) for item in source_records if item.get("record_identity")
    ]
    return {
        "schema": SCHEMA,
        "status": "UNKNOWN",
        "request_identity": request_identity,
        "provider_id": artifact.get("provider_id"),
        "model_identity": artifact.get("model_identity"),
        "generation_identity": artifact.get("generation_identity"),
        "calibration_identity": artifact.get("calibration_identity"),
        "operating_envelope": artifact.get("operating_envelope"),
        "source_record_identities": source_ids,
        "selected_source_record_identities": [],
        "source_vs_generated": "source-identities-only",
        "abstained": True,
        "escalation_reason": reason,
        "comparison": {"baseline_selected_source_record_identities": [], "disagreement": True},
        "measurements": {
            "provider_elapsed_ns": duration_ns,
            "context_bytes_avoided": 0,
            "estimated_tokens_avoided": 0,
        },
        "reproducibility": {
            "protocol": PROTOCOL,
            "artifact_identity": artifact.get("artifact_identity"),
            "response_identity": None,
        },
        "lineage_identity": lineage_identity,
        "authority": AUTHORITY,
        "semantics": "Forge-shadow-observation; learned-proposal-only; not-a-verdict",
    }


def invoke_shadow_provider(
    command: Sequence[str],
    artifact: Mapping[str, Any],
    source_records: Sequence[Mapping[str, Any]],
    *,
    context_observations: Sequence[Mapping[str, Any]] = (),
    timeout_seconds: float = 5.0,
    output_bytes: int = MAX_RESPONSE_BYTES,
    lineage_identity: str | None = None,
) -> dict[str, Any]:
    """Invoke a provider and return a Forge shadow observation.

    ``source_records`` contain identities and compact feature inputs.  Forge
    never reconstructs or accepts a generated summary as source evidence.
    """

    if not command or any(not isinstance(item, str) or not item for item in command):
        raise LearnedSpecialistError("provider command must be a non-empty argv")
    if not 0.1 <= timeout_seconds <= 30 or not 1024 <= output_bytes <= MAX_RESPONSE_BYTES:
        raise LearnedSpecialistError("provider invocation limits are outside the Forge envelope")
    checked_artifact = validate_artifact(artifact, expected_role="forge.evidence-relevance")
    if len(canonical_bytes(checked_artifact)) > MAX_ARTIFACT_BYTES:
        raise LearnedSpecialistError("specialist artifact exceeds Forge input ceiling")
    if len(source_records) > MAX_QUERIES:
        raise LearnedSpecialistError("source record batch exceeds Forge query ceiling")
    queries = []
    for record in source_records:
        identity = _nonempty(record.get("record_identity"), "record_identity")
        features = record.get("features")
        if (
            not isinstance(features, list)
            or len(features) != 4
            or any(not isinstance(item, int) for item in features)
        ):
            raise LearnedSpecialistError(
                "source record features are not a four-lane bounded vector"
            )
        queries.append(
            {"query_id": identity, "source_record_identity": identity, "features": features}
        )
    request = {
        "protocol_version": PROTOCOL,
        "type": "infer",
        "request_id": _digest(
            {
                "artifact": checked_artifact.get("artifact_identity"),
                "queries": queries,
                "lineage": lineage_identity,
            }
        ),
        "artifact": checked_artifact,
        "queries": queries,
        "context_observations": list(context_observations),
        "lineage_identity": lineage_identity,
    }
    request_identity = request["request_id"]
    encoded_request = canonical_bytes(request)
    if len(encoded_request) > MAX_REQUEST_BYTES:
        raise LearnedSpecialistError("specialist request exceeds Forge input ceiling")
    started = time.perf_counter_ns()
    try:
        completed = run_provider(
            list(command),
            cwd=Path.cwd(),
            timeout=timeout_seconds,
            output_cap=output_bytes,
            environment=dict(os.environ),
            stdin=encoded_request + b"\n",
        )
    except ForgeError as error:
        return _unknown_shadow(
            request_identity=request_identity,
            artifact=checked_artifact,
            source_records=source_records,
            reason="provider-invocation-failed-or-timed-out",
            duration_ns=time.perf_counter_ns() - started,
            lineage_identity=lineage_identity,
        ) | {"error": str(error)[:256]}
    duration_ns = time.perf_counter_ns() - started
    if completed.returncode != 0:
        return _unknown_shadow(
            request_identity=request_identity,
            artifact=checked_artifact,
            source_records=source_records,
            reason="provider-exit-or-output-limit",
            duration_ns=duration_ns,
            lineage_identity=lineage_identity,
        )
    try:
        response = json.loads(completed.stdout)
        checked_response = _validate_response(response, checked_artifact, request_identity)
    except (json.JSONDecodeError, LearnedSpecialistError) as error:
        return _unknown_shadow(
            request_identity=request_identity,
            artifact=checked_artifact,
            source_records=source_records,
            reason="provider-response-invalid-or-stale",
            duration_ns=duration_ns,
            lineage_identity=lineage_identity,
        ) | {"error": str(error)[:256]}
    return build_evidence_relevance_shadow(
        artifact=checked_artifact,
        request_identity=request_identity,
        response=checked_response,
        source_records=source_records,
        duration_ns=duration_ns,
        lineage_identity=lineage_identity,
    )


def build_evidence_relevance_shadow(
    *,
    artifact: Mapping[str, Any],
    request_identity: str,
    response: Mapping[str, Any],
    source_records: Sequence[Mapping[str, Any]],
    duration_ns: int,
    lineage_identity: str | None = None,
) -> dict[str, Any]:
    """Compare provider proposals with a deterministic source-record baseline."""

    checked_artifact = validate_artifact(artifact, expected_role="forge.evidence-relevance")
    checked_response = _validate_response(response, checked_artifact, request_identity)
    results = checked_response["results"]
    if len(results) != len(source_records):
        raise LearnedSpecialistError("specialist result count does not match source records")
    source_ids: list[str] = []
    selected_ids: list[str] = []
    baseline_ids: list[str] = []
    abstentions = 0
    correct_abstentions = 0
    confidence_values: list[float] = []
    iterations: list[int] = []
    operations: list[int] = []
    for record, result in zip(source_records, results, strict=True):
        identity = _nonempty(record.get("record_identity"), "record_identity")
        source_ids.append(identity)
        if bool(record.get("baseline_relevant")):
            baseline_ids.append(identity)
        if not isinstance(result, Mapping):
            raise LearnedSpecialistError("specialist result must be an object")
        result_sources = result.get("source_observation_identities")
        if not isinstance(result_sources, list) or identity not in result_sources:
            raise LearnedSpecialistError("specialist result lost source record identity")
        decision = result.get("decision")
        abstained = bool(result.get("abstained"))
        if abstained:
            abstentions += 1
            if bool(record.get("novel")):
                correct_abstentions += 1
        elif decision == "relevant":
            selected_ids.append(identity)
        confidence = result.get("confidence")
        if isinstance(confidence, (int, float)):
            confidence_values.append(float(confidence))
        iterations.append(int(result.get("reasoning_iterations", 0)))
        operations.append(int(result.get("operations", 0)))
    baseline_set = set(baseline_ids)
    selected_set = set(selected_ids)
    relevant_recall = len(selected_set & baseline_set) / len(baseline_set) if baseline_set else 1.0
    false_omissions = sorted(baseline_set - selected_set)
    context_available = sum(int(record.get("source_bytes", 0)) for record in source_records)
    context_selected = sum(
        int(record.get("source_bytes", 0))
        for record in source_records
        if record.get("record_identity") in selected_set
    )
    expected_abstentions = sum(bool(record.get("novel")) for record in source_records)
    return {
        "schema": SCHEMA,
        "status": "OBSERVED",
        "request_identity": request_identity,
        "provider_id": checked_artifact["provider_id"],
        "model_identity": checked_artifact["model_identity"],
        "generation_identity": checked_artifact["generation_identity"],
        "calibration_identity": checked_artifact["calibration_identity"],
        "operating_envelope": checked_artifact["operating_envelope"],
        "lineage_identity": lineage_identity,
        "source_record_identities": source_ids,
        "selected_source_record_identities": selected_ids,
        "source_vs_generated": "selected-identities-are-source-records; no-generated-summary",
        "confidence": min(confidence_values) if confidence_values else 0.0,
        "abstained": abstentions > 0,
        "abstention_count": abstentions,
        "escalation_reason": "novel-or-low-confidence-records" if abstentions else None,
        "comparison": {
            "baseline_selected_source_record_identities": baseline_ids,
            "relevant_evidence_recall": relevant_recall,
            "false_omitted_source_record_identities": false_omissions,
            "abstention_correctness": correct_abstentions / expected_abstentions
            if expected_abstentions
            else 1.0,
            "disagreement": selected_set != baseline_set or abstentions > 0,
        },
        "measurements": {
            "source_records_available": len(source_records),
            "source_records_selected": len(selected_ids),
            "context_bytes_available": context_available,
            "context_bytes_selected": context_selected,
            "context_bytes_avoided": max(0, context_available - context_selected),
            "estimated_tokens_avoided": max(0, context_available - context_selected) // 4,
            "provider_elapsed_ns": duration_ns,
            "reasoning_iterations": iterations,
            "provider_operations": operations,
        },
        "reproducibility": {
            "protocol": PROTOCOL,
            "artifact_identity": checked_artifact.get("artifact_identity"),
            "response_identity": checked_response.get("response_identity"),
            "input_identity": _digest({"source_record_identities": source_ids}),
        },
        "authority": AUTHORITY,
        "semantics": "Forge-shadow-observation; learned-proposal-only; not-a-verdict",
        "limitations": [
            (
                "source identities and baseline comparison are retained; generated summaries "
                "are not evidence"
            ),
            (
                "shadow agreement and recall are bounded measurements, not correctness or "
                "promotion evidence"
            ),
            "Forge verifier, policy, and evaluator authority remain independent",
        ],
    }


def read_artifact(path: str | Path) -> dict[str, Any]:
    payload = Path(path).read_bytes()
    if len(payload) > MAX_ARTIFACT_BYTES:
        raise LearnedSpecialistError("specialist artifact exceeds Forge input ceiling")
    try:
        value = json.loads(payload)
    except json.JSONDecodeError as error:
        raise LearnedSpecialistError("specialist artifact is not JSON") from error
    return validate_artifact(value)


__all__ = [
    "AUTHORITY",
    "LearnedSpecialistError",
    "build_evidence_relevance_shadow",
    "invoke_shadow_provider",
    "read_artifact",
    "validate_artifact",
]
