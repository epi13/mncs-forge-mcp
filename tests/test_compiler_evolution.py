from __future__ import annotations

import copy

import pytest

from mncs_forge.compiler_evolution import (
    LANGUAGE_COMPILATION_STUDY_RESULT_CONTRACT_ID,
    LANGUAGE_EXPERIMENT_RESULT_CONTRACT_ID,
    OBSERVATION_ONLY_INTERPRETATION,
    CompilerExperimentObservation,
    compare_compiler_experiments,
)
from mncs_forge.config import ForgeConfig
from mncs_forge.engine import Forge
from mncs_forge.errors import ForgeError
from mncs_forge.records import RecordType, new_record


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
            "source": "source-fingerprint",
            "lexical_tokens": "lexical-fingerprint",
            "concrete_syntax_tree": "cst-fingerprint",
            "abstract_syntax_tree": "ast-fingerprint",
            "semantic": "semantic-fingerprint",
            "semantic_graph": "graph-fingerprint",
            "identity_map": "identity-fingerprint",
            "validation": "validation-fingerprint",
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


def language_experiment(backend: str = "mncs-portable-wasm-mvp") -> dict[str, object]:
    study = language_result()
    study["target_identity"] = "mncs:compiler:target:portable"
    study["backend_identity"] = f"mncs:compiler:backend:{backend}"
    study["realization_plan_identity"] = f"mncs:compiler:plan:{backend}"
    study["backend_artifact_identity"] = f"mncs:compiler:artifact:{backend}"
    return {
        "schema_version": "0.1",
        "contract_id": LANGUAGE_EXPERIMENT_RESULT_CONTRACT_ID,
        "identity": f"mncs:language:experiment:result:{backend}",
        "definition": {"realization": {"identity": "mncs:compiler:realization-request:shared"}},
        "compiler_study": study,
        "backend": {"identity": f"mncs:compiler:backend:{backend}"},
        "realization_plan": {"identity": f"mncs:compiler:plan:{backend}"},
        "artifact": {
            "identity": f"mncs:compiler:artifact:{backend}",
            "artifact_kind": "wasm_module"
            if backend == "mncs-portable-wasm-mvp"
            else "research_bytecode",
        },
        "translation_validations": [{"judgement": "PASS"}],
        "status": "UNKNOWN",
        "interpretation": ("bounded_language_observation_not_universal_equivalence_or_conformance"),
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


def test_rejects_language_experiment_or_nested_study_authority_laundering() -> None:
    experiment = language_experiment()
    experiment["interpretation"] = "universal-equivalence"
    with pytest.raises(ForgeError, match="bounded-observation boundary") as outer:
        CompilerExperimentObservation.from_language_record(experiment)
    assert outer.value.code == "COMPILER_CONTRACT_MISMATCH"

    nested = language_experiment()
    assert isinstance(nested["compiler_study"], dict)
    nested["compiler_study"]["interpretation"] = "assured"
    with pytest.raises(ForgeError, match="observation-only boundary") as inner:
        CompilerExperimentObservation.from_language_record(nested)
    assert inner.value.code == "COMPILER_CONTRACT_MISMATCH"


def test_persists_lists_and_compares_language_owned_experiments(config: ForgeConfig) -> None:
    forge = Forge(config)
    left_record = forge.compiler_experiment_record(language_result())
    changed = copy.deepcopy(language_result())
    changed["identity"] = "mncs:compiler:compilation-study-result:right"
    changed["run_identity"] = "mncs:compiler:study-run:right"
    assert isinstance(changed["stage_fingerprints"], dict)
    changed["stage_fingerprints"]["semantic_graph"] = "changed-graph-fingerprint"
    right_record = forge.compiler_experiment_record(changed)

    listing = forge.compiler_experiments_list()
    assert len(listing["experiments"]) == 2
    assert listing["assurance_status"] is None
    comparison = forge.compiler_experiments_compare(
        str(left_record["experiment_id"]),
        str(right_record["experiment_id"]),
    )
    assert comparison["earliest_observed_difference"] == "semantic_graph"
    assert comparison["assurance_status"] is None
    assert comparison["conformance_status"] is None
    assert forge.ledger.verify()["ok"] is True


def test_projects_backend_plural_language_experiments_without_choosing_legality(
    config: ForgeConfig,
) -> None:
    forge = Forge(config)
    wasm = forge.compiler_experiment_record(language_experiment())
    bytecode = forge.compiler_experiment_record(language_experiment("mncs-research-bytecode"))
    listing = forge.compiler_experiments_list()
    assert {item["backend_artifact_kind"] for item in listing["experiments"]} == {
        "wasm_module",
        "research_bytecode",
    }
    comparison = forge.compiler_experiments_compare(
        str(wasm["experiment_id"]), str(bytecode["experiment_id"])
    )
    assert comparison["earliest_observed_difference"] is None
    assert comparison["same_realization_request"] is True
    assert comparison["same_backend"] is False
    assert comparison["same_backend_artifact"] is False
    assert comparison["validation_statuses"] == {
        "left": ["PASS"],
        "right": ["PASS"],
    }
    assert comparison["assurance_status"] is None
    assert comparison["conformance_status"] is None


def test_recording_the_same_compiler_experiment_is_idempotent(config: ForgeConfig) -> None:
    forge = Forge(config)
    first = forge.compiler_experiment_record(language_result())
    second = forge.compiler_experiment_record(language_result())

    assert second == first
    assert forge.ledger.verify()["entries"] == 1
    assert len(forge.compiler_experiments_list()["experiments"]) == 1


def test_persisted_compiler_record_rejects_verdict_laundering() -> None:
    observation = CompilerExperimentObservation.from_language_record(language_result())
    fields = {
        "language_contract_id": observation.contract_id,
        "language_record_identity": observation.language_record_identity,
        "run_identity": observation.run_identity,
        "compiler_identity": observation.compiler_identity,
        "pipeline_identity": observation.pipeline_identity,
        "compilation_status": observation.compilation_status,
        "language_record": language_result(),
        "observation": observation.to_json(),
        "recorded_at": "2026-08-20T00:00:00+00:00",
        "interpretation": OBSERVATION_ONLY_INTERPRETATION,
        "assurance_status": "PASS",
        "conformance_status": None,
    }
    with pytest.raises(ForgeError, match="cannot claim assurance") as error:
        new_record(RecordType.COMPILER_EXPERIMENT, fields)
    assert error.value.code == "RECORD_AUTHORITY"

    fields["assurance_status"] = None
    fields["language_contract_id"] = "forge:competing-compiler-contract:1"
    with pytest.raises(ForgeError, match="unsupported language contract") as error:
        new_record(RecordType.COMPILER_EXPERIMENT, fields)
    assert error.value.code == "RECORD_CONTRACT"
