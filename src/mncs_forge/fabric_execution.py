"""Translate substrate execution facts into the Forge runner observation boundary.

This adapter does not schedule work, register workers, refresh inventory, or
import Fabric. A future Fabric-backed runner would call Fabric, then hand the
resulting facts to ``FabricExecutionAdapter``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from .errors import ForgeError
from .execution import validate_argv, validate_limits
from .execution_observations import bytes_sha256, canonical_sha256
from .ports import (
    AggregateOutputObservation,
    ExecutionObservation,
    ExecutionResult,
    ExecutionSession,
    RunnerCapabilities,
    RunnerCapability,
    StreamObservation,
)


@dataclass(frozen=True, slots=True)
class FabricExecutionFacts:
    """Narrow, substrate-translated facts consumed by Forge.

    These fields are what Forge needs to decide what an execution can prove.
    They are not a Fabric client type and do not include queue, lease, or
    inventory mechanics.
    """

    record_identity: str
    job_identity: str | None
    worker_identity: str | None
    host_identity: str | None
    os_family: str
    architecture: str
    argv: tuple[str, ...]
    command_identity: str
    environment_identity: str
    executable_identity: str | None
    image_identity: str | None
    returncode: int | None
    termination_category: str
    started_at: str | None
    ended_at: str | None
    duration_seconds: float | None
    stdout: StreamObservation
    stderr: StreamObservation
    timeout_seconds: float
    stdout_limit: int
    stderr_limit: int
    containment: RunnerCapability
    network_isolation: RunnerCapability
    filesystem_isolation: RunnerCapability
    same_operator: bool | None
    cwd_identity: str
    stdin_identity: str
    error_code: str | None = None


def _capability(value: object, field_name: str) -> RunnerCapability:
    if value == "enforced":
        return "enforced"
    if value == "not-provided":
        return "not-provided"
    if value == "unknown":
        return "unknown"
    raise ForgeError("FABRIC_ADAPTER", f"{field_name} is not a runner capability state")


def _optional_text(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _stream_from_mapping(value: object, field_name: str, *, limit: int) -> StreamObservation:
    if not isinstance(value, dict):
        raise ForgeError("FABRIC_ADAPTER", f"{field_name} must be an object")
    total = value.get("total_bytes", value.get("bytes"))
    retained = value.get("retained_bytes")
    complete = value.get("complete_sha256", value.get("sha256"))
    retained_sha = value.get("retained_sha256")
    truncated = value.get("truncated")
    captured = value.get("captured_utf8")
    captured_bytes = captured.encode("utf-8") if isinstance(captured, str) else b""
    retained_bytes = retained if isinstance(retained, int) else len(captured_bytes)
    return StreamObservation(
        total_bytes=total if isinstance(total, int) else None,
        observed_bytes=total if isinstance(total, int) else retained_bytes,
        retained_bytes=retained_bytes,
        retained_sha256=retained_sha
        if isinstance(retained_sha, str)
        else (bytes_sha256(captured_bytes) if captured_bytes else None),
        complete_sha256=complete[7:]
        if isinstance(complete, str) and complete.startswith("sha256:")
        else (complete if isinstance(complete, str) else None),
        truncated=truncated if isinstance(truncated, bool) else None,
        limit_hit=bool(value.get("limit_hit", truncated)),
        limit_bytes=limit,
    )


class FabricExecutionAdapter:
    """Map Fabric-shaped execution records onto Forge observations."""

    runner_identity = "runner.fabric-adapter-v1"
    runner_version = "1"

    def capabilities_from_facts(self, facts: FabricExecutionFacts) -> RunnerCapabilities:
        return RunnerCapabilities(
            runner_kind="fabric-backed",
            runner_version=self.runner_version,
            os_family=facts.os_family,
            architecture=facts.architecture,
            execution_scope="remote",
            shell_execution="disabled",
            timeout_enforcement="enforced",
            stdout_limit="enforced",
            stderr_limit="enforced",
            process_group_termination="unknown",
            sandbox_isolation=facts.containment,
            network_isolation=facts.network_isolation,
            filesystem_isolation=facts.filesystem_isolation,
        )

    def facts_from_record(self, record: Mapping[str, object]) -> FabricExecutionFacts:
        """Accept a Fabric execution-record-shaped object without importing Fabric."""

        if record.get("schema_version") != "mncs-fabric.execution-record.v0.1":
            raise ForgeError("FABRIC_ADAPTER", "unsupported Fabric execution-record schema")
        node = record.get("node")
        if not isinstance(node, dict):
            raise ForgeError("FABRIC_ADAPTER", "Fabric execution record is missing node facts")
        argv = record.get("argv", node.get("argv"))
        if not isinstance(argv, list) or not argv:
            raise ForgeError("FABRIC_ADAPTER", "Fabric execution record is missing argv")
        timeout = record.get("timeout_seconds", 1)
        stdout_limit = record.get("stdout_limit", 65536)
        stderr_limit = record.get("stderr_limit", stdout_limit)
        if not isinstance(timeout, (int, float)) or not isinstance(stdout_limit, int):
            raise ForgeError("FABRIC_ADAPTER", "Fabric execution limits are malformed")
        if not isinstance(stderr_limit, int):
            raise ForgeError("FABRIC_ADAPTER", "Fabric execution limits are malformed")
        stdout = _stream_from_mapping(record.get("stdout"), "stdout", limit=stdout_limit)
        stderr = _stream_from_mapping(record.get("stderr"), "stderr", limit=stderr_limit)
        environment = record.get("environment_identity")
        if not isinstance(environment, str) or not environment:
            environment = canonical_sha256({"environment": {}})
        command_identity = record.get("command_identity")
        if not isinstance(command_identity, str) or not command_identity:
            command_identity = canonical_sha256({"argv": argv})
        termination = record.get("termination_reason", record.get("termination_category"))
        if not isinstance(termination, str) or not termination:
            termination = "unknown"
        mapped = {
            "completed": "completed",
            "exit-zero": "completed",
            "nonzero-exit": "nonzero-exit",
            "timeout": "timeout",
            "output-limit": "output-limit",
            "signal": "signal",
            "crash": "crash",
            "cancelled": "cancelled",
        }.get(termination, "internal-runner-error")
        returncode = record.get("returncode")
        duration = record.get("duration_seconds")
        same_operator = record.get("same_operator")
        return FabricExecutionFacts(
            record_identity=str(record.get("record_id") or ""),
            job_identity=_optional_text(record.get("job_identity")),
            worker_identity=_optional_text(node.get("worker_identity") or node.get("identity")),
            host_identity=_optional_text(node.get("host_identity") or node.get("hostname")),
            os_family=str(node.get("os_family") or node.get("os") or "unknown"),
            architecture=str(node.get("architecture") or node.get("arch") or "unknown"),
            argv=tuple(str(item) for item in argv),
            command_identity=command_identity,
            environment_identity=environment,
            executable_identity=_optional_text(record.get("executable_identity")),
            image_identity=_optional_text(record.get("image_identity")),
            returncode=returncode if isinstance(returncode, int) else None,
            termination_category=mapped,
            started_at=_optional_text(record.get("started_at")),
            ended_at=_optional_text(record.get("ended_at")),
            duration_seconds=float(duration) if isinstance(duration, (int, float)) else None,
            stdout=stdout,
            stderr=stderr,
            timeout_seconds=float(timeout),
            stdout_limit=stdout_limit,
            stderr_limit=stderr_limit,
            containment=_capability(record.get("containment", "unknown"), "containment"),
            network_isolation=_capability(
                record.get("network_isolation", "unknown"), "network_isolation"
            ),
            filesystem_isolation=_capability(
                record.get("filesystem_isolation", "unknown"), "filesystem_isolation"
            ),
            same_operator=same_operator if isinstance(same_operator, bool) else None,
            cwd_identity=str(record.get("cwd_identity") or canonical_sha256({"cwd": "fabric"})),
            stdin_identity=str(record.get("stdin_identity") or bytes_sha256(b"")),
            error_code=_optional_text(record.get("error_code")),
        )

    def observation_from_facts(self, facts: FabricExecutionFacts) -> ExecutionObservation:
        capabilities = self.capabilities_from_facts(facts)
        aggregate_total = (
            facts.stdout.total_bytes + facts.stderr.total_bytes
            if facts.stdout.total_bytes is not None and facts.stderr.total_bytes is not None
            else None
        )
        return ExecutionObservation(
            argv=facts.argv,
            command_identity=facts.command_identity,
            cwd_identity=facts.cwd_identity,
            environment_identity=facts.environment_identity,
            stdin_identity=facts.stdin_identity,
            timeout_seconds=facts.timeout_seconds,
            stdout_limit=facts.stdout_limit,
            stderr_limit=facts.stderr_limit,
            started_at=facts.started_at,
            ended_at=facts.ended_at,
            duration_seconds=facts.duration_seconds,
            returncode=facts.returncode,
            signal=None,
            termination_category=facts.termination_category,  # type: ignore[arg-type]
            stdout=facts.stdout,
            stderr=facts.stderr,
            aggregate_output=AggregateOutputObservation(
                total_bytes=aggregate_total,
                observed_bytes=facts.stdout.observed_bytes + facts.stderr.observed_bytes,
                retained_bytes=facts.stdout.retained_bytes + facts.stderr.retained_bytes,
                limit_hit=facts.stdout.limit_hit or facts.stderr.limit_hit,
                limit_bytes=None,
            ),
            capabilities=capabilities,
            runner_identity=self.runner_identity,
            runner_version=self.runner_version,
            executable_identity=facts.executable_identity,
            runtime_identity=None,
            error_code=facts.error_code,
            worker_identity=facts.worker_identity,
            host_identity=facts.host_identity,
            image_identity=facts.image_identity,
            placement_identity=facts.job_identity,
            filesystem_policy="fabric-declared",
            network_policy="fabric-declared",
            same_operator=facts.same_operator,
        )

    def session_from_facts(
        self, facts: FabricExecutionFacts, *, stdout: bytes = b"", stderr: bytes = b""
    ) -> ExecutionSession:
        observation = self.observation_from_facts(facts)
        result = None
        if facts.returncode is not None and facts.duration_seconds is not None:
            result = ExecutionResult(
                argv=list(facts.argv),
                returncode=facts.returncode,
                stdout=stdout,
                stderr=stderr,
                duration_seconds=facts.duration_seconds,
            )
        return ExecutionSession(
            observation=observation,
            stdout=stdout,
            stderr=stderr,
            result=result,
            error_code=facts.error_code,
            error_message=None,
        )


class ScriptedRunner:
    """In-memory runner used to prove Forge core is substrate-agnostic."""

    def __init__(self, sessions: list[ExecutionSession]) -> None:
        self._sessions = list(sessions)
        self.calls = 0

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
        session = self.run(
            command,
            cwd=cwd,
            timeout=timeout,
            output_cap=output_cap,
            stderr_cap=stderr_cap,
            environment=environment,
            stdin=stdin,
        )
        if session.result is None:
            raise ForgeError(
                session.error_code or "COMMAND_START",
                session.error_message or "scripted runner has no execution result",
            )
        return session.result

    def observe(
        self,
        command: object,
        *,
        cwd: Path,
        timeout: float,
        output_cap: int,
        stderr_cap: int | None = None,
        environment: dict[str, str],
        stdin: bytes = b"",
    ) -> ExecutionObservation:
        return self.run(
            command,
            cwd=cwd,
            timeout=timeout,
            output_cap=output_cap,
            stderr_cap=stderr_cap,
            environment=environment,
            stdin=stdin,
        ).observation

    def run(
        self,
        command: object,
        *,
        cwd: Path,
        timeout: float,
        output_cap: int,
        stderr_cap: int | None = None,
        environment: dict[str, str],
        stdin: bytes = b"",
    ) -> ExecutionSession:
        del cwd, environment, stdin
        validate_argv(command)
        validate_limits(timeout, output_cap, stderr_cap)
        if self.calls >= len(self._sessions):
            raise ForgeError("FABRIC_ADAPTER", "scripted runner has no remaining sessions")
        session = self._sessions[self.calls]
        self.calls += 1
        return session

    def inspect_capabilities(self) -> RunnerCapabilities:
        if not self._sessions:
            raise ForgeError("FABRIC_ADAPTER", "scripted runner has no capabilities")
        return self._sessions[0].observation.capabilities
