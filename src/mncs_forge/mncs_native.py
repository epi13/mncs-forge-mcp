"""Explicit host adapter for the MNCS-native Forge slice.

The adapter is intentionally narrow. It locates a sibling ``mncs-language``
checkout (or an explicitly configured one), invokes the language-owned CLI
through Forge's bounded runner, and returns the language's structured result.
It does not turn a compiler result into an assurance claim or implement a
second execution or hashing authority.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import ForgeError
from .execution import run_bounded
from .serialization import reject_duplicate_keys

NATIVE_SCHEMA_VERSION = "0.1"
NATIVE_STATUS_CODES = {"PASS": 1, "FAIL": 2, "UNKNOWN": 3}
DEFAULT_TIMEOUT_SECONDS = 120.0
DEFAULT_OUTPUT_BYTES = 1_000_000


@dataclass(frozen=True, slots=True)
class NativeInvocation:
    """One bounded language-owned invocation and its untrusted JSON payload."""

    command: tuple[str, ...]
    returncode: int
    stdout: bytes
    stderr: bytes
    payload: dict[str, Any] | None

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and self.payload is not None


def canonical_candidate_material(
    parent_digest: bytes,
    source_digest: bytes,
    status: str,
    changed_files: bytes,
) -> bytes:
    """Mirror the MNCS chunk contract for host-side differential checks.

    The byte order is declared by ``mncs/forge/serialization.mncs``. This
    helper only materializes bytes; SHA-256 remains an explicit host boundary.
    """

    if len(parent_digest) != 32 or len(source_digest) != 32:
        raise ValueError("parent_digest and source_digest must each be 32 bytes")
    if len(changed_files) != 4:
        raise ValueError("changed_files must be exactly 4 bytes")
    try:
        status_code = NATIVE_STATUS_CODES[status]
    except KeyError as exc:
        raise ValueError("status must be PASS, FAIL, or UNKNOWN") from exc
    return bytes((67, 1, status_code)) + parent_digest + source_digest + changed_files


def canonical_candidate_digest(
    parent_digest: bytes,
    source_digest: bytes,
    status: str,
    changed_files: bytes,
) -> bytes:
    """Hash host-materialized candidate bytes at the declared boundary."""

    return hashlib.sha256(
        canonical_candidate_material(parent_digest, source_digest, status, changed_files)
    ).digest()


class NativeForgeAdapter:
    """Invoke MNCS Language without changing the Forge compatibility surface."""

    def __init__(
        self,
        forge_root: Path,
        *,
        language_root: Path | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        output_bytes: int = DEFAULT_OUTPUT_BYTES,
    ) -> None:
        self.forge_root = forge_root.resolve()
        self.language_root = self._discover_language_root(language_root)
        self.timeout_seconds = timeout_seconds
        self.output_bytes = output_bytes

    @staticmethod
    def _discover_language_root(explicit: Path | None) -> Path | None:
        candidates: list[Path] = []
        configured = os.environ.get("MNCS_LANGUAGE_ROOT")
        if configured:
            candidates.append(Path(configured))
        if explicit is not None:
            candidates.append(explicit)
        candidates.append(Path(__file__).resolve().parents[3] / "mncs-language")
        for candidate in candidates:
            root = candidate.resolve()
            if (root / "Cargo.toml").is_file() and (root / "library").is_dir():
                return root
        return None

    @property
    def available(self) -> bool:
        return self.language_root is not None

    def _command(self) -> list[str]:
        configured = os.environ.get("MNCS_CLI")
        if configured:
            if "\x00" in configured:
                raise ForgeError("NATIVE_CONFIG_INVALID", "MNCS_CLI contains NUL")
            return [configured]
        cargo = shutil.which("cargo")
        if cargo is None:
            raise ForgeError("NATIVE_UNAVAILABLE", "cargo is not available")
        assert self.language_root is not None
        return [
            cargo,
            "run",
            "--quiet",
            "--manifest-path",
            str(self.language_root / "Cargo.toml"),
            "-p",
            "mncs-cli",
            "--",
        ]

    def invoke(self, arguments: list[str]) -> NativeInvocation:
        if self.language_root is None:
            raise ForgeError(
                "NATIVE_UNAVAILABLE",
                "mncs-language sibling checkout is unavailable; native Forge is UNKNOWN",
            )
        if not self.forge_root.is_dir():
            raise ForgeError("NATIVE_CONFIG_INVALID", "Forge root is not a directory")
        command = [*self._command(), *arguments]
        environment = dict(os.environ)
        library_path = os.pathsep.join(
            (str(self.language_root / "library"), str(self.forge_root))
        )
        environment["MNCS_LIBRARY_PATH"] = library_path
        result = run_bounded(
            command,
            cwd=self.forge_root,
            timeout=self.timeout_seconds,
            output_cap=self.output_bytes,
            stderr_cap=self.output_bytes,
            environment=environment,
        )
        payload: dict[str, Any] | None = None
        try:
            decoded = result.stdout.decode("utf-8")
            value = json.loads(decoded, object_pairs_hook=reject_duplicate_keys)
            if isinstance(value, dict):
                payload = value
        except (UnicodeDecodeError, ValueError):
            payload = None
        return NativeInvocation(
            command=tuple(command),
            returncode=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            payload=payload,
        )

    def source_study(self, source: Path, *, node_id: str = "forge-native") -> NativeInvocation:
        return self.invoke(["source-study", str(source.resolve()), "--node-id", node_id])

    def execute(self, source: Path, request: Path, *, backend: bool = False) -> NativeInvocation:
        command = "execute-backend" if backend else "execute"
        return self.invoke([command, str(source.resolve()), str(request.resolve())])
