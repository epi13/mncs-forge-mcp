"""Bounded no-shell subprocess and Provider Protocol execution."""

from __future__ import annotations

import json
import os
import selectors
import signal
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import ForgeError

STATUSES = {"PASS", "FAIL", "UNKNOWN"}


@dataclass(frozen=True)
class ExecutionResult:
    argv: list[str]
    returncode: int
    stdout: bytes
    stderr: bytes
    duration_seconds: float


def validate_argv(command: object) -> list[str]:
    if not isinstance(command, list) or not command:
        raise ForgeError("INVALID_COMMAND", "command must be a non-empty argument array")
    if not all(isinstance(value, str) and value and "\x00" not in value for value in command):
        raise ForgeError(
            "INVALID_COMMAND", "every command argument must be a non-empty NUL-free string"
        )
    return list(command)


def _terminate(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    try:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGTERM)
        else:
            process.terminate()
        process.wait(timeout=1)
    except (OSError, subprocess.TimeoutExpired):
        try:
            if os.name == "posix":
                os.killpg(process.pid, signal.SIGKILL)
            else:
                process.kill()
        except OSError:
            pass
        process.wait(timeout=2)


def run_bounded(
    command: object,
    *,
    cwd: Path,
    timeout: float,
    output_cap: int,
    environment: dict[str, str],
    stdin: bytes = b"",
) -> ExecutionResult:
    argv = validate_argv(command)
    if timeout <= 0 or output_cap <= 0:
        raise ForgeError("INVALID_LIMIT", "timeout and output cap must be positive")
    started = time.monotonic()
    try:
        process = subprocess.Popen(
            argv,
            cwd=cwd,
            env=environment,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            start_new_session=os.name == "posix",
        )
    except OSError as exc:
        raise ForgeError("COMMAND_START", f"cannot start declared command: {exc}") from exc
    assert process.stdin is not None
    assert process.stdout is not None
    assert process.stderr is not None
    try:
        process.stdin.write(stdin)
        process.stdin.close()
    except BrokenPipeError:
        pass
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ, "stdout")
    selector.register(process.stderr, selectors.EVENT_READ, "stderr")
    chunks: dict[str, bytearray] = {"stdout": bytearray(), "stderr": bytearray()}
    deadline = started + timeout
    try:
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                _terminate(process)
                raise ForgeError("TIMEOUT", f"declared command exceeded {timeout:g} seconds")
            events = selector.select(min(remaining, 0.1))
            if not events and process.poll() is not None:
                events = [(key, selectors.EVENT_READ) for key in selector.get_map().values()]
            for key, _ in events:
                data = os.read(key.fd, 65536)
                if not data:
                    selector.unregister(key.fileobj)
                    continue
                target = chunks[str(key.data)]
                target.extend(data)
                if len(target) > output_cap:
                    _terminate(process)
                    raise ForgeError(
                        "OUTPUT_LIMIT", f"{key.data} exceeded the {output_cap}-byte cap"
                    )
        returncode = process.wait(timeout=max(0.1, deadline - time.monotonic()))
    except subprocess.TimeoutExpired as exc:
        _terminate(process)
        raise ForgeError("TIMEOUT", f"declared command exceeded {timeout:g} seconds") from exc
    finally:
        selector.close()
        if process.poll() is None:
            _terminate(process)
    return ExecutionResult(
        argv=argv,
        returncode=returncode,
        stdout=bytes(chunks["stdout"]),
        stderr=bytes(chunks["stderr"]),
        duration_seconds=round(time.monotonic() - started, 6),
    )


def parse_provider_response(stdout: bytes) -> dict[str, Any]:
    try:
        text = stdout.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ForgeError("PROVIDER_FRAMING", "provider stdout is not UTF-8") from exc
    lines = text.splitlines()
    if len(lines) != 1 or not lines[0]:
        raise ForgeError(
            "PROVIDER_FRAMING", "provider must emit exactly one non-empty JSON Lines response"
        )
    try:
        value = json.loads(lines[0])
    except json.JSONDecodeError as exc:
        raise ForgeError("PROVIDER_MALFORMED", f"invalid provider JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ForgeError("PROVIDER_MALFORMED", "provider response must be an object")
    if value.get("protocol_version") != "0.1":
        raise ForgeError("PROVIDER_UNSUPPORTED", "only Provider Protocol 0.1 is supported")
    if value.get("type") not in {
        "analysis_response",
        "capabilities",
        "health_response",
        "error",
        "cancelled",
    }:
        raise ForgeError("PROVIDER_MALFORMED", "provider response type is invalid")
    if not isinstance(value.get("provider"), dict):
        raise ForgeError("PROVIDER_MALFORMED", "provider identity must be an object")
    if not isinstance(value.get("extensions"), dict):
        raise ForgeError("PROVIDER_MALFORMED", "provider extensions must be an object")
    if value.get("type") == "analysis_response" and value.get("status") not in STATUSES:
        raise ForgeError("PROVIDER_MALFORMED", "analysis result status must be PASS/FAIL/UNKNOWN")
    return value
