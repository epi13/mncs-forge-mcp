from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from mncs_forge.adapters import LocalProcessRunner
from mncs_forge.errors import ForgeError


@pytest.fixture
def runner() -> LocalProcessRunner:
    return LocalProcessRunner()


def execute_code(
    runner: LocalProcessRunner,
    code: str,
    *,
    cwd: Path | None = None,
    timeout: float = 1,
    output_cap: int = 4096,
    stderr_cap: int | None = None,
    stdin: bytes = b"",
    environment: dict[str, str] | None = None,
):
    return runner.execute(
        [sys.executable, "-c", code],
        cwd=cwd or Path.cwd(),
        timeout=timeout,
        output_cap=output_cap,
        stderr_cap=stderr_cap,
        environment={
            **os.environ,
            "PYTHONUNBUFFERED": "1",
            **(environment or {}),
        },
        stdin=stdin,
    )


def test_local_runner_capabilities_are_explicit(runner: LocalProcessRunner) -> None:
    capabilities = runner.inspect_capabilities()

    assert capabilities.runner_kind == "local-process"
    assert capabilities.execution_scope == "local"
    assert capabilities.shell_execution == "disabled"
    assert capabilities.timeout_enforcement == "enforced"
    assert capabilities.stdout_limit == "enforced"
    assert capabilities.stderr_limit == "enforced"
    assert capabilities.sandbox_isolation == "not-provided"
    assert capabilities.network_isolation == "not-provided"
    assert capabilities.filesystem_isolation == "not-provided"
    assert capabilities.process_group_termination in {"enforced", "not-provided"}


@pytest.mark.parametrize(
    "command",
    [[], (), [""], ["python", ""], ["python\x00"]],
)
def test_runner_rejects_invalid_argument_arrays(
    runner: LocalProcessRunner, command: object
) -> None:
    with pytest.raises(ForgeError) as issue:
        runner.execute(
            command,
            cwd=Path.cwd(),
            timeout=1,
            output_cap=128,
            environment=dict(os.environ),
        )
    assert issue.value.code == "INVALID_COMMAND"


@pytest.mark.parametrize(
    ("timeout", "output_cap", "stderr_cap"),
    [(0, 128, None), (-1, 128, None), (1, 0, None), (1, -1, None), (1, 128, 0)],
)
def test_runner_rejects_nonpositive_limits(
    runner: LocalProcessRunner, timeout: float, output_cap: int, stderr_cap: int | None
) -> None:
    with pytest.raises(ForgeError) as issue:
        execute_code(
            runner,
            "print('unused')",
            timeout=timeout,
            output_cap=output_cap,
            stderr_cap=stderr_cap,
        )
    assert issue.value.code == "INVALID_LIMIT"


def test_runner_does_not_interpret_shell_metacharacters(
    runner: LocalProcessRunner, tmp_path: Path
) -> None:
    marker = tmp_path / "shell-marker"
    argument = f"; touch {marker}"
    result = runner.execute(
        [sys.executable, "-c", "import sys; sys.stdout.write(sys.argv[1])", argument],
        cwd=tmp_path,
        timeout=1,
        output_cap=4096,
        environment={**os.environ, "PYTHONUNBUFFERED": "1"},
    )
    assert result.stdout.decode() == argument
    assert not marker.exists()


def test_runner_preserves_success_nonzero_stdin_cwd_and_environment(
    runner: LocalProcessRunner, tmp_path: Path
) -> None:
    result = execute_code(
        runner,
        "import os, pathlib, sys; print(pathlib.Path.cwd()); "
        "print(os.environ['MNCS_FORGE_TASK7A']); print(sys.stdin.read())",
        cwd=tmp_path,
        stdin=b"input-data",
        environment={"MNCS_FORGE_TASK7A": "present"},
    )
    assert result.returncode == 0
    assert result.stdout.decode().splitlines() == [str(tmp_path), "present", "input-data"]

    failed = execute_code(runner, "import sys; sys.stderr.write('diagnostic'); sys.exit(7)")
    assert failed.returncode == 7
    assert failed.stderr == b"diagnostic"


def test_runner_passes_explicit_environment(runner: LocalProcessRunner) -> None:
    result = runner.execute(
        [sys.executable, "-c", "import os; print(os.environ['MNCS_FORGE_TASK7A'])"],
        cwd=Path.cwd(),
        timeout=1,
        output_cap=128,
        environment={"PATH": os.environ["PATH"], "MNCS_FORGE_TASK7A": "present"},
    )
    assert result.stdout == b"present\n"


def test_runner_reports_executable_start_failure(
    runner: LocalProcessRunner, tmp_path: Path
) -> None:
    with pytest.raises(ForgeError) as issue:
        runner.execute(
            [str(tmp_path / "missing-executable")],
            cwd=tmp_path,
            timeout=1,
            output_cap=128,
            environment=dict(os.environ),
        )
    assert issue.value.code == "COMMAND_START"


@pytest.mark.parametrize(
    ("stream", "output_cap", "stderr_cap"),
    [("stdout", 16, 128), ("stderr", 128, 16)],
)
def test_runner_enforces_independent_output_caps(
    runner: LocalProcessRunner, stream: str, output_cap: int, stderr_cap: int
) -> None:
    code = f"import sys; sys.{stream}.write('x' * 64); sys.{stream}.flush()"
    with pytest.raises(ForgeError) as issue:
        execute_code(
            runner,
            code,
            output_cap=output_cap,
            stderr_cap=stderr_cap,
        )
    assert issue.value.code == "OUTPUT_LIMIT"
    assert stream in issue.value.message


def test_runner_enforces_timeout(runner: LocalProcessRunner) -> None:
    with pytest.raises(ForgeError) as issue:
        execute_code(runner, "import time; time.sleep(5)", timeout=0.1)
    assert issue.value.code == "TIMEOUT"


def test_runner_accepts_early_stdin_close(runner: LocalProcessRunner) -> None:
    result = execute_code(
        runner,
        "import os; os.close(0)",
        stdin=b"x" * (128 * 1024),
    )
    assert result.returncode == 0


@pytest.mark.skipif(os.name != "posix", reason="requires POSIX process-group semantics")
def test_timeout_terminates_a_simple_spawned_child_process(
    runner: LocalProcessRunner, tmp_path: Path
) -> None:
    child_pid = tmp_path / "child.pid"
    code = (
        "import pathlib, subprocess, sys, time; "
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)']); "
        f"pathlib.Path({str(child_pid)!r}).write_text(str(child.pid)); time.sleep(30)"
    )
    with pytest.raises(ForgeError) as issue:
        execute_code(runner, code, timeout=1)
    assert issue.value.code == "TIMEOUT"

    pid = int(child_pid.read_text(encoding="utf-8"))
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return
    if sys.platform.startswith("linux"):
        state = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8").split()[2]
        if state == "Z":
            return
    os.kill(pid, 9)
    pytest.fail("timeout left the spawned child process running")
