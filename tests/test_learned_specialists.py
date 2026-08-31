from __future__ import annotations

import hashlib
from typing import Any

import pytest

from mncs_forge.learned_specialists import (
    LearnedSpecialistError,
    build_evidence_relevance_shadow,
    invoke_shadow_provider,
    validate_artifact,
)
from mncs_forge.serialization import canonical_bytes


def digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(canonical_bytes(value)).hexdigest()


def artifact() -> dict[str, Any]:
    value: dict[str, Any] = {
        "schema": "mnel-recurrent-specialist-artifact/0.1",
        "provider_id": "mnel-bounded-recurrent-specialist/0.1",
        "provider_abi": "mnel-specialist-provider-abi/0.1",
        "target_role": "forge.evidence-relevance",
        "generation_identity": digest("g0"),
        "architecture_identity": digest("architecture"),
        "training_code_identity": digest("training"),
        "training_dataset_identity": digest("dataset"),
        "training_spec_identity": digest("spec"),
        "checkpoint_identity": digest("checkpoint"),
        "calibration_identity": digest("calibration"),
        "operating_envelope": {
            "max_iterations": 4,
            "minimum_confidence": 600,
            "maximum_distance": 700,
            "convergence_delta": 2,
            "maximum_context_observations": 32,
            "maximum_query_abs": 1000,
            "envelope_identity": digest("envelope"),
        },
        "class_centroids": {"relevant": [800, 800, 800, 800], "irrelevant": [100, 100, 100, 100]},
        "training_record_ids": ["train-1"],
        "source_evidence_references": ["train-1"],
        "parent_model_identity": None,
        "negative_memory": ["never-certify"],
        "inherited_strategies": [],
        "known_counterexamples": [],
        "prior_failure_causes": [],
        "authority": "diagnostic-only",
        "semantics": "identity-bound-learned-specialist; diagnostic-only; not-a-verdict",
    }
    value["model_identity"] = digest(value)
    value["artifact_identity"] = digest(value)
    return value


def response_for(request_identity: str) -> dict[str, Any]:
    value: dict[str, Any] = {
        "protocol_version": "mnel-recurrent-specialist-provider/0.1",
        "type": "inference_response",
        "request_id": request_identity,
        "provider": {
            "id": "mnel-bounded-recurrent-specialist",
            "identity": "provider-v1",
            "version": "0.1",
        },
        "provider_abi": "mnel-specialist-provider-abi/0.1",
        "model_identity": artifact()["model_identity"],
        "generation_identity": artifact()["generation_identity"],
        "target_role": "forge.evidence-relevance",
        "results": [
            {
                "source_observation_identities": ["source-important"],
                "decision": "relevant",
                "abstained": False,
                "confidence": 0.9,
                "reasoning_iterations": 1,
                "operations": 17,
            },
            {
                "source_observation_identities": ["source-novel"],
                "decision": "ABSTAIN",
                "abstained": True,
                "confidence": 0.5,
                "reasoning_iterations": 4,
                "operations": 65,
            },
        ],
        "authority": "diagnostic-only",
        "semantics": "bounded-recurrent-structured-decisions; not-a-verdict",
    }
    value["response_identity"] = digest(value)
    return value


def test_shadow_preserves_source_identity_and_measures_omissions() -> None:
    value = artifact()
    request_identity = digest({"request": "evidence"})
    result = build_evidence_relevance_shadow(
        artifact=value,
        request_identity=request_identity,
        response=response_for(request_identity),
        source_records=[
            {
                "record_identity": "source-important",
                "features": [800, 800, 800, 800],
                "baseline_relevant": True,
                "source_bytes": 1000,
            },
            {
                "record_identity": "source-novel",
                "features": [500, 500, 500, 500],
                "baseline_relevant": True,
                "novel": True,
                "source_bytes": 3000,
            },
        ],
        duration_ns=10,
        lineage_identity=digest("lineage"),
    )
    assert result["status"] == "OBSERVED"
    assert result["source_record_identities"] == ["source-important", "source-novel"]
    assert result["selected_source_record_identities"] == ["source-important"]
    assert result["comparison"]["false_omitted_source_record_identities"] == ["source-novel"]
    assert result["comparison"]["abstention_correctness"] == 1.0
    assert result["measurements"]["context_bytes_avoided"] == 3000
    assert result["authority"] == "diagnostic-only"
    assert "verdict" not in result


def test_stale_or_wrong_role_artifacts_are_refused() -> None:
    value = artifact()
    broken = dict(value)
    broken["class_centroids"] = {"relevant": [801, 800, 800, 800]}
    with pytest.raises(LearnedSpecialistError):
        validate_artifact(broken, expected_role="forge.evidence-relevance")
    with pytest.raises(LearnedSpecialistError):
        validate_artifact(value, expected_role="control.tool-family-routing")


def test_response_identity_and_source_binding_are_checked() -> None:
    value = artifact()
    request_identity = digest({"request": "evidence"})
    response = response_for(request_identity)
    response["results"][0]["source_observation_identities"] = ["other-source"]
    response["response_identity"] = digest(
        {key: item for key, item in response.items() if key != "response_identity"}
    )
    with pytest.raises(LearnedSpecialistError):
        build_evidence_relevance_shadow(
            artifact=value,
            request_identity=request_identity,
            response=response,
            source_records=[
                {
                    "record_identity": "source-important",
                    "features": [800, 800, 800, 800],
                    "baseline_relevant": True,
                },
                {
                    "record_identity": "source-novel",
                    "features": [500, 500, 500, 500],
                    "baseline_relevant": True,
                    "novel": True,
                },
            ],
            duration_ns=1,
        )


def test_provider_failure_preserves_lineage_reference_as_unknown() -> None:
    result = invoke_shadow_provider(
        ["provider-that-is-not-installed"],
        artifact(),
        [{"record_identity": "source-important", "features": [800, 800, 800, 800]}],
        lineage_identity=digest("lineage"),
    )
    assert result["status"] == "UNKNOWN"
    assert result["lineage_identity"] == digest("lineage")
    assert result["authority"] == "diagnostic-only"
