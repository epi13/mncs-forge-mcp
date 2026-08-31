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
from collections.abc import Mapping, Sequence
from contextlib import ExitStack, suppress
from dataclasses import dataclass
from importlib.resources import as_file, files
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
_LIFECYCLE_MODULE = "mncs.forge.lifecycle.v1"
_RECONCILIATION_MODULE = "mncs.forge.reconciliation.v1"
_IDENTITY_MODULE = "mncs.core.identity.v1"


def _encode_identity_component(value: str) -> str:
    return "".join(
        chr(byte)
        if (chr(byte).isalnum() and byte < 128) or byte in (ord("_"), ord("-"), ord("."))
        else f"%{byte:02X}"
        for byte in value.encode("utf-8")
    )


def _semantic_identity(kind: str, *components: str) -> str:
    encoded = "::".join(_encode_identity_component(component) for component in components)
    return f"mncs:0.2:{kind}:{encoded}"


def _finite_type_identity(module: str, name: str) -> str:
    return _semantic_identity("finite-type", module, name)


def _finite_variant_identity(module: str, type_name: str, variant: str) -> str:
    return _semantic_identity("finite-variant", module, type_name, variant)


def _record_type_identity(module: str, name: str, fields: Mapping[str, str]) -> str:
    canonical = "".join(
        f"{field_name}:{field_type};" for field_name, field_type in sorted(fields.items())
    )
    return _semantic_identity("record-type", module, name, canonical)


_STAGE_TYPE = _finite_type_identity(_LIFECYCLE_MODULE, "Stage")
_OPERATION_TYPE = _finite_type_identity(_LIFECYCLE_MODULE, "Operation")
_EVENT_KIND_TYPE = _finite_type_identity(_LIFECYCLE_MODULE, "EventKind")
_DISPOSITION_TYPE = _finite_type_identity(_LIFECYCLE_MODULE, "Disposition")
_FRESHNESS_TYPE = _finite_type_identity(_LIFECYCLE_MODULE, "Freshness")
_STATUS_TYPE = _finite_type_identity("mncs.core.status.v1", "Status")
_DIGEST_TYPE = _record_type_identity(_IDENTITY_MODULE, "Digest32", {"bytes": "[byte; 32]"})
_HISTORY_EVENT_TYPE = _record_type_identity(
    _LIFECYCLE_MODULE,
    "HistoryEvent",
    {
        "candidate": _DIGEST_TYPE,
        "epoch": _DIGEST_TYPE,
        "kind": "EventKind",
        "parent_candidate": _DIGEST_TYPE,
        "parent_epoch": _DIGEST_TYPE,
        "status": _STATUS_TYPE,
    },
)
_PROJECTION_INPUT_TYPE = _record_type_identity(
    _LIFECYCLE_MODULE,
    "ProjectionInput",
    {
        "current_candidate": _DIGEST_TYPE,
        "event_count": "byte",
        "events": "[HistoryEvent; 32]",
        "required_evidence": "byte",
    },
)
_PROJECTION_STATE_TYPE = _record_type_identity(
    _LIFECYCLE_MODULE,
    "ProjectionState",
    {
        "active_epoch": _DIGEST_TYPE,
        "candidate_count": "i64",
        "current_candidate": _DIGEST_TYPE,
        "disposition": "Disposition",
        "epoch_count": "i64",
        "evaluated": "bool",
        "evidence": _STATUS_TYPE,
        "evidence_count": "i64",
        "frozen": "bool",
        "freshness": "Freshness",
        "lineage_ok": "bool",
        "parent_candidate": _DIGEST_TYPE,
        "parent_epoch": _DIGEST_TYPE,
        "stage": "Stage",
    },
)
_PROJECTION_RESULT_TYPE = _record_type_identity(
    _LIFECYCLE_MODULE,
    "ProjectionResult",
    {"projection": "ProjectionState", "reason": "byte", "status": _STATUS_TYPE},
)
_CATEGORY_INPUT_TYPE = _record_type_identity(
    _RECONCILIATION_MODULE,
    "CategoryInput",
    {
        "category": _DIGEST_TYPE,
        "count": "byte",
        "statuses": f"[{_STATUS_TYPE}; 8]",
        "unsupported_count": "byte",
    },
)
_CATEGORY_PROJECTION_TYPE = _record_type_identity(
    _RECONCILIATION_MODULE,
    "CategoryProjection",
    {
        "category": _DIGEST_TYPE,
        "conflict": "bool",
        "fail_count": "i64",
        "observed_count": "i64",
        "pass_count": "i64",
        "status": _STATUS_TYPE,
        "unknown_count": "i64",
        "unsupported_count": "i64",
        "valid": "bool",
    },
)
_RECONCILIATION_INPUT_TYPE = _record_type_identity(
    _RECONCILIATION_MODULE,
    "ReconciliationInput",
    {"categories": "[CategoryInput; 16]", "category_count": "byte"},
)
_RECONCILIATION_STATE_TYPE = _record_type_identity(
    _RECONCILIATION_MODULE,
    "ReconciliationState",
    {
        "categories": "[CategoryProjection; 16]",
        "category_count": "i64",
        "conflicting_category_count": "i64",
        "observed_count": "i64",
        "status": _STATUS_TYPE,
        "unsupported_count": "i64",
        "valid": "bool",
    },
)
_RECONCILIATION_RESULT_TYPE = _record_type_identity(
    _RECONCILIATION_MODULE,
    "ReconciliationResult",
    {"reason": "byte", "state": "ReconciliationState", "status": _STATUS_TYPE},
)
_FINITE_VARIANTS: dict[str, dict[str, int]] = {
    _STATUS_TYPE: _STATUS_VARIANTS,
    _STAGE_TYPE: _LIFECYCLE_STAGES,
    _OPERATION_TYPE: _LIFECYCLE_OPERATIONS,
    _EVENT_KIND_TYPE: {
        "Empty": 0,
        "EpochStarted": 1,
        "CandidateRegistered": 2,
        "EvidenceObserved": 3,
        "CandidateSelected": 4,
        "CandidateRejected": 5,
        "CandidateFrozen": 6,
        "EvaluationRecorded": 7,
    },
    _DISPOSITION_TYPE: {"Undisposed": 0, "Selected": 1, "Rejected": 2, "Conflict": 3},
    _FRESHNESS_TYPE: {
        "NotApplicable": 0,
        "Current": 1,
        "Stale": 2,
        "Unknown": 3,
    },
}
NATIVE_EXECUTION_CONTRACT = "mncs-forge.native-execution.v1"
NATIVE_LIFECYCLE_PROJECTION_CONTRACT = "mncs-forge.lifecycle-projection.v1"
NATIVE_RECONCILIATION_CONTRACT = "mncs-forge.reconciliation-projection.v1"


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


@dataclass(frozen=True, slots=True)
class NativeLifecycleProjection:
    """Typed MNCS projection of bounded Forge lifecycle history."""

    stage: str
    active_epoch: bytes
    parent_epoch: bytes
    current_candidate: bytes
    parent_candidate: bytes
    evidence: str
    disposition: str
    freshness: str
    lineage_ok: bool
    epoch_count: int
    candidate_count: int
    evidence_count: int
    frozen: bool
    evaluated: bool
    status: str
    reason: int


@dataclass(frozen=True, slots=True)
class NativeReconciliationCategory:
    """Typed MNCS projection for one bounded technical evidence category."""

    category: bytes
    status: str
    pass_count: int
    fail_count: int
    unknown_count: int
    observed_count: int
    conflict: bool
    unsupported_count: int


@dataclass(frozen=True, slots=True)
class NativeReconciliationProjection:
    """Typed MNCS projection of a bounded technical evidence envelope."""

    categories: tuple[NativeReconciliationCategory, ...]
    status: str
    category_count: int
    conflicting_category_count: int
    unsupported_count: int
    observed_count: int
    valid: bool
    reason: int


_LIFECYCLE_CACHE: dict[tuple[object, ...], NativeLifecycleResult] = {}
_LIFECYCLE_PROJECTION_CACHE: dict[tuple[object, ...], NativeLifecycleProjection] = {}
_RECONCILIATION_CACHE: dict[tuple[object, ...], NativeReconciliationProjection] = {}


def canonical_candidate_material(
    parent_digest: bytes,
    source_digest: bytes,
    status: str,
    changed_files: bytes,
) -> bytes:
    """Mirror the MNCS chunk contract for host-side differential checks.

    The byte order is declared by the packaged Forge MNCS serialization module. This
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
        self._resource_stack = ExitStack()
        configured_source = os.environ.get("MNCS_FORGE_NATIVE_SOURCE")
        if configured_source:
            self.native_source = Path(configured_source).expanduser().resolve()
            self.native_root = self.native_source.parent
        else:
            resource_root = files("mncs_forge.resources").joinpath("native", "forge")
            self.native_root = self._resource_stack.enter_context(as_file(resource_root))
            self.native_source = self.native_root / "core.mncs"

    def __del__(self) -> None:
        # ``as_file`` normally resolves to the installed filesystem.  The
        # context is still closed for zip-backed importers and test fixtures.
        stack = getattr(self, "_resource_stack", None)
        if stack is not None:
            with suppress(Exception):
                stack.close()

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
        """Whether the packaged Forge MNCS entrypoint is available."""

        return self.native_source.is_file()

    @property
    def forge_modules_available(self) -> bool:
        return all(
            (self.native_root / name).is_file()
            for name in (
                "core.mncs",
                "identity.mncs",
                "lifecycle.mncs",
                "reconciliation.mncs",
                "records.mncs",
                "serialization.mncs",
            )
        )

    def ensure_available(self) -> None:
        """Fail closed when required native execution cannot be selected."""

        if self.language_root is None:
            raise ForgeError("NATIVE_UNAVAILABLE", "mncs-language checkout is unavailable")
        if not self.forge_modules_available:
            raise ForgeError("NATIVE_UNAVAILABLE", "packaged Forge MNCS modules are unavailable")
        self._command()

    def status(self, mode: str) -> dict[str, object]:
        """Return an observable, non-authoritative native selection status."""

        if mode == "off":
            return {"mode": mode, "selected": False, "available": False, "reason": "disabled"}
        available = self.language_root is not None and self.forge_modules_available
        if available:
            try:
                command = self._command()
            except ForgeError as exc:
                return {
                    "mode": mode,
                    "selected": False,
                    "available": False,
                    "reason": exc.code,
                }
            return {
                "mode": mode,
                "selected": True,
                "available": True,
                "command": list(command),
            }
        return {
            "mode": mode,
            "selected": False,
            "available": False,
            "reason": "NATIVE_UNAVAILABLE",
        }

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
            for relative in (Path("target/release/mncs"), Path("target/debug/mncs")):
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
        library_path = os.pathsep.join((str(self.language_root / "library"), str(self.native_root)))
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

    @staticmethod
    def _content_identity(paths: list[Path]) -> str:
        digest = hashlib.sha256()
        for path in sorted(path for path in paths if path.is_file()):
            relative = path.as_posix().encode("utf-8")
            digest.update(len(relative).to_bytes(4, "big"))
            digest.update(relative)
            content = path.read_bytes()
            digest.update(len(content).to_bytes(8, "big"))
            digest.update(content)
        return digest.hexdigest()

    def semantic_input_identity(self) -> str:
        """Identify every source/runtime input that can affect a native result."""

        self.ensure_available()
        assert self.language_root is not None
        forge_sources = list(self.native_root.glob("*.mncs"))
        library_sources = list((self.language_root / "library").rglob("*.mncs"))
        compiler_sources = list((self.language_root / "crates").rglob("*.rs"))
        manifest_sources = [
            self.language_root / "Cargo.toml",
            self.language_root / "Cargo.lock",
        ]
        command = self._command()
        command_identity: list[Path] = []
        if command and Path(command[0]).is_file():
            command_identity.append(Path(command[0]))
        identity = {
            "contract": NATIVE_EXECUTION_CONTRACT,
            "forge_sources": self._content_identity(forge_sources),
            "library_sources": self._content_identity(library_sources),
            "compiler_sources": self._content_identity(compiler_sources + manifest_sources),
            "command": command,
            "command_content": self._content_identity(command_identity),
        }
        return hashlib.sha256(json.dumps(identity, sort_keys=True).encode("utf-8")).hexdigest()

    def source_study(self, source: Path, *, node_id: str = "forge-native") -> NativeInvocation:
        return self.invoke(["source-study", str(source.resolve()), "--node-id", node_id])

    def execute(self, source: Path, request: Path, *, backend: bool = False) -> NativeInvocation:
        command = "execute-backend" if backend else "execute"
        return self.invoke([command, str(source.resolve()), str(request.resolve())])

    @staticmethod
    def _finite_argument(type_name: str, variant: str, discriminant: int) -> dict[str, object]:
        type_identity = (
            type_name
            if type_name.startswith(_MNCS_TYPE_PREFIX)
            else f"{_MNCS_TYPE_PREFIX}{type_name}"
        )
        variant_type_name = type_identity[len(_MNCS_TYPE_PREFIX) :]
        return {
            "finite": {
                "type_identity": type_identity,
                "variant_identity": f"{_MNCS_VARIANT_PREFIX}{variant_type_name}::{variant}",
                "discriminant": discriminant,
            }
        }

    @staticmethod
    def _finite_value(
        type_identity: str, module: str, type_name: str, variant: str
    ) -> dict[str, object]:
        try:
            discriminant = _FINITE_VARIANTS[type_identity][variant]
        except KeyError as exc:
            raise ForgeError(
                "NATIVE_CONFIG_INVALID", f"unknown native finite variant: {variant}"
            ) from exc
        return {
            "finite": {
                "type_identity": type_identity,
                "variant_identity": _finite_variant_identity(module, type_name, variant),
                "discriminant": discriminant,
            }
        }

    @staticmethod
    def _record_value(
        type_identity: str, name: str, fields: Mapping[str, object]
    ) -> dict[str, object]:
        return {
            "record": {
                "type_identity": type_identity,
                "name": name,
                "fields": [[field_name, fields[field_name]] for field_name in sorted(fields)],
            }
        }

    @staticmethod
    def _sequence_value(values: Sequence[object]) -> dict[str, object]:
        return {"sequence": {"values": list(values)}}

    @staticmethod
    def _digest_value(value: object, *, context: str) -> dict[str, object]:
        if value is None or value == "":
            raw = bytes(32)
        elif isinstance(value, bytes):
            raw = value
        elif isinstance(value, str):
            encoded = value.rsplit(":", 1)[-1]
            try:
                raw = bytes.fromhex(encoded)
            except ValueError as exc:
                raise ForgeError(
                    "NATIVE_LIFECYCLE_UNKNOWN", f"{context} is not a digest identity"
                ) from exc
        else:
            raise ForgeError("NATIVE_LIFECYCLE_UNKNOWN", f"{context} is not a digest identity")
        if len(raw) != 32:
            raise ForgeError("NATIVE_LIFECYCLE_UNKNOWN", f"{context} is not a 32-byte digest")
        return NativeForgeAdapter._record_value(
            _DIGEST_TYPE,
            "Digest32",
            {
                "bytes": NativeForgeAdapter._sequence_value(
                    [{"byte": {"value": item}} for item in raw]
                )
            },
        )

    @staticmethod
    def _history_event_value(event: Mapping[str, object]) -> dict[str, object]:
        kind = str(event.get("kind", "Empty"))
        if kind not in _FINITE_VARIANTS[_EVENT_KIND_TYPE]:
            raise ForgeError("NATIVE_LIFECYCLE_UNKNOWN", f"unknown native history event: {kind}")
        status = str(event.get("status", "UNKNOWN"))
        if status not in _STATUS_VARIANTS:
            raise ForgeError("NATIVE_LIFECYCLE_UNKNOWN", f"unknown native event status: {status}")
        return NativeForgeAdapter._record_value(
            _HISTORY_EVENT_TYPE,
            "HistoryEvent",
            {
                "candidate": NativeForgeAdapter._digest_value(
                    event.get("candidate"), context="history candidate"
                ),
                "epoch": NativeForgeAdapter._digest_value(
                    event.get("epoch"), context="history epoch"
                ),
                "kind": NativeForgeAdapter._finite_value(
                    _EVENT_KIND_TYPE, _LIFECYCLE_MODULE, "EventKind", kind
                ),
                "parent_candidate": NativeForgeAdapter._digest_value(
                    event.get("parent_candidate"), context="history parent candidate"
                ),
                "parent_epoch": NativeForgeAdapter._digest_value(
                    event.get("parent_epoch"), context="history parent epoch"
                ),
                "status": NativeForgeAdapter._finite_value(
                    _STATUS_TYPE, "mncs.core.status.v1", "Status", status
                ),
            },
        )

    @staticmethod
    def reconciliation_category_identity(category: str) -> bytes:
        """Bind a host category label without making strings part of the ABI."""

        if not isinstance(category, str) or not category:
            raise ForgeError("NATIVE_RECONCILIATION_UNKNOWN", "evidence category is malformed")
        return hashlib.sha256(
            b"mncs-forge.reconciliation.category.v1\0" + category.encode("utf-8")
        ).digest()

    @classmethod
    def _reconciliation_category_value(
        cls, category: str, records: Sequence[Mapping[str, object]]
    ) -> dict[str, object]:
        if len(records) == 0 or len(records) > 8:
            raise ForgeError(
                "NATIVE_RECONCILIATION_UNKNOWN",
                "native evidence category must contain between 1 and 8 records",
            )
        statuses: list[dict[str, object]] = []
        unsupported_count = 0
        for record in records:
            if not isinstance(record, Mapping):
                raise ForgeError(
                    "NATIVE_RECONCILIATION_UNKNOWN",
                    f"native evidence record is malformed for category {category}",
                )
            status = record.get("status")
            if not isinstance(status, str) or status not in _STATUS_VARIANTS:
                raise ForgeError(
                    "NATIVE_RECONCILIATION_UNKNOWN",
                    f"native evidence status is invalid for category {category}",
                )
            statuses.append(
                cls._finite_value(_STATUS_TYPE, "mncs.core.status.v1", "Status", str(status))
            )
            unsupported = record.get("unsupported_constructs", [])
            if isinstance(unsupported, Sequence) and not isinstance(unsupported, (str, bytes)):
                unsupported_count += len(unsupported)
            elif unsupported is not None:
                raise ForgeError(
                    "NATIVE_RECONCILIATION_UNKNOWN",
                    f"unsupported construct list is malformed for category {category}",
                )
        if unsupported_count > 255:
            raise ForgeError(
                "NATIVE_RECONCILIATION_UNKNOWN",
                f"unsupported construct count exceeds the byte bound for category {category}",
            )
        statuses.extend(
            cls._finite_value(_STATUS_TYPE, "mncs.core.status.v1", "Status", "UNKNOWN")
            for _ in range(8 - len(statuses))
        )
        return cls._record_value(
            _CATEGORY_INPUT_TYPE,
            "CategoryInput",
            {
                "category": cls._digest_value(
                    cls.reconciliation_category_identity(category),
                    context="reconciliation category",
                ),
                "count": {"byte": {"value": len(records)}},
                "statuses": cls._sequence_value(statuses),
                "unsupported_count": {"byte": {"value": unsupported_count}},
            },
        )

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
        type_identity = (
            type_name
            if type_name.startswith(_MNCS_TYPE_PREFIX)
            else f"{_MNCS_TYPE_PREFIX}{type_name}"
        )
        if finite.get("type_identity") != type_identity:
            raise ForgeError("NATIVE_LIFECYCLE_UNKNOWN", f"{context} has an invalid type")
        variant_type_name = type_identity[len(_MNCS_TYPE_PREFIX) :]
        expected_prefix = f"{_MNCS_VARIANT_PREFIX}{variant_type_name}::"
        variant_identity = finite.get("variant_identity")
        if not isinstance(variant_identity, str) or not variant_identity.startswith(
            expected_prefix
        ):
            raise ForgeError("NATIVE_LIFECYCLE_UNKNOWN", f"{context} has an invalid type")
        variant = variant_identity[len(expected_prefix) :]
        discriminant = finite.get("discriminant")
        if not isinstance(discriminant, int) or isinstance(discriminant, bool):
            raise ForgeError("NATIVE_LIFECYCLE_UNKNOWN", f"{context} has no discriminant")
        expected_values = _FINITE_VARIANTS[type_identity]
        expected = expected_values.get(variant)
        if expected is None or discriminant != expected:
            raise ForgeError("NATIVE_LIFECYCLE_UNKNOWN", f"{context} has an invalid variant")
        return variant

    @staticmethod
    def _record_value_fields(value: object, expected_type: str, *, context: str) -> dict[str, Any]:
        if not isinstance(value, dict) or not isinstance(value.get("record"), dict):
            raise ForgeError("NATIVE_LIFECYCLE_UNKNOWN", f"{context} is not a record")
        record = value["record"]
        if record.get("type_identity") != expected_type:
            raise ForgeError("NATIVE_LIFECYCLE_UNKNOWN", f"{context} has an invalid type")
        fields = record.get("fields")
        if not isinstance(fields, list):
            raise ForgeError("NATIVE_LIFECYCLE_UNKNOWN", f"{context} has malformed fields")
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
    def _boolean(value: object, *, context: str) -> bool:
        if not isinstance(value, dict) or not isinstance(value.get("boolean"), dict):
            raise ForgeError("NATIVE_LIFECYCLE_UNKNOWN", f"{context} is not a boolean")
        result = value["boolean"].get("value")
        if not isinstance(result, bool):
            raise ForgeError("NATIVE_LIFECYCLE_UNKNOWN", f"{context} has an invalid value")
        return result

    @staticmethod
    def _integer(value: object, *, context: str) -> int:
        if not isinstance(value, dict) or not isinstance(value.get("integer"), dict):
            raise ForgeError("NATIVE_LIFECYCLE_UNKNOWN", f"{context} is not an integer")
        result = value["integer"].get("value")
        if not isinstance(result, int) or isinstance(result, bool):
            raise ForgeError("NATIVE_LIFECYCLE_UNKNOWN", f"{context} has an invalid value")
        return result

    @classmethod
    def _digest_bytes(cls, value: object, *, context: str) -> bytes:
        fields = cls._record_value_fields(value, _DIGEST_TYPE, context=context)
        sequence = fields.get("bytes")
        if not isinstance(sequence, dict) or not isinstance(sequence.get("sequence"), dict):
            raise ForgeError("NATIVE_LIFECYCLE_UNKNOWN", f"{context} bytes are malformed")
        values = sequence["sequence"].get("values")
        if not isinstance(values, list) or len(values) != 32:
            raise ForgeError("NATIVE_LIFECYCLE_UNKNOWN", f"{context} bytes are malformed")
        output = bytearray()
        for item in values:
            output.append(cls._byte(item, context=context))
        return bytes(output)

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
        if not self.forge_modules_available:
            raise ForgeError(
                "NATIVE_UNAVAILABLE", "packaged Forge MNCS lifecycle source is unavailable"
            )
        command = tuple(self._command())
        semantic_identity = self.semantic_input_identity()
        cache_key = (
            NATIVE_EXECUTION_CONTRACT,
            semantic_identity,
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

    def lifecycle_projection(
        self,
        events: Sequence[Mapping[str, object]],
        *,
        current_candidate: str | None,
        required_evidence: int,
    ) -> NativeLifecycleProjection:
        """Project bounded typed lifecycle history in the MNCS runtime.

        The host supplies only normalized record observations and digest
        identities.  The native module owns parentage, disposition, freshness,
        status, and stage projection; persistence and digest production remain
        outside the language boundary.
        """

        if len(events) > 32:
            raise ForgeError(
                "NATIVE_LIFECYCLE_UNKNOWN", "native history exceeds the 32-event bound"
            )
        if not isinstance(required_evidence, int) or isinstance(required_evidence, bool):
            raise ForgeError("NATIVE_LIFECYCLE_UNKNOWN", "native evidence bound is not an integer")
        if not 0 <= required_evidence <= 255:
            raise ForgeError(
                "NATIVE_LIFECYCLE_UNKNOWN", "native evidence bound is outside byte range"
            )
        self.ensure_available()
        event_list = [dict(event) for event in events]
        cache_key = (
            NATIVE_LIFECYCLE_PROJECTION_CONTRACT,
            self.semantic_input_identity(),
            json.dumps(event_list, sort_keys=True),
            current_candidate or "",
            required_evidence,
        )
        cached = _LIFECYCLE_PROJECTION_CACHE.get(cache_key)
        if cached is not None:
            return cached
        event_values = [self._history_event_value(event) for event in event_list]
        event_values.extend(self._history_event_value({}) for _ in range(32 - len(event_values)))
        request_value = self._record_value(
            _PROJECTION_INPUT_TYPE,
            "ProjectionInput",
            {
                "current_candidate": self._digest_value(
                    current_candidate, context="current candidate"
                ),
                "event_count": {"byte": {"value": len(event_list)}},
                "events": self._sequence_value(event_values),
                "required_evidence": {"byte": {"value": required_evidence}},
            },
        )
        request = {
            "schema_version": NATIVE_SCHEMA_VERSION,
            "target": {"module": "mncs.forge.core.v1", "function": "lifecycle_project"},
            "arguments": [request_value],
            "step_budget": 200_000,
        }
        with tempfile.TemporaryDirectory(prefix=".mncs-native-", dir=self.forge_root) as directory:
            request_path = Path(directory) / "lifecycle-projection-request.json"
            request_path.write_text(json.dumps(request), encoding="utf-8")
            invocation = self.execute(self.native_source, request_path)
        if not invocation.ok or invocation.payload is None:
            raise ForgeError(
                "NATIVE_LIFECYCLE_UNKNOWN",
                "language-owned lifecycle projection did not return valid JSON "
                f"(returncode {invocation.returncode})",
            )
        result_fields = self._record_fields(invocation.payload, context="lifecycle projection")
        projection_fields = self._record_value_fields(
            result_fields.get("projection"),
            _PROJECTION_STATE_TYPE,
            context="lifecycle projection state",
        )
        stage = self._finite_variant(
            projection_fields.get("stage"), _STAGE_TYPE, context="lifecycle projection stage"
        )
        evidence = self._finite_variant(
            projection_fields.get("evidence"), _STATUS_TYPE, context="lifecycle projection evidence"
        )
        disposition = self._finite_variant(
            projection_fields.get("disposition"),
            _DISPOSITION_TYPE,
            context="lifecycle projection disposition",
        )
        freshness = self._finite_variant(
            projection_fields.get("freshness"),
            _FRESHNESS_TYPE,
            context="lifecycle projection freshness",
        )
        status = self._finite_variant(
            result_fields.get("status"), _STATUS_TYPE, context="lifecycle projection status"
        )
        result = NativeLifecycleProjection(
            stage=stage,
            active_epoch=self._digest_bytes(
                projection_fields.get("active_epoch"), context="active epoch"
            ),
            parent_epoch=self._digest_bytes(
                projection_fields.get("parent_epoch"), context="parent epoch"
            ),
            current_candidate=self._digest_bytes(
                projection_fields.get("current_candidate"), context="current candidate"
            ),
            parent_candidate=self._digest_bytes(
                projection_fields.get("parent_candidate"), context="parent candidate"
            ),
            evidence=evidence,
            disposition=disposition,
            freshness=freshness,
            lineage_ok=self._boolean(
                projection_fields.get("lineage_ok"), context="lifecycle lineage flag"
            ),
            epoch_count=self._integer(
                projection_fields.get("epoch_count"), context="lifecycle epoch count"
            ),
            candidate_count=self._integer(
                projection_fields.get("candidate_count"), context="lifecycle candidate count"
            ),
            evidence_count=self._integer(
                projection_fields.get("evidence_count"), context="lifecycle evidence count"
            ),
            frozen=self._boolean(projection_fields.get("frozen"), context="lifecycle frozen flag"),
            evaluated=self._boolean(
                projection_fields.get("evaluated"), context="lifecycle evaluated flag"
            ),
            status=status,
            reason=self._byte(result_fields.get("reason"), context="lifecycle projection reason"),
        )
        _LIFECYCLE_PROJECTION_CACHE[cache_key] = result
        return result

    def reconciliation_projection(
        self, categories: Mapping[str, Sequence[Mapping[str, object]]]
    ) -> NativeReconciliationProjection:
        """Project bounded technical evidence categories through MNCS.

        Category labels, record identities, and disclosure-shaped values remain
        host concerns. The native kernel owns the bounded status fold, per
        category conflict classification, and aggregate technical status.
        """

        if not isinstance(categories, Mapping):
            raise ForgeError(
                "NATIVE_RECONCILIATION_UNKNOWN",
                "native reconciliation categories are malformed",
            )
        for category, records in categories.items():
            if not isinstance(category, str) or not category:
                raise ForgeError(
                    "NATIVE_RECONCILIATION_UNKNOWN",
                    "native reconciliation category is malformed",
                )
            if not isinstance(records, Sequence) or isinstance(records, (str, bytes)):
                raise ForgeError(
                    "NATIVE_RECONCILIATION_UNKNOWN",
                    f"native evidence records are malformed for category {category}",
                )
        ordered = sorted(categories.items())
        if len(ordered) > 16:
            raise ForgeError(
                "NATIVE_RECONCILIATION_UNKNOWN",
                "native reconciliation exceeds the 16-category bound",
            )
        self.ensure_available()
        category_values = [
            self._reconciliation_category_value(category, records) for category, records in ordered
        ]
        empty = self._reconciliation_category_value("__unused__", [{"status": "UNKNOWN"}])
        category_values.extend(empty for _ in range(16 - len(category_values)))
        try:
            serialized = json.dumps(
                {
                    "categories": [
                        {
                            "category": category,
                            "records": [dict(record) for record in records],
                        }
                        for category, records in ordered
                    ]
                },
                sort_keys=True,
            )
        except (TypeError, ValueError) as exc:
            raise ForgeError(
                "NATIVE_RECONCILIATION_UNKNOWN",
                "native reconciliation input cannot be serialized",
            ) from exc
        cache_key = (
            NATIVE_RECONCILIATION_CONTRACT,
            self.semantic_input_identity(),
            serialized,
        )
        cached = _RECONCILIATION_CACHE.get(cache_key)
        if cached is not None:
            return cached
        request_value = self._record_value(
            _RECONCILIATION_INPUT_TYPE,
            "ReconciliationInput",
            {
                "categories": self._sequence_value(category_values),
                "category_count": {"byte": {"value": len(ordered)}},
            },
        )
        request = {
            "schema_version": NATIVE_SCHEMA_VERSION,
            "target": {
                "module": "mncs.forge.core.v1",
                "function": "evidence_reconcile",
            },
            "arguments": [request_value],
            "step_budget": 500_000,
        }
        with tempfile.TemporaryDirectory(prefix=".mncs-native-", dir=self.forge_root) as directory:
            request_path = Path(directory) / "reconciliation-request.json"
            request_path.write_text(json.dumps(request), encoding="utf-8")
            invocation = self.execute(self.native_source, request_path)
        if not invocation.ok or invocation.payload is None:
            raise ForgeError(
                "NATIVE_RECONCILIATION_UNKNOWN",
                "language-owned reconciliation did not return valid JSON "
                f"(returncode {invocation.returncode})",
            )
        result_fields = self._record_fields(invocation.payload, context="reconciliation")
        state_fields = self._record_value_fields(
            result_fields.get("state"),
            _RECONCILIATION_STATE_TYPE,
            context="reconciliation state",
        )
        category_sequence = state_fields.get("categories")
        if not isinstance(category_sequence, dict) or not isinstance(
            category_sequence.get("sequence"), dict
        ):
            raise ForgeError(
                "NATIVE_RECONCILIATION_UNKNOWN", "reconciliation categories are malformed"
            )
        category_items = category_sequence["sequence"].get("values")
        if not isinstance(category_items, list) or len(category_items) != 16:
            raise ForgeError(
                "NATIVE_RECONCILIATION_UNKNOWN", "reconciliation categories are malformed"
            )
        category_count = self._integer(
            state_fields.get("category_count"), context="reconciliation category count"
        )
        if category_count != len(ordered) or not 0 <= category_count <= 16:
            raise ForgeError(
                "NATIVE_RECONCILIATION_UNKNOWN",
                "reconciliation category count disagrees with the request",
            )
        result_status = self._finite_variant(
            result_fields.get("status"),
            _STATUS_TYPE,
            context="reconciliation result status",
        )
        state_status = self._finite_variant(
            state_fields.get("status"),
            _STATUS_TYPE,
            context="reconciliation state status",
        )
        valid = self._boolean(state_fields.get("valid"), context="reconciliation validity")
        reason = self._byte(result_fields.get("reason"), context="reconciliation reason")
        if not valid or reason != 0 or state_status != result_status:
            raise ForgeError(
                "NATIVE_RECONCILIATION_UNKNOWN",
                "language-owned reconciliation reported an invalid bounded projection",
            )
        projected: list[NativeReconciliationCategory] = []
        for index in range(category_count):
            fields = self._record_value_fields(
                category_items[index],
                _CATEGORY_PROJECTION_TYPE,
                context="reconciliation category projection",
            )
            category_digest = self._digest_bytes(
                fields.get("category"), context="reconciliation category identity"
            )
            expected_digest = self.reconciliation_category_identity(ordered[index][0])
            if category_digest != expected_digest:
                raise ForgeError(
                    "NATIVE_RECONCILIATION_MISMATCH",
                    "native reconciliation category identity disagrees with the request",
                )
            projected.append(
                NativeReconciliationCategory(
                    category=category_digest,
                    status=self._finite_variant(
                        fields.get("status"),
                        _STATUS_TYPE,
                        context="reconciliation category status",
                    ),
                    pass_count=self._integer(
                        fields.get("pass_count"), context="reconciliation pass count"
                    ),
                    fail_count=self._integer(
                        fields.get("fail_count"), context="reconciliation fail count"
                    ),
                    unknown_count=self._integer(
                        fields.get("unknown_count"), context="reconciliation unknown count"
                    ),
                    observed_count=self._integer(
                        fields.get("observed_count"), context="reconciliation observed count"
                    ),
                    conflict=self._boolean(
                        fields.get("conflict"), context="reconciliation conflict flag"
                    ),
                    unsupported_count=self._integer(
                        fields.get("unsupported_count"),
                        context="reconciliation unsupported count",
                    ),
                )
            )
        result = NativeReconciliationProjection(
            categories=tuple(projected),
            status=result_status,
            category_count=category_count,
            conflicting_category_count=self._integer(
                state_fields.get("conflicting_category_count"),
                context="reconciliation conflict count",
            ),
            unsupported_count=self._integer(
                state_fields.get("unsupported_count"),
                context="reconciliation unsupported count",
            ),
            observed_count=self._integer(
                state_fields.get("observed_count"), context="reconciliation observed count"
            ),
            valid=valid,
            reason=reason,
        )
        if result.conflicting_category_count != sum(item.conflict for item in projected):
            raise ForgeError(
                "NATIVE_RECONCILIATION_MISMATCH",
                "native reconciliation conflict count is inconsistent",
            )
        if result.observed_count != sum(item.observed_count for item in projected):
            raise ForgeError(
                "NATIVE_RECONCILIATION_MISMATCH",
                "native reconciliation observed count is inconsistent",
            )
        if result.unsupported_count != sum(item.unsupported_count for item in projected):
            raise ForgeError(
                "NATIVE_RECONCILIATION_MISMATCH",
                "native reconciliation unsupported count is inconsistent",
            )
        _RECONCILIATION_CACHE[cache_key] = result
        return result
