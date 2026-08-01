"""Bounded subprocess pipe collection for Windows.

Windows select-based selectors do not support anonymous subprocess pipes. Reader
threads preserve the same timeout and per-stream byte caps without buffering
unbounded output through communicate().
"""

from __future__ import annotations

import subprocess
import threading
import time
from typing import BinaryIO, NoReturn

from .errors import ForgeError


def _raise_after_termination(
    process: subprocess.Popen[bytes],
    *,
    code: str,
    message: str,
) -> NoReturn:
    from .execution import _terminate

    _terminate(process)
    raise ForgeError(code, message)


def collect_windows_pipes(
    process: subprocess.Popen[bytes],
    *,
    timeout: float,
    stdout_cap: int,
    stderr_cap: int,
) -> tuple[int, bytes, bytes]:
    """Collect two Windows pipes while enforcing independent byte caps."""

    assert process.stdout is not None
    assert process.stderr is not None
    outputs = {"stdout": bytearray(), "stderr": bytearray()}
    overflow = threading.Event()
    overflow_name: list[str] = []
    overflow_lock = threading.Lock()

    def read_stream(name: str, stream: BinaryIO, cap: int) -> None:
        target = outputs[name]
        while chunk := stream.read(65536):
            target.extend(chunk)
            if len(target) > cap:
                with overflow_lock:
                    if not overflow_name:
                        overflow_name.append(name)
                overflow.set()
                return

    threads = [
        threading.Thread(
            target=read_stream,
            args=("stdout", process.stdout, stdout_cap),
            daemon=True,
        ),
        threading.Thread(
            target=read_stream,
            args=("stderr", process.stderr, stderr_cap),
            daemon=True,
        ),
    ]
    for thread in threads:
        thread.start()
    deadline = time.monotonic() + timeout
    while any(thread.is_alive() for thread in threads):
        if overflow.is_set():
            name = overflow_name[0] if overflow_name else "output"
            cap = stdout_cap if name == "stdout" else stderr_cap
            _raise_after_termination(
                process,
                code="OUTPUT_LIMIT",
                message=f"{name} exceeded the {cap}-byte cap",
            )
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            _raise_after_termination(
                process,
                code="TIMEOUT",
                message=f"declared command exceeded {timeout:g} seconds",
            )
        for thread in threads:
            thread.join(timeout=min(remaining, 0.01))
    try:
        returncode = process.wait(timeout=max(0.1, deadline - time.monotonic()))
    except subprocess.TimeoutExpired:
        _raise_after_termination(
            process,
            code="TIMEOUT",
            message=f"declared command exceeded {timeout:g} seconds",
        )
    return returncode, bytes(outputs["stdout"]), bytes(outputs["stderr"])
