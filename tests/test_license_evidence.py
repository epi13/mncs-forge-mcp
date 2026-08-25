"""License-evidence scan tests (Forge rights/provenance analysis domain)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from mncs_forge.application.license_evidence import (
    compute_content_digest,
    scan_license_evidence,
)
from mncs_forge.config import ForgeConfig


@pytest.fixture()
def project_root(tmp_path: Path) -> Path:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "demo"\nversion = "0.1.0"\nlicense = "Apache-2.0"\n',
        encoding="utf-8",
    )
    return tmp_path


def _config(root: Path) -> ForgeConfig:
    raw: dict[str, Any] = {
        "project": {"name": "demo", "identity": "demo-project"},
        "limits": {"timeout_seconds": 1, "output_bytes": 1024},
    }
    return ForgeConfig(
        config_path=root / "mncs-forge.toml",
        root=root,
        raw=raw,
        path_values={},
        providers={},
        workflows={},
        verifiers={},
    )


def test_declared_metadata_becomes_observed_declaration(project_root: Path) -> None:
    evidence = scan_license_evidence(_config(project_root))
    claims = [c for c in evidence["claims"] if c["claim_type"] == "license-identification"]
    assert any(
        c["confidence"] == "observed-declaration" and "Apache-2.0" in c["statement"]
        for c in claims
    )


def test_missing_evidence_is_explicitly_unknown(tmp_path: Path) -> None:
    evidence = scan_license_evidence(_config(tmp_path))
    assert evidence["claims"] == [
        {
            "claim_type": "unknown-license-state",
            "statement": evidence["claims"][0]["statement"],
            "confidence": "insufficient-evidence",
        }
    ]
    assert "do not infer one" in evidence["claims"][0]["statement"]


def test_notice_file_hash_and_heuristic_confidence(project_root: Path) -> None:
    (project_root / "LICENSE").write_text(
        "Apache License\nVersion 2.0, January 2004\n", encoding="utf-8"
    )
    evidence = scan_license_evidence(_config(project_root))
    heuristic = [c for c in evidence["claims"] if c["confidence"] == "heuristic"]
    assert len(heuristic) == 1
    assert heuristic[0]["spdx_expression"] == "Apache-2.0"
    observations = {o["name"]: o for o in evidence["observations"]}
    recorded = observations["notice_file:LICENSE"]["value"]["sha256"]
    import hashlib

    assert (
        recorded
        == hashlib.sha256(
            b"Apache License\nVersion 2.0, January 2004\n"
        ).hexdigest()
    )


def test_digest_tamper_detection(project_root: Path) -> None:
    evidence = scan_license_evidence(_config(project_root))
    ok = compute_content_digest(evidence) == evidence["content_digest"]
    assert ok
    tampered = dict(evidence)
    tampered["claims"] = []
    assert compute_content_digest(tampered) != evidence["content_digest"]


def test_producer_reference_shape(project_root: Path) -> None:
    evidence = scan_license_evidence(_config(project_root))
    producer = evidence["producer"]
    assert producer["producer"] == "mncs-forge"
    assert producer["stableId"] == evidence["evidence_id"]
