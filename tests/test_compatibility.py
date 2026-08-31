from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import cast

import pytest

from mncs_forge.errors import ForgeError
from mncs_forge.ledger import Ledger
from mncs_forge.records import (
    LEGACY_SCHEMA_VERSION,
    MIGRATIONS,
    RECORD_GROUP_TYPES,
    RecordType,
    load_record_file,
    new_record,
    parse_record,
)
from mncs_forge.serialization import canonical_bytes, local_json_identity

LEGACY = Path("tests/fixtures/legacy-0.1")
STATE = LEGACY / "complete-state"


def _legacy_lines() -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for line in (STATE / "ledger.jsonl").read_text(encoding="utf-8").splitlines():
        value = json.loads(line)
        assert isinstance(value, dict)
        result.append(cast(dict[str, object], value))
    return result


def _candidate_fields(candidate_id: str) -> dict[str, object]:
    return {
        "candidate_id": candidate_id,
        "parent_candidate": None,
        "changed_files": [],
        "declared_hypothesis": "compatibility",
        "generator_identity": "generator",
        "generator_configuration_identity": "configuration",
        "source_epoch": "epoch:fixture",
        "registered_at": "2026-01-01T00:00:00+00:00",
        "current_file_identities": {},
        "useful_benefit_objective": "contract.md",
        "objective_identity": "sha256:fixture",
        "supersedes": None,
    }


def test_legacy_fixture_sha256_contract_is_unchanged() -> None:
    for line in (LEGACY / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        expected, relative = line.split("  ", 1)
        assert hashlib.sha256((LEGACY / relative).read_bytes()).hexdigest() == expected


def test_0_1_0b1_semantic_compatibility_snapshot_is_current() -> None:
    subprocess.run(
        [sys.executable, "scripts/generate-compatibility-snapshot.py", "--check"],
        check=True,
    )


def test_cli_variadic_positional_requiredness_is_semantic() -> None:
    snapshot_path = Path("tests/compatibility/0.1.0b1.json")
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    command = snapshot["cli"]["commands"]["providers blockers"]
    assert command["arguments"][0]["nargs"] == "*"
    assert command["arguments"][0]["required"] is False


def test_legacy_ledger_raw_integrity_is_verified_before_migration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_verified = False
    original_verify = Ledger._verify_raw_records
    original_normalize = MIGRATIONS.normalize

    def observe_raw_verify(self: Ledger, records: list[dict[str, object]]) -> str:
        nonlocal raw_verified
        result = original_verify(self, records)  # type: ignore[arg-type]
        raw_verified = True
        return result

    def migration_after_raw(*args: object, **kwargs: object) -> object:
        assert raw_verified, "migration ran before raw ledger verification"
        return original_normalize(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Ledger, "_verify_raw_records", observe_raw_verify)
    monkeypatch.setattr(MIGRATIONS, "normalize", migration_after_raw)
    assert Ledger(STATE).verify() == {
        "ok": True,
        "entries": 14,
        "head": "5191095c54cf0ec7aaad5ac766901512d37fdcca9e617b1303043f1140600b5a",
        "algorithm": "Forge local hash-linked JSONL SHA-256 v1",
    }


def test_complete_legacy_state_loads_deterministically_without_rewrite() -> None:
    ledger_path = STATE / "ledger.jsonl"
    before = ledger_path.read_bytes()
    first = Ledger(STATE).records()
    second = Ledger(STATE).records()
    assert ledger_path.read_bytes() == before
    assert [canonical_bytes(entry.to_json()) for entry in first] == [
        canonical_bytes(entry.to_json()) for entry in second
    ]
    assert all(entry.source_schema_version == LEGACY_SCHEMA_VERSION for entry in first)
    assert all(entry.payload.source_schema_version == LEGACY_SCHEMA_VERSION for entry in first)
    for entry in first:
        reparsed = parse_record(entry.payload.to_json(), expected_type=entry.payload.record_type)
        assert canonical_bytes(reparsed.to_json()) == canonical_bytes(entry.payload.to_json())


def test_every_legacy_immutable_record_loads_from_trusted_group_context() -> None:
    loaded = 0
    for path in sorted((STATE / "records").glob("*/*.json")):
        group = path.parent.name
        record = load_record_file(path, group=group)
        assert record.record_type is RECORD_GROUP_TYPES[group]
        loaded += 1
    assert loaded == 14


def test_legacy_statuses_are_preserved_exactly() -> None:
    raw_statuses: list[str] = []
    for entry in _legacy_lines():
        payload = cast(dict[str, object], entry["payload"])
        field = "evidence_status" if entry["kind"] == "disposition" else "status"
        value = payload.get(field)
        if isinstance(value, str):
            raw_statuses.append(value)
    normalized_statuses = [
        entry.payload.status
        for entry in Ledger(STATE).records()
        if entry.payload.status is not None
    ]
    assert normalized_statuses == raw_statuses
    assert {"PASS", "FAIL", "UNKNOWN"}.issubset(raw_statuses)


def test_legacy_record_identities_remain_historical() -> None:
    identities = {
        entry.payload.identity for entry in Ledger(STATE).records() if entry.payload.identity
    }
    assert "epoch:eae60fc625779926d937eb4040caf5241c8eb4428b589989bbf93e5c2c2288f4" in identities
    assert (
        "verifier-action:42a8d72e22b201bfd34d218393f829802cb730911f3f29ff178d28f6b39c40fc"
        in identities
    )
    assert (
        "forge-json-sha256-v1:a1a3fce36db50fad44155c3148fd409b5ced996fe33dc12c41597adc0d53713f"
        in identities
    )
    candidate_ids = {
        str(entry.payload["candidate_id"]) for entry in Ledger(STATE).records("candidate")
    }
    assert candidate_ids == {
        "forge-tree-sha256-v1:026f657b5cd689dfa1dfeb3d7de95431800fa2854108e23ed519cb13e0303ff2",
        "forge-tree-sha256-v1:3130f57cdb0898848f8f168e62082f37340456af89bc18f7856a891958d0b8f5",
    }


def test_legacy_unknown_fields_are_preserved_as_non_normative_extensions() -> None:
    candidate_path = next((STATE / "records/candidates").glob("*.json"))
    raw = json.loads(candidate_path.read_text(encoding="utf-8"))
    assert isinstance(raw, dict)
    raw["historical_vendor_note"] = {"claimed_status": "PASS"}
    record = parse_record(raw, expected_type=RecordType.CANDIDATE)
    extensions = cast(dict[str, object], record.to_json()["extensions"])
    preserved = cast(dict[str, object], extensions["legacy_unknown_fields"])
    assert preserved["historical_vendor_note"] == {"claimed_status": "PASS"}


def test_legacy_unknown_field_keeps_historical_record_identity_projection() -> None:
    result_path = next((STATE / "records/results").glob("*.json"))
    raw = json.loads(result_path.read_text(encoding="utf-8"))
    assert isinstance(raw, dict)
    raw["historical_vendor_note"] = "bounded legacy extension"
    raw_without_identity = {key: value for key, value in raw.items() if key != "output_identity"}
    raw["output_identity"] = local_json_identity(raw_without_identity)
    migrated = parse_record(raw, expected_type=RecordType.WORKFLOW_RESULT)
    assert migrated["output_identity"] == raw["output_identity"]
    reparsed = parse_record(migrated.to_json(), expected_type=RecordType.WORKFLOW_RESULT)
    assert canonical_bytes(reparsed.to_json()) == canonical_bytes(migrated.to_json())


@pytest.mark.parametrize(
    ("group", "record_type"),
    [
        ("results", RecordType.WORKFLOW_RESULT),
        ("evaluations", RecordType.FINAL_EVALUATION),
        ("bundles", RecordType.BUNDLE),
    ],
)
def test_early_legacy_result_subject_migrates_without_identity_or_status_drift(
    group: str, record_type: RecordType
) -> None:
    record_path = next((STATE / f"records/{group}").glob("*.json"))
    raw = json.loads(record_path.read_text(encoding="utf-8"))
    assert isinstance(raw, dict)
    raw.pop("subject_type")
    raw_without_identity = {key: value for key, value in raw.items() if key != "output_identity"}
    raw["output_identity"] = local_json_identity(raw_without_identity)
    historical_identity = raw["output_identity"]
    historical_status = raw["status"]

    migrated = parse_record(raw, expected_type=record_type)

    assert migrated["subject_type"] == "candidate"
    assert migrated.identity == historical_identity
    assert migrated.status == historical_status
    reparsed = parse_record(migrated.to_json(), expected_type=record_type)
    assert canonical_bytes(reparsed.to_json()) == canonical_bytes(migrated.to_json())


def test_early_legacy_result_never_infers_project_authority_from_identity_text() -> None:
    record_path = next((STATE / "records/results").glob("*.json"))
    raw = json.loads(record_path.read_text(encoding="utf-8"))
    assert isinstance(raw, dict)
    raw.pop("subject_type")
    raw["candidate_identity"] = "project:historical-fixture"
    raw_without_identity = {key: value for key, value in raw.items() if key != "output_identity"}
    raw["output_identity"] = local_json_identity(raw_without_identity)

    migrated = parse_record(raw, expected_type=RecordType.WORKFLOW_RESULT)

    assert migrated["subject_type"] == "candidate"


def test_legacy_project_subject_must_participate_in_historical_identity() -> None:
    record_path = next((STATE / "records/results").glob("*.json"))
    raw = json.loads(record_path.read_text(encoding="utf-8"))
    assert isinstance(raw, dict)
    raw["subject_type"] = "project"
    without_subject = {
        key: value for key, value in raw.items() if key not in {"output_identity", "subject_type"}
    }
    raw["output_identity"] = local_json_identity(without_subject)

    with pytest.raises(ForgeError) as issue:
        parse_record(raw, expected_type=RecordType.WORKFLOW_RESULT)
    assert issue.value.code == "RECORD_IDENTITY"


def test_legacy_extensions_and_unknown_fields_both_round_trip() -> None:
    result_path = next((STATE / "records/results").glob("*.json"))
    raw = json.loads(result_path.read_text(encoding="utf-8"))
    assert isinstance(raw, dict)
    raw["extensions"] = {"historical_vendor": {"note": "preserve me"}}
    raw["historical_vendor_note"] = "also preserve me"
    raw_without_identity = {key: value for key, value in raw.items() if key != "output_identity"}
    raw["output_identity"] = local_json_identity(raw_without_identity)

    migrated = parse_record(raw, expected_type=RecordType.WORKFLOW_RESULT)
    reparsed = parse_record(migrated.to_json(), expected_type=RecordType.WORKFLOW_RESULT)

    extensions = cast(dict[str, object], migrated.to_json()["extensions"])
    assert extensions["historical_vendor"] == {"note": "preserve me"}
    assert canonical_bytes(reparsed.to_json()) == canonical_bytes(migrated.to_json())


@pytest.mark.parametrize(
    "extensions, code",
    [
        ("not-an-object", "RECORD_MALFORMED"),
        ({"legacy_unknown_fields": {}}, "RECORD_EXTENSION_CONFLICT"),
    ],
)
def test_legacy_unknown_field_preservation_never_discards_extensions(
    extensions: object, code: str
) -> None:
    candidate_path = next((STATE / "records/candidates").glob("*.json"))
    raw = json.loads(candidate_path.read_text(encoding="utf-8"))
    assert isinstance(raw, dict)
    raw["extensions"] = extensions
    raw["historical_vendor_note"] = "preserve"
    with pytest.raises(ForgeError) as issue:
        parse_record(raw, expected_type=RecordType.CANDIDATE)
    assert issue.value.code == code


def test_raw_valid_type_mismatched_current_ledger_fails_after_integrity(
    tmp_path: Path,
) -> None:
    ledger = Ledger(tmp_path)
    candidate = new_record(
        RecordType.CANDIDATE,
        _candidate_fields("forge-tree-sha256-v1:" + "2" * 64),
    )
    ledger.append("candidate", candidate)
    raw = json.loads((tmp_path / "ledger.jsonl").read_text(encoding="utf-8"))
    assert isinstance(raw, dict)
    payload = cast(dict[str, object], raw["payload"])
    payload["record_type"] = "epoch"
    body = {key: value for key, value in raw.items() if key != "entry_hash"}
    raw["entry_hash"] = Ledger._entry_hash(cast(dict[str, object], body))  # type: ignore[arg-type]
    (tmp_path / "ledger.jsonl").write_text(
        json.dumps(raw, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":"))
        + "\n",
        encoding="utf-8",
    )
    assert ledger.verify_chain()["ok"] is True
    with pytest.raises(ForgeError) as issue:
        ledger.verify()
    assert issue.value.code == "RECORD_TYPE_MISMATCH"


def test_raw_valid_legacy_ledger_rejects_invalid_migrated_status(tmp_path: Path) -> None:
    result_path = next((STATE / "records/results").glob("*.json"))
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    payload["status"] = "CERTIFIED"
    without_identity = {key: value for key, value in payload.items() if key != "output_identity"}
    payload["output_identity"] = local_json_identity(without_identity)
    entry_body: dict[str, object] = {
        "sequence": 1,
        "timestamp": "2026-01-01T00:00:00+00:00",
        "kind": "result",
        "previous_hash": "0" * 64,
        "payload": payload,
    }
    entry = {**entry_body, "entry_hash": Ledger._entry_hash(entry_body)}
    (tmp_path / "ledger.jsonl").write_text(
        json.dumps(
            entry, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")
        )
        + "\n",
        encoding="utf-8",
    )

    ledger = Ledger(tmp_path)
    assert ledger.verify_chain()["ok"] is True
    with pytest.raises(ForgeError) as issue:
        ledger.records()
    assert issue.value.code == "RECORD_STATUS"


def test_future_version_is_never_reinterpreted_as_legacy() -> None:
    with pytest.raises(ForgeError) as issue:
        parse_record(
            {"record_type": "candidate", "schema_version": "9999"},
            expected_type=RecordType.CANDIDATE,
        )
    assert issue.value.code == "UNSUPPORTED_RECORD_VERSION"
