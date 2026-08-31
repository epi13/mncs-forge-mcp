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
import tempfile
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
_MNCS_TYPE_PREFIX = "mncs:0.2:finite-type:"
_MNCS_VARIANT_PREFIX = "mncs:0.2:finite-variant:"
_STATUS_VARIANTS = {"PASS": 0, "FAIL": 1, "UNKNOWN": 2}
_LIFECYCLE_STAGES = {
    "NoEpoch": 0,
    "EpochActive": 1,
    "CandidateRegistered": 2,
    "EvidenceIncomplete": 3,
    "CandidateReady": 4,
    "CandidateSelected": 5,
    "CandidateRejected": 6,
    "CandidateFrozen": 7,
    "EvaluationComplete": 8,
    "AmbiguousHistory": 9,
}
_LIFECYCLE_OPERATIONS = {
    "BeginEpoch": 0,
    "RegisterCandidate": 1,
    "AddEvidence": 2,
    "SelectCandidate": 3,
    "RejectCandidate": 4,
    "FreezeCandidate": 5,
    "RecordEvaluation": 6,
}
_STAGE_TYPE = "mncs.forge.lifecycle.v1::Stage"
_OPERATION_TYPE = "mncs.forge.lifecycle.v1::Operation"
_STATUS_TYPE = "mncs.core.status.v1::Status"


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


@dataclass(frozen=True, slots=True)
class NativeLifecycleResult:
    """The validated result of one language-owned lifecycle preflight."""

    stage: str
    operation: str
    next_stage: str
    status: str
    reason: int


_LIFECYCLE_CACHE: dict[tuple[object, ...], NativeLifecycleResult] = {}


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
        configured_source = os.environ.get("MNCS_FORGE_NATIVE_SOURCE")
        self.native_source = (
            Path(configured_source).expanduser().resolve()
            if configured_source
            else Path(__file__).resolve().parents[2] / "mncs" / "forge" / "core.mncs"
        )

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

    @property
    def source_available(self) -> bool:
        """Whether the checked-in Forge MNCS entrypoint is available."""

        return self.native_source.is_file()

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
        if self.source_available:
            for relative in (Path("target/debug/mncs"), Path("target/release/mncs")):
                binary = self.language_root / relative
                if binary.is_file() and os.access(binary, os.X_OK):
                    # The CLI loads Forge source at invocation time. Its
                    # timestamp therefore does not need to track the source
                    # checkout, and using the built binary keeps lifecycle
                    # preflights bounded without a cargo rebuild per call.
                    return [str(binary)]
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
        library_path = os.pathsep.join((str(self.language_root / "library"), str(self.forge_root)))
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

    @staticmethod
    def _finite_argument(type_name: str, variant: str, discriminant: int) -> dict[str, object]:
        return {
            "finite": {
                "type_identity": f"{_MNCS_TYPE_PREFIX}{type_name}",
                "variant_identity": f"{_MNCS_VARIANT_PREFIX}{type_name}::{variant}",
                "discriminant": discriminant,
            }
        }

    @staticmethod
    def _record_fields(payload: dict[str, Any], *, context: str) -> dict[str, Any]:
        if payload.get("status") != "returned":
            raise ForgeError("NATIVE_LIFECYCLE_UNKNOWN", f"{context} did not return a value")
        returned = payload.get("returned")
        if not isinstance(returned, list) or len(returned) != 1:
            raise ForgeError(
                "NATIVE_LIFECYCLE_UNKNOWN",
                f"{context} returned an unexpected value count",
            )
        value = returned[0]
        if not isinstance(value, dict) or not isinstance(value.get("record"), dict):
            raise ForgeError("NATIVE_LIFECYCLE_UNKNOWN", f"{context} did not return a record")
        fields = value["record"].get("fields")
        if not isinstance(fields, list):
            raise ForgeError("NATIVE_LIFECYCLE_UNKNOWN", f"{context} record fields are malformed")
        result: dict[str, Any] = {}
        for field in fields:
            if (
                not isinstance(field, list)
                or len(field) != 2
                or not isinstance(field[0], str)
                or field[0] in result
            ):
                raise ForgeError("NATIVE_LIFECYCLE_UNKNOWN", f"{context} has malformed fields")
            result[field[0]] = field[1]
        return result

    @staticmethod
    def _finite_variant(value: object, type_name: str, *, context: str) -> str:
        if not isinstance(value, dict) or not isinstance(value.get("finite"), dict):
            raise ForgeError("NATIVE_LIFECYCLE_UNKNOWN", f"{context} is not a finite value")
        finite = value["finite"]
        if finite.get("type_identity") != f"{_MNCS_TYPE_PREFIX}{type_name}":
            raise ForgeError("NATIVE_LIFECYCLE_UNKNOWN", f"{context} has an invalid type")
        expected_prefix = f"{_MNCS_VARIANT_PREFIX}{type_name}::"
        variant_identity = finite.get("variant_identity")
        if not isinstance(variant_identity, str) or not variant_identity.startswith(
            expected_prefix
        ):
            raise ForgeError("NATIVE_LIFECYCLE_UNKNOWN", f"{context} has an invalid type")
        variant = variant_identity[len(expected_prefix) :]
        discriminant = finite.get("discriminant")
        if not isinstance(discriminant, int) or isinstance(discriminant, bool):
            raise ForgeError("NATIVE_LIFECYCLE_UNKNOWN", f"{context} has no discriminant")
        expected_values = {
            _STATUS_TYPE: _STATUS_VARIANTS,
            _STAGE_TYPE: _LIFECYCLE_STAGES,
            _OPERATION_TYPE: _LIFECYCLE_OPERATIONS,
        }[type_name]
        expected = expected_values.get(variant)
        if expected is None or discriminant != expected:
            raise ForgeError("NATIVE_LIFECYCLE_UNKNOWN", f"{context} has an invalid variant")
        return variant

    @staticmethod
    def _byte(value: object, *, context: str) -> int:
        if not isinstance(value, dict) or not isinstance(value.get("byte"), dict):
            raise ForgeError("NATIVE_LIFECYCLE_UNKNOWN", f"{context} is not a byte")
        result = value["byte"].get("value")
        if not isinstance(result, int) or isinstance(result, bool) or not 0 <= result <= 255:
            raise ForgeError("NATIVE_LIFECYCLE_UNKNOWN", f"{context} has an invalid value")
        return result

    def lifecycle_preflight(
        self, stage: str, operation: str, evidence: str = "UNKNOWN"
    ) -> NativeLifecycleResult:
        """Run the typed MNCS lifecycle kernel for a covered Forge transition.

        The request is created in a bounded temporary directory and carries
        finite values only. Forge identities are deliberately excluded from
        this preflight because the MNCS kernel is checking transition
        semantics, while identity production remains a host boundary.
        """

        if stage not in _LIFECYCLE_STAGES:
            raise ForgeError("NATIVE_CONFIG_INVALID", f"unknown native lifecycle stage: {stage}")
        if operation not in _LIFECYCLE_OPERATIONS:
            raise ForgeError(
                "NATIVE_CONFIG_INVALID", f"unknown native lifecycle operation: {operation}"
            )
        if evidence not in _STATUS_VARIANTS:
            raise ForgeError("NATIVE_CONFIG_INVALID", f"unknown native status: {evidence}")
        if not self.available:
            raise ForgeError("NATIVE_UNAVAILABLE", "mncs-language checkout is unavailable")
        if not self.source_available:
            raise ForgeError(
                "NATIVE_UNAVAILABLE", "checked-in Forge MNCS lifecycle source is unavailable"
            )
        command = tuple(self._command())
        cache_key = (
            str(self.language_root),
            str(self.native_source),
            self.native_source.stat().st_mtime_ns,
            *command,
            stage,
            operation,
            evidence,
        )
        cached = _LIFECYCLE_CACHE.get(cache_key)
        if cached is not None:
            return cached
        request = {
            "schema_version": NATIVE_SCHEMA_VERSION,
            "target": {
                "module": "mncs.forge.core.v1",
                "function": "lifecycle_preflight",
            },
            "arguments": [
                self._finite_argument(_STAGE_TYPE, stage, _LIFECYCLE_STAGES[stage]),
                self._finite_argument(_OPERATION_TYPE, operation, _LIFECYCLE_OPERATIONS[operation]),
                self._finite_argument(_STATUS_TYPE, evidence, _STATUS_VARIANTS[evidence]),
            ],
            "step_budget": 4096,
        }
        with tempfile.TemporaryDirectory(prefix=".mncs-native-", dir=self.forge_root) as directory:
            request_path = Path(directory) / "lifecycle-request.json"
            request_path.write_text(json.dumps(request), encoding="utf-8")
            invocation = self.execute(self.native_source, request_path)
        if not invocation.ok or invocation.payload is None:
            raise ForgeError(
                "NATIVE_LIFECYCLE_UNKNOWN",
                "language-owned lifecycle preflight did not return valid JSON "
                f"(returncode {invocation.returncode})",
            )
        fields = self._record_fields(invocation.payload, context="lifecycle preflight")
        state = fields.get("state")
        if not isinstance(state, dict) or not isinstance(state.get("record"), dict):
            raise ForgeError("NATIVE_LIFECYCLE_UNKNOWN", "lifecycle result state is malformed")
        state_fields = state["record"].get("fields")
        if not isinstance(state_fields, list):
            raise ForgeError("NATIVE_LIFECYCLE_UNKNOWN", "lifecycle result state has no fields")
        state_map: dict[str, Any] = {}
        for field in state_fields:
            if (
                not isinstance(field, list)
                or len(field) != 2
                or not isinstance(field[0], str)
                or field[0] in state_map
            ):
                raise ForgeError("NATIVE_LIFECYCLE_UNKNOWN", "lifecycle result state is malformed")
            state_map[field[0]] = field[1]
        next_stage = self._finite_variant(
            state_map.get("stage"), _STAGE_TYPE, context="lifecycle next stage"
        )
        status = self._finite_variant(
            fields.get("status"), _STATUS_TYPE, context="lifecycle result status"
        )
        reason = self._byte(fields.get("reason"), context="lifecycle result reason")
        result = NativeLifecycleResult(
            stage=stage,
            operation=operation,
            next_stage=next_stage,
            status=status,
            reason=reason,
        )
        _LIFECYCLE_CACHE[cache_key] = result
        return result
