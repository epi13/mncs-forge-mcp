"""Reference Forge Cell policy, bundle, and execution-receipt validation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from importlib.resources import files
from typing import Literal, cast

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError

AssuranceStatus = Literal["PASS", "FAIL", "UNKNOWN"]
DocumentKind = Literal["policy", "test-bundle", "execution-record"]

_SCHEMA_FILES: dict[DocumentKind, str] = {
    "policy": "forge-cell-policy-0.1.schema.json",
    "test-bundle": "forge-cell-test-bundle-0.1.schema.json",
    "execution-record": "forge-cell-execution-record-0.1.schema.json",
}


class ForgeCellValidationError(ValueError):
    """Raised when a Forge Cell document does not satisfy its declared schema."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class AssuranceAssessment:
    """Fail-closed interpretation of one execution record against one policy."""

    status: AssuranceStatus
    reasons: tuple[str, ...]
    requested: tuple[str, ...]
    enforced: tuple[str, ...]
    unmet: tuple[str, ...]


def _schema(kind: DocumentKind) -> dict[str, object]:
    resource = files("mncs_forge.resources").joinpath(_SCHEMA_FILES[kind])
    value = json.loads(resource.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ForgeCellValidationError("SCHEMA_INVALID", f"{kind} schema is not an object")
    try:
        Draft202012Validator.check_schema(value)
    except SchemaError as issue:
        raise ForgeCellValidationError("SCHEMA_INVALID", str(issue)) from issue
    return value


def validate_forge_cell_document(kind: DocumentKind, document: object) -> None:
    """Validate a Forge Cell document without executing or trusting it."""

    try:
        Draft202012Validator(_schema(kind)).validate(document)
    except ValidationError as issue:
        path = "/".join(str(part) for part in issue.absolute_path)
        location = f" at {path}" if path else ""
        raise ForgeCellValidationError(
            "DOCUMENT_INVALID",
            f"invalid Forge Cell {kind}{location}: {issue.message}",
        ) from issue


def _string_tuple(value: object, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ForgeCellValidationError("DOCUMENT_INVALID", f"{field} is not a string array")
    return tuple(cast(list[str], value))


def assess_execution_assurance(
    policy: dict[str, object],
    record: dict[str, object],
    *,
    expected_nonce: str | None = None,
) -> AssuranceAssessment:
    """Assess declared execution assurance separately from the test result.

    A program may return ``PASS`` while this assessment returns ``UNKNOWN`` because a requested
    isolation or custody property was not established. Identity or challenge contradictions are
    ``FAIL``. Missing capabilities remain ``UNKNOWN``.
    """

    validate_forge_cell_document("policy", policy)
    validate_forge_cell_document("execution-record", record)

    requested = _string_tuple(policy["requested_assurance"], "requested_assurance")
    recorded_requested = _string_tuple(record["requested_assurance"], "requested_assurance")
    enforced = _string_tuple(record["enforced_assurance"], "enforced_assurance")
    unmet = _string_tuple(record["unmet_assurance"], "unmet_assurance")

    requested_set = set(requested)
    recorded_requested_set = set(recorded_requested)
    enforced_set = set(enforced)
    unmet_set = set(unmet)
    reasons: list[str] = []

    if record["policy_id"] != policy["policy_id"]:
        reasons.append("execution record policy identity does not match the requested policy")
    if recorded_requested_set != requested_set:
        reasons.append("execution record changed the requested assurance set")
    if enforced_set & unmet_set:
        reasons.append("an assurance property is both enforced and unmet")
    if (enforced_set | unmet_set) - requested_set:
        reasons.append("execution record claims an assurance property not requested by policy")
    policy_attestation = cast(dict[str, object], policy["attestation"])
    record_attestation = cast(dict[str, object], record["attestation"])
    accepted_kinds = _string_tuple(policy_attestation["accepted_kinds"], "accepted_kinds")
    if record_attestation["kind"] not in set(accepted_kinds):
        reasons.append("execution record attestation kind is not accepted by policy")
    if expected_nonce is not None and record["challenge_nonce"] != expected_nonce:
        reasons.append("execution record challenge nonce does not match the verifier challenge")

    if reasons:
        return AssuranceAssessment("FAIL", tuple(reasons), requested, enforced, unmet)

    missing = requested_set - enforced_set - unmet_set
    if missing:
        reasons.append(f"requested assurance was not accounted for: {', '.join(sorted(missing))}")
    if unmet_set:
        reasons.append(f"requested assurance was not established: {', '.join(sorted(unmet_set))}")

    if policy_attestation["fresh_challenge_required"] and expected_nonce is None:
        reasons.append("fresh challenge verification was required but not supplied")

    attested_levels = {
        "platform-attested",
        "confidential-attested",
        "external-custody",
    }
    if enforced_set & attested_levels:
        if record_attestation["verification_status"] != "VERIFIED":
            reasons.append("attested assurance was claimed without verified attestation evidence")
        if not record_attestation["nonce_binding"]:
            reasons.append("attested assurance was claimed without challenge binding")
        if record_attestation["kind"] == "none":
            reasons.append("attested assurance was claimed without an attestation kind")

    if reasons:
        return AssuranceAssessment("UNKNOWN", tuple(reasons), requested, enforced, unmet)
    return AssuranceAssessment("PASS", (), requested, enforced, unmet)
