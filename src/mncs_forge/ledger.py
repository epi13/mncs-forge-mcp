"""Hash-linked, append-only Forge ledger."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from filelock import FileLock

from .errors import ForgeError
from .serialization import canonical_bytes

GENESIS = "0" * 64


class Ledger:
    def __init__(self, state_dir: Path) -> None:
        self.state_dir = state_dir
        self.path = state_dir / "ledger.jsonl"
        self.lock = FileLock(str(state_dir / "ledger.lock"), timeout=30)

    def _read_unlocked(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        records: list[dict[str, Any]] = []
        try:
            with self.path.open("r", encoding="utf-8") as stream:
                for line_number, line in enumerate(stream, start=1):
                    if not line.endswith("\n"):
                        raise ForgeError(
                            "LEDGER_TRUNCATED", f"ledger line {line_number} is incomplete"
                        )
                    value = json.loads(line)
                    if not isinstance(value, dict):
                        raise ForgeError(
                            "LEDGER_MALFORMED", f"ledger line {line_number} is not an object"
                        )
                    records.append(value)
        except (OSError, json.JSONDecodeError) as exc:
            raise ForgeError("LEDGER_MALFORMED", f"cannot read ledger: {exc}") from exc
        return records

    @staticmethod
    def _entry_hash(entry_without_hash: dict[str, Any]) -> str:
        return hashlib.sha256(canonical_bytes(entry_without_hash)).hexdigest()

    def verify(self) -> dict[str, object]:
        with self.lock:
            records = self._read_unlocked()
            previous = GENESIS
            for index, entry in enumerate(records, start=1):
                actual_hash = entry.get("entry_hash")
                body = {key: value for key, value in entry.items() if key != "entry_hash"}
                if entry.get("sequence") != index:
                    raise ForgeError("LEDGER_SEQUENCE", f"invalid sequence at ledger entry {index}")
                if entry.get("previous_hash") != previous:
                    raise ForgeError("LEDGER_LINK", f"broken hash link at ledger entry {index}")
                expected_hash = self._entry_hash(body)
                if actual_hash != expected_hash:
                    raise ForgeError("LEDGER_TAMPER", f"hash mismatch at ledger entry {index}")
                previous = expected_hash
            return {
                "ok": True,
                "entries": len(records),
                "head": previous,
                "algorithm": "Forge local hash-linked JSONL SHA-256 v1",
            }

    def append(self, kind: str, payload: dict[str, object]) -> dict[str, Any]:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        with self.lock:
            records = self._read_unlocked()
            if records:
                self._verify_records(records)
            previous = records[-1]["entry_hash"] if records else GENESIS
            body: dict[str, Any] = {
                "sequence": len(records) + 1,
                "timestamp": datetime.now(UTC).isoformat(),
                "kind": kind,
                "previous_hash": previous,
                "payload": payload,
            }
            entry = {**body, "entry_hash": self._entry_hash(body)}
            flags = os.O_APPEND | os.O_CREAT | os.O_WRONLY
            descriptor = os.open(self.path, flags, 0o600)
            try:
                os.write(descriptor, canonical_bytes(entry) + b"\n")
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            return entry

    def _verify_records(self, records: list[dict[str, Any]]) -> None:
        previous = GENESIS
        for index, entry in enumerate(records, start=1):
            body = {key: value for key, value in entry.items() if key != "entry_hash"}
            expected = self._entry_hash(body)
            if (
                entry.get("sequence") != index
                or entry.get("previous_hash") != previous
                or entry.get("entry_hash") != expected
            ):
                raise ForgeError("LEDGER_TAMPER", f"ledger verification failed at entry {index}")
            previous = expected

    def records(self, kind: str | None = None) -> list[dict[str, Any]]:
        with self.lock:
            records = self._read_unlocked()
            self._verify_records(records)
            if kind is None:
                return records
            return [entry for entry in records if entry.get("kind") == kind]
