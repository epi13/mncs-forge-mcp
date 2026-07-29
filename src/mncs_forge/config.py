"""Configuration loading and validation."""

from __future__ import annotations

import json
import os
import tomllib
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path, PurePosixPath
from typing import Any

from jsonschema import Draft202012Validator

from .errors import ForgeError
from .execution import validate_argv
from .paths import (
    resolve_contained,
    validate_relative_path,
    validate_scopes_do_not_overlap,
    validate_tree_containment,
)


@dataclass(frozen=True)
class Workflow:
    name: str
    category: str
    mode: str
    command: list[str]
    provider_protocol: bool
    provider_id: str | None
    environment: dict[str, str]
    disclosure: str


@dataclass(frozen=True)
class ForgeConfig:
    config_path: Path
    root: Path
    raw: dict[str, Any]
    path_values: dict[str, list[str]]
    workflows: dict[str, Workflow]

    @property
    def project_name(self) -> str:
        return str(self.raw["project"]["name"])

    @property
    def project_identity(self) -> str:
        return str(self.raw["project"]["identity"])

    @property
    def timeout(self) -> float:
        return float(self.raw["limits"]["timeout_seconds"])

    @property
    def output_cap(self) -> int:
        return int(self.raw["limits"]["output_bytes"])

    @property
    def state_dir(self) -> Path:
        return self.root / ".mncs-forge"

    def paths(self, key: str, *, must_exist: bool = False) -> list[Path]:
        return [
            resolve_contained(self.root, value, must_exist=must_exist)
            for value in self.path_values[key]
        ]

    def relative_scopes(self, *keys: str) -> list[PurePosixPath]:
        return [
            validate_relative_path(value) for key in keys for value in self.path_values.get(key, [])
        ]

    def environment(self, workflow: Workflow) -> dict[str, str]:
        allowed = set(self.raw.get("environment_allowlist", []))
        result: dict[str, str] = {}
        for key in allowed:
            if key in os.environ:
                result[key] = os.environ[key]
        for key, value in workflow.environment.items():
            if key not in allowed:
                raise ForgeError(
                    "ENVIRONMENT_FORBIDDEN",
                    f"workflow {workflow.name} declares non-allowlisted environment key {key}",
                )
            result[key] = value
        return result

    def public_commands(self) -> dict[str, list[str]]:
        commands = self.raw.get("commands", {})
        return {name: list(value) for name, value in commands.items()}


def _schema() -> dict[str, Any]:
    path = files("mncs_forge.resources").joinpath("mncs-forge-config.schema.json")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ForgeError("INTERNAL_SCHEMA", "packaged configuration schema is invalid")
    return value


def validate_config_data(data: object) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ForgeError("CONFIG_INVALID", "configuration root must be a TOML table")
    errors = sorted(
        Draft202012Validator(_schema()).iter_errors(data), key=lambda item: list(item.path)
    )
    if errors:
        issue = errors[0]
        location = ".".join(str(part) for part in issue.absolute_path) or "<root>"
        raise ForgeError("CONFIG_INVALID", f"{location}: {issue.message}")
    return data


def load_config(path: Path | str = Path("mncs-forge.toml")) -> ForgeConfig:
    config_path = Path(path).expanduser().resolve(strict=True)
    try:
        with config_path.open("rb") as stream:
            raw = validate_config_data(tomllib.load(stream))
    except OSError as exc:
        raise ForgeError("CONFIG_READ", f"cannot read configuration: {exc}") from exc
    project_root = validate_relative_path(str(raw["project"]["root"]), allow_dot=True)
    root = config_path.parent.joinpath(*project_root.parts).resolve(strict=True)
    path_values = {key: list(value) for key, value in raw["paths"].items()}
    for values in path_values.values():
        for value in values:
            resolved = resolve_contained(root, value, must_exist=False)
            validate_tree_containment(root, resolved)
    writable = [
        validate_relative_path(value)
        for key in ("candidates", "generated", "outputs")
        for value in path_values[key]
    ]
    protected = [
        validate_relative_path(value)
        for key in ("contracts", "references", "evaluators", "acceptance_policies", "protected")
        for value in path_values[key]
    ]
    validate_scopes_do_not_overlap(writable, protected)
    for policy in raw["policies"].values():
        resolve_contained(root, str(policy), must_exist=False)
    workflows: dict[str, Workflow] = {}
    for item in raw["workflows"]:
        name = str(item["name"])
        if name in workflows:
            raise ForgeError("CONFIG_INVALID", f"duplicate workflow name: {name}")
        command = validate_argv(item["command"])
        workflows[name] = Workflow(
            name=name,
            category=str(item["category"]),
            mode=str(item["mode"]),
            command=command,
            provider_protocol=bool(item["provider_protocol"]),
            provider_id=str(item["provider_id"]) if "provider_id" in item else None,
            environment=dict(item.get("environment", {})),
            disclosure=str(item.get("disclosure", "compact")),
        )
    providers: set[tuple[str, ...]] = set()
    for provider in raw.get("providers", []):
        providers.add(tuple(validate_argv(provider["command"])))
    for workflow in workflows.values():
        if workflow.provider_protocol and tuple(workflow.command) not in providers:
            raise ForgeError(
                "UNDECLARED_COMMAND",
                f"provider workflow {workflow.name} command is not declared in providers",
            )
    return ForgeConfig(
        config_path=config_path,
        root=root,
        raw=raw,
        path_values=path_values,
        workflows=workflows,
    )
