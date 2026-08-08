"""Inward-facing application ports for records, execution, and local observations."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from .records import ForgeRecord, LedgerEntry

if TYPE_CHECKING:
    from .config import Provider


@dataclass(frozen=True)
class ExecutionResult:
    argv: list[str]
    returncode: int
    stdout: bytes
    stderr: bytes
    duration_seconds: float


class CommandExecutor(Protocol):
    """Execute one already-declared bounded command without interpreting domain meaning."""

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
    ) -> ExecutionResult: ...


class RecordReader(Protocol):
    """Read verified typed history without exposing a concrete ledger implementation."""

    def records(self, kind: str | None = None) -> list[LedgerEntry]: ...

    def records_for(self, kinds: frozenset[str]) -> list[LedgerEntry]: ...

    def verify(self) -> dict[str, object]: ...


class RecordCommitter(Protocol):
    """Transactional record persistence needed by application services."""

    def commit(self, record_group: str, ledger_kind: str, record: ForgeRecord) -> LedgerEntry: ...

    def recover(self) -> dict[str, int]: ...

    def action_execution(
        self, action_id: str, *, timeout: float = 30
    ) -> AbstractContextManager[None]: ...


class ProjectObserver(Protocol):
    """Observe filesystem-bound identities and construct isolated local workspaces."""

    def authority_paths(self) -> list[Path]: ...

    def candidate_paths(self) -> list[Path]: ...

    def current_candidate_identity(self) -> str: ...

    def current_authority_identities(self) -> dict[str, str]: ...

    def content_identity(self, paths: list[Path]) -> str: ...

    def identity_map(self, paths: list[Path]) -> dict[str, str]: ...

    def selection_evidence_policy(self) -> tuple[str, tuple[str, ...], str | None]: ...

    def evidence_envelopes(
        self,
    ) -> tuple[dict[str, tuple[str, ...]], dict[str, str], dict[str, str]]: ...

    def current_freeze_bindings(
        self,
        candidate_identity: str | None = None,
        freeze: Mapping[str, object] | None = None,
    ) -> dict[str, str]: ...

    def provider_executable(self, provider: Provider) -> tuple[Path, str]: ...

    def provider_workspace(self, *, evaluator: bool = False) -> AbstractContextManager[str]: ...

    def validate_changed_files(self, changed_files: list[str]) -> dict[str, str]: ...

    def command_path(self, command: list[str]) -> str | None: ...


class VerifierCatalog(Protocol):
    def list_declared(self) -> dict[str, object]: ...


def record_by_id(records: RecordReader, kind: str, identity: str, key: str) -> ForgeRecord:
    for entry in reversed(records.records(kind)):
        if entry.payload.get(key) == identity:
            return entry.payload
    from .errors import ForgeError

    raise ForgeError("RECORD_NOT_FOUND", f"no {kind} record for {identity}")


def payloads(records: RecordReader, kind: str) -> Iterator[ForgeRecord]:
    return (entry.payload for entry in records.records(kind))
