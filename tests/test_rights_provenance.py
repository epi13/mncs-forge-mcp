from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from mncs_forge.config import ForgeConfig, load_config
from mncs_forge.engine import Forge
from mncs_forge.errors import ForgeError


def _begin_and_register(forge: Forge) -> dict[str, object]:
    forge.epoch_begin(generator_identity="generator-v1", evaluator_identity="evaluator-v1")
    return forge.candidate_register(
        changed_files=["candidate/main.py"],
        hypothesis="retain behavior",
        generator_identity="generator-v1",
        generator_config_identity="generator-config-v1",
    )


def _manifest(
    candidate_identity: str,
    *,
    origin: str = "human-directed-machine-generated",
    copyright_status: str = "mixed-or-undetermined",
    rights_basis: str = "no-exclusive-right-asserted",
    third_party_material: str = "none-known",
    source_license_status: str | None = None,
    provenance_validation: str = "passed",
    human_acceptance: str = "accepted",
) -> dict[str, object]:
    sources: list[dict[str, str]] = []
    if source_license_status is not None:
        sources.append(
            {
                "kind": "repository",
                "reference": "upstream/example",
                "license_status": source_license_status,
                "license": "Apache-2.0",
            }
        )
    return {
        "schema_version": "0.1.0",
        "artifact": {
            "id": candidate_identity,
            "type": "source-code",
            "paths": ["candidate/main.py"],
        },
        "provenance": {
            "origin_classification": origin,
            "participants": [
                {"type": "agent", "role": "generator", "name": "generator-v1"}
            ],
            "process_evidence": [],
        },
        "rights": {
            "distribution_license": "Apache-2.0",
            "copyright_status": copyright_status,
            "rights_basis": rights_basis,
            "third_party_material": third_party_material,
            "sources": sources,
        },
        "review": {
            "technical_validation": "passed",
            "provenance_validation": provenance_validation,
            "human_acceptance": human_acceptance,
        },
    }


def _with_policy(
    config: ForgeConfig, project: Path, manifest: dict[str, object], *, mode: str
) -> ForgeConfig:
    path = project / "evidence/rights-provenance.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    raw = {
        **config.raw,
        "rights_provenance": {
            "mode": mode,
            "manifest": "evidence/rights-provenance.json",
        },
    }
    return replace(config, raw=raw)


def test_config_schema_accepts_rights_provenance_policy(project: Path) -> None:
    config_path = project / "mncs-forge.toml"
    with config_path.open("a", encoding="utf-8") as stream:
        stream.write(
            "\n[rights_provenance]\n"
            'mode = "observe"\n'
            'manifest = "evidence/rights-provenance.json"\n'
        )
    loaded = load_config(config_path)
    assert loaded.raw["rights_provenance"]["mode"] == "observe"


def test_default_observe_mode_preserves_unknown_without_blocking(config: ForgeConfig) -> None:
    forge = Forge(config)
    candidate = _begin_and_register(forge)
    rights = forge.claim_status()["rights_provenance"]
    assert isinstance(rights, dict)
    assert rights["candidate_identity"] == candidate["candidate_id"]
    assert rights["policy_mode"] == "observe"
    assert rights["evidence_status"] == "UNKNOWN"
    assert rights["legal_conclusion"] == "NOT_MADE"
    assert rights["policy"]["blocking"] is False  # type: ignore[index]
    draft = rights["draft_manifest"]
    assert isinstance(draft, dict)
    assert draft["provenance"]["origin_classification"] == "origin-uncertain"  # type: ignore[index]


def test_advisory_mode_reports_review_without_becoming_a_gate(
    config: ForgeConfig, project: Path
) -> None:
    initial = Forge(config)
    candidate = _begin_and_register(initial)
    candidate_id = str(candidate["candidate_id"])
    manifest = _manifest(
        candidate_id,
        rights_basis="unknown-needs-review",
        third_party_material="unknown",
        provenance_validation="incomplete",
        human_acceptance="not-reviewed",
    )
    advisory = Forge(_with_policy(config, project, manifest, mode="advisory"))
    rights = advisory.claim_status()["rights_provenance"]
    assert isinstance(rights, dict)
    assert rights["evidence_status"] == "UNKNOWN"
    assert rights["policy"]["blocking"] is False  # type: ignore[index]
    assert rights["policy"]["disposition"] == "REVIEW_REQUIRED"  # type: ignore[index]
    blockers = advisory.claim_blockers("rights_provenance")
    assert blockers["blocked"] is False
    assert blockers["review_required"] is True


def test_machine_origin_does_not_imply_public_domain_or_legal_clearance(
    config: ForgeConfig, project: Path
) -> None:
    initial = Forge(config)
    candidate = _begin_and_register(initial)
    candidate_id = str(candidate["candidate_id"])
    manifest = _manifest(
        candidate_id,
        origin="autonomous-machine-generated",
        copyright_status="machine-originated-unresolved",
    )
    forge = Forge(_with_policy(config, project, manifest, mode="advisory"))
    rights = forge.claim_status()["rights_provenance"]
    assert isinstance(rights, dict)
    assert rights["origin_classification"] == "autonomous-machine-generated"
    assert rights["copyright_status"] == "machine-originated-unresolved"
    assert rights["evidence_status"] == "PASS"
    assert rights["legal_conclusion"] == "NOT_MADE"
    assert rights["policy"]["blocking"] is False  # type: ignore[index]


def test_enforced_mode_blocks_candidate_selection_on_incompatible_source(
    config: ForgeConfig, project: Path
) -> None:
    initial = Forge(config)
    candidate = _begin_and_register(initial)
    candidate_id = str(candidate["candidate_id"])
    initial.development_checks_run(["pass-check"], candidate_id)
    manifest = _manifest(
        candidate_id,
        third_party_material="present",
        source_license_status="incompatible",
    )
    enforced = Forge(_with_policy(config, project, manifest, mode="enforced"))
    with pytest.raises(ForgeError) as issue:
        enforced.candidate_disposition(
            candidate_id,
            disposition="selected",
            reason="technical evidence passed",
        )
    assert issue.value.code == "RIGHTS_PROVENANCE_BLOCKED"
    promotion = enforced.claim_blockers("promotion")
    assert promotion["blocked"] is True
    assert any(
        item["claim_class"] == "rights_provenance"  # type: ignore[index]
        for item in promotion["blockers"]  # type: ignore[union-attr]
    )


def test_observe_mode_retains_selection_snapshot_without_changing_technical_gate(
    config: ForgeConfig, project: Path
) -> None:
    initial = Forge(config)
    candidate = _begin_and_register(initial)
    candidate_id = str(candidate["candidate_id"])
    initial.development_checks_run(["pass-check"], candidate_id)
    manifest = _manifest(
        candidate_id,
        rights_basis="unknown-needs-review",
        third_party_material="unknown",
        provenance_validation="incomplete",
        human_acceptance="not-reviewed",
    )
    observe = Forge(_with_policy(config, project, manifest, mode="observe"))
    selected = observe.candidate_disposition(
        candidate_id,
        disposition="selected",
        reason="technical gate passed; rights evidence observed",
    )
    assert selected["disposition"] == "selected"
    extensions = selected["extensions"]
    assert isinstance(extensions, dict)
    rights = extensions["rights_provenance"]
    assert isinstance(rights, dict)
    assert rights["evidence_status"] == "UNKNOWN"
    assert rights["policy"]["blocking"] is False  # type: ignore[index]


def test_candidate_comparison_reports_rights_domain_side_by_side(
    config: ForgeConfig, project: Path
) -> None:
    forge = Forge(config)
    first = _begin_and_register(forge)
    (project / "candidate/main.py").write_text("VALUE = 2\n", encoding="utf-8")
    second = forge.candidate_register(
        changed_files=["candidate/main.py"],
        hypothesis="candidate two",
        generator_identity="generator-v1",
        generator_config_identity="generator-config-v1",
        parent_candidate=str(first["candidate_id"]),
    )
    result = forge.candidate_compare([str(first["candidate_id"]), str(second["candidate_id"])])
    for item in result["candidates"]:  # type: ignore[union-attr]
        assert item["rights_provenance"]["legal_conclusion"] == "NOT_MADE"
        assert item["rights_provenance"]["policy_mode"] == "observe"
