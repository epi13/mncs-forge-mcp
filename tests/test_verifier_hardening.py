from __future__ import annotations

from pathlib import Path

from mncs_forge.config import ForgeConfig
from mncs_forge.engine import Forge


def begin_and_register(forge: Forge) -> dict[str, object]:
    forge.epoch_begin(generator_identity="generator-v1", evaluator_identity="evaluator-v1")
    return forge.candidate_register(
        changed_files=["candidate/main.py"],
        hypothesis="hardened verifier fixture",
        generator_identity="generator-v1",
        generator_config_identity="generator-config-v1",
    )


def test_deleted_changed_path_uses_explicit_absent_identity(
    config: ForgeConfig,
    project: Path,
) -> None:
    forge = Forge(config)
    candidate = begin_and_register(forge)
    (project / "candidate/main.py").unlink()
    result = forge.verifier_run(
        "verify-pass",
        candidate_identity=str(candidate["candidate_id"]),
        changed_paths=["candidate/main.py"],
        scope="file",
    )
    assert result["status"] == "PASS"
    identity = result["input_identities"]["changed_path_identities"]["candidate/main.py"]
    assert str(identity).startswith("forge-json-sha256-v1:")


def test_started_action_receives_terminal_unknown_on_authority_drift(
    config: ForgeConfig,
    monkeypatch: object,
) -> None:
    forge = Forge(config)
    begin_and_register(forge)
    original = forge._current_authority_identities
    calls = 0

    def drifting_authority() -> dict[str, str]:
        nonlocal calls
        calls += 1
        if calls == 1:
            return original()
        return {"drift": "sha256:" + "0" * 64}

    monkeypatch.setattr(forge, "_current_authority_identities", drifting_authority)  # type: ignore[attr-defined]
    result = forge.verifier_run(
        "verify-pass",
        changed_paths=["candidate/main.py"],
        scope="file",
    )
    assert result["status"] == "UNKNOWN"
    assert result["operational_error"]["code"] == "PROVIDER_MUTATION"
    kinds = [entry["kind"] for entry in forge.ledger.records()]
    assert kinds[-2:] == ["verifier_action", "verifier_result"]


def test_batch_supports_per_verifier_parameters(config: ForgeConfig) -> None:
    forge = Forge(config)
    begin_and_register(forge)
    result = forge.verifier_batch(
        ["verify-pass", "verify-unknown"],
        changed_paths=["candidate/main.py"],
        scope="file",
        question_parameters={
            "shared": {"note": "shared"},
            "by_verifier": {
                "verify-pass": {"note": "pass-specific"},
                "verify-unknown": {"note": "unknown-specific"},
            },
        },
    )
    assert [item["status"] for item in result["results"]] == ["PASS", "UNKNOWN"]
    assert result["recorded_result_count"] == 2
    assert result["unrecorded_result_count"] == 0


def test_batch_retains_explicit_unknown_when_one_run_is_rejected(
    config: ForgeConfig,
) -> None:
    forge = Forge(config)
    begin_and_register(forge)
    result = forge.verifier_batch(
        ["verify-pass", "verify-unknown"],
        changed_paths=["candidate/main.py"],
        scope="file",
        question_parameters={
            "by_verifier": {
                "verify-pass": {"not-declared": True},
                "verify-unknown": {"note": "still-runs"},
            }
        },
    )
    first, second = result["results"]
    assert first["status"] == "UNKNOWN"
    assert first["recorded"] is False
    assert first["operational_error"]["code"] == "VERIFIER_PARAMETER"
    assert second["status"] == "UNKNOWN"
    assert second["output_identity"]
    assert result["partial_execution_explicit"] is True
