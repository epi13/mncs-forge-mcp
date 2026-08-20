"""Persisted observation workflows for language-owned compiler studies."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from ..compiler_evolution import (
    OBSERVATION_ONLY_INTERPRETATION,
    CompilerExperimentObservation,
    compare_compiler_experiments,
)
from ..errors import ForgeError
from ..ports import RecordCommitter, RecordReader
from ..records import ForgeRecord, RecordType, new_record
from .support import now


class CompilerEvolutionService:
    """Record and compare compiler observations without granting verdict authority."""

    def __init__(self, *, records: RecordReader, record_store: RecordCommitter) -> None:
        self.records = records
        self.record_store = record_store

    def record(self, language_record: Mapping[str, object]) -> dict[str, object]:
        observation = CompilerExperimentObservation.from_language_record(language_record)
        record = new_record(
            RecordType.COMPILER_EXPERIMENT,
            {
                "language_contract_id": observation.contract_id,
                "language_record_identity": observation.language_record_identity,
                "run_identity": observation.run_identity,
                "compiler_identity": observation.compiler_identity,
                "pipeline_identity": observation.pipeline_identity,
                "compilation_status": observation.compilation_status,
                "language_record": dict(language_record),
                "observation": observation.to_json(),
                "recorded_at": now(),
                "interpretation": OBSERVATION_ONLY_INTERPRETATION,
                "assurance_status": None,
                "conformance_status": None,
            },
        )
        for entry in self.records.records("compiler_experiment"):
            if entry.payload.get("experiment_id") == record.get("experiment_id"):
                return entry.payload.to_object_dict()
        self.record_store.commit("compiler-experiments", "compiler_experiment", record)
        return record.to_object_dict()

    def list(self) -> dict[str, object]:
        experiments = [
            self._summary(entry.payload) for entry in self.records.records("compiler_experiment")
        ]
        return {
            "experiments": experiments,
            "interpretation": OBSERVATION_ONLY_INTERPRETATION,
            "assurance_status": None,
            "conformance_status": None,
        }

    def compare(self, left_experiment_id: str, right_experiment_id: str) -> dict[str, object]:
        left = self._observation(self._get(left_experiment_id))
        right = self._observation(self._get(right_experiment_id))
        return compare_compiler_experiments(left, right).to_json()

    def _get(self, experiment_id: str) -> ForgeRecord:
        for entry in self.records.records("compiler_experiment"):
            if entry.payload.get("experiment_id") == experiment_id:
                return entry.payload
        raise ForgeError(
            "COMPILER_EXPERIMENT_NOT_FOUND",
            f"unknown compiler experiment: {experiment_id}",
        )

    @staticmethod
    def _observation(record: ForgeRecord) -> CompilerExperimentObservation:
        raw = record.get("language_record")
        if not isinstance(raw, Mapping):  # pragma: no cover - record validation enforces this
            raise ForgeError(
                "COMPILER_OBSERVATION_MALFORMED",
                "persisted compiler experiment has no language record",
            )
        return CompilerExperimentObservation.from_language_record(cast(Mapping[str, object], raw))

    @staticmethod
    def _summary(record: ForgeRecord) -> dict[str, object]:
        return {
            "experiment_id": record["experiment_id"],
            "language_record_identity": record["language_record_identity"],
            "run_identity": record["run_identity"],
            "compiler_identity": record["compiler_identity"],
            "pipeline_identity": record["pipeline_identity"],
            "compilation_status": record["compilation_status"],
            "recorded_at": record["recorded_at"],
        }
