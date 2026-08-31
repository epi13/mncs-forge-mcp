from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from mncs_forge.config import ForgeConfig
from mncs_forge.engine import Forge, aggregate_status
from mncs_forge.errors import ForgeError


def begin(forge: Forge) -> dict[str, object]:
    return forge.epoch_begin(generator_identity="generator-v1", evaluator_identity="evaluator-v1")


def register(forge: Forge, *, parent: str | None = None) -> dict[str, object]:
    return forge.candidate_register(
        changed_files=["candidate/main.py"],
        hypothesis="retain behavior",
        generator_identity="generator-v1",
        generator_config_identity="generator-config-v1",
        parent_candidate=parent,
    )


def test_project_inspection_and_doctor(config: ForgeConfig) -> None:
    forge = Forge(config)
    assert forge.doctor()["ok"] is True
    result = forge.project_inspect()
    assert result["project"]["name"] == "fixture"  # type: ignore[index]
    assert result["mode"] == "development"
    assert result["active_candidate"] is None


def test_no_providers_configured_is_explicit(config: ForgeConfig) -> None:
    forge = Forge(replace(config, providers={}))
    listing = forge.provider_list()
    assert listing["configured_count"] == 0
    assert listing["status"] == "UNKNOWN"
    blockers = forge.capability_blockers()
    assert blockers["status"] == "PASS"
    assert blockers["no_requirement_note"]


def test_required_capability_absent_is_unknown_blocker(config: ForgeConfig) -> None:
    raw = {**config.raw, "required_capabilities": ["data-flow"]}
    forge = Forge(replace(config, raw=raw))
    result = forge.capability_blockers()
    assert result["status"] == "UNKNOWN"
    assert result["blocked"] is True
    assert result["blockers"][0]["capability"] == "data-flow"  # type: ignore[index]


def test_unsupported_capability_remains_unknown(config: ForgeConfig) -> None:
    forge = Forge(config)
    forge.provider_probe("provider-pass")
    result = forge.capability_blockers(["whole-program-alias-analysis"])
    assert result["status"] == "UNKNOWN"
    assert result["blocked"] is True


@pytest.mark.parametrize(
    ("provider_id", "error_code"),
    [
        ("provider-malformed", "PROVIDER_MALFORMED"),
        ("provider-timeout", "TIMEOUT"),
        ("provider-identity-drift", "PROVIDER_IDENTITY_DRIFT"),
    ],
)
def test_provider_probe_failures_close_to_unknown(
    config: ForgeConfig, provider_id: str, error_code: str
) -> None:
    result = Forge(config).provider_probe(provider_id)
    assert result["status"] == "UNKNOWN"
    assert result["error_code"] == error_code


def test_executable_identity_drift_blocks_probe(config: ForgeConfig) -> None:
    provider = replace(
        config.providers["provider-pass"],
        executable_identity="sha256:" + ("0" * 64),
    )
    forge = Forge(replace(config, providers={"provider-pass": provider}))
    result = forge.provider_probe("provider-pass")
    assert result["status"] == "UNKNOWN"
    assert result["error_code"] == "PROVIDER_IDENTITY_DRIFT"


def test_candidate_registration_and_lineage(config: ForgeConfig, project: Path) -> None:
    forge = Forge(config)
    begin(forge)
    first = register(forge)
    (project / "candidate/main.py").write_text("VALUE = 2\n", encoding="utf-8")
    second = register(forge, parent=str(first["candidate_id"]))
    assert second["parent_candidate"] == first["candidate_id"]
    assert second["candidate_id"] != first["candidate_id"]


def test_project_workflow_does_not_require_candidate_state(config: ForgeConfig) -> None:
    result = Forge(config).development_checks_run(["project-check"])
    assert result["candidate_identity"] is None
    assert result["subject_identities"] == ["project:fixture-v1"]
    assert result["aggregate_status"] == "PASS"


def test_protected_changed_file_rejected(config: ForgeConfig) -> None:
    forge = Forge(config)
    begin(forge)
    with pytest.raises(ForgeError, match="protected"):
        forge.candidate_register(
            changed_files=["protected/holdout.txt"],
            hypothesis="bad",
            generator_identity="generator",
            generator_config_identity="config",
        )


def test_development_write_boundary_rejected(config: ForgeConfig) -> None:
    forge = Forge(config)
    begin(forge)
    with pytest.raises(ForgeError, match="outside"):
        forge.candidate_register(
            changed_files=["evidence/result.json"],
            hypothesis="bad",
            generator_identity="generator",
            generator_config_identity="config",
        )


def test_stale_baseline_rejected(config: ForgeConfig, project: Path) -> None:
    forge = Forge(config)
    begin(forge)
    (project / "contract/contract.md").write_text("drift\n", encoding="utf-8")
    with pytest.raises(ForgeError, match="drifted"):
        register(forge)


def test_candidate_identity_mismatch(config: ForgeConfig) -> None:
    forge = Forge(config)
    begin(forge)
    with pytest.raises(ForgeError, match="identity"):
        forge.candidate_register(
            changed_files=["candidate/main.py"],
            hypothesis="test",
            generator_identity="generator",
            generator_config_identity="config",
            expected_identity="forge-tree-sha256-v1:stale",
        )


def test_declared_check_and_shell_injection_resistance(config: ForgeConfig, project: Path) -> None:
    forge = Forge(config)
    begin(forge)
    candidate = register(forge)
    result = forge.development_checks_run(
        ["pass-check", "injection-check"], str(candidate["candidate_id"])
    )
    assert result["aggregate_status"] == "PASS"
    assert not (project / "PWNED").exists()


def test_undeclared_command_rejected(config: ForgeConfig) -> None:
    forge = Forge(config)
    begin(forge)
    register(forge)
    with pytest.raises(ForgeError, match="not declared"):
        forge.development_checks_run(["arbitrary-shell"])


@pytest.mark.parametrize(
    ("workflow", "code"),
    [("timeout-check", "TIMEOUT"), ("output-check", "OUTPUT_LIMIT")],
)
def test_bounded_execution(config: ForgeConfig, workflow: str, code: str) -> None:
    forge = Forge(config)
    begin(forge)
    register(forge)
    with pytest.raises(ForgeError) as issue:
        forge.development_checks_run([workflow])
    assert issue.value.code == code


@pytest.mark.parametrize(
    ("workflow", "status"),
    [
        ("provider-pass", "PASS"),
        ("provider-fail", "FAIL"),
        ("provider-unknown", "UNKNOWN"),
    ],
)
def test_provider_statuses(config: ForgeConfig, workflow: str, status: str) -> None:
    forge = Forge(config)
    begin(forge)
    register(forge)
    result = forge.development_checks_run([workflow])
    assert result["aggregate_status"] == status


@pytest.mark.parametrize("workflow", ["provider-malformed", "provider-oversize"])
def test_malformed_or_oversize_provider_rejected(config: ForgeConfig, workflow: str) -> None:
    forge = Forge(config)
    begin(forge)
    register(forge)
    with pytest.raises(ForgeError):
        forge.development_checks_run([workflow])


def test_provider_disagreement_and_status_dominance(config: ForgeConfig) -> None:
    forge = Forge(config)
    begin(forge)
    candidate = register(forge)
    forge.development_checks_run(["provider-pass", "provider-unknown", "provider-fail"])
    result = forge.evidence_reconcile(str(candidate["candidate_id"]))
    assert result["required_gate_aggregation"] == "FAIL"
    assert "bounded_structural_analysis" in result["conflicting_evidence"]
    assert aggregate_status(["PASS", "UNKNOWN", "FAIL"]) == "FAIL"
    assert aggregate_status(["PASS", "UNKNOWN"]) == "UNKNOWN"


def test_failure_and_unknown_explanations(config: ForgeConfig) -> None:
    forge = Forge(config)
    begin(forge)
    register(forge)
    forge.development_checks_run(["provider-fail"])
    fail = forge.failure_explain()
    assert fail["status"] == "FAIL"
    assert fail["repair_allowed"] is True
    forge.development_checks_run(["provider-unknown"])
    unknown = forge.failure_explain()
    assert unknown["status"] == "UNKNOWN"
    assert unknown["exact_unresolved_fact"]


def test_selection_requires_complete_pass(config: ForgeConfig) -> None:
    forge = Forge(config)
    begin(forge)
    candidate = register(forge)
    with pytest.raises(ForgeError) as issue:
        forge.candidate_disposition(
            str(candidate["candidate_id"]), disposition="selected", reason="premature"
        )
    assert issue.value.code == "EVIDENCE_INCOMPLETE"
    forge.development_checks_run(["pass-check"])
    selected = forge.candidate_disposition(
        str(candidate["candidate_id"]), disposition="selected", reason="declared rule"
    )
    assert selected["disposition"] == "selected"


def test_rejection_preserves_history(config: ForgeConfig) -> None:
    forge = Forge(config)
    begin(forge)
    candidate = register(forge)
    forge.candidate_disposition(
        str(candidate["candidate_id"]), disposition="rejected", reason="regression"
    )
    assert forge.ledger.verify()["entries"] == 3


def test_compare_is_policy_bound_and_does_not_select(config: ForgeConfig, project: Path) -> None:
    forge = Forge(config)
    begin(forge)
    first = register(forge)
    (project / "candidate/main.py").write_text("VALUE = 2\n", encoding="utf-8")
    second = register(forge, parent=str(first["candidate_id"]))
    comparison = forge.candidate_compare([str(first["candidate_id"]), str(second["candidate_id"])])
    assert comparison["selected_candidate"] is None
    assert comparison["pareto_or_tie_status"] == "REVIEW_REQUIRED"


def test_evaluator_mode_rejects_mutation_operations(config: ForgeConfig) -> None:
    evaluator = Forge(config, mode="evaluator")
    with pytest.raises(ForgeError, match="development"):
        begin(evaluator)


def test_freeze_and_evaluator_run_are_immutable(config: ForgeConfig, project: Path) -> None:
    development = Forge(config)
    begin(development)
    candidate = register(development)
    development.development_checks_run(["pass-check"])
    development.candidate_disposition(
        str(candidate["candidate_id"]), disposition="selected", reason="all required PASS"
    )
    freeze = development.candidate_freeze(
        str(candidate["candidate_id"]),
        environment_identity="environment-v1",
        required_evidence_plan="evaluator/policy.json",
    )
    before = (project / "candidate/main.py").read_bytes()
    result = Forge(config, mode="evaluator").final_evaluation_run(["evaluator-pass"])
    assert result["aggregate_status"] == "PASS"
    assert result["freeze_id"] == freeze["freeze_id"]
    assert (project / "candidate/main.py").read_bytes() == before


def test_freeze_drift_rejected(config: ForgeConfig, project: Path) -> None:
    development = Forge(config)
    begin(development)
    candidate = register(development)
    development.development_checks_run(["pass-check"])
    development.candidate_disposition(
        str(candidate["candidate_id"]), disposition="selected", reason="all required PASS"
    )
    development.candidate_freeze(
        str(candidate["candidate_id"]),
        environment_identity="environment-v1",
        required_evidence_plan="evaluator/policy.json",
    )
    (project / "contract/contract.md").write_text("changed\n", encoding="utf-8")
    with pytest.raises(ForgeError, match="drift"):
        Forge(config, mode="evaluator").final_evaluation_run(["evaluator-pass"])


def test_claim_status_blockers_and_determinism(config: ForgeConfig) -> None:
    forge = Forge(config)
    first = forge.claim_status()
    second = forge.claim_status()
    assert first == second
    assert first["statuses"]["independent_evaluation"] == "UNKNOWN"  # type: ignore[index]
    blockers = forge.claim_blockers("promotion")
    assert blockers["blocked"] is True
    assert any(
        item["work_class"] == "independent_evaluator_work"
        for item in blockers["blockers"]  # type: ignore[union-attr]
    )
