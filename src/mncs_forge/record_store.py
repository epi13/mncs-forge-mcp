"""Recoverable local commits for immutable Forge records and their ledger entries."""

from __future__ import annotations

import errno
import hashlib
import json
import os
import shutil
import uuid
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from pathlib import Path
from typing import Protocol, cast

from filelock import FileLock, Timeout

from .errors import ForgeError
from .ledger import GENESIS, LEDGER_LINE_BYTE_CAP, Ledger
from .records import (
    CURRENT_SCHEMA_VERSION,
    PERSISTED_RECORD_CONTEXTS,
    ForgeRecord,
    JsonObject,
    LedgerEntry,
    immutable_record_path,
    load_record_file,
    normalize_ledger_entry,
    persisted_record_context,
    safe_record_identity,
)
from .serialization import canonical_bytes

TRANSACTION_SCHEMA_VERSION = 1
INDEX_SCHEMA_VERSION = 1
IMMUTABLE_RECORD_BYTE_CAP = 4_000_000

Failpoint = Callable[[str], None]


class RecordStore(Protocol):
    """Persistence boundary; lifecycle authorization remains outside this protocol."""

    def commit(self, record_group: str, ledger_kind: str, record: ForgeRecord) -> LedgerEntry: ...

    def recover(self) -> dict[str, int]: ...

    def action_execution(
        self, action_id: str, *, timeout: float = 30
    ) -> AbstractContextManager[None]: ...


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sync_directory(path: Path) -> bool:
    """Sync directory metadata where Python/the platform exposes that primitive."""

    try:
        descriptor = os.open(path, os.O_RDONLY)
    except (OSError, AttributeError) as exc:
        if os.name == "nt" or (
            isinstance(exc, OSError)
            and exc.errno in {errno.EACCES, errno.EBADF, errno.EINVAL, errno.ENOTSUP}
        ):
            return False
        raise ForgeError(
            "STORAGE_DIRECTORY_SYNC", f"cannot open directory for sync: {path}"
        ) from exc
    try:
        os.fsync(descriptor)
    except OSError as exc:
        if os.name == "nt" or exc.errno in {errno.EBADF, errno.EINVAL, errno.ENOTSUP}:
            return False
        raise ForgeError("STORAGE_DIRECTORY_SYNC", f"cannot sync directory: {path}") from exc
    finally:
        os.close(descriptor)
    return True


def _durable_mkdir(path: Path) -> None:
    missing: list[Path] = []
    current = path
    while not current.exists():
        missing.append(current)
        if current.parent == current:
            break
        current = current.parent
    path.mkdir(parents=True, exist_ok=True)
    for created in reversed(missing):
        _sync_directory(created)
        _sync_directory(created.parent)


def _durable_write(path: Path, value: bytes, *, exclusive: bool = False) -> None:
    _durable_mkdir(path.parent)
    flags = os.O_CREAT | os.O_WRONLY | os.O_TRUNC
    if exclusive:
        flags |= os.O_EXCL
    descriptor = os.open(path, flags, 0o600)
    try:
        view = memoryview(value)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise OSError("short durable write")
            view = view[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _atomic_write(path: Path, value: bytes) -> None:
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    _durable_write(temporary, value, exclusive=True)
    os.replace(temporary, path)
    _sync_directory(path.parent)


class LocalRecordStore:
    """Filesystem transaction journal for one record plus one ledger append."""

    def __init__(
        self,
        state_dir: Path,
        ledger: Ledger | None = None,
        *,
        failpoint: Failpoint | None = None,
        recover_on_open: bool = True,
    ) -> None:
        self.state_dir = state_dir
        self.ledger = ledger or Ledger(state_dir)
        self.lock = self.ledger.lock
        self.transactions_dir = state_dir / "transactions"
        self.index_path = state_dir / "ledger-index.json"
        self.action_locks_dir = state_dir / "action-locks"
        self._failpoint = failpoint
        if recover_on_open:
            self.recover()

    def _trip(self, name: str) -> None:
        if self._failpoint is not None:
            self._failpoint(name)

    @staticmethod
    def _record_bytes(record: ForgeRecord) -> bytes:
        return canonical_bytes(record.to_json()) + b"\n"

    def _ledger_bytes_unlocked(self) -> bytes:
        try:
            return self.ledger.path.read_bytes() if self.ledger.path.exists() else b""
        except OSError as exc:
            raise ForgeError("LEDGER_MALFORMED", f"cannot read ledger bytes: {exc}") from exc

    def _journal_bytes(self, journal: JsonObject) -> bytes:
        return canonical_bytes(journal) + b"\n"

    def commit(self, record_group: str, ledger_kind: str, record: ForgeRecord) -> LedgerEntry:
        context = persisted_record_context(group=record_group, ledger_kind=ledger_kind)
        if record.record_type is not context.record_type:
            raise ForgeError(
                "RECORD_TYPE_MISMATCH",
                f"storage context requires {context.record_type.value}, "
                f"got {record.record_type.value}",
            )
        if record.schema_version != CURRENT_SCHEMA_VERSION:
            raise ForgeError("RECORD_VERSION_WRITE", "new records require schema version 1")
        identity = record.get(context.identity_field)
        if not isinstance(identity, str) or not identity:
            raise ForgeError(
                "RECORD_IDENTITY", f"record requires string identity field {context.identity_field}"
            )
        destination = immutable_record_path(self.state_dir, record_group, identity)
        record_bytes = self._record_bytes(record)
        if len(record_bytes) > IMMUTABLE_RECORD_BYTE_CAP:
            raise ForgeError("RECORD_SIZE", "immutable record exceeds the storage byte limit")
        _durable_mkdir(self.state_dir)
        with self.lock:
            self._recover_unlocked()
            raw_records = self.ledger._read_unlocked_raw()
            self.ledger._verify_raw_records(raw_records)
            existing = [
                normalize_ledger_entry(raw)
                for raw in raw_records
                if raw.get("kind") == ledger_kind
                and isinstance(raw.get("payload"), dict)
                and cast(dict[str, object], raw["payload"]).get(context.identity_field) == identity
            ]
            if destination.exists() or existing:
                return self._resolve_duplicate(
                    destination=destination,
                    record=record,
                    record_bytes=record_bytes,
                    entries=existing,
                )

            ledger_before = self._ledger_bytes_unlocked()
            raw_entry, entry = self.ledger._build_entry_unlocked(
                kind=ledger_kind, payload=record, records=raw_records
            )
            ledger_after = ledger_before + canonical_bytes(raw_entry) + b"\n"
            if len(canonical_bytes(raw_entry)) + 1 > LEDGER_LINE_BYTE_CAP:
                raise ForgeError("RECORD_SIZE", "ledger entry exceeds the storage byte limit")
            txid = uuid.uuid4().hex
            tx_dir = self.transactions_dir / txid
            record_stage = tx_dir / "record.stage"
            ledger_stage = tx_dir / "ledger.stage"
            journal_path = tx_dir / "journal.json"
            relative_destination = destination.relative_to(self.state_dir).as_posix()
            journal: JsonObject = {
                "schema_version": TRANSACTION_SCHEMA_VERSION,
                "transaction_id": txid,
                "state": "PREPARED",
                "record_group": record_group,
                "ledger_kind": ledger_kind,
                "record_identity": identity,
                "record_destination": relative_destination,
                "record_sha256": _sha256(record_bytes),
                "ledger_before_sha256": _sha256(ledger_before),
                "ledger_after_sha256": _sha256(ledger_after),
                "expected_sequence": entry.sequence,
                "expected_previous_hash": entry.previous_hash,
                "entry_hash": entry.entry_hash,
            }
            self._trip("before_prepare")
            _durable_mkdir(tx_dir)
            _sync_directory(self.transactions_dir)
            _durable_write(record_stage, record_bytes, exclusive=True)
            self._trip("after_record_staged")
            _durable_write(ledger_stage, ledger_after, exclusive=True)
            self._trip("after_ledger_staged")
            _atomic_write(journal_path, self._journal_bytes(journal))
            _sync_directory(tx_dir)
            self._trip("after_prepared")
            _durable_mkdir(destination.parent)
            os.replace(record_stage, destination)
            _sync_directory(destination.parent)
            self._trip("after_record_published")
            self._trip("before_ledger_published")
            self._assert_expected_ledger(journal, ledger_before)
            os.replace(ledger_stage, self.ledger.path)
            _sync_directory(self.state_dir)
            self._trip("after_ledger_published")
            self._trip("before_committed")
            journal["state"] = "COMMITTED"
            _atomic_write(journal_path, self._journal_bytes(journal))
            self._trip("after_committed")
            self._trip("during_index_update")
            self._rebuild_index_unlocked()
            self._cleanup_transaction_unlocked(tx_dir)
            return entry

    def _resolve_duplicate(
        self,
        *,
        destination: Path,
        record: ForgeRecord,
        record_bytes: bytes,
        entries: list[LedgerEntry],
    ) -> LedgerEntry:
        if len(entries) != 1 or not destination.is_file():
            raise ForgeError(
                "RECORD_STORAGE_CONFLICT",
                "record identity has an incomplete or duplicate durable representation",
            )
        try:
            persisted = destination.read_bytes()
        except OSError as exc:
            raise ForgeError("RECORD_STORAGE_CONFLICT", f"cannot inspect duplicate: {exc}") from exc
        if persisted != record_bytes or entries[0].payload.to_json() != record.to_json():
            raise ForgeError(
                "RECORD_EXISTS", "immutable record identity already exists with different content"
            )
        return entries[0]

    def _assert_expected_ledger(self, journal: JsonObject, expected_bytes: bytes) -> None:
        actual = self._ledger_bytes_unlocked()
        if actual != expected_bytes or _sha256(actual) != journal["ledger_before_sha256"]:
            raise ForgeError(
                "TRANSACTION_LEDGER_CONFLICT",
                "ledger head changed after transaction preparation",
            )
        raw = self.ledger._read_unlocked_raw()
        head = self.ledger._verify_raw_records(raw)
        if (
            len(raw) + 1 != journal["expected_sequence"]
            or head != journal["expected_previous_hash"]
        ):
            raise ForgeError(
                "TRANSACTION_LEDGER_CONFLICT", "prepared predecessor no longer matches ledger"
            )

    def recover(self) -> dict[str, int]:
        _durable_mkdir(self.state_dir)
        with self.lock:
            recovered = self._recover_unlocked()
            raw = self.ledger._read_unlocked_raw()
            self.ledger._verify_raw_records(raw)
            entries = [normalize_ledger_entry(item) for item in raw]
            self.ledger._verify_immutable_records_unlocked(entries)
            if self.index_path.exists():
                self._ensure_index_unlocked(raw)
            return recovered

    def _recover_unlocked(self) -> dict[str, int]:
        completed = 0
        abandoned = 0
        if not self.transactions_dir.exists():
            return {"completed": 0, "abandoned": 0}
        for tx_dir in sorted(path for path in self.transactions_dir.iterdir() if path.is_dir()):
            journal_path = tx_dir / "journal.json"
            if not journal_path.exists():
                self._cleanup_transaction_unlocked(tx_dir)
                abandoned += 1
                continue
            journal = self._load_journal(tx_dir, journal_path)
            self._recover_transaction_unlocked(tx_dir, journal)
            completed += 1
        return {"completed": completed, "abandoned": abandoned}

    def _load_journal(self, tx_dir: Path, path: Path) -> JsonObject:
        try:
            raw = json.loads(path.read_bytes())
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
            raise ForgeError(
                "RECOVERY_JOURNAL_MALFORMED", f"cannot read transaction journal: {exc}"
            ) from exc
        required = {
            "schema_version",
            "transaction_id",
            "state",
            "record_group",
            "ledger_kind",
            "record_identity",
            "record_destination",
            "record_sha256",
            "ledger_before_sha256",
            "ledger_after_sha256",
            "expected_sequence",
            "expected_previous_hash",
            "entry_hash",
        }
        if not isinstance(raw, dict) or set(raw) != required:
            raise ForgeError("RECOVERY_JOURNAL_MALFORMED", "transaction journal shape is invalid")
        journal = cast(JsonObject, raw)
        hash_fields = {
            "record_sha256",
            "ledger_before_sha256",
            "ledger_after_sha256",
            "expected_previous_hash",
            "entry_hash",
        }
        if (
            journal["schema_version"] != TRANSACTION_SCHEMA_VERSION
            or journal["transaction_id"] != tx_dir.name
            or journal["state"] not in {"PREPARED", "COMMITTED"}
            or not isinstance(journal["expected_sequence"], int)
            or isinstance(journal["expected_sequence"], bool)
            or journal["expected_sequence"] < 1
            or any(
                not isinstance(journal[key], str)
                for key in required - {"schema_version", "expected_sequence"}
            )
            or any(
                len(cast(str, journal[key])) != 64
                or any(character not in "0123456789abcdef" for character in cast(str, journal[key]))
                for key in hash_fields
            )
        ):
            raise ForgeError("RECOVERY_JOURNAL_MALFORMED", "transaction journal values are invalid")
        return journal

    def _recover_transaction_unlocked(self, tx_dir: Path, journal: JsonObject) -> None:
        group = cast(str, journal["record_group"])
        kind = cast(str, journal["ledger_kind"])
        identity = cast(str, journal["record_identity"])
        context = persisted_record_context(group=group, ledger_kind=kind)
        expected_destination = immutable_record_path(self.state_dir, group, identity)
        try:
            declared_destination = self.state_dir / cast(str, journal["record_destination"])
            declared_destination.resolve().relative_to(self.state_dir.resolve())
        except (OSError, ValueError) as exc:
            raise ForgeError(
                "RECOVERY_JOURNAL_MALFORMED", "record destination escapes state"
            ) from exc
        if declared_destination != expected_destination:
            raise ForgeError("RECOVERY_JOURNAL_MALFORMED", "record destination is not canonical")
        record_stage = tx_dir / "record.stage"
        ledger_stage = tx_dir / "ledger.stage"
        final_record = expected_destination
        ledger_bytes = self._ledger_bytes_unlocked()
        ledger_hash = _sha256(ledger_bytes)
        before = cast(str, journal["ledger_before_sha256"])
        after = cast(str, journal["ledger_after_sha256"])

        self._validate_recovery_file(
            final_record if final_record.exists() else record_stage,
            cast(str, journal["record_sha256"]),
            "record",
        )
        if ledger_hash == before:
            if journal["state"] == "COMMITTED":
                raise ForgeError("RECOVERY_AMBIGUOUS", "committed transaction has old ledger")
            self._validate_recovery_file(ledger_stage, after, "staged ledger")
            if not final_record.exists():
                _durable_mkdir(final_record.parent)
                os.replace(record_stage, final_record)
                _sync_directory(final_record.parent)
            self._assert_recovery_predecessor(journal)
            os.replace(ledger_stage, self.ledger.path)
            _sync_directory(self.state_dir)
            ledger_bytes = self._ledger_bytes_unlocked()
            ledger_hash = _sha256(ledger_bytes)
        if ledger_hash != after:
            raise ForgeError("RECOVERY_LEDGER_CONFLICT", "ledger matches neither transaction state")
        if not final_record.is_file():
            raise ForgeError("RECOVERY_AMBIGUOUS", "transaction ledger exists without its record")
        self._validate_recovery_file(final_record, cast(str, journal["record_sha256"]), "record")
        raw = self.ledger._read_unlocked_raw()
        self.ledger._verify_raw_records(raw)
        if len(raw) < cast(int, journal["expected_sequence"]):
            raise ForgeError("RECOVERY_AMBIGUOUS", "transaction ledger entry is absent")
        entry = normalize_ledger_entry(raw[cast(int, journal["expected_sequence"]) - 1])
        if entry.entry_hash != journal["entry_hash"] or entry.kind != kind:
            raise ForgeError(
                "RECOVERY_AMBIGUOUS", "transaction ledger entry does not match journal"
            )
        record = load_record_file(final_record, group=context.group)
        if record.to_json() != entry.payload.to_json():
            raise ForgeError("RECOVERY_AMBIGUOUS", "transaction record and ledger payload differ")
        journal["state"] = "COMMITTED"
        _atomic_write(tx_dir / "journal.json", self._journal_bytes(journal))
        self._rebuild_index_unlocked()
        self._cleanup_transaction_unlocked(tx_dir)

    def _assert_recovery_predecessor(self, journal: JsonObject) -> None:
        raw = self.ledger._read_unlocked_raw()
        head = self.ledger._verify_raw_records(raw)
        if (
            len(raw) + 1 != journal["expected_sequence"]
            or head != journal["expected_previous_hash"]
        ):
            raise ForgeError(
                "RECOVERY_LEDGER_CONFLICT", "prepared transaction predecessor has changed"
            )

    @staticmethod
    def _validate_recovery_file(path: Path, expected_hash: str, label: str) -> None:
        try:
            value = path.read_bytes()
        except OSError as exc:
            raise ForgeError("RECOVERY_AMBIGUOUS", f"{label} is missing or unreadable") from exc
        if _sha256(value) != expected_hash:
            raise ForgeError("RECOVERY_STAGE_MISMATCH", f"{label} content was substituted")

    def _cleanup_transaction_unlocked(self, tx_dir: Path) -> None:
        try:
            shutil.rmtree(tx_dir)
        except OSError as exc:
            raise ForgeError(
                "RECOVERY_CLEANUP", f"cannot remove transaction metadata: {exc}"
            ) from exc
        _sync_directory(self.transactions_dir)

    def _index_data_unlocked(self, raw: list[JsonObject]) -> JsonObject:
        ledger_bytes = self._ledger_bytes_unlocked()
        by_kind: dict[str, list[int]] = {}
        identities: dict[str, int] = {}
        for item in raw:
            entry = normalize_ledger_entry(item)
            by_kind.setdefault(entry.kind, []).append(entry.sequence)
            context = persisted_record_context(
                group=PERSISTED_RECORD_CONTEXTS[entry.kind].group, ledger_kind=entry.kind
            )
            identity = entry.payload.get(context.identity_field)
            if isinstance(identity, str):
                identities[f"{entry.kind}:{identity}"] = entry.sequence
        head = raw[-1]["entry_hash"] if raw else GENESIS
        return {
            "schema_version": INDEX_SCHEMA_VERSION,
            "ledger_sha256": _sha256(ledger_bytes),
            "ledger_size": len(ledger_bytes),
            "ledger_head": head,
            "entry_count": len(raw),
            "sequences_by_kind": cast(JsonObject, by_kind),
            "identity_sequences": cast(JsonObject, identities),
        }

    def _ensure_index_unlocked(self, raw: list[JsonObject]) -> None:
        expected = self._index_data_unlocked(raw)
        try:
            current = json.loads(self.index_path.read_bytes())
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, RecursionError):
            current = None
        if current != expected:
            _atomic_write(self.index_path, canonical_bytes(expected) + b"\n")

    def _rebuild_index_unlocked(self) -> None:
        raw = self.ledger._read_unlocked_raw()
        self.ledger._verify_raw_records(raw)
        self._ensure_index_unlocked(raw)

    @contextmanager
    def action_execution(self, action_id: str, *, timeout: float = 30) -> Iterator[None]:
        """Hold an OS lock while a durable verifier action may still be executing."""

        path = self.action_locks_dir / f"{safe_record_identity(action_id)}.lock"
        lock = FileLock(str(path), timeout=timeout)
        _durable_mkdir(self.action_locks_dir)
        try:
            with lock:
                yield
        except Timeout as exc:
            raise ForgeError(
                "ACTION_EXECUTION_BUSY", "verifier action is already executing"
            ) from exc
