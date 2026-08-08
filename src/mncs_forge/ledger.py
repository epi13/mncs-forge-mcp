"""Hash-linked, append-only Forge ledger."""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Collection
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from filelock import FileLock

from .errors import ForgeError
from .records import (
    CURRENT_SCHEMA_VERSION,
    LEDGER_KIND_TYPES,
    PERSISTED_RECORD_CONTEXTS,
    ForgeRecord,
    JsonObject,
    LedgerEntry,
    RecordType,
    immutable_record_path,
    load_record_file,
    normalize_ledger_entry,
)
from .serialization import canonical_bytes

GENESIS = "0" * 64
LEDGER_LINE_BYTE_CAP = 16_000_000


def _reject_nonstandard_number(value: str) -> None:
    raise ForgeError("LEDGER_MALFORMED", f"ledger contains non-standard number: {value}")


class Ledger:
    def __init__(self, state_dir: Path) -> None:
        self.state_dir = state_dir
        self.path = state_dir / "ledger.jsonl"
        self.index_path = state_dir / "ledger-index.json"
        self.lock = FileLock(str(state_dir / "ledger.lock"), timeout=30)
        self._cached_digest: str | None = None
        self._cached_raw: list[JsonObject] | None = None
        self._verified_digest: str | None = None
        self._verified_head: str | None = None

    def _read_unlocked_raw(self) -> list[JsonObject]:
        if not self.path.exists():
            self._cached_digest = hashlib.sha256(b"").hexdigest()
            self._cached_raw = []
            return self._cached_raw
        records: list[JsonObject] = []
        try:
            ledger_bytes = self.path.read_bytes()
            digest = hashlib.sha256(ledger_bytes).hexdigest()
            if digest == self._cached_digest and self._cached_raw is not None:
                return self._cached_raw
            for line_number, line in enumerate(ledger_bytes.splitlines(keepends=True), start=1):
                if not line.endswith(b"\n"):
                    raise ForgeError("LEDGER_TRUNCATED", f"ledger line {line_number} is incomplete")
                if len(line) > LEDGER_LINE_BYTE_CAP:
                    raise ForgeError(
                        "LEDGER_MALFORMED",
                        f"ledger line {line_number} exceeds the byte limit",
                    )
                value = json.loads(line, parse_constant=_reject_nonstandard_number)
                if not isinstance(value, dict):
                    raise ForgeError(
                        "LEDGER_MALFORMED", f"ledger line {line_number} is not an object"
                    )
                records.append(cast(JsonObject, value))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
            raise ForgeError("LEDGER_MALFORMED", f"cannot read ledger: {exc}") from exc
        self._cached_digest = digest
        self._cached_raw = records
        return records

    @staticmethod
    def _entry_hash(entry_without_hash: JsonObject) -> str:
        return hashlib.sha256(canonical_bytes(entry_without_hash)).hexdigest()

    def _require_recovered_unlocked(self) -> None:
        transactions = self.state_dir / "transactions"
        try:
            unresolved = transactions.is_dir() and any(
                path.is_dir() for path in transactions.iterdir()
            )
        except OSError as exc:
            raise ForgeError(
                "RECOVERY_REQUIRED", f"cannot inspect transaction state: {exc}"
            ) from exc
        if unresolved:
            raise ForgeError(
                "RECOVERY_REQUIRED",
                "unfinished storage transactions must be recovered before ledger reads",
            )

    def verify_chain(self) -> dict[str, object]:
        with self.lock:
            self._require_recovered_unlocked()
            records = self._read_unlocked_raw()
            previous = self._verify_raw_records(records)
            return {
                "ok": True,
                "entries": len(records),
                "head": previous,
                "algorithm": "Forge local hash-linked JSONL SHA-256 v1",
            }

    def verify(self) -> dict[str, object]:
        """Verify the raw chain and every ledger-backed immutable companion."""

        with self.lock:
            self._require_recovered_unlocked()
            records = self._read_unlocked_raw()
            previous = self._verify_raw_records(records)
            normalized = [normalize_ledger_entry(entry) for entry in records]
            self._verify_immutable_records_unlocked(normalized)
            return {
                "ok": True,
                "entries": len(records),
                "head": previous,
                "algorithm": "Forge local hash-linked JSONL SHA-256 v1",
            }

    def _verify_immutable_records_unlocked(self, records: list[LedgerEntry]) -> None:
        for entry in records:
            context = PERSISTED_RECORD_CONTEXTS[entry.kind]
            identity = entry.payload.get(context.identity_field)
            if not isinstance(identity, str) or not identity:
                raise ForgeError(
                    "RECORD_IDENTITY",
                    f"ledger entry {entry.sequence} has no valid {context.identity_field}",
                )
            path = immutable_record_path(self.state_dir, context.group, identity)
            if not path.is_file():
                raise ForgeError(
                    "RECORD_FILE_MISSING",
                    f"immutable record is missing for ledger entry {entry.sequence}",
                )
            try:
                record = load_record_file(path, group=context.group)
            except ForgeError as exc:
                raise ForgeError(
                    "RECORD_FILE_MALFORMED",
                    f"immutable record for ledger entry {entry.sequence} is invalid: {exc.message}",
                ) from exc
            if record.to_json() != entry.payload.to_json():
                raise ForgeError(
                    "RECORD_FILE_MISMATCH",
                    f"immutable record differs from ledger entry {entry.sequence}",
                )
            if entry.source_schema_version == CURRENT_SCHEMA_VERSION:
                try:
                    persisted_bytes = path.read_bytes()
                except OSError as exc:
                    raise ForgeError(
                        "RECORD_FILE_MALFORMED",
                        f"cannot read immutable record for ledger entry {entry.sequence}",
                    ) from exc
                if persisted_bytes != canonical_bytes(entry.payload.to_json()) + b"\n":
                    raise ForgeError(
                        "RECORD_FILE_MISMATCH",
                        f"immutable record serialization differs at ledger entry {entry.sequence}",
                    )

    def append(self, kind: str, payload: ForgeRecord) -> LedgerEntry:
        """Low-level ledger-only append retained for compatibility and recovery tests.

        Application code must use RecordStore.commit so the immutable companion is
        published in the same recoverable transaction.
        """
        try:
            expected_type = LEDGER_KIND_TYPES[kind]
        except KeyError as exc:
            raise ForgeError("RECORD_CONTEXT", f"unsupported ledger kind: {kind}") from exc
        if payload.record_type is not expected_type:
            raise ForgeError(
                "RECORD_TYPE_MISMATCH",
                f"ledger kind {kind} requires {expected_type.value}, "
                f"got {payload.record_type.value}",
            )
        if payload.schema_version != CURRENT_SCHEMA_VERSION:
            raise ForgeError("RECORD_VERSION_WRITE", "new ledger payloads require schema version 1")
        self.state_dir.mkdir(parents=True, exist_ok=True)
        with self.lock:
            records = self._read_unlocked_raw()
            if records:
                self._verify_raw_records(records)
            previous = records[-1]["entry_hash"] if records else GENESIS
            body: JsonObject = {
                "record_type": RecordType.LEDGER_ENTRY.value,
                "schema_version": CURRENT_SCHEMA_VERSION,
                "sequence": len(records) + 1,
                "timestamp": datetime.now(UTC).isoformat(),
                "kind": kind,
                "previous_hash": previous,
                "payload": payload.to_json(),
            }
            entry = {**body, "entry_hash": self._entry_hash(body)}
            flags = os.O_APPEND | os.O_CREAT | os.O_WRONLY | getattr(os, "O_BINARY", 0)
            descriptor = os.open(self.path, flags, 0o600)
            try:
                os.write(descriptor, canonical_bytes(entry) + b"\n")
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            return normalize_ledger_entry(entry)

    def _build_entry_unlocked(
        self,
        *,
        kind: str,
        payload: ForgeRecord,
        records: list[JsonObject],
        timestamp: str | None = None,
    ) -> tuple[JsonObject, LedgerEntry]:
        try:
            expected_type = LEDGER_KIND_TYPES[kind]
        except KeyError as exc:
            raise ForgeError("RECORD_CONTEXT", f"unsupported ledger kind: {kind}") from exc
        if payload.record_type is not expected_type:
            raise ForgeError(
                "RECORD_TYPE_MISMATCH",
                f"ledger kind {kind} requires {expected_type.value}, "
                f"got {payload.record_type.value}",
            )
        if payload.schema_version != CURRENT_SCHEMA_VERSION:
            raise ForgeError("RECORD_VERSION_WRITE", "new ledger payloads require schema version 1")
        previous = records[-1]["entry_hash"] if records else GENESIS
        body: JsonObject = {
            "record_type": RecordType.LEDGER_ENTRY.value,
            "schema_version": CURRENT_SCHEMA_VERSION,
            "sequence": len(records) + 1,
            "timestamp": timestamp or datetime.now(UTC).isoformat(),
            "kind": kind,
            "previous_hash": previous,
            "payload": payload.to_json(),
        }
        raw = {**body, "entry_hash": self._entry_hash(body)}
        return raw, normalize_ledger_entry(raw)

    def _verify_raw_records(self, records: list[JsonObject]) -> str:
        """Verify the historical/raw representation before any payload migration."""

        if (
            records is self._cached_raw
            and self._cached_digest == self._verified_digest
            and self._verified_head is not None
        ):
            return self._verified_head

        previous = GENESIS
        for index, entry in enumerate(records, start=1):
            body = {key: value for key, value in entry.items() if key != "entry_hash"}
            expected = self._entry_hash(body)
            if entry.get("sequence") != index:
                raise ForgeError("LEDGER_SEQUENCE", f"invalid sequence at ledger entry {index}")
            if entry.get("previous_hash") != previous:
                raise ForgeError("LEDGER_LINK", f"broken hash link at ledger entry {index}")
            if entry.get("entry_hash") != expected:
                raise ForgeError("LEDGER_TAMPER", f"hash mismatch at ledger entry {index}")
            previous = expected
        if records is self._cached_raw:
            self._verified_digest = self._cached_digest
            self._verified_head = previous
        return previous

    def records(self, kind: str | None = None) -> list[LedgerEntry]:
        with self.lock:
            self._require_recovered_unlocked()
            raw_records = self._read_unlocked_raw()
            self._verify_raw_records(raw_records)
            selected = (
                raw_records
                if kind is None
                else self._select_with_index_unlocked(raw_records, frozenset({kind}))
            )
            return [normalize_ledger_entry(entry) for entry in selected]

    def records_for(self, kinds: Collection[str]) -> list[LedgerEntry]:
        """Read one verified snapshot and normalize only the requested record kinds."""

        selected_kinds = frozenset(kinds)
        with self.lock:
            self._require_recovered_unlocked()
            raw_records = self._read_unlocked_raw()
            self._verify_raw_records(raw_records)
            return [
                normalize_ledger_entry(entry)
                for entry in self._select_with_index_unlocked(raw_records, selected_kinds)
            ]

    def _select_with_index_unlocked(
        self, raw_records: list[JsonObject], kinds: frozenset[str]
    ) -> list[JsonObject]:
        """Use a validated derived sequence map, falling back to authoritative history."""

        try:
            value = json.loads(self.index_path.read_bytes())
            if not isinstance(value, dict):
                raise ValueError("index is not an object")
            sequences_by_kind = value.get("sequences_by_kind")
            expected_head = raw_records[-1]["entry_hash"] if raw_records else GENESIS
            if (
                value.get("schema_version") != 1
                or value.get("ledger_sha256") != self._cached_digest
                or value.get("ledger_head") != expected_head
                or value.get("entry_count") != len(raw_records)
                or not isinstance(sequences_by_kind, dict)
            ):
                raise ValueError("index does not bind current authoritative history")
            selected_sequences: set[int] = set()
            for kind in kinds:
                sequences = sequences_by_kind.get(kind, [])
                if not isinstance(sequences, list):
                    raise ValueError("index sequence list is malformed")
                for sequence in sequences:
                    if (
                        not isinstance(sequence, int)
                        or isinstance(sequence, bool)
                        or sequence < 1
                        or sequence > len(raw_records)
                        or raw_records[sequence - 1].get("kind") != kind
                    ):
                        raise ValueError("index sequence does not match authoritative history")
                    selected_sequences.add(sequence)
            return [raw_records[sequence - 1] for sequence in sorted(selected_sequences)]
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, RecursionError, ValueError):
            return [entry for entry in raw_records if entry.get("kind") in kinds]
