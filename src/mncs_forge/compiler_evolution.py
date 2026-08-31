"""Observation-only consumption of MNCS Language compiler study contracts.

The MNCS Language repository owns the record vocabulary. Forge projects a
bounded comparison surface from that contract and does not reinterpret a
compiler pass status as assurance, conformance, promotion, or certification.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from .errors import ForgeError

LANGUAGE_COMPILATION_STUDY_RESULT_CONTRACT_ID = "mncs:language:compilation-study-result:0.1"
LANGUAGE_EXPERIMENT_RESULT_CONTRACT_ID = "mncs:language:experiment-result:0.1"
LANGUAGE_EXPERIMENT_INTERPRETATION = (
    "bounded_language_observation_not_universal_equivalence_or_conformance"
)
OBSERVATION_ONLY_INTERPRETATION = "observation_only_not_assurance_or_conformance"
STAGE_ORDER = (
    "source",
    "lexical_tokens",
    "concrete_syntax_tree",
    "abstract_syntax_tree",
    "semantic",
    "semantic_graph",
    "identity_map",
    "validation",
    "hir",
    "ssa",
    "selected_ssa",
    "target_lowering_plan",
    "backend_artifact",
)


def _text(record: Mapping[str, object], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value:
        raise ForgeError(
            "COMPILER_OBSERVATION_MALFORMED",
            f"MNCS Language compiler observation requires non-empty {field}",
        )
    return value


def _optional_text(record: Mapping[str, object], field: str) -> str | None:
    value = record.get(field)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ForgeError(
            "COMPILER_OBSERVATION_MALFORMED",
            f"MNCS Language compiler observation {field} must be null or non-empty text",
        )
    return value


def _mapping(record: Mapping[str, object], field: str) -> Mapping[str, object]:
    value = record.get(field)
    if not isinstance(value, Mapping):
        raise ForgeError(
            "COMPILER_OBSERVATION_MALFORMED",
            f"MNCS Language compiler observation requires object {field}",
        )
    if not all(isinstance(key, str) for key in value):
        raise ForgeError(
            "COMPILER_OBSERVATION_MALFORMED",
            f"MNCS Language compiler observation {field} has a non-text key",
        )
    return value


def _sequence(record: Mapping[str, object], field: str) -> Sequence[object]:
    value = record.get(field)
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ForgeError(
            "COMPILER_OBSERVATION_MALFORMED",
            f"MNCS Language compiler observation requires array {field}",
        )
    return value


@dataclass(frozen=True, slots=True)
class CompilerPassObservation:
    edge_identity: str
    pass_identity: str
    pass_id: str
    input_artifact: str
    output_artifact: str
    status: str

    @classmethod
    def from_language_record(cls, record: Mapping[str, object]) -> CompilerPassObservation:
        status = _text(record, "status")
        if status not in {"PASS", "FAIL", "UNKNOWN"}:
            raise ForgeError(
                "COMPILER_OBSERVATION_MALFORMED",
                "compiler pass observation status must be PASS, FAIL, or UNKNOWN",
            )
        return cls(
            edge_identity=_text(record, "edge_identity"),
            pass_identity=_text(record, "pass_identity"),
            pass_id=_text(record, "pass_id"),
            input_artifact=_text(record, "input_artifact"),
            output_artifact=_text(record, "output_artifact"),
            status=status,
        )

    def to_json(self) -> dict[str, object]:
        return {
            "edge_identity": self.edge_identity,
            "pass_identity": self.pass_identity,
            "pass_id": self.pass_id,
            "input_artifact": self.input_artifact,
            "output_artifact": self.output_artifact,
            "status": self.status,
        }


@dataclass(frozen=True, slots=True)
class CompilerExperimentObservation:
    contract_id: str
    schema_version: str
    language_record_identity: str
    run_identity: str
    compiler_identity: str
    pipeline_identity: str
    compiler_host_identity: str
    build_host_identity: str
    target_identity: str | None
    compilation_status: str
    stage_fingerprints: tuple[tuple[str, str], ...]
    pass_executions: tuple[CompilerPassObservation, ...]
    unresolved_obligations: tuple[str, ...]
    interpretation: str
    backend_identity: str | None = None
    realization_request_identity: str | None = None
    realization_plan_identity: str | None = None
    backend_artifact_identity: str | None = None
    backend_artifact_kind: str | None = None
    experiment_status: str | None = None
    validation_judgements: tuple[str, ...] = ()

    @classmethod
    def from_language_record(cls, record: Mapping[str, object]) -> CompilerExperimentObservation:
        contract_id = _text(record, "contract_id")
        experiment_record: Mapping[str, object] | None = None
        study_record = record
        if contract_id == LANGUAGE_EXPERIMENT_RESULT_CONTRACT_ID:
            experiment_record = record
            interpretation = _text(record, "interpretation")
            if interpretation != LANGUAGE_EXPERIMENT_INTERPRETATION:
                raise ForgeError(
                    "COMPILER_CONTRACT_MISMATCH",
                    "language experiment did not preserve its bounded-observation boundary",
                )
            study_record = _mapping(record, "compiler_study")
        elif contract_id != LANGUAGE_COMPILATION_STUDY_RESULT_CONTRACT_ID:
            raise ForgeError(
                "COMPILER_CONTRACT_MISMATCH",
                f"unsupported MNCS Language compiler contract: {contract_id}",
            )
        study_contract = _text(study_record, "contract_id")
        if study_contract != LANGUAGE_COMPILATION_STUDY_RESULT_CONTRACT_ID:
            raise ForgeError(
                "COMPILER_CONTRACT_MISMATCH",
                "language experiment does not contain the supported compiler study contract",
            )
        study_interpretation = _text(study_record, "interpretation")
        if study_interpretation != OBSERVATION_ONLY_INTERPRETATION:
            raise ForgeError(
                "COMPILER_CONTRACT_MISMATCH",
                "compiler study contract did not preserve the observation-only boundary",
            )
        compilation_status = _text(study_record, "compilation_status")
        if compilation_status not in {
            "completed",
            "completed_with_unresolved_obligations",
            "failed",
        }:
            raise ForgeError(
                "COMPILER_OBSERVATION_MALFORMED",
                f"unsupported compiler completion status: {compilation_status}",
            )

        raw_fingerprints = _mapping(study_record, "stage_fingerprints")
        stage_fingerprints: list[tuple[str, str]] = []
        for stage, fingerprint in raw_fingerprints.items():
            if not isinstance(fingerprint, str) or not fingerprint:
                raise ForgeError(
                    "COMPILER_OBSERVATION_MALFORMED",
                    f"compiler stage fingerprint {stage} must be non-empty text",
                )
            stage_fingerprints.append((stage, fingerprint))
        stage_fingerprints.sort()

        pass_executions: list[CompilerPassObservation] = []
        for item in _sequence(study_record, "pass_executions"):
            if not isinstance(item, Mapping):
                raise ForgeError(
                    "COMPILER_OBSERVATION_MALFORMED",
                    "compiler pass execution must be an object",
                )
            pass_executions.append(CompilerPassObservation.from_language_record(item))

        unresolved: list[str] = []
        for item in _sequence(study_record, "unresolved_obligations"):
            if not isinstance(item, str) or not item:
                raise ForgeError(
                    "COMPILER_OBSERVATION_MALFORMED",
                    "unresolved compiler obligation identities must be non-empty text",
                )
            unresolved.append(item)

        backend_identity = None
        realization_request_identity = None
        realization_plan_identity = None
        backend_artifact_identity = None
        backend_artifact_kind = None
        experiment_status = None
        validation_judgements: tuple[str, ...] = ()
        if experiment_record is not None:
            backend_identity = _text(_mapping(experiment_record, "backend"), "identity")
            definition = _mapping(experiment_record, "definition")
            realization_request_identity = _text(_mapping(definition, "realization"), "identity")
            realization_plan_identity = _text(
                _mapping(experiment_record, "realization_plan"), "identity"
            )
            artifact = _mapping(experiment_record, "artifact")
            backend_artifact_identity = _text(artifact, "identity")
            backend_artifact_kind = _text(artifact, "artifact_kind")
            experiment_status = _text(experiment_record, "status")
            if experiment_status not in {"PASS", "FAIL", "UNKNOWN"}:
                raise ForgeError(
                    "COMPILER_OBSERVATION_MALFORMED",
                    "language experiment status must be PASS, FAIL, or UNKNOWN",
                )
            judgements: list[str] = []
            for validation in _sequence(experiment_record, "translation_validations"):
                if not isinstance(validation, Mapping):
                    raise ForgeError(
                        "COMPILER_OBSERVATION_MALFORMED",
                        "translation validation must be an object",
                    )
                judgement = _text(validation, "judgement")
                if judgement not in {"PASS", "FAIL", "UNKNOWN"}:
                    raise ForgeError(
                        "COMPILER_OBSERVATION_MALFORMED",
                        "translation validation judgement must be PASS, FAIL, or UNKNOWN",
                    )
                judgements.append(judgement)
            validation_judgements = tuple(judgements)

        return cls(
            contract_id=contract_id,
            schema_version=_text(record, "schema_version"),
            language_record_identity=_text(record, "identity"),
            run_identity=_text(study_record, "run_identity"),
            compiler_identity=_text(study_record, "compiler_identity"),
            pipeline_identity=_text(study_record, "pipeline_identity"),
            compiler_host_identity=_text(study_record, "compiler_host_identity"),
            build_host_identity=_text(study_record, "build_host_identity"),
            target_identity=_optional_text(study_record, "target_identity"),
            compilation_status=compilation_status,
            stage_fingerprints=tuple(stage_fingerprints),
            pass_executions=tuple(pass_executions),
            unresolved_obligations=tuple(sorted(set(unresolved))),
            interpretation=OBSERVATION_ONLY_INTERPRETATION,
            backend_identity=backend_identity,
            realization_request_identity=realization_request_identity,
            realization_plan_identity=realization_plan_identity,
            backend_artifact_identity=backend_artifact_identity,
            backend_artifact_kind=backend_artifact_kind,
            experiment_status=experiment_status,
            validation_judgements=validation_judgements,
        )

    def fingerprint_map(self) -> dict[str, str]:
        return dict(self.stage_fingerprints)

    def to_json(self) -> dict[str, object]:
        return {
            "contract_id": self.contract_id,
            "schema_version": self.schema_version,
            "language_record_identity": self.language_record_identity,
            "run_identity": self.run_identity,
            "compiler_identity": self.compiler_identity,
            "pipeline_identity": self.pipeline_identity,
            "compiler_host_identity": self.compiler_host_identity,
            "build_host_identity": self.build_host_identity,
            "target_identity": self.target_identity,
            "compilation_status": self.compilation_status,
            "stage_fingerprints": self.fingerprint_map(),
            "pass_executions": [item.to_json() for item in self.pass_executions],
            "unresolved_obligations": list(self.unresolved_obligations),
            "interpretation": self.interpretation,
            "backend_identity": self.backend_identity,
            "realization_request_identity": self.realization_request_identity,
            "realization_plan_identity": self.realization_plan_identity,
            "backend_artifact_identity": self.backend_artifact_identity,
            "backend_artifact_kind": self.backend_artifact_kind,
            "experiment_status": self.experiment_status,
            "validation_judgements": list(self.validation_judgements),
        }


@dataclass(frozen=True, slots=True)
class StageFingerprintComparison:
    stage: str
    left: str | None
    right: str | None
    outcome: str

    def to_json(self) -> dict[str, object]:
        return {
            "stage": self.stage,
            "left": self.left,
            "right": self.right,
            "outcome": self.outcome,
        }


@dataclass(frozen=True, slots=True)
class CompilerExperimentComparison:
    left_record_identity: str
    right_record_identity: str
    stages: tuple[StageFingerprintComparison, ...]
    earliest_observed_difference: str | None
    pass_status_changes: tuple[tuple[str, str | None, str | None], ...]
    same_realization_request: bool | None = None
    same_backend: bool | None = None
    same_backend_artifact: bool | None = None
    validation_statuses: tuple[tuple[str, ...], tuple[str, ...]] = ((), ())
    interpretation: str = OBSERVATION_ONLY_INTERPRETATION
    assurance_status: None = None
    conformance_status: None = None

    def to_json(self) -> dict[str, object]:
        return {
            "left_record_identity": self.left_record_identity,
            "right_record_identity": self.right_record_identity,
            "stages": [stage.to_json() for stage in self.stages],
            "earliest_observed_difference": self.earliest_observed_difference,
            "pass_status_changes": [
                {"pass_identity": identity, "left": left, "right": right}
                for identity, left, right in self.pass_status_changes
            ],
            "same_realization_request": self.same_realization_request,
            "same_backend": self.same_backend,
            "same_backend_artifact": self.same_backend_artifact,
            "validation_statuses": {
                "left": list(self.validation_statuses[0]),
                "right": list(self.validation_statuses[1]),
            },
            "interpretation": self.interpretation,
            "assurance_status": self.assurance_status,
            "conformance_status": self.conformance_status,
        }


def compare_compiler_experiments(
    left: CompilerExperimentObservation,
    right: CompilerExperimentObservation,
) -> CompilerExperimentComparison:
    left_fingerprints = left.fingerprint_map()
    right_fingerprints = right.fingerprint_map()
    extras = sorted((set(left_fingerprints) | set(right_fingerprints)) - set(STAGE_ORDER))
    stages: list[StageFingerprintComparison] = []
    earliest: str | None = None
    for stage in (*STAGE_ORDER, *extras):
        left_value = left_fingerprints.get(stage)
        right_value = right_fingerprints.get(stage)
        if left_value is None and right_value is None:
            outcome = "not_emitted"
        elif left_value is None or right_value is None:
            outcome = "missing"
        elif left_value == right_value:
            outcome = "equal"
        else:
            outcome = "different"
        if earliest is None and outcome not in {"equal", "not_emitted"}:
            earliest = stage
        stages.append(StageFingerprintComparison(stage, left_value, right_value, outcome))

    left_passes = {item.pass_identity: item.status for item in left.pass_executions}
    right_passes = {item.pass_identity: item.status for item in right.pass_executions}
    pass_status_changes = tuple(
        (identity, left_passes.get(identity), right_passes.get(identity))
        for identity in sorted(set(left_passes) | set(right_passes))
        if left_passes.get(identity) != right_passes.get(identity)
    )
    return CompilerExperimentComparison(
        left_record_identity=left.language_record_identity,
        right_record_identity=right.language_record_identity,
        stages=tuple(stages),
        earliest_observed_difference=earliest,
        pass_status_changes=pass_status_changes,
        same_realization_request=_optional_equal(
            left.realization_request_identity, right.realization_request_identity
        ),
        same_backend=_optional_equal(left.backend_identity, right.backend_identity),
        same_backend_artifact=_optional_equal(
            left.backend_artifact_identity, right.backend_artifact_identity
        ),
        validation_statuses=(left.validation_judgements, right.validation_judgements),
    )


def _optional_equal(left: str | None, right: str | None) -> bool | None:
    if left is None and right is None:
        return None
    return left == right
