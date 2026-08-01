"""MNCS Forge control-plane operations shared by CLI and MCP."""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import __version__
from .config import ForgeConfig, Provider, Workflow
from .errors import ForgeError
from .execution import (
    STATUSES,
    ExecutionResult,
    parse_provider_capabilities,
    parse_provider_response,
    run_bounded,
)
from .identity import content_identity, file_identity, identity_map
from .ledger import Ledger
from .micro_verifiers import MicroVerifierService
from .paths import is_within, resolve_contained, validate_relative_path
from .serialization import canonical_bytes, local_json_identity, read_json

STATUS_ORDER = {"PASS": 0, "UNKNOWN": 1, "FAIL": 2}
CLAIM_CLASSES = (
    "mncs_implementation_result",
    "mncds_development_process_result",
    "local_reproduction",
    "operator_controlled_reproduction",
    "independent_evaluation",
    "protected_holdout",
    "witnessed_evidence",
    "operational_evidence",
    "governance_approval",
)
PUBLIC_LIMITATIONS = [
    "experimental non-normative reference implementation",
    "not required for MNCS conformance and not an accredited certification system",
    "cannot create independent evaluation, protected custody, witnessing, or governance approval",
    "local results do not promote MNCS, MNCDS, an RFC, or a case study",
    "REVIEW_REQUIRED is a workflow disposition, not an MNCS result",
    "missing or unsupported evidence remains UNKNOWN",
    "configured subprocesses are trusted providers; Forge is not an OS or network sandbox",
]
SECRET_PATTERN = re.compile(
    r"(?i)(token|secret|password|authorization|api[_-]?key)([\"'=:\\s]+)([^\\s,\"']+)"
)


def aggregate_status(statuses: Iterable[str]) -> str:
    values = [status for status in statuses if status in STATUSES]
    if not values:
        return "UNKNOWN"
    return max(values, key=STATUS_ORDER.__getitem__)


def _redact(text: str, limit: int = 4096) -> str:
    return SECRET_PATTERN.sub(r"\1\2<redacted>", text[:limit])


def _now() -> str:
    return datetime.now(UTC).isoformat()


class Forge:
    def __init__(self, config: ForgeConfig, mode: str = "development") -> None:
        if mode not in {"development", "evaluator"}:
            raise ForgeError("INVALID_MODE", "mode must be development or evaluator")
        self.config = config
        self.mode = mode
        self.ledger = Ledger(config.state_dir)

    def _require_mode(self, expected: str) -> None:
        if self.mode != expected:
            raise ForgeError(
                "MODE_FORBIDDEN", f"operation requires {expected} mode; current mode is {self.mode}"
            )

    def _records(self, kind: str) -> list[dict[str, Any]]:
        return self.ledger.records(kind)

    def _latest_payload(self, kind: str) -> dict[str, Any] | None:
        records = self._records(kind)
        return dict(records[-1]["payload"]) if records else None

    def _record_by_id(self, kind: str, identity: str, key: str) -> dict[str, Any]:
        for entry in reversed(self._records(kind)):
            payload = entry["payload"]
            if payload.get(key) == identity:
                return dict(payload)
        raise ForgeError("RECORD_NOT_FOUND", f"no {kind} record for {identity}")

    def _write_immutable(self, group: str, identity: str, value: dict[str, object]) -> Path:
        directory = self.config.state_dir / "records" / group
        directory.mkdir(parents=True, exist_ok=True)
        safe_identity = re.sub(r"[^A-Za-z0-9._-]", "_", identity)
        path = directory / f"{safe_identity}.json"
        try:
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc:
            raise ForgeError(
                "RECORD_EXISTS", f"immutable record already exists: {identity}"
            ) from exc
        try:
            os.write(descriptor, canonical_bytes(value) + b"\n")
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        return path

    def _authority_paths(self) -> list[Path]:
        return [
            *self.config.paths("contracts"),
            *self.config.paths("references"),
            *self.config.paths("evaluators"),
            *self.config.paths("acceptance_policies"),
            *self.config.paths("protected"),
        ]

    def _candidate_paths(self) -> list[Path]:
        return [*self.config.paths("candidates"), *self.config.paths("generated")]

    def _current_candidate_identity(self) -> str:
        return content_identity(self.config.root, self._candidate_paths())

    def _current_authority_identities(self) -> dict[str, str]:
        return identity_map(self.config.root, self._authority_paths())

    def _command_version(self, command: list[str]) -> str:
        try:
            result = run_bounded(
                [*command, "version"],
                cwd=self.config.root,
                timeout=min(self.config.timeout, 10),
                output_cap=min(self.config.output_cap, 65536),
                environment={"PATH": os.environ.get("PATH", "")},
            )
            if result.returncode != 0:
                result = run_bounded(
                    [*command, "--version"],
                    cwd=self.config.root,
                    timeout=min(self.config.timeout, 10),
                    output_cap=min(self.config.output_cap, 65536),
                    environment={"PATH": os.environ.get("PATH", "")},
                )
            return (
                _redact(result.stdout.decode("utf-8", errors="replace").strip(), 512) or "UNKNOWN"
            )
        except ForgeError:
            return "UNKNOWN"

    def doctor(self) -> dict[str, object]:
        ledger: dict[str, object]
        try:
            ledger = self.ledger.verify()
        except ForgeError as exc:
            ledger = exc.as_dict()
        commands = {
            name: {
                "argv": value,
                "executable": shutil.which(value[0])
                or (
                    str(resolve_contained(self.config.root, value[0], must_exist=False))
                    if "/" in value[0]
                    else None
                ),
            }
            for name, value in self.config.public_commands().items()
        }
        return {
            "ok": bool(ledger.get("ok", False)),
            "forge_version": __version__,
            "config": str(self.config.config_path),
            "project_root": str(self.config.root),
            "mode": self.mode,
            "ledger": ledger,
            "commands": commands,
            "network_required": False,
            "limitations": PUBLIC_LIMITATIONS,
        }

    def project_inspect(self) -> dict[str, object]:
        epoch = self._latest_payload("epoch")
        candidate = self._latest_payload("candidate")
        commands = self.config.public_commands()
        providers = self.provider_list()
        return {
            "project": {
                "name": self.config.project_name,
                "identity": self.config.project_identity,
                "root": str(self.config.root),
            },
            "mode": self.mode,
            "configured_paths": self.config.path_values,
            "candidate_write_boundaries": [
                str(path) for path in self.config.relative_scopes("candidates", "generated")
            ],
            "protected_authorities": [
                str(path)
                for path in self.config.relative_scopes(
                    "contracts",
                    "references",
                    "evaluators",
                    "acceptance_policies",
                    "protected",
                )
            ],
            "declared_workflows": [
                {
                    "name": item.name,
                    "category": item.category,
                    "mode": item.mode,
                    "provider_protocol": item.provider_protocol,
                    "subject": item.subject,
                }
                for item in self.config.workflows.values()
            ],
            "current_epoch": epoch,
            "active_candidate": candidate,
            "available_public_commands": list(commands),
            "detected_versions": {
                name: self._command_version(command) for name, command in commands.items()
            },
            "configured_providers": providers["providers"],
            "required_capabilities": self.config.required_capabilities,
            "provider_discovery_status": providers["status"],
            "declared_micro_verifiers": MicroVerifierService(self).list_declared()["verifiers"],
            "limitations": PUBLIC_LIMITATIONS,
        }

    def _latest_provider_probe(self, provider_id: str) -> dict[str, Any] | None:
        for entry in reversed(self._records("provider_probe")):
            payload = entry["payload"]
            if payload.get("provider_id") == provider_id:
                return dict(payload)
        return None

    def _provider_executable(self, provider: Provider) -> tuple[Path, str]:
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

    @staticmethod
    def _provider_declared_model(provider: Provider) -> dict[str, object]:
        return {
            "provider_id": provider.provider_id,
            "name": provider.name,
            "declared_identity": provider.identity,
            "declared_version": provider.version,
            "command": [_redact(item, 1024) for item in provider.command],
            "transport": provider.transport,
            "required": provider.required,
            "declared_capabilities": provider.capabilities,
            "supported_constructs": provider.supported_constructs,
            "unsupported_constructs": provider.unsupported_constructs,
            "limitations": provider.limitations,
            "expected_executable_identity": provider.executable_identity,
            "descriptor": provider.descriptor,
        }

    def _provider_inventory_item(self, provider: Provider) -> dict[str, object]:
        item = self._provider_declared_model(provider)
        latest = self._latest_provider_probe(provider.provider_id)
        item.update(
            {
                "availability": "UNKNOWN",
                "status": "UNKNOWN",
                "executable": None,
                "executable_identity": None,
                "last_probe_result": latest,
                "probe_stale": False,
            }
        )
        try:
            executable, identity = self._provider_executable(provider)
        except ForgeError as exc:
            item.update(
                {
                    "availability": "UNAVAILABLE",
                    "limitations": [*provider.limitations, exc.message],
                    "availability_error": exc.code,
                }
            )
            return item
        probe_stale = bool(latest and latest.get("executable_identity") != identity)
        item.update(
            {
                "availability": "AVAILABLE",
                "executable": str(executable),
                "executable_identity": identity,
                "status": (
                    "PASS"
                    if latest and latest.get("status") == "PASS" and not probe_stale
                    else "UNKNOWN"
                ),
                "probe_stale": probe_stale,
            }
        )
        return item

    def provider_list(self) -> dict[str, object]:
        providers = [
            self._provider_inventory_item(provider) for provider in self.config.providers.values()
        ]
        return {
            "providers": providers,
            "configured_count": len(providers),
            "required_capabilities": self.config.required_capabilities,
            "status": aggregate_status(str(item["status"]) for item in providers),
            "limitations": (
                [
                    "no providers are configured; Forge does not infer structural capability "
                    "from source reading or command availability"
                ]
                if not providers
                else [
                    "availability is not analysis evidence; a recognized explicit capability "
                    "probe is required before a capability can satisfy policy"
                ]
            ),
            "dominance": "FAIL > UNKNOWN > PASS",
        }

    def _record_provider_probe(self, record: dict[str, object]) -> dict[str, object]:
        record["output_identity"] = local_json_identity(record)
        self._write_immutable("provider-probes", str(record["output_identity"]), record)
        self.ledger.append("provider_probe", record)
        return record

    def provider_probe(self, provider_id: str) -> dict[str, object]:
        self._require_mode("development")
        try:
            provider = self.config.providers[provider_id]
        except KeyError as exc:
            raise ForgeError(
                "PROVIDER_NOT_CONFIGURED", f"provider is not configured: {provider_id}"
            ) from exc
        started_at = _now()
        executable_identity: str | None = None
        executable: Path | None = None
        try:
            executable, executable_identity = self._provider_executable(provider)
            request = {
                "protocol_version": "0.1",
                "type": "capabilities",
                "request_id": "forge-capabilities-"
                + local_json_identity(
                    {
                        "provider": provider.provider_id,
                        "executable": executable_identity,
                        "at": started_at,
                    }
                ).split(":", 1)[1][:24],
                "extensions": {},
            }
            with tempfile.TemporaryDirectory(prefix="mncs-forge-provider-probe-") as temporary:
                execution = run_bounded(
                    [str(executable), *provider.command[1:]],
                    cwd=Path(temporary),
                    timeout=self.config.timeout,
                    output_cap=self.config.output_cap,
                    environment=self.config.provider_environment(provider),
                    stdin=canonical_bytes(request) + b"\n",
                )
            if execution.returncode != 0:
                raise ForgeError(
                    "PROVIDER_EXIT",
                    f"provider exited {execution.returncode}: "
                    + _redact(execution.stderr.decode("utf-8", errors="replace")),
                )
            response = parse_provider_capabilities(execution.stdout)
            response_identity = dict(response["provider"])
            if not any(
                isinstance(response_identity.get(key), str) and response_identity.get(key)
                for key in ("id", "name")
            ) or not any(
                isinstance(response_identity.get(key), str) and response_identity.get(key)
                for key in ("identity", "version")
            ):
                raise ForgeError(
                    "PROVIDER_MALFORMED",
                    "provider probe requires a name/id and an identity/version",
                )
            if (
                provider.identity is not None
                and response_identity.get("identity") != provider.identity
            ):
                raise ForgeError(
                    "PROVIDER_IDENTITY_DRIFT",
                    f"provider {provider.provider_id} reported a different identity",
                )
            if (
                provider.version is not None
                and response_identity.get("version") != provider.version
            ):
                raise ForgeError(
                    "PROVIDER_IDENTITY_DRIFT",
                    f"provider {provider.provider_id} reported a different version",
                )
            extensions = dict(response["extensions"])
            probed_capabilities = list(response["analyses"])
            unsupported = list(extensions.get("unsupported_constructs", []))
            record: dict[str, object] = {
                **self._provider_declared_model(provider),
                "availability": "AVAILABLE",
                "status": "PASS",
                "probe_kind": "provider-protocol-capabilities",
                "provider_identity": response_identity,
                "executable": str(executable),
                "executable_identity": executable_identity,
                "probed_capabilities": probed_capabilities,
                "supported_constructs": list(
                    extensions.get("supported_constructs", provider.supported_constructs)
                ),
                "unsupported_constructs": sorted(
                    set([*provider.unsupported_constructs, *unsupported])
                ),
                "limitations": [
                    *provider.limitations,
                    *list(extensions.get("limitations", [])),
                    "capability-probe PASS is not analysis or conformance PASS",
                ],
                "protocol_statuses": list(response["statuses"]),
                "cancellation": bool(response["cancellation"]),
                "health_checks": bool(response["health_checks"]),
                "duration_seconds": execution.duration_seconds,
                "stderr_diagnostic": _redact(execution.stderr.decode("utf-8", errors="replace")),
                "returncode": execution.returncode,
                "recorded_at": _now(),
            }
            return self._record_provider_probe(record)
        except ForgeError as exc:
            record = {
                **self._provider_declared_model(provider),
                "availability": (
                    "UNAVAILABLE"
                    if exc.code in {"PROVIDER_UNAVAILABLE", "COMMAND_START"}
                    else "UNKNOWN"
                ),
                "status": "UNKNOWN",
                "probe_kind": "provider-protocol-capabilities",
                "provider_identity": None,
                "executable": str(executable) if executable else None,
                "executable_identity": executable_identity,
                "probed_capabilities": [],
                "limitations": [*provider.limitations, exc.message],
                "error_code": exc.code,
                "recorded_at": _now(),
            }
            return self._record_provider_probe(record)

    def capability_blockers(
        self, required_capabilities: list[str] | None = None
    ) -> dict[str, object]:
        required = sorted(set([*self.config.required_capabilities, *(required_capabilities or [])]))
        inventory = {
            provider.provider_id: self._provider_inventory_item(provider)
            for provider in self.config.providers.values()
        }
        blockers: list[dict[str, object]] = []
        satisfied: list[dict[str, object]] = []
        informational: list[dict[str, object]] = []
        for provider in self.config.providers.values():
            item = inventory[provider.provider_id]
            if provider.required and item["status"] != "PASS":
                blockers.append(
                    {
                        "kind": "required_provider",
                        "provider_id": provider.provider_id,
                        "status": "UNKNOWN",
                        "problem": (
                            "required provider is unavailable, unprobed, stale, or inconclusive"
                        ),
                    }
                )
            elif not provider.required and item["availability"] != "AVAILABLE":
                informational.append(
                    {
                        "kind": "optional_provider",
                        "provider_id": provider.provider_id,
                        "status": "UNKNOWN",
                        "problem": "optional provider is unavailable",
                    }
                )
        for capability in required:
            candidates = [
                item
                for provider_id, item in inventory.items()
                if capability in self.config.providers[provider_id].capabilities
            ]
            established = [
                item
                for item in candidates
                if item["status"] == "PASS"
                and isinstance(item["last_probe_result"], dict)
                and capability in item["last_probe_result"].get("probed_capabilities", [])
                and capability not in item["last_probe_result"].get("unsupported_constructs", [])
            ]
            if established:
                satisfied.append(
                    {
                        "capability": capability,
                        "status": "PASS",
                        "providers": sorted(str(item["provider_id"]) for item in established),
                        "scope": "validated capability discovery only",
                    }
                )
            else:
                blockers.append(
                    {
                        "kind": "required_capability",
                        "capability": capability,
                        "status": "UNKNOWN",
                        "providers": sorted(str(item["provider_id"]) for item in candidates),
                        "problem": (
                            "no current recognized provider probe established this capability"
                        ),
                    }
                )
        return {
            "required_capabilities": required,
            "satisfied": satisfied,
            "blockers": blockers,
            "informational_limitations": informational,
            "blocked": bool(blockers),
            "status": aggregate_status(str(item["status"]) for item in [*satisfied, *blockers])
            if required or blockers
            else "PASS",
            "no_requirement_note": (
                "PASS with no required capabilities means only that no capability policy "
                "is blocked; it is not structural-analysis evidence"
                if not required and not blockers
                else None
            ),
            "missing_is_pass": False,
            "dominance": "FAIL > UNKNOWN > PASS",
        }

    def verifier_list(self) -> dict[str, object]:
        return MicroVerifierService(self).list_declared()

    def verifier_describe(self, verifier_id: str) -> dict[str, object]:
        return MicroVerifierService(self).describe(verifier_id)

    def verifier_match(
        self,
        *,
        uncertainty_classes: list[str],
        language: str | None = None,
        artifact_type: str | None = None,
        changed_paths: list[str] | None = None,
        scope: str | None = None,
        maximum_cost: str = "high",
        required_category: str | None = None,
        active_mode: str | None = None,
    ) -> dict[str, object]:
        return MicroVerifierService(self).match(
            uncertainty_classes=uncertainty_classes,
            language=language,
            artifact_type=artifact_type,
            changed_paths=changed_paths,
            scope=scope,
            maximum_cost=maximum_cost,
            required_category=required_category,
            active_mode=active_mode,
        )

    def verifier_run(
        self,
        verifier_id: str,
        *,
        candidate_identity: str | None = None,
        changed_paths: list[str] | None = None,
        scope: str | None = None,
        source_region: dict[str, object] | None = None,
        contract_identity: str | None = None,
        dependency_slice_identities: dict[str, str] | None = None,
        prior_artifact_identity: str | None = None,
        question_parameters: dict[str, object] | None = None,
    ) -> dict[str, object]:
        return MicroVerifierService(self).run(
            verifier_id,
            candidate_identity=candidate_identity,
            changed_paths=changed_paths,
            scope=scope,
            source_region=source_region,
            contract_identity=contract_identity,
            dependency_slice_identities=dependency_slice_identities,
            prior_artifact_identity=prior_artifact_identity,
            question_parameters=question_parameters,
        )

    def verifier_batch(
        self,
        verifier_ids: list[str],
        *,
        candidate_identity: str | None = None,
        changed_paths: list[str] | None = None,
        scope: str | None = None,
        source_region: dict[str, object] | None = None,
        contract_identity: str | None = None,
        dependency_slice_identities: dict[str, str] | None = None,
        prior_artifact_identity: str | None = None,
        question_parameters: dict[str, object] | None = None,
    ) -> dict[str, object]:
        return MicroVerifierService(self).batch(
            verifier_ids,
            candidate_identity=candidate_identity,
            changed_paths=changed_paths,
            scope=scope,
            source_region=source_region,
            contract_identity=contract_identity,
            dependency_slice_identities=dependency_slice_identities,
            prior_artifact_identity=prior_artifact_identity,
            question_parameters=question_parameters,
        )

    def verifier_explain(self, output_identity: str) -> dict[str, object]:
        return MicroVerifierService(self).explain(output_identity)

    def epoch_begin(
        self,
        *,
        generator_identity: str,
        evaluator_identity: str,
        parent_epoch: str | None = None,
        authority_overlap: list[str] | None = None,
    ) -> dict[str, object]:
        self._require_mode("development")
        if parent_epoch:
            self._record_by_id("epoch", parent_epoch, "epoch_id")
        contract = content_identity(self.config.root, self.config.paths("contracts"))
        objective_path = resolve_contained(
            self.config.root,
            str(self.config.raw["policies"]["useful_benefit_objective"]),
            must_exist=False,
        )
        evaluator = content_identity(self.config.root, self.config.paths("evaluators"))
        baseline = content_identity(
            self.config.root,
            [*self._candidate_paths(), *self._authority_paths()],
        )
        record: dict[str, object] = {
            "baseline_identity": baseline,
            "generator_identity": generator_identity,
            "evaluator_identity": evaluator_identity or evaluator,
            "contract_identity": contract,
            "objective_identity": content_identity(self.config.root, [objective_path]),
            "visible_partition_identities": identity_map(
                self.config.root,
                [
                    *self.config.paths("contracts"),
                    *self.config.paths("references"),
                    *self.config.paths("development_evidence"),
                ],
            ),
            "authority_identities": self._current_authority_identities(),
            "declared_authority_overlap": sorted(authority_overlap or []),
            "parent_epoch": parent_epoch,
            "created_at": _now(),
        }
        record["epoch_id"] = "epoch:" + local_json_identity(record).split(":", 1)[1]
        self._write_immutable("epochs", str(record["epoch_id"]), record)
        self.ledger.append("epoch", record)
        return record

    def _validate_changed_files(self, changed_files: list[str]) -> dict[str, str]:
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

    def candidate_register(
        self,
        *,
        changed_files: list[str],
        hypothesis: str,
        generator_identity: str,
        generator_config_identity: str,
        parent_candidate: str | None = None,
        expected_identity: str | None = None,
    ) -> dict[str, object]:
        self._require_mode("development")
        epoch = self._latest_payload("epoch")
        if epoch is None:
            raise ForgeError("NO_ACTIVE_EPOCH", "begin an epoch before registering a candidate")
        if self._current_authority_identities() != epoch["authority_identities"]:
            raise ForgeError("STALE_BASELINE", "protected authority drifted since the epoch began")
        if parent_candidate:
            self._record_by_id("candidate", parent_candidate, "candidate_id")
        current = self._current_candidate_identity()
        if expected_identity is not None and expected_identity != current:
            raise ForgeError("STALE_CANDIDATE", "candidate identity does not match current content")
        current_files = self._validate_changed_files(changed_files)
        objective_path = resolve_contained(
            self.config.root,
            str(self.config.raw["policies"]["useful_benefit_objective"]),
            must_exist=False,
        )
        record: dict[str, object] = {
            "candidate_id": current,
            "parent_candidate": parent_candidate,
            "changed_files": sorted(current_files),
            "declared_hypothesis": hypothesis,
            "generator_identity": generator_identity,
            "generator_configuration_identity": generator_config_identity,
            "source_epoch": epoch["epoch_id"],
            "registered_at": _now(),
            "current_file_identities": current_files,
            "useful_benefit_objective": str(
                self.config.raw["policies"]["useful_benefit_objective"]
            ),
            "objective_identity": content_identity(self.config.root, [objective_path]),
            "supersedes": None,
        }
        self._write_immutable("candidates", current, record)
        self.ledger.append("candidate", record)
        return record

    def _candidate(self, candidate_id: str | None) -> dict[str, Any]:
        candidate = (
            self._record_by_id("candidate", candidate_id, "candidate_id")
            if candidate_id
            else self._latest_payload("candidate")
        )
        if candidate is None:
            raise ForgeError("NO_CANDIDATE", "no registered candidate exists")
        if candidate["candidate_id"] != self._current_candidate_identity():
            raise ForgeError(
                "STALE_CANDIDATE", "registered candidate no longer matches current content"
            )
        return candidate

    def _workflow(self, name: str, expected_mode: str) -> Workflow:
        try:
            workflow = self.config.workflows[name]
        except KeyError as exc:
            raise ForgeError("UNDECLARED_COMMAND", f"workflow is not declared: {name}") from exc
        if workflow.mode not in {expected_mode, "both"}:
            raise ForgeError(
                "WORKFLOW_MODE", f"workflow {name} is not declared for {expected_mode} mode"
            )
        return workflow

    def _provider_workspace(self, *, evaluator: bool = False) -> tempfile.TemporaryDirectory[str]:
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

    def _run_workflow(
        self, workflow: Workflow, candidate: dict[str, Any], *, evaluator: bool
    ) -> dict[str, object]:
        request: dict[str, object] | None = None
        stdin = b""
        working_directory = self.config.root
        temporary: tempfile.TemporaryDirectory[str] | None = None
        if workflow.provider_protocol:
            request = {
                "protocol_version": "0.1",
                "type": "analysis_request",
                "request_id": "forge-"
                + local_json_identity(
                    {
                        "candidate": candidate["candidate_id"],
                        "workflow": workflow.name,
                        "at": _now(),
                    }
                ).split(":", 1)[1][:24],
                "analysis": workflow.category,
                "component": {
                    "candidate_identity": candidate["candidate_id"],
                    "source_epoch": candidate["source_epoch"],
                },
                "limits": {
                    "timeout_seconds": self.config.timeout,
                    "output_bytes": self.config.output_cap,
                },
                "extensions": {"mncs_forge": {"mode": self.mode}},
            }
            stdin = canonical_bytes(request) + b"\n"
            temporary = self._provider_workspace(evaluator=evaluator)
            working_directory = Path(temporary.name)
        elif evaluator:
            temporary = self._provider_workspace(evaluator=True)
            working_directory = Path(temporary.name)
        try:
            execution = run_bounded(
                workflow.command,
                cwd=working_directory,
                timeout=self.config.timeout,
                output_cap=self.config.output_cap,
                environment=self.config.environment(workflow),
                stdin=stdin,
            )
        finally:
            if temporary is not None:
                temporary.cleanup()
        return self._execution_record(workflow, execution, candidate, request, evaluator=evaluator)

    def _execution_record(
        self,
        workflow: Workflow,
        execution: ExecutionResult,
        candidate: dict[str, Any],
        request: dict[str, object] | None,
        *,
        evaluator: bool,
    ) -> dict[str, object]:
        protocol: dict[str, Any] | None = None
        if workflow.provider_protocol:
            if execution.returncode != 0:
                raise ForgeError(
                    "PROVIDER_EXIT",
                    f"provider exited {execution.returncode}: "
                    + _redact(execution.stderr.decode("utf-8", errors="replace")),
                )
            protocol = parse_provider_response(execution.stdout)
            status = str(protocol.get("status", "UNKNOWN"))
            method = str(protocol.get("type"))
            provider = dict(protocol["provider"])
            witnesses = list(protocol.get("witnesses", []))
            limitations = list(protocol.get("limitations", []))
            unsupported = list(protocol.get("extensions", {}).get("unsupported", []))
        else:
            status = "UNKNOWN"
            method = "declared-command"
            provider = {"id": workflow.provider_id or workflow.name, "kind": "declared-workflow"}
            witnesses = []
            limitations = [
                "command completion is not evidence PASS; "
                "no validated structured result was emitted"
            ]
            unsupported = []
            if execution.returncode != 0:
                status = "FAIL"
                witnesses = [{"exit_code": execution.returncode}]
                limitations = []
            elif execution.stdout:
                try:
                    value = json.loads(execution.stdout)
                    if isinstance(value, dict) and value.get("status") in STATUSES:
                        status = str(value["status"])
                        witnesses = list(value.get("witnesses", []))
                        limitations = list(value.get("limitations", []))
                        unsupported = list(value.get("unsupported_constructs", []))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    pass
        if evaluator and workflow.disclosure == "status-only":
            witnesses = []
        record: dict[str, object] = {
            "candidate_identity": candidate["candidate_id"],
            "subject_type": workflow.subject,
            "provider_or_evaluator_identity": provider,
            "method": method,
            "workflow": workflow.name,
            "category": workflow.category,
            "scope": "declared configuration paths",
            "environment": {
                "allowlisted_keys": sorted(self.config.environment(workflow)),
                "values_disclosed": False,
            },
            "duration_seconds": execution.duration_seconds,
            "status": status,
            "witnesses_or_counterexamples": witnesses[:20],
            "limitations": limitations[:20],
            "unsupported_constructs": unsupported[:20],
            "stderr_diagnostic": _redact(execution.stderr.decode("utf-8", errors="replace")),
            "returncode": execution.returncode,
            "recorded_at": _now(),
            "protocol_request_identity": local_json_identity(request) if request else None,
        }
        record["output_identity"] = local_json_identity(record)
        return record

    def development_checks_run(
        self, workflow_names: list[str], candidate_id: str | None = None
    ) -> dict[str, object]:
        self._require_mode("development")
        results: list[dict[str, object]] = []
        candidate: dict[str, Any] | None = None
        for name in workflow_names:
            workflow = self._workflow(name, "development")
            if workflow.subject == "project":
                if candidate_id is not None:
                    raise ForgeError(
                        "WORKFLOW_SUBJECT",
                        f"project workflow {name} does not accept a candidate identity",
                    )
                subject = {
                    "candidate_id": f"project:{self.config.project_identity}",
                    "source_epoch": None,
                }
            else:
                candidate = candidate or self._candidate(candidate_id)
                subject = candidate
            result = self._run_workflow(workflow, subject, evaluator=False)
            self._write_immutable("results", str(result["output_identity"]), result)
            self.ledger.append("result", result)
            results.append(result)
        return {
            "candidate_identity": candidate["candidate_id"] if candidate else None,
            "subject_identities": sorted({str(item["candidate_identity"]) for item in results}),
            "results": results,
            "aggregate_status": aggregate_status(str(item["status"]) for item in results),
            "dominance": "FAIL > UNKNOWN > PASS",
        }

    def _result_records(self, candidate_id: str | None = None) -> list[dict[str, Any]]:
        results = [dict(entry["payload"]) for entry in self._records("result")]
        if candidate_id is not None:
            return [item for item in results if item.get("candidate_identity") == candidate_id]
        return results

    def failure_explain(self, output_identity: str | None = None) -> dict[str, object]:
        results = self._result_records()
        if output_identity:
            results = [item for item in results if item.get("output_identity") == output_identity]
        if not results:
            raise ForgeError("RESULT_NOT_FOUND", "no matching check result exists")
        result = results[-1]
        status = str(result["status"])
        base: dict[str, object] = {
            "status": status,
            "candidate_identity": result["candidate_identity"],
            "workflow": result["workflow"],
            "affected_claim": result["category"],
            "repair_allowed": self.mode == "development",
        }
        if status == "FAIL":
            base.update(
                {
                    "violated_invariant_or_gate": result["category"],
                    "witness_or_counterexample": result["witnesses_or_counterexamples"],
                    "relevant_locations": [
                        item.get("location")
                        for item in result["witnesses_or_counterexamples"]
                        if isinstance(item, dict) and item.get("location")
                    ],
                    "permitted_next_actions": (
                        [
                            "inspect compact witness",
                            "repair within declared write paths",
                            "rerun check",
                        ]
                        if self.mode == "development"
                        else ["record rejection", "start a new development epoch"]
                    ),
                }
            )
        elif status == "UNKNOWN":
            base.update(
                {
                    "exact_unresolved_fact": result["limitations"]
                    or result["unsupported_constructs"]
                    or ["provider did not establish PASS or FAIL"],
                    "provider_limitation": result["limitations"],
                    "required_evidence_or_provider": (
                        "a declared provider that supports the unresolved semantics"
                    ),
                    "uncertainty_under_current_policy": (
                        "mandatory until a declared policy says otherwise"
                    ),
                }
            )
        else:
            base["message"] = "result is PASS; there is no failure or unknown to explain"
        return base

    def candidate_compare(self, candidate_ids: list[str]) -> dict[str, object]:
        if len(candidate_ids) < 2:
            raise ForgeError("COMPARE_INPUT", "at least two candidate identities are required")
        policy_path = resolve_contained(
            self.config.root, str(self.config.raw["policies"]["selection"]), must_exist=False
        )
        policy_identity = content_identity(self.config.root, [policy_path])
        candidates: list[dict[str, object]] = []
        for candidate_id in candidate_ids:
            self._record_by_id("candidate", candidate_id, "candidate_id")
            results = self._result_records(candidate_id)
            statuses = [str(item["status"]) for item in results]
            candidates.append(
                {
                    "candidate_identity": candidate_id,
                    "correctness_and_safety": aggregate_status(statuses),
                    "resource_constraints": [
                        item["status"] for item in results if item["category"] == "resource_checks"
                    ]
                    or ["UNKNOWN"],
                    "useful_benefit_measurements": [
                        item["witnesses_or_counterexamples"]
                        for item in results
                        if item["category"] == "benchmark"
                    ],
                    "regressions": [
                        item["workflow"] for item in results if item["status"] == "FAIL"
                    ],
                    "evidence_completeness": "complete"
                    if results and all(item["status"] == "PASS" for item in results)
                    else "incomplete",
                    "unknown_results": [
                        item["workflow"] for item in results if item["status"] == "UNKNOWN"
                    ],
                    "environmental_comparability": "UNKNOWN",
                }
            )
        return {
            "selection_policy": str(self.config.raw["policies"]["selection"]),
            "selection_policy_identity": policy_identity,
            "candidates": candidates,
            "pareto_or_tie_status": "REVIEW_REQUIRED",
            "selected_candidate": None,
            "note": "Forge does not select on a single observed benchmark run",
        }

    def candidate_disposition(
        self, candidate_id: str, *, disposition: str, reason: str
    ) -> dict[str, object]:
        self._require_mode("development")
        self._record_by_id("candidate", candidate_id, "candidate_id")
        if disposition not in {"selected", "rejected"}:
            raise ForgeError("INVALID_DISPOSITION", "disposition must be selected or rejected")
        results = self._result_records(candidate_id)
        aggregate = aggregate_status(str(item["status"]) for item in results)
        if disposition == "selected" and aggregate != "PASS":
            raise ForgeError(
                "SELECTION_BLOCKED",
                f"selection requires complete comparable PASS evidence; aggregate is {aggregate}",
            )
        policy_path = resolve_contained(
            self.config.root, str(self.config.raw["policies"]["selection"]), must_exist=False
        )
        record: dict[str, object] = {
            "candidate_identity": candidate_id,
            "disposition": disposition,
            "reason": reason,
            "selection_rule": str(self.config.raw["policies"]["selection"]),
            "selection_policy_identity": content_identity(self.config.root, [policy_path]),
            "evidence_status": aggregate,
            "recorded_at": _now(),
        }
        record["disposition_id"] = "disposition:" + local_json_identity(record).split(":", 1)[1]
        self._write_immutable("dispositions", str(record["disposition_id"]), record)
        self.ledger.append("disposition", record)
        return record

    def candidate_freeze(
        self, candidate_id: str, *, environment_identity: str, required_evidence_plan: str
    ) -> dict[str, object]:
        self._require_mode("development")
        candidate = self._candidate(candidate_id)
        selections = [
            dict(entry["payload"])
            for entry in self._records("disposition")
            if entry["payload"].get("candidate_identity") == candidate_id
            and entry["payload"].get("disposition") == "selected"
        ]
        if not selections:
            raise ForgeError("FREEZE_BLOCKED", "candidate must have an immutable selection record")
        plan_path = resolve_contained(self.config.root, required_evidence_plan, must_exist=True)
        paths = self.config.raw["paths"]
        record: dict[str, object] = {
            "candidate_identity": candidate["candidate_id"],
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
            "selection_record": selections[-1]["disposition_id"],
            "environment": environment_identity,
            "required_evidence_plan": required_evidence_plan,
            "required_evidence_plan_identity": content_identity(self.config.root, [plan_path]),
            "frozen_path_sets": {
                key: list(paths[key])
                for key in ("candidates", "contracts", "references", "evaluators", "protected")
            },
            "frozen_at": _now(),
        }
        record["freeze_id"] = "freeze:" + local_json_identity(record).split(":", 1)[1]
        self._write_immutable("freezes", str(record["freeze_id"]), record)
        self.ledger.append("freeze", record)
        return record

    def _verify_freeze(self, freeze: dict[str, Any]) -> None:
        checks = {
            "candidate_identity": self._current_candidate_identity(),
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
        drift = [name for name, value in checks.items() if freeze.get(name) != value]
        if drift:
            raise ForgeError(
                "FREEZE_DRIFT", "frozen identities drifted: " + ", ".join(sorted(drift))
            )

    def final_evaluation_run(self, workflow_names: list[str]) -> dict[str, object]:
        self._require_mode("evaluator")
        freeze = self._latest_payload("freeze")
        if freeze is None:
            raise ForgeError("NO_FREEZE", "evaluator mode requires a frozen candidate")
        self._verify_freeze(freeze)
        candidate = self._record_by_id(
            "candidate", str(freeze["candidate_identity"]), "candidate_id"
        )
        results: list[dict[str, object]] = []
        for name in workflow_names:
            workflow = self._workflow(name, "evaluator")
            before = self._current_authority_identities()
            candidate_before = self._current_candidate_identity()
            result = self._run_workflow(workflow, candidate, evaluator=True)
            if before != self._current_authority_identities():
                raise ForgeError("EVALUATION_DRIFT", "authority files changed during evaluation")
            if candidate_before != self._current_candidate_identity():
                raise ForgeError("EVALUATION_DRIFT", "candidate changed during evaluation")
            self._verify_freeze(freeze)
            self._write_immutable("evaluations", str(result["output_identity"]), result)
            self.ledger.append("evaluation", result)
            results.append(result)
        return {
            "freeze_id": freeze["freeze_id"],
            "candidate_identity": freeze["candidate_identity"],
            "results": [
                {
                    "workflow": item["workflow"],
                    "status": item["status"],
                    "limitations": item["limitations"],
                    "output_identity": item["output_identity"],
                }
                for item in results
            ],
            "aggregate_status": aggregate_status(str(item["status"]) for item in results),
            "repair_feedback_withheld": True,
            "dominance": "FAIL > UNKNOWN > PASS",
        }

    def _structured_statuses(self) -> list[dict[str, str]]:
        records: list[dict[str, str]] = []
        seen = 0
        for root in [
            *self.config.paths("development_evidence"),
            *self.config.paths("outputs"),
        ]:
            paths = (
                [root] if root.is_file() else sorted(root.rglob("*.json")) if root.exists() else []
            )
            for path in paths:
                if seen >= 1000:
                    break
                seen += 1
                try:
                    value = read_json(path, byte_cap=self.config.output_cap)
                except (OSError, ValueError, json.JSONDecodeError):
                    continue
                statuses = self._extract_statuses(value)
                for status in statuses:
                    relative = path.relative_to(self.config.root).as_posix()
                    records.append(
                        {
                            "source": relative,
                            "status": status,
                            "claim_class": self._classify_record(relative),
                        }
                    )
        return records

    def _extract_statuses(self, value: object) -> list[str]:
        statuses: list[str] = []
        if isinstance(value, dict):
            for key, child in value.items():
                if key in {"status", "result", "overall_status", "aggregate_status"}:
                    if isinstance(child, str) and child in STATUSES:
                        statuses.append(child)
                elif isinstance(child, (dict, list)):
                    statuses.extend(self._extract_statuses(child))
        elif isinstance(value, list):
            for child in value:
                statuses.extend(self._extract_statuses(child))
        return statuses

    @staticmethod
    def _classify_record(path: str) -> str:
        lowered = path.lower()
        if "mncds" in lowered or "development-record" in lowered:
            return "mncds_development_process_result"
        if "independent" in lowered:
            return "independent_evaluation"
        if "holdout" in lowered or "protected" in lowered:
            return "protected_holdout"
        if "witness" in lowered:
            return "witnessed_evidence"
        if "operational" in lowered or "monitor" in lowered:
            return "operational_evidence"
        if "governance" in lowered or "approval" in lowered:
            return "governance_approval"
        if "reproduction" in lowered:
            return "local_reproduction"
        return "mncs_implementation_result"

    def claim_status(self) -> dict[str, object]:
        source_records = self._structured_statuses()
        statuses: dict[str, str] = {}
        sources: dict[str, list[str]] = {}
        for claim_class in CLAIM_CLASSES:
            matching = [item for item in source_records if item["claim_class"] == claim_class]
            statuses[claim_class] = aggregate_status(item["status"] for item in matching)
            sources[claim_class] = sorted({item["source"] for item in matching})[:20]
        statuses["operator_controlled_reproduction"] = "UNKNOWN"
        statuses["promotion_disposition"] = (
            "REVIEW_REQUIRED"
            if all(value == "PASS" for value in statuses.values())
            else "NOT_PROMOTABLE"
        )
        return {
            "statuses": statuses,
            "sources": sources,
            "dominance": "FAIL > UNKNOWN > PASS",
            "promotion_note": "REVIEW_REQUIRED is a workflow disposition, not an MNCS result",
            "missing_is_pass": False,
        }

    def claim_blockers(self, requested_claim: str) -> dict[str, object]:
        status = self.claim_status()
        raw_statuses = status["statuses"]
        if not isinstance(raw_statuses, dict):
            raise ForgeError("INTERNAL_STATUS", "claim status map is invalid")
        statuses = {str(key): str(value) for key, value in raw_statuses.items()}
        mapping = {
            "mncs": ["mncs_implementation_result"],
            "mncds": ["mncds_development_process_result"],
            "independent": ["independent_evaluation"],
            "protected": ["protected_holdout"],
            "promotion": list(CLAIM_CLASSES),
        }
        required = mapping.get(requested_claim, [requested_claim])
        blockers: list[dict[str, str]] = []
        category_map = {
            "mncs_implementation_result": "locally_executable_work",
            "mncds_development_process_result": "locally_executable_work",
            "local_reproduction": "locally_executable_work",
            "operator_controlled_reproduction": "physical_machine_work",
            "independent_evaluation": "independent_evaluator_work",
            "protected_holdout": "protected_custody_work",
            "witnessed_evidence": "witnessed_work",
            "operational_evidence": "operational_work",
            "governance_approval": "governance_work",
        }
        for name in required:
            current = statuses.get(name, "UNKNOWN")
            if current != "PASS":
                blockers.append(
                    {
                        "claim_class": name,
                        "status": current,
                        "problem": "failed evidence"
                        if current == "FAIL"
                        else "absent or unsupported evidence",
                        "work_class": category_map.get(name, "unsupported_work"),
                    }
                )
        return {
            "requested_claim": requested_claim,
            "blockers": blockers,
            "blocked": bool(blockers),
            "stale_or_conflicting": [
                item["source"]
                for item in self._structured_statuses()
                if item["status"] in {"FAIL", "UNKNOWN"}
            ][:20],
            "boundary": "Forge reports blockers; it cannot create external authority or promotion",
        }

    def evidence_reconcile(self, candidate_id: str | None = None) -> dict[str, object]:
        results = self._result_records(candidate_id)
        by_category: dict[str, list[dict[str, Any]]] = {}
        for result in results:
            by_category.setdefault(str(result["category"]), []).append(result)
        categories: dict[str, object] = {}
        conflicts: list[str] = []
        for category, items in sorted(by_category.items()):
            values = {str(item["status"]) for item in items}
            if len(values) > 1:
                conflicts.append(category)
            categories[category] = {
                "status": aggregate_status(values),
                "dependencies": [],
                "records": [item["output_identity"] for item in items],
                "unsupported": sorted(
                    {str(value) for item in items for value in item["unsupported_constructs"]}
                ),
            }
        aggregate = aggregate_status(
            str(value["status"]) for value in categories.values() if isinstance(value, dict)
        )
        return {
            "candidate_identity": candidate_id,
            "required_gate_aggregation": aggregate,
            "categories": categories,
            "conflicting_evidence": conflicts,
            "stale_identities": [],
            "claim_limitations": (
                ["one or more required gates are not PASS"] if aggregate != "PASS" else []
            ),
            "unresolved_blockers": [
                name
                for name, value in categories.items()
                if isinstance(value, dict) and value["status"] != "PASS"
            ],
            "dominance": "FAIL > UNKNOWN > PASS",
            "normative_logic_delegated": "MNCS and MNCDS validators remain offline authorities",
        }

    def bundle_build(
        self, workflow_name: str, candidate_id: str | None = None
    ) -> dict[str, object]:
        candidate = self._candidate(candidate_id)
        workflow = self._workflow(workflow_name, self.mode)
        if workflow.category not in {"mncs_bundle_validation", "mncds_record_validation"}:
            raise ForgeError("WORKFLOW_CATEGORY", "bundle requires an MNCS or MNCDS workflow")
        result = self._run_workflow(workflow, candidate, evaluator=self.mode == "evaluator")
        self._write_immutable("bundles", str(result["output_identity"]), result)
        self.ledger.append("bundle", result)
        integrity = str(result["status"])
        return {
            "package_creation": "COMPLETED" if result["returncode"] == 0 else "FAILED",
            "package_integrity": integrity,
            "schema_validity": integrity,
            "cryptographic_validity": "UNKNOWN",
            "trust": "UNKNOWN",
            "certification_eligibility": "UNKNOWN",
            "operational_disposition": "REVIEW_REQUIRED",
            "result_reference": result["output_identity"],
            "note": "a valid package or signature is not proof of correctness",
        }
