from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures.process import ProcessPoolExecutor
from multiprocessing import get_context
from pathlib import Path

import pytest

from mncs_forge.errors import ForgeError
from mncs_forge.ledger import Ledger
from mncs_forge.record_store import LocalRecordStore
from mncs_forge.records import (
    LEDGER_KIND_TYPES,
    PERSISTED_RECORD_CONTEXTS,
    RECORD_GROUP_TYPES,
    ForgeRecord,
    RecordType,
    immutable_record_path,
    new_record,
)
from mncs_forge.serialization import canonical_bytes


def candidate(value: int, *, hypothesis: str | None = None) -> ForgeRecord:
    return new_record(
        RecordType.CANDIDATE,
        {
            "candidate_id": f"forge-tree-sha256-v1:{value:064x}",
            "parent_candidate": None,
            "changed_files": [],
            "declared_hypothesis": hypothesis or f"candidate {value}",
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


def test_persisted_context_map_covers_exact_ledger_and_record_vocabularies() -> None:
    assert set(PERSISTED_RECORD_CONTEXTS) == set(LEDGER_KIND_TYPES)
    assert {context.group for context in PERSISTED_RECORD_CONTEXTS.values()} == set(
        RECORD_GROUP_TYPES
    )
    for kind, context in PERSISTED_RECORD_CONTEXTS.items():
        assert context.ledger_kind == kind
        assert context.record_type is LEDGER_KIND_TYPES[kind]
        assert context.record_type is RECORD_GROUP_TYPES[context.group]


def test_normal_commit_publishes_one_record_and_one_ledger_entry(tmp_path: Path) -> None:
    store = LocalRecordStore(tmp_path)
    record = candidate(1)

    entry = store.commit("candidates", "candidate", record)

    assert entry.sequence == 1
    assert immutable_record_path(tmp_path, "candidates", str(record["candidate_id"])).is_file()
    assert Ledger(tmp_path).verify() == {
        "ok": True,
        "entries": 1,
        "head": entry.entry_hash,
        "algorithm": "Forge local hash-linked JSONL SHA-256 v1",
    }


def test_identical_duplicate_is_idempotent_and_conflicting_duplicate_fails(
    tmp_path: Path,
) -> None:
    store = LocalRecordStore(tmp_path)
    original = candidate(1)
    first = store.commit("candidates", "candidate", original)

    assert store.commit("candidates", "candidate", original).entry_hash == first.entry_hash
    with pytest.raises(ForgeError) as issue:
        store.commit("candidates", "candidate", candidate(1, hypothesis="different"))
    assert issue.value.code == "RECORD_EXISTS"
    assert Ledger(tmp_path).verify()["entries"] == 1


def test_concurrent_writers_serialize_sequence_and_links(tmp_path: Path) -> None:
    stores = [LocalRecordStore(tmp_path) for _ in range(8)]

    with ThreadPoolExecutor(max_workers=8) as pool:
        entries = list(
            pool.map(
                lambda item: stores[item % len(stores)].commit(
                    "candidates", "candidate", candidate(item)
                ),
                range(40),
            )
        )

    assert sorted(entry.sequence for entry in entries) == list(range(1, 41))
    records = Ledger(tmp_path).records()
    assert len({entry.sequence for entry in records}) == 40
    assert Ledger(tmp_path).verify()["entries"] == 40


def test_concurrent_same_identity_is_deterministic(tmp_path: Path) -> None:
    stores = [LocalRecordStore(tmp_path) for _ in range(4)]
    record = candidate(1)
    with ThreadPoolExecutor(max_workers=4) as pool:
        entries = list(
            pool.map(lambda store: store.commit("candidates", "candidate", record), stores)
        )
    assert len({entry.entry_hash for entry in entries}) == 1
    assert Ledger(tmp_path).verify()["entries"] == 1


def test_missing_replaced_and_mismatched_immutable_records_are_detected(
    tmp_path: Path,
) -> None:
    store = LocalRecordStore(tmp_path)
    record = candidate(1)
    store.commit("candidates", "candidate", record)
    path = immutable_record_path(tmp_path, "candidates", str(record["candidate_id"]))
    original = path.read_bytes()

    path.unlink()
    with pytest.raises(ForgeError) as missing:
        Ledger(tmp_path).verify()
    assert missing.value.code == "RECORD_FILE_MISSING"

    path.write_bytes(b"{}\n")
    with pytest.raises(ForgeError) as malformed:
        Ledger(tmp_path).verify()
    assert malformed.value.code == "RECORD_FILE_MALFORMED"

    path.write_bytes(original)
    value = json.loads(original)
    value["declared_hypothesis"] = "replacement"
    path.write_text(json.dumps(value) + "\n", encoding="utf-8")
    with pytest.raises(ForgeError) as mismatch:
        Ledger(tmp_path).verify()
    assert mismatch.value.code == "RECORD_FILE_MISMATCH"


def test_rehashed_ledger_payload_that_differs_from_record_is_detected(tmp_path: Path) -> None:
    record = candidate(1)
    LocalRecordStore(tmp_path).commit("candidates", "candidate", record)
    raw = json.loads((tmp_path / "ledger.jsonl").read_bytes())
    raw["payload"]["declared_hypothesis"] = "ledger replacement"
    body = {key: value for key, value in raw.items() if key != "entry_hash"}
    raw["entry_hash"] = Ledger._entry_hash(body)
    (tmp_path / "ledger.jsonl").write_bytes(canonical_bytes(raw) + b"\n")

    assert Ledger(tmp_path).verify_chain()["ok"] is True
    with pytest.raises(ForgeError) as issue:
        Ledger(tmp_path).verify()
    assert issue.value.code == "RECORD_FILE_MISMATCH"


def test_store_rejects_mismatched_typed_storage_context(tmp_path: Path) -> None:
    store = LocalRecordStore(tmp_path)
    with pytest.raises(ForgeError) as group_issue:
        store.commit("epochs", "candidate", candidate(1))
    assert group_issue.value.code == "RECORD_CONTEXT"
    with pytest.raises(ForgeError) as type_issue:
        store.commit("epochs", "epoch", candidate(1))
    assert type_issue.value.code == "RECORD_TYPE_MISMATCH"


def _crash_worker(state_dir: str) -> None:
    def crash(name: str) -> None:
        if name == "after_prepared":
            os._exit(77)

    LocalRecordStore(Path(state_dir), failpoint=crash).commit(
        "candidates", "candidate", candidate(9)
    )


def _process_commit(args: tuple[str, int]) -> int:
    state_dir, value = args
    entry = LocalRecordStore(Path(state_dir)).commit("candidates", "candidate", candidate(value))
    return entry.sequence


def test_multiple_processes_serialize_the_next_sequence(tmp_path: Path) -> None:
    values = [(str(tmp_path), value) for value in range(12)]
    with ProcessPoolExecutor(max_workers=4, mp_context=get_context("spawn")) as pool:
        sequences = list(pool.map(_process_commit, values))
    assert sorted(sequences) == list(range(1, 13))
    assert Ledger(tmp_path).verify()["entries"] == 12


def test_real_process_exit_after_prepared_recovers(tmp_path: Path) -> None:
    process = get_context("spawn").Process(target=_crash_worker, args=(str(tmp_path),))
    process.start()
    process.join(20)
    assert process.exitcode == 77

    store = LocalRecordStore(tmp_path)
    assert Ledger(tmp_path).verify()["entries"] == 1
    assert store.recover() == {"completed": 0, "abandoned": 0}
