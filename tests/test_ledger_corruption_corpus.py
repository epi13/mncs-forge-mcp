from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest

from mncs_forge.errors import ForgeError
from mncs_forge.ledger import Ledger
from mncs_forge.records import RecordType, new_record
from mncs_forge.serialization import canonical_bytes


def _candidate(value: int):  # type: ignore[no-untyped-def]
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


def _raw_entries(tmp_path: Path) -> list[dict[str, object]]:
    ledger = Ledger(tmp_path)
    ledger.append("candidate", _candidate(1))
    ledger.append("candidate", _candidate(2))
    return [json.loads(line) for line in (tmp_path / "ledger.jsonl").read_text().splitlines()]


def _write_entries(tmp_path: Path, entries: list[dict[str, object]]) -> None:
    (tmp_path / "ledger.jsonl").write_bytes(
        b"".join(canonical_bytes(entry) + b"\n" for entry in entries)
    )


def _recompute(entry: dict[str, object]) -> None:
    body = {key: value for key, value in entry.items() if key != "entry_hash"}
    entry["entry_hash"] = Ledger._entry_hash(body)


def _drop_first(entries: list[dict[str, object]]) -> None:
    del entries[0]


def _reverse(entries: list[dict[str, object]]) -> None:
    entries.reverse()


def _duplicate_first(entries: list[dict[str, object]]) -> None:
    entries.insert(1, dict(entries[0]))


def _break_previous_hash(entries: list[dict[str, object]]) -> None:
    entries[1]["previous_hash"] = "f" * 64
    _recompute(entries[1])


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        (lambda entries: entries.append({"sequence": 3}), "LEDGER_TRUNCATED"),
        (_drop_first, "LEDGER_SEQUENCE"),
        (_reverse, "LEDGER_SEQUENCE"),
        (_duplicate_first, "LEDGER_SEQUENCE"),
        (_break_previous_hash, "LEDGER_LINK"),
    ],
    ids=["truncated-line", "missing-first-entry", "reordered", "duplicate-sequence", "wrong-link"],
)
def test_ledger_corruption_corpus_fails_closed(
    tmp_path: Path, mutation: Callable[[list[dict[str, object]]], None], expected_code: str
) -> None:
    entries = _raw_entries(tmp_path)
    if expected_code == "LEDGER_TRUNCATED":
        path = tmp_path / "ledger.jsonl"
        path.write_bytes(path.read_bytes() + b'{"sequence":')
    else:
        mutation(entries)
        _write_entries(tmp_path, entries)

    with pytest.raises(ForgeError) as issue:
        Ledger(tmp_path).verify_chain()
    assert issue.value.code == expected_code
