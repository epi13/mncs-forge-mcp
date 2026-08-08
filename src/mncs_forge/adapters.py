"""Local adapters implementing inward-facing Forge application ports."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from collections.abc import Mapping
from pathlib import Path

from .config import ForgeConfig, Provider
from .errors import ForgeError
from .execution import run_bounded
from .identity import content_identity, file_identity, identity_map
from .paths import is_within, resolve_contained, validate_relative_path
from .ports import ExecutionResult
from .serialization import local_json_identity, read_json


class LocalCommandExecutor:
    """Preserve the existing bounded local-process semantics behind `CommandExecutor`."""

    def execute(
        self,
        command: object,
        *,
        cwd: Path,
        timeout: float,
        output_cap: int,
        stderr_cap: int | None = None,
        environment: dict[str, str],
        stdin: bytes = b"",
    ) -> ExecutionResult:
        return run_bounded(
            command,
            cwd=cwd,
            timeout=timeout,
            output_cap=output_cap,
            stderr_cap=stderr_cap,
            environment=environment,
            stdin=stdin,
        )


class LocalProjectObserver:
    """Observe project identities and prepare local copied workspaces."""

    def __init__(self, config: ForgeConfig) -> None:
        self.config = config

    def authority_paths(self) -> list[Path]:
        return [
            *self.config.paths("contracts"),
            *self.config.paths("references"),
            *self.config.paths("evaluators"),
            *self.config.paths("acceptance_policies"),
            *self.config.paths("protected"),
        ]

    def candidate_paths(self) -> list[Path]:
        return [*self.config.paths("candidates"), *self.config.paths("generated")]

    def current_candidate_identity(self) -> str:
        return content_identity(self.config.root, self.candidate_paths())

    def current_authority_identities(self) -> dict[str, str]:
        return identity_map(self.config.root, self.authority_paths())

    def content_identity(self, paths: list[Path]) -> str:
        return content_identity(self.config.root, paths)

    def identity_map(self, paths: list[Path]) -> dict[str, str]:
        return identity_map(self.config.root, paths)

    def selection_evidence_policy(self) -> tuple[str, tuple[str, ...], str | None]:
        policy_path = resolve_contained(
            self.config.root,
            str(self.config.raw["policies"]["selection"]),
            must_exist=False,
        )
        policy_identity = content_identity(self.config.root, [policy_path])
        try:
            value = read_json(policy_path, byte_cap=self.config.output_cap)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            return policy_identity, (), f"selection policy cannot be read: {exc}"
        if not isinstance(value, dict):
            return policy_identity, (), "selection policy must be a JSON object"
        raw = value.get("required_workflows", value.get("required"))
        if (
            not isinstance(raw, list)
            or not raw
            or not all(isinstance(item, str) and item for item in raw)
        ):
            return (
                policy_identity,
                (),
                "selection policy must declare a non-empty required_workflows or required list",
            )
        return policy_identity, tuple(dict.fromkeys(raw)), None

    def evidence_envelopes(
        self,
    ) -> tuple[dict[str, tuple[str, ...]], dict[str, str], dict[str, str]]:
        workflow_environment_keys = {
            name: tuple(sorted(self.config.environment(workflow)))
            for name, workflow in self.config.workflows.items()
        }
        verifier_environment_identities = {
            verifier_id: local_json_identity(
                self.config.environment(self.config.workflows[verifier.workflow])
            )
            for verifier_id, verifier in self.config.verifiers.items()
        }
        policy_paths = [
            *self.config.paths("acceptance_policies"),
            resolve_contained(
                self.config.root,
                str(self.config.raw["policies"]["selection"]),
                must_exist=False,
            ),
            resolve_contained(
                self.config.root,
                str(self.config.raw["policies"]["useful_benefit_objective"]),
                must_exist=False,
            ),
        ]
        policy_identity = content_identity(self.config.root, policy_paths)
        return (
            workflow_environment_keys,
            verifier_environment_identities,
            {verifier_id: policy_identity for verifier_id in self.config.verifiers},
        )

    def current_freeze_bindings(
        self,
        candidate_identity: str | None = None,
        freeze: Mapping[str, object] | None = None,
    ) -> dict[str, str]:
        bindings = {
            "candidate_identity": candidate_identity or self.current_candidate_identity(),
            "contract_identity": content_identity(self.config.root, self.config.paths("contracts")),
            "reference_identity": content_identity(
                self.config.root, self.config.paths("references")
            ),
            "evaluator_identity": content_identity(
                self.config.root, self.config.paths("evaluators")
            ),
            "acceptance_policy_identity": content_identity(
                self.config.root, self.config.paths("acceptance_policies")
            ),
            "protected_identity": content_identity(
                self.config.root, self.config.paths("protected")
            ),
        }
        plan = freeze.get("required_evidence_plan") if freeze is not None else None
        if isinstance(plan, str):
            plan_path = resolve_contained(self.config.root, plan, must_exist=False)
            bindings["required_evidence_plan_identity"] = content_identity(
                self.config.root, [plan_path]
            )
        return bindings

    def provider_executable(self, provider: Provider) -> tuple[Path, str]:
        value = provider.command[0]
        if "/" in value:
            path = Path(value)
            if path.is_absolute():
                try:
                    executable = path.resolve(strict=True)
                except OSError as exc:
                    raise ForgeError(
                        "PROVIDER_UNAVAILABLE",
                        f"provider {provider.provider_id} executable is unavailable: {exc}",
                    ) from exc
            else:
                executable = resolve_contained(self.config.root, value, must_exist=True)
        else:
            resolved = shutil.which(
                value, path=self.config.provider_environment(provider).get("PATH", "")
            )
            if resolved is None:
                raise ForgeError(
                    "PROVIDER_UNAVAILABLE",
                    f"provider {provider.provider_id} executable is not on the allowlisted PATH",
                )
            executable = Path(resolved).resolve(strict=True)
        if not executable.is_file() or not os.access(executable, os.X_OK):
            raise ForgeError(
                "PROVIDER_UNAVAILABLE",
                f"provider {provider.provider_id} executable is not an executable file",
            )
        identity = file_identity(executable)
        if provider.executable_identity and identity != provider.executable_identity:
            raise ForgeError(
                "PROVIDER_IDENTITY_DRIFT",
                f"provider {provider.provider_id} executable identity drifted",
            )
        return executable, identity

    def provider_workspace(self, *, evaluator: bool = False) -> tempfile.TemporaryDirectory[str]:
        temporary = tempfile.TemporaryDirectory(prefix="mncs-forge-provider-")
        workspace = Path(temporary.name)
        visible_keys = [
            "candidates",
            "generated",
            "contracts",
            "references",
            "development_evidence",
            "evaluators",
            "acceptance_policies",
        ]
        if evaluator:
            visible_keys.append("protected")
        for key in visible_keys:
            for source in self.config.paths(key):
                if not source.exists():
                    continue
                relative = source.relative_to(self.config.root)
                target = workspace / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                if source.is_dir():
                    shutil.copytree(source, target, symlinks=False, dirs_exist_ok=True)
                else:
                    shutil.copy2(source, target, follow_symlinks=True)
        return temporary

    def validate_changed_files(self, changed_files: list[str]) -> dict[str, str]:
        writable = self.config.relative_scopes("candidates", "generated")
        protected = self.config.relative_scopes(
            "contracts", "references", "evaluators", "acceptance_policies", "protected"
        )
        identities: dict[str, str] = {}
        for value in sorted(set(changed_files)):
            relative = validate_relative_path(value)
            if is_within(relative, protected):
                raise ForgeError(
                    "PROTECTED_MODIFICATION",
                    f"candidate change touches protected authority: {value}",
                )
            if not is_within(relative, writable):
                raise ForgeError(
                    "WRITE_BOUNDARY", f"candidate change is outside declared write paths: {value}"
                )
            resolved = resolve_contained(self.config.root, value, must_exist=True)
            if not resolved.is_file():
                raise ForgeError("INVALID_CHANGED_FILE", f"changed path is not a file: {value}")
            identities[value] = file_identity(resolved)
        return identities

    def command_path(self, command: list[str]) -> str | None:
        return shutil.which(command[0]) or (
            str(resolve_contained(self.config.root, command[0], must_exist=False))
            if "/" in command[0]
            else None
        )
