from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import pytest

from mncs_forge import mncs_native
from mncs_forge.errors import ForgeError
from mncs_forge.mncs_native import (
    NativeForgeAdapter,
    NativeInvocation,
    NativeLifecycleResult,
    canonical_candidate_digest,
    canonical_candidate_material,
)
from mncs_forge.ports import ExecutionResult
from mncs_forge.serialization import read_json

ROOT = Path(__file__).resolve().parents[1]


def _sequence_value(values: Iterable[int]) -> dict[str, object]:
    return {"sequence": {"values": [{"byte": {"value": value}} for value in values]}}


def test_canonical_candidate_material_matches_declared_chunk_contract() -> None:
    parent = bytes(range(32))
    source = bytes(reversed(range(32)))
    changed_files = b"\x01\x02\x03\x04"

    material = canonical_candidate_material(parent, source, "UNKNOWN", changed_files)

    assert len(material) == 71
    assert material[:3] == bytes((67, 1, 3))
    assert material[3:35] == parent
    assert material[35:67] == source
    assert material[67:] == changed_files
    assert canonical_candidate_digest(parent, source, "UNKNOWN", changed_files)


@pytest.mark.parametrize(
    ("parent", "source", "status", "changed_files"),
    [
        (b"", bytes(32), "PASS", bytes(4)),
        (bytes(32), b"", "PASS", bytes(4)),
        (bytes(32), bytes(32), "MAYBE", bytes(4)),
        (bytes(32), bytes(32), "PASS", b""),
    ],
)
def test_canonical_candidate_material_rejects_malformed_boundary_values(
    parent: bytes, source: bytes, status: str, changed_files: bytes
) -> None:
    with pytest.raises(ValueError):
        canonical_candidate_material(parent, source, status, changed_files)


def test_json_reader_rejects_duplicate_members_and_invalid_utf8(tmp_path: Path) -> None:
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_bytes(b'{"status":"PASS","status":"FAIL"}')
    with pytest.raises(ValueError, match="duplicate JSON object key"):
        read_json(duplicate)

    invalid_utf8 = tmp_path / "invalid-utf8.json"
    invalid_utf8.write_bytes(b'{"status":"\xff"}')
    with pytest.raises(UnicodeDecodeError):
        read_json(invalid_utf8)


def test_native_response_rejects_duplicate_members(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = NativeForgeAdapter(ROOT)
    if not adapter.available:
        pytest.skip("mncs-language checkout is not available")

    monkeypatch.setattr(
        mncs_native,
        "run_bounded",
        lambda *args, **kwargs: ExecutionResult(
            argv=["fixture"],
            returncode=0,
            stdout=b'{"status":"returned","status":"FAIL"}',
            stderr=b"",
            duration_seconds=0.0,
        ),
    )

    result = adapter.invoke(["fixture"])

    assert result.payload is None
    assert not result.ok


def test_native_body_execution_returns_language_owned_status() -> None:
    adapter = NativeForgeAdapter(ROOT)
    if not adapter.available:
        pytest.skip("mncs-language checkout is not available")

    result = adapter.execute(
        ROOT / "mncs/forge/core.mncs",
        ROOT / "examples/execution/native-status-probe.json",
    )

    assert result.ok
    assert result.payload is not None
    assert result.payload["status"] == "returned"
    assert result.payload["returned"][0]["finite"]["variant_identity"].endswith("::UNKNOWN")


def test_native_canonical_material_matches_host_materialization() -> None:
    adapter = NativeForgeAdapter(ROOT)
    if not adapter.available:
        pytest.skip("mncs-language checkout is not available")

    result = adapter.execute(
        ROOT / "mncs/forge/core.mncs",
        ROOT / "examples/execution/native-canonical-probe.json",
    )

    assert result.ok
    assert result.payload is not None
    fields = result.payload["returned"][0]["record"]["fields"]
    by_name = {field[0]: field[1] for field in fields}
    assert by_name["header"] == _sequence_value((67, 1, 3))
    assert by_name["parent"] == _sequence_value(range(32))
    assert by_name["source"] == _sequence_value(reversed(range(32)))
    assert by_name["changed_files"] == _sequence_value((1, 2, 3, 4))


def test_native_backend_execution_accepts_no_argument_status_probe() -> None:
    adapter = NativeForgeAdapter(ROOT)
    if not adapter.available:
        pytest.skip("mncs-language checkout is not available")

    result = adapter.execute(
        ROOT / "mncs/forge/core.mncs",
        ROOT / "examples/execution/native-status-probe.json",
        backend=True,
    )

    assert result.ok
    assert result.payload is not None
    assert result.payload["status"] == "returned"
    assert result.payload["returned"][0]["finite"]["variant_identity"].endswith("::UNKNOWN")


@pytest.mark.parametrize(
    ("stage", "operation", "evidence", "next_stage", "status", "reason"),
    [
        ("NoEpoch", "BeginEpoch", "UNKNOWN", "EpochActive", "PASS", 0),
        ("EpochActive", "RegisterCandidate", "UNKNOWN", "CandidateRegistered", "UNKNOWN", 0),
        ("CandidateReady", "SelectCandidate", "PASS", "CandidateSelected", "PASS", 0),
        ("CandidateReady", "RejectCandidate", "UNKNOWN", "CandidateRejected", "FAIL", 9),
        ("CandidateSelected", "FreezeCandidate", "PASS", "CandidateFrozen", "PASS", 0),
    ],
)
def test_native_lifecycle_preflight_matches_typed_kernel(
    stage: str,
    operation: str,
    evidence: str,
    next_stage: str,
    status: str,
    reason: int,
) -> None:
    adapter = NativeForgeAdapter(ROOT)
    if not adapter.available:
        pytest.skip("mncs-language checkout is not available")

    result = adapter.lifecycle_preflight(stage, operation, evidence)

    assert result == NativeLifecycleResult(stage, operation, next_stage, status, reason)


def test_native_lifecycle_preflight_rejects_malformed_structured_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = NativeForgeAdapter(ROOT)
    if not adapter.available:
        pytest.skip("mncs-language checkout is not available")

    monkeypatch.setattr(
        adapter,
        "execute",
        lambda *args, **kwargs: NativeInvocation(
            command=("fixture",),
            returncode=0,
            stdout=b"{}",
            stderr=b"",
            payload={"status": "returned", "returned": [{"not_a_record": {}}]},
        ),
    )
    mncs_native._LIFECYCLE_CACHE.clear()

    with pytest.raises(ForgeError, match="did not return a record"):
        adapter.lifecycle_preflight("NoEpoch", "BeginEpoch")
