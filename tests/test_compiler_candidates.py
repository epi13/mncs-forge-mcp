from __future__ import annotations

import pytest

from mncs_forge.config import ForgeConfig
from mncs_forge.engine import Forge
from mncs_forge.errors import ForgeError


def register(forge: Forge, suffix: str, *, benefit: str = "faster") -> dict[str, object]:
    return forge.compiler_candidate_register(
        baseline_artifact_identity="ssa:baseline",
        candidate_artifact_identity=f"ssa:candidate:{suffix}",
        generator_identity="generator:constant-fold",
        declared_transformation=suffix,
        claimed_relation="observational-equivalence",
        expected_benefit=benefit,
        protected_properties=["return_value"],
        target_envelope="mncs:target:portable-wasm-mvp-0.1",
        required_validation="translation-validation",
    )


def test_isolated_candidate_is_not_the_baseline(config: ForgeConfig) -> None:
    forge = Forge(config)
    with pytest.raises(ForgeError, match="cannot share the trusted baseline"):
        forge.compiler_candidate_register(
            baseline_artifact_identity="ssa:same",
            candidate_artifact_identity="ssa:same",
            generator_identity="generator",
            declared_transformation="rewrite",
            claimed_relation="eq",
            expected_benefit="faster",
            protected_properties=[],
        )


def test_fail_loses_and_unknown_is_not_promoted(config: ForgeConfig) -> None:
    forge = Forge(config)
    invalid = register(forge, "invalid")
    unknown = register(forge, "unknown")
    valid = register(forge, "valid")
    failed = forge.compiler_candidate_attach_validation(
        str(invalid["candidate_id"]),
        validator_identity="mncs:validator:checked-elision:0.1",
        judgement="FAIL",
        claimed_relation="observational-equivalence",
        counterexample={"case_id": "overflow"},
    )
    unresolved = forge.compiler_candidate_attach_validation(
        str(unknown["candidate_id"]),
        validator_identity="mncs:validator:checked-elision:0.1",
        judgement="UNKNOWN",
        claimed_relation="observational-equivalence",
        limitations=["no overflow proof"],
    )
    passed = forge.compiler_candidate_attach_validation(
        str(valid["candidate_id"]),
        validator_identity="mncs:validator:constant-folding:0.1",
        judgement="PASS",
        claimed_relation="observational-equivalence",
    )
    tournament = forge.compiler_tournament(
        [
            str(failed["candidate_id"]),
            str(unresolved["candidate_id"]),
            str(passed["candidate_id"]),
        ]
    )
    assert tournament["rejected"][0]["candidate_id"] == failed["candidate_id"]
    assert tournament["unresolved"][0]["candidate_id"] == unresolved["candidate_id"]
    assert tournament["accepted"][0]["candidate_id"] == passed["candidate_id"]
    with pytest.raises(ForgeError, match="search cannot promote it"):
        forge.compiler_candidate_select(
            str(failed["candidate_id"]),
            policy="explicit-protected-property-policy",
        )
    selected = forge.compiler_candidate_select(
        str(passed["candidate_id"]),
        policy="explicit-protected-property-policy",
    )
    assert selected["policy_disposition"] == "accept"
    assert selected["assurance_status"] is None


def test_stale_validation_cannot_promote(config: ForgeConfig) -> None:
    forge = Forge(config)
    candidate = register(forge, "stale")
    stale = forge.compiler_candidate_attach_validation(
        str(candidate["candidate_id"]),
        validator_identity="mncs:validator:backend:0.1",
        judgement="PASS",
        claimed_relation="observational-equivalence",
        stale=True,
    )
    assert stale["semantic_status"] == "UNKNOWN"
    assert stale["policy_disposition"] == "retain_unresolved"


def test_target_envelope_is_not_global(config: ForgeConfig) -> None:
    forge = Forge(config)
    linux = forge.compiler_candidate_register(
        baseline_artifact_identity="ssa:baseline",
        candidate_artifact_identity="ssa:linux",
        generator_identity="generator:backend",
        declared_transformation="linux-abi",
        claimed_relation="observational-equivalence",
        expected_benefit="native",
        protected_properties=["return_value"],
        target_envelope="linux-x86_64",
        required_validation="translation-validation",
    )
    windows = forge.compiler_candidate_register(
        baseline_artifact_identity="ssa:baseline",
        candidate_artifact_identity="ssa:windows",
        generator_identity="generator:backend",
        declared_transformation="windows-abi",
        claimed_relation="observational-equivalence",
        expected_benefit="native",
        protected_properties=["return_value"],
        target_envelope="windows-x86_64",
        required_validation="translation-validation",
    )
    comparison = forge.compiler_candidates_compare(
        str(linux["candidate_id"]),
        str(windows["candidate_id"]),
    )
    assert comparison["same_target_envelope"] is False
    listed = forge.compiler_candidates_list()
    assert listed["assurance_status"] is None
    assert len(listed["candidates"]) == 2
