from __future__ import annotations

import copy

import pytest

from mncs_forge.compiler_evolution import (
    LANGUAGE_COMPILATION_STUDY_RESULT_CONTRACT_ID,
    CompilerExperimentObservation,
    compare_compiler_experiments,
)
from mncs_forge.errors import ForgeError


def language_result() -> dict[str, object]:
    return {
        "schema_version": "0.1",
        "contract_id": LANGUAGE_COMPILATION_STUDY_RESULT_CONTRACT_ID,
        "identity": "mncs:compiler:compilation-study-result:left",
        "run_identity": "mncs:compiler:study-run:left",
        "compiler_identity": "mncs:compiler:compiler:reference",
        "pipeline_identity": "mncs:compiler:pass-pipeline:reference",
        "compiler_host_identity": "mncs:compiler:compiler-host:linux",
        "build_host_identity": "mncs:compiler:build-host:linux",
        "target_identity": None,
        "compilation_status": "completed_with_unresolved_obligations",
        "stage_fingerprints": {
            "semantic": "semantic-fingerprint",
            "hir": "hir-fingerprint",
            "ssa": "ssa-fingerprint",
        },
        "pass_executions": [
            {
                "edge_identity": "mncs:compiler:transformation-edge:hir",
                "pass_identity": "mncs:compiler:compiler-pass:hir",
                "pass_id": "lower-semantic-to-hir",
                "input_artifact": "mncs:compiler:artifact:semantic",
                "output_artifact": "mncs:compiler:artifact:hir",
                "status": "UNKNOWN",
            }
        ],
        "unresolved_obligations": ["mncs:obligation:contract-evidence"],
        "interpretation": "observation_only_not_assurance_or_conformance",
    }


def test_consumes_language_owned_contract_without_inventing_a_forge_verdict() -> None:
    observation = CompilerExperimentObservation.from_language_record(language_result())
    assert observation.contract_id == LANGUAGE_COMPILATION_STUDY_RESULT_CONTRACT_ID
    assert observation.pass_executions[0].status == "UNKNOWN"
    assert observation.unresolved_obligations == ("mncs:obligation:contract-evidence",)
    assert "assurance_status" not in observation.to_json()
    assert "conformance_status" not in observation.to_json()


def test_comparison_localizes_the_first_ir_difference_as_observation_only() -> None:
    left = CompilerExperimentObservation.from_language_record(language_result())
    changed = copy.deepcopy(language_result())
    changed["identity"] = "mncs:compiler:compilation-study-result:right"
    changed["run_identity"] = "mncs:compiler:study-run:right"
    assert isinstance(changed["stage_fingerprints"], dict)
    changed["stage_fingerprints"]["ssa"] = "changed-ssa-fingerprint"
    right = CompilerExperimentObservation.from_language_record(changed)

    comparison = compare_compiler_experiments(left, right).to_json()
    assert comparison["earliest_observed_difference"] == "ssa"
    assert comparison["assurance_status"] is None
    assert comparison["conformance_status"] is None


def test_unemitted_target_and_backend_stages_are_not_reported_as_divergence() -> None:
    observation = CompilerExperimentObservation.from_language_record(language_result())
    comparison = compare_compiler_experiments(observation, observation).to_json()
    assert comparison["earliest_observed_difference"] is None
    stages = {item["stage"]: item["outcome"] for item in comparison["stages"]}
    assert stages["target_lowering_plan"] == "not_emitted"
    assert stages["backend_artifact"] == "not_emitted"


def test_pass_status_changes_are_retained_without_promotion_semantics() -> None:
    left = CompilerExperimentObservation.from_language_record(language_result())
    changed = copy.deepcopy(language_result())
    changed["identity"] = "mncs:compiler:compilation-study-result:right"
    assert isinstance(changed["pass_executions"], list)
    assert isinstance(changed["pass_executions"][0], dict)
    changed["pass_executions"][0]["status"] = "PASS"
    right = CompilerExperimentObservation.from_language_record(changed)

    comparison = compare_compiler_experiments(left, right).to_json()
    assert comparison["pass_status_changes"] == [
        {
            "pass_identity": "mncs:compiler:compiler-pass:hir",
            "left": "UNKNOWN",
            "right": "PASS",
        }
    ]
    assert comparison["assurance_status"] is None


def test_rejects_a_competing_or_unsupported_compiler_contract() -> None:
    record = language_result()
    record["contract_id"] = "mncs:forge:compiler-study:0.1"
    with pytest.raises(ForgeError, match="unsupported MNCS Language compiler contract") as error:
        CompilerExperimentObservation.from_language_record(record)
    assert error.value.code == "COMPILER_CONTRACT_MISMATCH"


def test_rejects_observation_laundering_into_a_stronger_interpretation() -> None:
    record = language_result()
    record["interpretation"] = "conformant"
    with pytest.raises(ForgeError, match="observation-only boundary") as error:
        CompilerExperimentObservation.from_language_record(record)
    assert error.value.code == "COMPILER_CONTRACT_MISMATCH"
