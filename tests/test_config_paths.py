from __future__ import annotations

import json
from pathlib import Path

import pytest

from mncs_forge.config import ForgeConfig, load_config
from mncs_forge.errors import ForgeError
from mncs_forge.execution import validate_argv
from mncs_forge.paths import resolve_contained, validate_relative_path


def test_configuration_validates(config: object) -> None:
    assert config is not None


def test_configuration_defaults_remain_compatible(config: ForgeConfig) -> None:
    assert config.verifier_limits == {
        "max_batch": 8,
        "request_bytes": 65536,
        "batch_timeout_seconds": 2.0,
        "witness_bytes": 32768,
        "stderr_bytes": 4096,
        "result_bytes": 131072,
        "max_changed_paths": 64,
        "max_dependency_identities": 64,
        "max_question_parameters": 32,
    }
    project_workflow = config.workflows["project-check"]
    assert project_workflow.disclosure == "compact"
    assert project_workflow.subject == "project"
    candidate_workflow = config.workflows["pass-check"]
    assert candidate_workflow.disclosure == "compact"
    assert candidate_workflow.subject == "candidate"
    provider = config.providers["provider-pass"]
    assert provider.transport == "stdio-jsonl"
    assert provider.required is False


def test_runtime_state_override_is_outside_source_tree(
    config: ForgeConfig, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime_root = tmp_path.parent / "forge-runtime-state"
    monkeypatch.setenv("MNCS_FORGE_STATE_DIR", str(runtime_root))
    assert config.state_dir == (runtime_root / config.project_identity).resolve()
    assert config.root not in config.state_dir.parents


def test_provider_defaults_are_applied_when_optional_fields_are_absent(project: Path) -> None:
    path = project / "mncs-forge.toml"
    text = path.read_text(encoding="utf-8")
    text = text.replace('transport = "stdio-jsonl"\n', "", 1)
    text = text.replace("required = false\n", "", 1)
    config = load_config(path)

    provider = config.providers["provider-pass"]
    assert provider.transport == "stdio-jsonl"
    assert provider.required is False


def test_schema_copies_are_identical() -> None:
    root = Path(__file__).parents[1]
    assert json.loads((root / "schemas/mncs-forge-config.schema.json").read_text()) == json.loads(
        (root / "src/mncs_forge/resources/mncs-forge-config.schema.json").read_text()
    )


@pytest.mark.parametrize(
    ("content", "code"),
    [
        ("version = [", "CONFIG_INVALID"),
        ("version = 999\n", "CONFIG_INVALID"),
        ("version = 1\n[unknown]\nvalue = true\n", "CONFIG_INVALID"),
    ],
)
def test_malformed_or_unsupported_configuration_has_stable_error(
    tmp_path: Path, content: str, code: str
) -> None:
    path = tmp_path / "mncs-forge.toml"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ForgeError) as issue:
        load_config(path)
    assert issue.value.code == code


def test_unreadable_configuration_has_stable_error(tmp_path: Path) -> None:
    with pytest.raises(ForgeError) as issue:
        load_config(tmp_path / "missing.toml")
    assert issue.value.code == "CONFIG_READ"


@pytest.mark.parametrize("value", ["../secret", "candidate/../../secret", "/tmp/secret"])
def test_traversal_and_absolute_rejected(value: str) -> None:
    with pytest.raises(ForgeError):
        validate_relative_path(value)


def test_symlink_escape_rejected(project: Path, tmp_path: Path) -> None:
    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.mkdir()
    (project / "candidate/link").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ForgeError, match="escapes"):
        resolve_contained(project, "candidate/link/file", must_exist=False)


def test_invalid_argument_types_rejected() -> None:
    with pytest.raises(ForgeError, match="argument"):
        validate_argv(["python", 7])


def test_protected_writable_overlap_rejected(project: Path) -> None:
    path = project / "mncs-forge.toml"
    text = path.read_text(encoding="utf-8").replace(
        'protected = ["protected"]', 'protected = ["candidate"]'
    )
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ForgeError, match="overlap"):
        load_config(path)


def test_undeclared_provider_command_rejected(project: Path) -> None:
    path = project / "mncs-forge.toml"
    text = path.read_text(encoding="utf-8")
    provider = text.index("[[providers]]")
    command = text.index("command = ", provider)
    command_end = text.index("\n", command)
    text = text[:command] + 'command = ["not-declared"]' + text[command_end:]
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ForgeError):
        load_config(path)


@pytest.mark.parametrize("reserved", ["shared", "by_verifier"])
def test_batch_parameter_envelope_keys_are_reserved(project: Path, reserved: str) -> None:
    path = project / "mncs-forge.toml"
    text = path.read_text(encoding="utf-8").replace(
        'parameter_keys = ["note"]',
        f'parameter_keys = ["{reserved}"]',
        1,
    )
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ForgeError) as issue:
        load_config(path)
    assert issue.value.code == "CONFIG_INVALID"


def test_relative_provider_symlink_escape_is_unavailable(project: Path, tmp_path: Path) -> None:
    outside = tmp_path.parent / f"{tmp_path.name}-provider-outside"
    outside.write_text("#!/bin/sh\n", encoding="utf-8")
    outside.chmod(0o755)
    (project / "candidate/provider-link").symlink_to(outside)
    path = project / "mncs-forge.toml"
    text = path.read_text(encoding="utf-8")
    marker = "[[providers]]\n"
    first = text.index(marker)
    command = text.index("command = ", first)
    end = text.index("\n", command)
    text = text[:command] + 'command = ["candidate/provider-link"]' + text[end:]
    workflow = text.index("[[workflows]]", end)
    workflow_command = text.index("command = ", workflow)
    workflow_end = text.index("\n", workflow_command)
    text = text[:workflow_command] + 'command = ["candidate/provider-link"]' + text[workflow_end:]
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ForgeError) as issue:
        load_config(path)
    assert issue.value.code == "SYMLINK_ESCAPE"
