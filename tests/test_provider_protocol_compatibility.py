from __future__ import annotations

import json
from pathlib import Path

import pytest

from mncs_forge.adapters import LocalCommandExecutor
from mncs_forge.config import ForgeConfig
from mncs_forge.engine import Forge
from mncs_forge.errors import ForgeError
from mncs_forge.execution import parse_provider_capabilities, parse_provider_response
from mncs_forge.execution_observations import bytes_sha256, canonical_sha256
from mncs_forge.ports import (
    AggregateOutputObservation,
    ExecutionObservation,
    ExecutionResult,
    ExecutionSession,
    StreamObservation,
)


def _capture_provider_request(
    captured: list[dict[str, object]],
):  # type: ignore[no-untyped-def]
    def execute(
        _self: LocalCommandExecutor,
        command: object,
        *,
        cwd: Path,
        timeout: float,
        output_cap: int,
        stderr_cap: int | None = None,
        environment: dict[str, str],
        stdin: bytes = b"",
    ) -> ExecutionResult:
        del cwd, timeout, output_cap, stderr_cap, environment
        request = json.loads(stdin)
        assert isinstance(request, dict)
        captured.append(request)
        provider = {
            "id": "fake-pass",
            "name": "fake-pass",
            "version": "1",
            "identity": "fake-pass",
        }
        if request["type"] == "capabilities":
            response = {
                "protocol_version": "0.1",
                "type": "capabilities",
                "provider": provider,
                "analyses": ["bounded-structural"],
                "statuses": ["PASS", "FAIL", "UNKNOWN"],
                "cancellation": False,
                "health_checks": True,
                "extensions": {},
            }
        else:
            response = {
                "protocol_version": "0.1",
                "type": "analysis_response",
                "request_id": request["request_id"],
                "provider": provider,
                "status": "UNKNOWN",
                "summary": "compatibility fixture remains inconclusive",
                "witnesses": [],
                "limitations": ["compatibility fixture does not establish evidence PASS"],
                "extensions": {
                    "unsupported": [],
                    "mncs_forge": {
                        "assumptions": [],
                        "dependency_envelope": {
                            "paths": ["candidate/main.py"],
                            "identities": {},
                            "complete": True,
                        },
                    },
                },
            }
        return ExecutionResult(
            argv=[str(item) for item in command] if isinstance(command, list) else [],
            returncode=0,
            stdout=json.dumps(response, sort_keys=True, separators=(",", ":")).encode() + b"\n",
            stderr=b"",
            duration_seconds=0.001,
        )

    return execute


def _stream(data: bytes) -> StreamObservation:
    digest = bytes_sha256(data) if data else None
    return StreamObservation(
        total_bytes=len(data),
        observed_bytes=len(data),
        retained_bytes=len(data),
        retained_sha256=digest,
        complete_sha256=digest,
        truncated=False,
        limit_hit=False,
        limit_bytes=max(len(data), 1),
    )


def _capture_provider_run(captured: list[dict[str, object]]):  # type: ignore[no-untyped-def]
    execute = _capture_provider_request(captured)

    def run(
        self: LocalCommandExecutor,
        command: object,
        *,
        cwd: Path,
        timeout: float,
        output_cap: int,
        stderr_cap: int | None = None,
        environment: dict[str, str],
        stdin: bytes = b"",
    ) -> ExecutionSession:
        result = execute(
            self,
            command,
            cwd=cwd,
            timeout=timeout,
            output_cap=output_cap,
            stderr_cap=stderr_cap,
            environment=environment,
            stdin=stdin,
        )
        stdout = _stream(result.stdout)
        stderr = _stream(result.stderr)
        observation = ExecutionObservation(
            argv=tuple(result.argv),
            command_identity=canonical_sha256({"argv": result.argv}),
            cwd_identity=canonical_sha256({"cwd": str(cwd)}),
            environment_identity=canonical_sha256(
                {"environment": {key: environment[key] for key in sorted(environment)}}
            ),
            stdin_identity=bytes_sha256(stdin),
            timeout_seconds=timeout,
            stdout_limit=output_cap,
            stderr_limit=stderr_cap or output_cap,
            started_at="2026-01-01T00:00:00.000000Z",
            ended_at="2026-01-01T00:00:00.001000Z",
            duration_seconds=result.duration_seconds,
            returncode=result.returncode,
            signal=None,
            termination_category="completed",
            stdout=stdout,
            stderr=stderr,
            aggregate_output=AggregateOutputObservation(
                total_bytes=stdout.total_bytes + stderr.total_bytes
                if stdout.total_bytes is not None and stderr.total_bytes is not None
                else None,
                observed_bytes=stdout.observed_bytes + stderr.observed_bytes,
                retained_bytes=stdout.retained_bytes + stderr.retained_bytes,
                limit_hit=False,
                limit_bytes=None,
            ),
            capabilities=LocalCommandExecutor().inspect_capabilities(),
            runner_identity=LocalCommandExecutor.runner_identity,
            runner_version="1",
            executable_identity=None,
            runtime_identity="runtime.test",
            error_code=None,
            worker_identity=None,
            host_identity=None,
            image_identity=None,
            placement_identity=None,
            filesystem_policy="unrestricted-process-workspace",
            network_policy="ambient-process-network",
            same_operator=True,
        )
        return ExecutionSession(
            observation=observation,
            stdout=result.stdout,
            stderr=result.stderr,
            result=result,
            error_code=None,
            error_message=None,
        )

    return run


def _candidate(forge: Forge) -> dict[str, object]:
    forge.epoch_begin(generator_identity="generator", evaluator_identity="evaluator")
    return forge.candidate_register(
        changed_files=["candidate/main.py"],
        hypothesis="Provider Protocol compatibility",
        generator_identity="generator",
        generator_config_identity="configuration",
    )


def _line(value: dict[str, object]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode() + b"\n"


def test_provider_protocol_0_1_response_shapes_and_errors_are_stable() -> None:
    provider = {"id": "provider", "identity": "provider-v1"}
    analysis = {
        "protocol_version": "0.1",
        "type": "analysis_response",
        "request_id": "request-1",
        "provider": provider,
        "status": "UNKNOWN",
        "summary": "bounded inconclusive response",
        "witnesses": [],
        "limitations": ["bounded fixture"],
        "extensions": {"unsupported": []},
    }
    capabilities = {
        "protocol_version": "0.1",
        "type": "capabilities",
        "provider": provider,
        "analyses": ["bounded-structural"],
        "statuses": ["PASS", "FAIL", "UNKNOWN"],
        "cancellation": False,
        "health_checks": True,
        "extensions": {
            "supported_constructs": ["direct-calls"],
            "unsupported_constructs": ["dynamic-dispatch"],
            "limitations": ["bounded fixture"],
        },
    }

    assert parse_provider_response(_line(analysis)) == analysis
    assert parse_provider_capabilities(_line(capabilities)) == capabilities

    future = {**analysis, "protocol_version": "999"}
    with pytest.raises(ForgeError) as unsupported:
        parse_provider_response(_line(future))
    assert unsupported.value.code == "PROVIDER_UNSUPPORTED"

    malformed = {**analysis, "status": "CERTIFIED"}
    with pytest.raises(ForgeError) as invalid:
        parse_provider_response(_line(malformed))
    assert invalid.value.code == "PROVIDER_MALFORMED"


def test_provider_protocol_0_1_capabilities_request_shape_is_stable(
    config: ForgeConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: list[dict[str, object]] = []
    monkeypatch.setattr(
        LocalCommandExecutor,
        "execute",
        _capture_provider_request(captured),
    )

    result = Forge(config).provider_probe("provider-pass")

    assert result["status"] == "PASS"
    assert len(captured) == 1
    request = captured[0]
    assert set(request) == {"protocol_version", "type", "request_id", "extensions"}
    assert request["protocol_version"] == "0.1"
    assert request["type"] == "capabilities"
    assert str(request["request_id"]).startswith("forge-capabilities-")
    assert request["extensions"] == {}


def test_provider_protocol_0_1_workflow_request_shape_is_stable(
    config: ForgeConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    forge = Forge(config)
    candidate = _candidate(forge)
    captured: list[dict[str, object]] = []
    monkeypatch.setattr(
        LocalCommandExecutor,
        "run",
        _capture_provider_run(captured),
    )

    result = forge.development_checks_run(["provider-pass"])

    assert result["aggregate_status"] == "UNKNOWN"
    request = captured[0]
    assert set(request) == {
        "protocol_version",
        "type",
        "request_id",
        "analysis",
        "component",
        "limits",
        "extensions",
    }
    assert request["protocol_version"] == "0.1"
    assert request["type"] == "analysis_request"
    assert request["analysis"] == "bounded_structural_analysis"
    assert request["component"] == {
        "candidate_identity": candidate["candidate_id"],
        "source_epoch": candidate["source_epoch"],
    }
    assert request["limits"] == {"timeout_seconds": 0.5, "output_bytes": 4096}
    assert request["extensions"] == {"mncs_forge": {"mode": "development"}}


def test_provider_protocol_0_1_verifier_extension_shape_is_stable(
    config: ForgeConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    forge = Forge(config)
    candidate = _candidate(forge)
    captured: list[dict[str, object]] = []
    monkeypatch.setattr(
        LocalCommandExecutor,
        "run",
        _capture_provider_run(captured),
    )

    result = forge.verifier_run(
        "verify-pass",
        changed_paths=["candidate/main.py"],
        scope="file",
        question_parameters={"note": "compatibility"},
    )

    assert result["status"] == "UNKNOWN"
    request = captured[0]
    assert set(request) == {
        "protocol_version",
        "type",
        "request_id",
        "analysis",
        "component",
        "limits",
        "extensions",
    }
    assert request["protocol_version"] == "0.1"
    assert request["type"] == "analysis_request"
    assert request["analysis"] == "bounded-structural"
    assert set(request["component"]) == {
        "candidate_identity",
        "source_epoch",
        "scope",
        "changed_paths",
        "source_region",
        "contract_identity",
        "dependency_slice_identities",
        "prior_artifact_identity",
    }
    assert request["component"]["candidate_identity"] == candidate["candidate_id"]
    assert request["limits"] == {"timeout_seconds": 0.25, "request_scope": "file"}
    extension = request["extensions"]["mncs_forge"]
    assert set(extension) == {
        "verifier_id",
        "verifier_version",
        "mode",
        "question_parameters",
        "input_identities",
    }
    assert extension["verifier_id"] == "verify-pass"
    assert extension["mode"] == "development"
    assert extension["question_parameters"] == {"note": "compatibility"}
