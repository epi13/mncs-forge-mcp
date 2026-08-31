from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from mncs_forge.errors import ForgeError
from mncs_forge.ledger import Ledger
from mncs_forge.records import ForgeRecord, RecordType, new_record, normalize_ledger_entry
from mncs_forge.serialization import canonical_bytes


def candidate(value: int) -> ForgeRecord:
    return new_record(
        RecordType.CANDIDATE,
        {
            "candidate_id": f"forge-tree-sha256-v1:{value:064x}",
            "parent_candidate": None,
            "changed_files": [],
            "declared_hypothesis": f"candidate {value}",
            "generator_identity": "generator",
            "generator_configuration_identity": "configuration",
            "source_epoch": "epoch:fixture",
            "registered_at": "2026-01-01T00:00:00+00:00",
            "current_file_identities": {},
            "useful_benefit_objective": "contract.md",
            "objective_identity": "sha256:fixture",
            "supersedes": None,
        },
    )


def test_append_and_verify(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path)
    first = ledger.append("candidate", candidate(1))
    second = ledger.append("candidate", candidate(2))
    assert first["sequence"] == 1
    assert second["previous_hash"] == first["entry_hash"]
    assert ledger.verify_chain()["entries"] == 2


def test_current_ledger_entry_round_trip_and_hash_projection_are_stable(
    tmp_path: Path,
) -> None:
    ledger = Ledger(tmp_path)
    entry = ledger.append("candidate", candidate(1))
    serialized = entry.to_json()
    body = {key: value for key, value in serialized.items() if key != "entry_hash"}

    assert serialized["record_type"] == "ledger_entry"
    assert serialized["schema_version"] == "1"
    assert entry.entry_hash == Ledger._entry_hash(body)
    assert canonical_bytes(normalize_ledger_entry(serialized).to_json()) == canonical_bytes(
        serialized
    )


def test_current_ledger_entry_round_trip_and_hash_projection_are_stable(
    tmp_path: Path,
) -> None:
    ledger = Ledger(tmp_path)
    entry = ledger.append("candidate", candidate(1))
    serialized = entry.to_json()
    body = {key: value for key, value in serialized.items() if key != "entry_hash"}

    assert serialized["record_type"] == "ledger_entry"
    assert serialized["schema_version"] == "1"
    assert entry.entry_hash == Ledger._entry_hash(body)
    assert canonical_bytes(normalize_ledger_entry(serialized).to_json()) == canonical_bytes(
        serialized
    )


def test_tamper_detected(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path)
    ledger.append("candidate", candidate(1))
    path = tmp_path / "ledger.jsonl"
    value = json.loads(path.read_text(encoding="utf-8"))
    value["payload"]["candidate_id"] = "rewritten"
    path.write_text(json.dumps(value) + "\n", encoding="utf-8")
    with pytest.raises(ForgeError, match="hash"):
        ledger.verify()


def test_concurrent_append_is_serialized(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path)
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda value: ledger.append("candidate", candidate(value)), range(40)))
    assert ledger.verify_chain()["entries"] == 40
