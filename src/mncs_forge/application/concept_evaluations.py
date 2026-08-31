"""Persisted Forge concept evaluations bound to Concept Experiments.

Evaluations stay bounded Forge-native results: they never certify their
generator and never claim MNCS conformance or universal correctness.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from ..concept_experiments import (
    CONCEPT_EVALUATION_INTERPRETATION,
    verify_concept_evaluation,
)
from ..errors import ForgeError
from ..ports import RecordCommitter, RecordReader
from ..records import ForgeRecord, JsonObject, RecordType, new_record
from .support import now


class ConceptEvaluationService:
    """Record, list, and fetch concept evaluations without granting verdict authority."""

    def __init__(self, *, records: RecordReader, record_store: RecordCommitter) -> None:
        self.records = records
        self.record_store = record_store

    def record(self, evaluation: Mapping[str, object]) -> dict[str, object]:
        material = verify_concept_evaluation(evaluation)
        digest = str(evaluation["content_digest"])
        record = new_record(
            RecordType.CONCEPT_EVALUATION,
            {
                "concept_experiment_id": material["concept_experiment_id"],
                "candidate_identity": material["candidate_identity"],
                "language_profile": material["language_profile"],
                "compiler_identity": material["compiler_identity"],
                "backend_identity": material["backend_identity"],
                "execution_identities": material["execution_identities"],
                "verifier_identity": material["verifier_identity"],
                "verifier_version": material["verifier_version"],
                "obligation": material["obligation"],
                "evidence_identities": material["evidence_identities"],
                "status": material["status"],
                "unresolved_obligations": material["unresolved_obligations"],
                "generator_identity": material["generator_identity"],
                "evaluator_policy_identity": material["evaluator_policy_identity"],
                "generator_certified": False,
                "evaluation_material": dict(evaluation),
                "stable_id": evaluation["stable_id"],
                "content_digest": digest,
                "interpretation": CONCEPT_EVALUATION_INTERPRETATION,
                "assurance_status": None,
                "conformance_status": None,
                "recorded_at": now(),
            },
        )
        for entry in self.records.records("concept_evaluation"):
            if entry.payload.get("content_digest") == digest:
                return entry.payload.to_object_dict()
        self.record_store.commit("concept-evaluations", "concept_evaluation", record)
        return record.to_object_dict()

    def list(self) -> dict[str, object]:
        evaluations = [
            self._summary(entry.payload) for entry in self.records.records("concept_evaluation")
        ]
        return {
            "evaluations": evaluations,
            "interpretation": CONCEPT_EVALUATION_INTERPRETATION,
            "assurance_status": None,
            "conformance_status": None,
        }

    def get(self, evaluation_id: str) -> dict[str, object]:
        normalized = evaluation_id.strip()
        for entry in self.records.records("concept_evaluation"):
            payload = entry.payload
            if normalized in {
                str(payload.get("evaluation_id")),
                str(payload.get("content_digest")),
                str(payload.get("stable_id")),
            }:
                return payload.to_object_dict()
        raise ForgeError(
            "CONCEPT_EVALUATION_NOT_FOUND",
            f"unknown concept evaluation: {evaluation_id}",
        )

    @staticmethod
    def _summary(record: ForgeRecord) -> JsonObject:
        material = record.get("evaluation_material")
        projected = material if isinstance(material, Mapping) else {}
        thawed = record.to_json()
        summary: JsonObject = {
            "evaluation_id": thawed["evaluation_id"],
            "stable_id": thawed["stable_id"],
            "content_digest": thawed["content_digest"],
            "concept_experiment_id": thawed["concept_experiment_id"],
            "candidate_identity": thawed["candidate_identity"],
            "language_profile": thawed["language_profile"],
            "compiler_identity": thawed["compiler_identity"],
            "backend_identity": thawed["backend_identity"],
            "execution_identities": thawed["execution_identities"],
            "verifier_identity": thawed["verifier_identity"],
            "obligation": thawed["obligation"],
            "evidence_identities": thawed["evidence_identities"],
            "status": thawed["status"],
            "unresolved_obligations": thawed["unresolved_obligations"],
            "generator_certified": thawed["generator_certified"],
            "recorded_at": thawed["recorded_at"],
            "interpretation": thawed["interpretation"],
            "assurance_status": None,
            "conformance_status": None,
        }
        if not isinstance(projected, Mapping):  # pragma: no cover - validation enforces objects
            raise ForgeError(
                "RECORD_MALFORMED",
                "persisted concept evaluation has malformed material",
            )
        summary["generator_identity"] = cast(JsonObject, projected).get("generator_identity")
        summary["claim_boundary"] = cast(JsonObject, projected).get("claim_boundary")
        return summary
