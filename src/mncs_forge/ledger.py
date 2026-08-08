"""Hash-linked, append-only Forge ledger."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from filelock import FileLock

from .errors import ForgeError
from .records import (
    CURRENT_SCHEMA_VERSION,
    LEDGER_KIND_TYPES,
    ForgeRecord,
    JsonObject,
    LedgerEntry,
    RecordType,
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
        self.lock = FileLock(str(state_dir / "ledger.lock"), timeout=30)

    def _read_unlocked_raw(self) -> list[JsonObject]:
        if not self.path.exists():
            return []
        records: list[JsonObject] = []
        try:
            with self.path.open("rb") as stream:
                for line_number, line in enumerate(stream, start=1):
                    if not line.endswith(b"\n"):
                        raise ForgeError(
                            "LEDGER_TRUNCATED", f"ledger line {line_number} is incomplete"
                        )
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
        return records

    @staticmethod
    def _entry_hash(entry_without_hash: JsonObject) -> str:
        return hashlib.sha256(canonical_bytes(entry_without_hash)).hexdigest()

    def verify(self) -> dict[str, object]:
        with self.lock:
            records = self._read_unlocked_raw()
            previous = self._verify_raw_records(records)
            return {
                "ok": True,
                "entries": len(records),
                "head": previous,
                "algorithm": "Forge local hash-linked JSONL SHA-256 v1",
            }

    def append(self, kind: str, payload: ForgeRecord) -> LedgerEntry:
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
            flags = os.O_APPEND | os.O_CREAT | os.O_WRONLY
            descriptor = os.open(self.path, flags, 0o600)
            try:
                os.write(descriptor, canonical_bytes(entry) + b"\n")
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            return normalize_ledger_entry(entry)

    def _verify_raw_records(self, records: list[JsonObject]) -> str:
        """Verify the historical/raw representation before any payload migration."""

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
        return previous

    def records(self, kind: str | None = None) -> list[LedgerEntry]:
        with self.lock:
            raw_records = self._read_unlocked_raw()
            self._verify_raw_records(raw_records)
            selected = (
                raw_records
                if kind is None
                else [entry for entry in raw_records if entry.get("kind") == kind]
            )
            return [normalize_ledger_entry(entry) for entry in selected]
