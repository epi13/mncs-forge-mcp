"""Compiler-search candidates isolated from language correctness authority."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..errors import ForgeError
from ..ports import RecordCommitter, RecordReader
from ..records import ForgeRecord, RecordType, new_record
from .support import now

SEARCH_ONLY_INTERPRETATION = "search_observation_not_language_correctness"
UNVALIDATED = "UNVALIDATED"
PASS = "PASS"
FAIL = "FAIL"
UNKNOWN = "UNKNOWN"
ACCEPT = "accept"
REJECT = "reject"
RETAIN_UNRESOLVED = "retain_unresolved"


class CompilerCandidateService:
    """Record and tournament compiler candidates without granting verdict authority."""

    def __init__(self, *, records: RecordReader, record_store: RecordCommitter) -> None:
        self.records = records
        self.record_store = record_store

    def register(
        self,
        *,
        baseline_artifact_identity: str,
        candidate_artifact_identity: str,
        generator_identity: str,
        declared_transformation: str,
        claimed_relation: str,
        expected_benefit: str,
        protected_properties: list[str],
        target_envelope: str,
        required_validation: str,
    ) -> dict[str, object]:
        if baseline_artifact_identity == candidate_artifact_identity:
            raise ForgeError(
                "COMPILER_CANDIDATE_NOT_ISOLATED",
                "a compiler candidate cannot share the trusted baseline artifact identity",
            )
        record = new_record(
            RecordType.COMPILER_CANDIDATE,
            {
                "baseline_artifact_identity": baseline_artifact_identity,
                "candidate_artifact_identity": candidate_artifact_identity,
                "generator_identity": generator_identity,
                "declared_transformation": declared_transformation,
                "claimed_relation": claimed_relation,
                "expected_benefit": expected_benefit,
                "protected_properties": sorted(protected_properties),
                "target_envelope": target_envelope,
                "required_validation": required_validation,
                "semantic_status": UNVALIDATED,
                "benchmark_observation": None,
                "validation": None,
                "policy_disposition": RETAIN_UNRESOLVED,
                "isolated": True,
                "generator_certified": False,
                "interpretation": SEARCH_ONLY_INTERPRETATION,
                "assurance_status": None,
                "conformance_status": None,
                "recorded_at": now(),
            },
        )
        for entry in self.records.records("compiler_candidate"):
            if entry.payload.get("candidate_id") == record.get("candidate_id"):
                return entry.payload.to_object_dict()
        self.record_store.commit("compiler-candidates", "compiler_candidate", record)
        return record.to_object_dict()

    def inventory(self) -> dict[str, object]:
        return {
            "candidates": [
                self._summary(entry.payload) for entry in self.records.records("compiler_candidate")
            ],
            "interpretation": SEARCH_ONLY_INTERPRETATION,
            "assurance_status": None,
            "conformance_status": None,
        }

    def compare(self, left_candidate_id: str, right_candidate_id: str) -> dict[str, object]:
        left = self._get(left_candidate_id)
        right = self._get(right_candidate_id)
        return {
            "left": self._summary(left),
            "right": self._summary(right),
            "same_baseline": left["baseline_artifact_identity"]
            == right["baseline_artifact_identity"],
            "same_target_envelope": left["target_envelope"] == right["target_envelope"],
            "semantic_statuses": {
                "left": left["semantic_status"],
                "right": right["semantic_status"],
            },
            "benchmark_observations": {
                "left": left["benchmark_observation"],
                "right": right["benchmark_observation"],
            },
            "interpretation": SEARCH_ONLY_INTERPRETATION,
            "note": (
                "benchmark observations cannot authorize a semantically failed or unknown candidate"
            ),
            "assurance_status": None,
            "conformance_status": None,
        }

    def attach_validation(
        self,
        candidate_id: str,
        *,
        validator_identity: str,
        judgement: str,
        claimed_relation: str,
        counterexample: dict[str, object] | None = None,
        limitations: list[str] | None = None,
        stale: bool = False,
    ) -> dict[str, object]:
        if judgement not in {PASS, FAIL, UNKNOWN}:
            raise ForgeError(
                "COMPILER_VALIDATION_STATUS",
                "compiler candidate validation must be PASS, FAIL, or UNKNOWN",
            )
        current = self._get(candidate_id)
        if current["generator_certified"] is not False:
            raise ForgeError(
                "RECORD_AUTHORITY",
                "a generator cannot certify its own compiler candidate",
            )
        semantic_status = UNKNOWN if stale else judgement
        if stale:
            judgement = UNKNOWN
        validation: dict[str, Any] = {
            "validator_identity": validator_identity,
            "judgement": judgement,
            "claimed_relation": claimed_relation,
            "counterexample": counterexample,
            "limitations": limitations or [],
            "freshness": "stale" if stale else "current",
            "independent_of_generator": True,
        }
        disposition = self._disposition(
            semantic_status,
            str(current["required_validation"]),
            current["benchmark_observation"],
        )
        record = new_record(
            RecordType.COMPILER_CANDIDATE,
            {
                **{
                    key: current[key]
                    for key in (
                        "baseline_artifact_identity",
                        "candidate_artifact_identity",
                        "generator_identity",
                        "declared_transformation",
                        "claimed_relation",
                        "expected_benefit",
                        "protected_properties",
                        "target_envelope",
                        "required_validation",
                        "isolated",
                        "generator_certified",
                        "interpretation",
                        "assurance_status",
                        "conformance_status",
                    )
                },
                "semantic_status": semantic_status,
                "benchmark_observation": current["benchmark_observation"],
                "validation": validation,
                "policy_disposition": disposition,
                "recorded_at": now(),
            },
        )
        self.record_store.commit("compiler-candidates", "compiler_candidate", record)
        return record.to_object_dict()

    def attach_benchmark(
        self, candidate_id: str, observation: Mapping[str, object]
    ) -> dict[str, object]:
        current = self._get(candidate_id)
        record = new_record(
            RecordType.COMPILER_CANDIDATE,
            {
                "baseline_artifact_identity": current["baseline_artifact_identity"],
                "candidate_artifact_identity": current["candidate_artifact_identity"],
                "generator_identity": current["generator_identity"],
                "declared_transformation": current["declared_transformation"],
                "claimed_relation": current["claimed_relation"],
                "expected_benefit": current["expected_benefit"],
                "protected_properties": CompilerCandidateService._string_list(
                    current["protected_properties"]
                ),
                "target_envelope": current["target_envelope"],
                "required_validation": current["required_validation"],
                "semantic_status": current["semantic_status"],
                "benchmark_observation": dict(observation),
                "validation": current["validation"],
                "policy_disposition": self._disposition(
                    str(current["semantic_status"]),
                    str(current["required_validation"]),
                    dict(observation),
                ),
                "isolated": True,
                "generator_certified": False,
                "interpretation": SEARCH_ONLY_INTERPRETATION,
                "assurance_status": None,
                "conformance_status": None,
                "recorded_at": now(),
            },
        )
        self.record_store.commit("compiler-candidates", "compiler_candidate", record)
        return record.to_object_dict()

    def tournament(self, candidate_ids: list[str]) -> dict[str, object]:
        ranked = [self._get(candidate_id) for candidate_id in candidate_ids]
        winners: list[dict[str, object]] = []
        rejected: list[dict[str, object]] = []
        unresolved: list[dict[str, object]] = []
        for record in ranked:
            disposition = self._disposition(
                str(record["semantic_status"]),
                str(record["required_validation"]),
                record["benchmark_observation"],
            )
            summary = self._summary(record)
            summary["policy_disposition"] = disposition
            if disposition == ACCEPT:
                winners.append(summary)
            elif disposition == REJECT:
                rejected.append(summary)
            else:
                unresolved.append(summary)
        return {
            "accepted": winners,
            "rejected": rejected,
            "unresolved": unresolved,
            "interpretation": SEARCH_ONLY_INTERPRETATION,
            "note": "a faster candidate with FAIL or required-UNKNOWN semantic status cannot win",
            "assurance_status": None,
            "conformance_status": None,
        }

    def select(self, candidate_id: str, *, policy: str) -> dict[str, object]:
        record = self._get(candidate_id)
        disposition = self._disposition(
            str(record["semantic_status"]),
            str(record["required_validation"]),
            record["benchmark_observation"],
        )
        if policy != "explicit-protected-property-policy":
            raise ForgeError(
                "COMPILER_CANDIDATE_POLICY",
                "compiler candidate selection requires an explicit protected-property policy",
            )
        if disposition != ACCEPT:
            raise ForgeError(
                "COMPILER_CANDIDATE_NOT_SELECTABLE",
                f"compiler candidate remains {disposition}; search cannot promote it",
            )
        return {
            "candidate_id": candidate_id,
            "policy_disposition": disposition,
            "semantic_status": record["semantic_status"],
            "interpretation": SEARCH_ONLY_INTERPRETATION,
            "assurance_status": None,
            "conformance_status": None,
        }

    def inspect_unresolved(self, candidate_id: str) -> dict[str, object]:
        record = self._get(candidate_id)
        return {
            "candidate_id": candidate_id,
            "semantic_status": record["semantic_status"],
            "required_validation": record["required_validation"],
            "validation": record["validation"],
            "policy_disposition": record["policy_disposition"],
            "interpretation": SEARCH_ONLY_INTERPRETATION,
        }

    def _get(self, candidate_id: str) -> ForgeRecord:
        matches = [
            entry.payload
            for entry in self.records.records("compiler_candidate")
            if entry.payload.get("candidate_id") == candidate_id
        ]
        if not matches:
            raise ForgeError(
                "COMPILER_CANDIDATE_NOT_FOUND",
                f"unknown compiler candidate: {candidate_id}",
            )
        return matches[-1]

    @staticmethod
    def _disposition(
        semantic_status: str,
        required_validation: str,
        benchmark: object,
    ) -> str:
        del benchmark  # measurement is never a promotion input
        if semantic_status == FAIL:
            return REJECT
        if semantic_status == PASS and required_validation in {
            "translation-validation",
            "bounded-agreement",
            "none",
        }:
            return ACCEPT
        return RETAIN_UNRESOLVED

    @staticmethod
    def _string_list(value: object) -> list[str]:
        if isinstance(value, (list, tuple)):
            return [str(item) for item in value]
        return []

    @staticmethod
    def _summary(record: ForgeRecord) -> dict[str, object]:
        payload = record.to_object_dict() if isinstance(record, ForgeRecord) else dict(record)
        return {
            "candidate_id": payload["candidate_id"],
            "baseline_artifact_identity": payload["baseline_artifact_identity"],
            "candidate_artifact_identity": payload["candidate_artifact_identity"],
            "generator_identity": payload["generator_identity"],
            "declared_transformation": payload["declared_transformation"],
            "semantic_status": payload["semantic_status"],
            "policy_disposition": payload["policy_disposition"],
            "target_envelope": payload["target_envelope"],
            "expected_benefit": payload["expected_benefit"],
        }
