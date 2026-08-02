from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import cast

import pytest
from jsonschema import Draft202012Validator

from mncs_forge.forge_cell import (
    DocumentKind,
    ForgeCellValidationError,
    assess_execution_assurance,
    validate_forge_cell_document,
)

ROOT = Path(__file__).parents[1]
EXAMPLES = ROOT / "examples" / "forge-cell"
SCHEMAS = ROOT / "src" / "mncs_forge" / "resources"


def load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


@pytest.mark.parametrize(
    "name",
    [
        "forge-cell-policy-0.1.schema.json",
        "forge-cell-test-bundle-0.1.schema.json",
        "forge-cell-execution-record-0.1.schema.json",
    ],
)
def test_forge_cell_schemas_are_valid_draft_2020_12(name: str) -> None:
    Draft202012Validator.check_schema(load_json(SCHEMAS / name))


@pytest.mark.parametrize(
    ("kind", "name"),
    [
        ("policy", "policy.json"),
        ("test-bundle", "test-bundle.json"),
        ("execution-record", "execution-record.json"),
    ],
)
def test_reference_documents_validate(kind: str, name: str) -> None:
    validate_forge_cell_document(cast(DocumentKind, kind), load_json(EXAMPLES / name))


def test_test_pass_does_not_promote_missing_isolation_assurance() -> None:
    policy = load_json(EXAMPLES / "policy.json")
    record = load_json(EXAMPLES / "execution-record.json")

    assessment = assess_execution_assurance(
        policy,
        record,
        expected_nonce="reference-nonce-0000000000000001",
    )

    assert record["result"] == "PASS"
    assert assessment.status == "UNKNOWN"
    assert assessment.unmet == ("process-isolated",)


def test_complete_enforcement_can_pass_assurance() -> None:
    policy = load_json(EXAMPLES / "policy.json")
    record = deepcopy(load_json(EXAMPLES / "execution-record.json"))
    record["enforced_assurance"] = ["policy-bound", "process-isolated"]
    record["unmet_assurance"] = []

    assessment = assess_execution_assurance(
        policy,
        record,
        expected_nonce="reference-nonce-0000000000000001",
    )

    assert assessment.status == "PASS"
    assert assessment.reasons == ()


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        ("policy", "policy identity"),
        ("nonce", "challenge nonce"),
        ("overlap", "both enforced and unmet"),
        ("extra", "not requested"),
    ],
)
def test_identity_and_assurance_contradictions_fail(mutation: str, reason: str) -> None:
    policy = load_json(EXAMPLES / "policy.json")
    record = deepcopy(load_json(EXAMPLES / "execution-record.json"))
    expected_nonce = "reference-nonce-0000000000000001"

    if mutation == "policy":
        record["policy_id"] = "different-policy"
    elif mutation == "nonce":
        expected_nonce = "different-nonce-0000000000000000"
    elif mutation == "overlap":
        record["enforced_assurance"] = ["policy-bound", "process-isolated"]
    elif mutation == "extra":
        record["enforced_assurance"] = ["policy-bound", "verity-enforced"]

    assessment = assess_execution_assurance(policy, record, expected_nonce=expected_nonce)

    assert assessment.status == "FAIL"
    assert any(reason in item for item in assessment.reasons)


def test_required_fresh_challenge_without_verifier_nonce_is_unknown() -> None:
    policy = load_json(EXAMPLES / "policy.json")
    record = deepcopy(load_json(EXAMPLES / "execution-record.json"))
    record["enforced_assurance"] = ["policy-bound", "process-isolated"]
    record["unmet_assurance"] = []

    assessment = assess_execution_assurance(policy, record)

    assert assessment.status == "UNKNOWN"
    assert any("fresh challenge" in item for item in assessment.reasons)


def test_unaccepted_attestation_kind_fails() -> None:
    policy = deepcopy(load_json(EXAMPLES / "policy.json"))
    record = deepcopy(load_json(EXAMPLES / "execution-record.json"))
    policy_attestation = cast(dict[str, object], policy["attestation"])
    policy_attestation["accepted_kinds"] = ["none"]
    record_attestation = cast(dict[str, object], record["attestation"])
    record_attestation["kind"] = "local-signature"
    record_attestation["verification_status"] = "PRESENT"

    assessment = assess_execution_assurance(
        policy,
        record,
        expected_nonce="reference-nonce-0000000000000001",
    )

    assert assessment.status == "FAIL"
    assert any("not accepted" in item for item in assessment.reasons)


def test_malformed_document_is_rejected_before_assessment() -> None:
    policy = load_json(EXAMPLES / "policy.json")
    record = load_json(EXAMPLES / "execution-record.json")
    del record["identities"]

    with pytest.raises(ForgeCellValidationError) as issue:
        assess_execution_assurance(policy, record)

    assert issue.value.code == "DOCUMENT_INVALID"
