import pytest

from mncs_forge.concept_experiments import build_concept_evaluation
from mncs_forge.errors import ForgeError


def evaluation(status: str = "UNKNOWN") -> dict[str, object]:
    return build_concept_evaluation(
        concept_experiment_id="cre-tristate-a",
        candidate_identity="candidate:tri-state:fixture",
        language_profile="mncs-language:source-profile:0.2",
        compiler_identity="mncs:compiler:fixture",
        backend_identity="mncs:language:backend:reference-interpreter",
        execution_identities=["mncs-fabric://execution/fixture/attempt/1"],
        verifier_identity="forge:verifier:tri-state",
        verifier_version="0.1",
        obligation="tri-state UNKNOWN preservation",
        evidence_identities=["sha256:" + "a" * 64],
        status=status,
        unresolved_obligations=["independent-backend-reproduction"],
        generator_identity="harness:model:builder",
        evaluator_policy_identity="forge:policy:tri-state",
    )


def test_unknown_is_retained_at_exact_forge_scope() -> None:
    value = evaluation()
    assert value["status"] == "UNKNOWN"
    assert value["producer"] == "mncs-forge"
    assert value["generator_certified"] is False
    assert value["stable_id"].startswith("mncs-forge://evaluation/")
    assert value["interpretation"] == "bounded_forge_evaluation_not_mncs_conformance"


def test_generator_cannot_be_the_named_evaluator() -> None:
    with pytest.raises(ForgeError, match="generator and evaluator"):
        build_concept_evaluation(
            concept_experiment_id="cre-a",
            candidate_identity="candidate:a",
            language_profile="language:a",
            compiler_identity="compiler:a",
            backend_identity="backend:a",
            execution_identities=[],
            verifier_identity="same:identity",
            verifier_version="0.1",
            obligation="obligation:a",
            evidence_identities=[],
            status="UNKNOWN",
            generator_identity="same:identity",
        )
