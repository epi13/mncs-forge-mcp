from __future__ import annotations

import json
from pathlib import Path

import pytest

from mncs_forge.config import load_config
from mncs_forge.errors import ForgeError
from mncs_forge.execution import validate_argv
from mncs_forge.paths import resolve_contained, validate_relative_path


def test_configuration_validates(config: object) -> None:
    assert config is not None


def test_schema_copies_are_identical() -> None:
    root = Path(__file__).parents[1]
    assert json.loads((root / "schemas/mncs-forge-config.schema.json").read_text()) == json.loads(
        (root / "src/mncs_forge/resources/mncs-forge-config.schema.json").read_text()
    )


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
    text = path.read_text(encoding="utf-8").replace(
        'command = ["/', 'command = ["not-declared", "/', 1
    )
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ForgeError):
        load_config(path)
