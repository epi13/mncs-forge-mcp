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
    subject: str


@dataclass(frozen=True)
class Provider:
    provider_id: str
    name: str
    identity: str | None
    version: str | None
    command: list[str]
    transport: str
    required: bool
    capabilities: list[str]
    supported_constructs: list[str]
    unsupported_constructs: list[str]
    limitations: list[str]
    executable_identity: str | None
    descriptor: str | None
    environment: dict[str, str]


@dataclass(frozen=True)
class Verifier:
    verifier_id: str
    version: str
    workflow: str
    provider_id: str
    method: str
    claim: str
    category: str
    modes: tuple[str, ...]
    languages: tuple[str, ...]
    artifact_types: tuple[str, ...]
    scopes: tuple[str, ...]
    input_kinds: tuple[str, ...]
    limitations: tuple[str, ...]
    assumptions: tuple[str, ...]
    timeout_seconds: float
    cost: str
    uncertainty_classes: tuple[str, ...]
    tags: tuple[str, ...]
    parameter_keys: tuple[str, ...]
    disclosure: str


@dataclass(frozen=True)
class ForgeConfig:
    config_path: Path
    root: Path
    raw: dict[str, Any]
    path_values: dict[str, list[str]]
    providers: dict[str, Provider]
    workflows: dict[str, Workflow]
    verifiers: dict[str, Verifier]

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
    def verifier_limits(self) -> dict[str, int | float]:
        configured = self.raw.get("verifier_limits", {})
        return {
            "max_batch": int(configured.get("max_batch", 8)),
            "request_bytes": int(configured.get("request_bytes", 65536)),
            "batch_timeout_seconds": float(
                configured.get("batch_timeout_seconds", min(self.timeout * 4, 300))
            ),
            "witness_bytes": int(configured.get("witness_bytes", 32768)),
            "stderr_bytes": int(configured.get("stderr_bytes", 4096)),
            "result_bytes": int(configured.get("result_bytes", 131072)),
            "max_changed_paths": int(configured.get("max_changed_paths", 64)),
            "max_dependency_identities": int(configured.get("max_dependency_identities", 64)),
            "max_question_parameters": int(configured.get("max_question_parameters", 32)),
        }

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
        return self._environment(workflow.environment, f"workflow {workflow.name}")

    def provider_environment(self, provider: Provider) -> dict[str, str]:
        return self._environment(provider.environment, f"provider {provider.provider_id}")

    def _environment(self, declared: dict[str, str], label: str) -> dict[str, str]:
        allowed = set(self.raw.get("environment_allowlist", []))
        result: dict[str, str] = {}
        for key in allowed:
            if key in os.environ:
                result[key] = os.environ[key]
        for key, value in declared.items():
            if key not in allowed:
                raise ForgeError(
                    "ENVIRONMENT_FORBIDDEN",
                    f"{label} declares non-allowlisted environment key {key}",
                )
            result[key] = value
        return result

    @property
    def required_capabilities(self) -> list[str]:
        return list(self.raw.get("required_capabilities", []))

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
            subject=str(item.get("subject", "candidate")),
        )
    providers: dict[str, Provider] = {}
    provider_commands: set[tuple[str, ...]] = set()
    for item in raw.get("providers", []):
        provider_id = str(item["id"])
        if provider_id in providers:
            raise ForgeError("CONFIG_INVALID", f"duplicate provider id: {provider_id}")
        command = validate_argv(item["command"])
        provider_commands.add(tuple(command))
        descriptor = str(item["descriptor"]) if "descriptor" in item else None
        if descriptor is not None:
            resolve_contained(root, descriptor, must_exist=False)
        providers[provider_id] = Provider(
            provider_id=provider_id,
            name=str(item.get("name", provider_id)),
            identity=str(item["identity"]) if "identity" in item else None,
            version=str(item["version"]) if "version" in item else None,
            command=command,
            transport=str(item.get("transport", "stdio-jsonl")),
            required=bool(item.get("required", False)),
            capabilities=list(item.get("capabilities", [])),
            supported_constructs=list(item.get("supported_constructs", [])),
            unsupported_constructs=list(item.get("unsupported_constructs", [])),
            limitations=list(item.get("limitations", [])),
            executable_identity=(
                str(item["executable_identity"]) if "executable_identity" in item else None
            ),
            descriptor=descriptor,
            environment=dict(item.get("environment", {})),
        )
    for workflow in workflows.values():
        if workflow.provider_protocol and tuple(workflow.command) not in provider_commands:
            raise ForgeError(
                "UNDECLARED_COMMAND",
                f"provider workflow {workflow.name} command is not declared in providers",
            )
        if workflow.provider_protocol and workflow.provider_id is not None:
            provider = providers.get(workflow.provider_id)
            if provider is None:
                raise ForgeError(
                    "UNDECLARED_PROVIDER",
                    f"provider workflow {workflow.name} references undeclared provider "
                    f"{workflow.provider_id}",
                )
            if provider.command != workflow.command:
                raise ForgeError(
                    "UNDECLARED_COMMAND",
                    f"provider workflow {workflow.name} command differs from provider "
                    f"{workflow.provider_id}",
                )
    verifiers: dict[str, Verifier] = {}
    may_run_development_providers = bool(raw["authority"]["development"]["may_run_providers"])
    for item in raw.get("verifiers", []):
        verifier_id = str(item["id"])
        if verifier_id in verifiers:
            raise ForgeError("CONFIG_INVALID", f"duplicate verifier id: {verifier_id}")
        provider_id = str(item["provider"])
        provider = providers.get(provider_id)
        if provider is None:
            raise ForgeError(
                "UNDECLARED_PROVIDER",
                f"verifier {verifier_id} references undeclared provider {provider_id}",
            )
        workflow_name = str(item["workflow"])
        verifier_workflow = workflows.get(workflow_name)
        if verifier_workflow is None:
            raise ForgeError(
                "UNDECLARED_COMMAND",
                f"verifier {verifier_id} references undeclared workflow {workflow_name}",
            )
        if not verifier_workflow.provider_protocol:
            raise ForgeError(
                "VERIFIER_WORKFLOW",
                f"verifier {verifier_id} requires a Provider Protocol workflow",
            )
        if (
            verifier_workflow.provider_id != provider_id
            or verifier_workflow.command != provider.command
        ):
            raise ForgeError(
                "VERIFIER_AUTHORITY",
                f"verifier {verifier_id} does not match workflow/provider authority",
            )
        method = str(item["method"])
        if method not in provider.capabilities:
            raise ForgeError(
                "VERIFIER_METHOD",
                f"verifier {verifier_id} method {method} is not a declared provider capability",
            )
        modes = tuple(str(value) for value in item["modes"])
        workflow_modes = (
            {"development", "evaluator"}
            if verifier_workflow.mode == "both"
            else {verifier_workflow.mode}
        )
        if not set(modes).issubset(workflow_modes):
            raise ForgeError(
                "VERIFIER_MODE",
                f"verifier {verifier_id} modes exceed workflow {workflow_name} authority",
            )
        if "development" in modes and not may_run_development_providers:
            raise ForgeError(
                "VERIFIER_AUTHORITY",
                f"verifier {verifier_id} grants development provider execution without authority",
            )
        category = str(item["category"])
        if category != verifier_workflow.category:
            raise ForgeError(
                "VERIFIER_CATEGORY",
                f"verifier {verifier_id} category must match workflow {workflow_name}",
            )
        timeout = float(item.get("timeout_seconds", raw["limits"]["timeout_seconds"]))
        if timeout > float(raw["limits"]["timeout_seconds"]):
            raise ForgeError(
                "VERIFIER_LIMIT",
                f"verifier {verifier_id} timeout exceeds the project limit",
            )
        disclosure = str(item.get("disclosure", verifier_workflow.disclosure))
        if verifier_workflow.disclosure == "status-only" and disclosure != "status-only":
            raise ForgeError(
                "VERIFIER_DISCLOSURE",
                f"verifier {verifier_id} cannot broaden status-only workflow disclosure",
            )
        verifiers[verifier_id] = Verifier(
            verifier_id=verifier_id,
            version=str(item["version"]),
            workflow=workflow_name,
            provider_id=provider_id,
            method=method,
            claim=str(item["claim"]),
            category=category,
            modes=modes,
            languages=tuple(str(value) for value in item.get("languages", [])),
            artifact_types=tuple(str(value) for value in item.get("artifact_types", [])),
            scopes=tuple(str(value) for value in item["scopes"]),
            input_kinds=tuple(str(value) for value in item["input_kinds"]),
            limitations=tuple(str(value) for value in item.get("limitations", [])),
            assumptions=tuple(str(value) for value in item.get("assumptions", [])),
            timeout_seconds=timeout,
            cost=str(item["cost"]),
            uncertainty_classes=tuple(str(value) for value in item.get("uncertainty_classes", [])),
            tags=tuple(str(value) for value in item.get("tags", [])),
            parameter_keys=tuple(str(value) for value in item.get("parameter_keys", [])),
            disclosure=disclosure,
        )
    return ForgeConfig(
        config_path=config_path,
        root=root,
        raw=raw,
        path_values=path_values,
        providers=providers,
        workflows=workflows,
        verifiers=verifiers,
    )
