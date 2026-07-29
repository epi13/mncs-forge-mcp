from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from mncs_forge.errors import ForgeError
from mncs_forge.ledger import Ledger


def test_append_and_verify(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path)
    first = ledger.append("action", {"name": "one"})
    second = ledger.append("action", {"name": "two"})
    assert first["sequence"] == 1
    assert second["previous_hash"] == first["entry_hash"]
    assert ledger.verify()["entries"] == 2


def test_tamper_detected(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path)
    ledger.append("action", {"name": "one"})
    path = tmp_path / "ledger.jsonl"
    value = json.loads(path.read_text(encoding="utf-8"))
    value["payload"]["name"] = "rewritten"
    path.write_text(json.dumps(value) + "\n", encoding="utf-8")
    with pytest.raises(ForgeError, match="hash"):
        ledger.verify()


def test_concurrent_append_is_serialized(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path)
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda value: ledger.append("action", {"value": value}), range(40)))
    assert ledger.verify()["entries"] == 40
