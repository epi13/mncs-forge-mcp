from __future__ import annotations

import json
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from typing import cast

import pytest
from jsonschema import Draft202012Validator

from mncs_forge.config import ForgeConfig
from mncs_forge.engine import Forge
from mncs_forge.errors import ForgeError
from mncs_forge.records import (
    CURRENT_SCHEMA_VERSION,
    RECORD_SPECS,
    RecordType,
    derive_record_identity,
    new_record,
    parse_record,
)
from mncs_forge.serialization import canonical_bytes

SCHEMA = Path("src/mncs_forge/resources/forge-records-1.schema.json")


def _schema() -> dict[str, object]:
    value = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return cast(dict[str, object], value)


def _sample_fields(record_type: RecordType) -> dict[str, object]:
    schema = _schema()
    definitions = cast(dict[str, object], schema["$defs"])
    definition = cast(dict[str, object], definitions[record_type.value])
    properties = cast(dict[str, object], definition["properties"])
    fields: dict[str, object] = {}
    identity_field = RECORD_SPECS[record_type].identity_field
    for field in RECORD_SPECS[record_type].required:
        if field == identity_field:
            continue
        property_value = cast(dict[str, object], properties[field])
        if "const" in property_value:
            fields[field] = property_value["const"]
        elif "enum" in property_value:
            fields[field] = cast(list[object], property_value["enum"])[0]
        elif property_value.get("type") == "string":
            fields[field] = "fixture"
        elif property_value.get("type") == "object":
            fields[field] = {}
        elif property_value.get("type") == "boolean":
            fields[field] = False
        elif property_value.get("type") == "array":
            fields[field] = []
        else:
            fields[field] = None
    if record_type is RecordType.CANDIDATE:
        fields["candidate_id"] = "forge-tree-sha256-v1:" + "1" * 64
    if record_type is RecordType.CANDIDATE_DISPOSITION:
        fields["disposition"] = "selected"
        fields["evidence_status"] = "PASS"
    if record_type is RecordType.VERIFIER_RESULT:
        fields["independent_evaluation"] = False
        fields["status"] = "UNKNOWN"
    if record_type is RecordType.EXECUTION_RECEIPT_BINDING:
        fields["status"] = "UNKNOWN"
        fields["receipt_completeness"] = "incomplete"
        fields["action_kind"] = "workflow_action"
        fields["established_properties"] = {
            "execution_completed": "unknown",
            "local_result_validity": "unknown",
            "runner_capability": "unknown",
            "filesystem_isolation": "not-established",
            "network_isolation": "not-established",
            "containerization": "not-established",
            "same_operator_execution": "established",
            "external_anchoring": "not-established",
            "witnessing": "not-established",
            "protected_custody": "not-established",
            "evaluator_independence": "not-established",
            "governance_certification": "not-established",
        }
        fields["mncs_receipt"] = None
        fields["receipt_identity"] = None
        fields["receipt_schema_version"] = None
    if record_type is RecordType.COMPILER_EXPERIMENT:
        fields["language_contract_id"] = "mncs:language:compilation-study-result:0.1"
        fields["interpretation"] = "observation_only_not_assurance_or_conformance"
        fields["compilation_status"] = "completed"
    if record_type is RecordType.COMPILER_CANDIDATE:
        fields["isolated"] = True
        fields["generator_certified"] = False
        fields["baseline_artifact_identity"] = "ssa:baseline"
        fields["candidate_artifact_identity"] = "ssa:candidate"
        fields["interpretation"] = "search_observation_not_language_correctness"
        fields["semantic_status"] = "UNVALIDATED"
        fields["policy_disposition"] = "retain_unresolved"
        fields["protected_properties"] = ["return_value"]
    return fields


@pytest.mark.parametrize("record_type", list(RECORD_SPECS))
def test_current_models_are_frozen_versioned_and_schema_valid(record_type: RecordType) -> None:
    record = new_record(record_type, _sample_fields(record_type))
    serialized = record.to_json()
    assert serialized["record_type"] == record_type.value
    assert serialized["schema_version"] == CURRENT_SCHEMA_VERSION
    with pytest.raises(FrozenInstanceError):
        record.schema_version = "2"  # type: ignore[misc]
    Draft202012Validator(_schema()).validate(serialized)


@pytest.mark.parametrize("record_type", list(RECORD_SPECS))
def test_current_record_round_trip_is_canonical(record_type: RecordType) -> None:
    original = new_record(record_type, _sample_fields(record_type))
    encoded = canonical_bytes(original.to_json())
    parsed = parse_record(original.to_json(), expected_type=record_type)
    assert type(parsed) is type(original)
    assert canonical_bytes(parsed.to_json()) == encoded
    if original.identity is not None:
        assert parsed.identity == original.identity
        assert parsed.identity == derive_record_identity(record_type, parsed.to_json())


def test_candidate_identity_remains_semantic_content_identity() -> None:
    fields = _sample_fields(RecordType.CANDIDATE)
    candidate = new_record(RecordType.CANDIDATE, fields)
    assert candidate["candidate_id"] == fields["candidate_id"]
    changed = dict(fields)
    changed["declared_hypothesis"] = "different record, same candidate content"
    assert new_record(RecordType.CANDIDATE, changed)["candidate_id"] == fields["candidate_id"]


def test_record_metadata_cannot_be_spoofed_by_writer_input() -> None:
    fields = _sample_fields(RecordType.CANDIDATE)
    fields["record_type"] = "epoch"
    with pytest.raises(ForgeError) as issue:
        new_record(RecordType.CANDIDATE, fields)
    assert issue.value.code == "RECORD_METADATA_SPOOF"


def test_unsupported_future_version_fails_with_stable_code() -> None:
    with pytest.raises(ForgeError) as issue:
        parse_record(
            {"record_type": "candidate", "schema_version": "9999"},
            expected_type=RecordType.CANDIDATE,
        )
    assert issue.value.code == "UNSUPPORTED_RECORD_VERSION"


def test_trusted_context_type_mismatch_fails_closed() -> None:
    candidate = new_record(RecordType.CANDIDATE, _sample_fields(RecordType.CANDIDATE))
    with pytest.raises(ForgeError) as issue:
        parse_record(candidate.to_json(), expected_type=RecordType.EPOCH)
    assert issue.value.code == "RECORD_TYPE_MISMATCH"


def test_missing_authority_field_is_not_defaulted() -> None:
    record = new_record(RecordType.VERIFIER_RESULT, _sample_fields(RecordType.VERIFIER_RESULT))
    malformed = record.to_json()
    del malformed["independent_evaluation"]
    with pytest.raises(ForgeError) as issue:
        parse_record(malformed, expected_type=RecordType.VERIFIER_RESULT)
    assert issue.value.code == "RECORD_MISSING_FIELD"


def test_current_unknown_top_level_field_is_rejected() -> None:
    record = new_record(RecordType.CANDIDATE, _sample_fields(RecordType.CANDIDATE))
    malformed = record.to_json()
    malformed["surprise_authority"] = True
    with pytest.raises(ForgeError) as issue:
        parse_record(malformed, expected_type=RecordType.CANDIDATE)
    assert issue.value.code == "RECORD_UNKNOWN_FIELD"


def test_extensions_round_trip_but_do_not_change_status() -> None:
    fields = _sample_fields(RecordType.VERIFIER_RESULT)
    fields["extensions"] = {"vendor_note": {"status": "PASS"}}
    record = new_record(RecordType.VERIFIER_RESULT, fields)
    assert record.status == "UNKNOWN"
    assert (
        parse_record(record.to_json(), expected_type=RecordType.VERIFIER_RESULT).to_json()
        == record.to_json()
    )


def test_action_identity_projection_is_explicit_and_metadata_bound() -> None:
    fields = _sample_fields(RecordType.VERIFIER_ACTION)
    fields["protocol_request_identity"] = "request:one"
    first = new_record(RecordType.VERIFIER_ACTION, fields)
    fields["protocol_request_identity"] = "request:two"
    second = new_record(RecordType.VERIFIER_ACTION, fields)
    assert first.identity == second.identity
    assert first.to_json()["record_type"] == "verifier_action"


def test_new_lifecycle_records_and_files_expose_metadata(config: ForgeConfig) -> None:
    forge = Forge(config)
    probe = forge.provider_probe("provider-pass")
    epoch = forge.epoch_begin(generator_identity="generator", evaluator_identity="evaluator")
    candidate = forge.candidate_register(
        changed_files=["candidate/main.py"],
        hypothesis="versioned lifecycle",
        generator_identity="generator",
        generator_config_identity="configuration",
    )
    workflow = forge.development_checks_run(["pass-check"])["results"]
    verifier = forge.verifier_run("verify-pass", changed_paths=["candidate/main.py"], scope="file")
    disposition = forge.candidate_disposition(
        str(candidate["candidate_id"]), disposition="selected", reason="fixture PASS"
    )
    freeze = forge.candidate_freeze(
        str(candidate["candidate_id"]),
        environment_identity="environment-v1",
        required_evidence_plan="evaluator/policy.json",
    )
    evaluation = Forge(config, mode="evaluator").final_evaluation_run(["evaluator-pass"])
    bundle_workflow = replace(
        config.workflows["pass-check"],
        name="bundle-pass",
        category="mncs_bundle_validation",
    )
    bundle_config = replace(config, workflows={**config.workflows, "bundle-pass": bundle_workflow})
    bundle = Forge(bundle_config).bundle_build("bundle-pass", str(candidate["candidate_id"]))

    assert probe["record_type"] == "provider_probe"
    assert epoch["record_type"] == "epoch"
    assert candidate["record_type"] == "candidate"
    assert cast(list[dict[str, object]], workflow)[0]["record_type"] == "workflow_result"
    assert verifier["record_type"] == "verifier_result"
    assert disposition["record_type"] == "candidate_disposition"
    assert freeze["record_type"] == "freeze"
    assert evaluation["aggregate_status"] == "PASS"
    assert bundle["result_reference"]
    for entry in forge.ledger.records():
        assert entry["record_type"] == "ledger_entry"
        Draft202012Validator(_schema()).validate(entry.to_json())
    for path in config.state_dir.glob("records/*/*.json"):
        persisted = json.loads(path.read_text(encoding="utf-8"))
        assert persisted["record_type"]
        assert persisted["schema_version"] == CURRENT_SCHEMA_VERSION


def test_schema_snapshot_is_valid_draft_2020_12() -> None:
    Draft202012Validator.check_schema(_schema())


def test_compiler_experiment_schema_requires_null_verdict_fields() -> None:
    definitions = cast(dict[str, object], _schema()["$defs"])
    experiment = cast(dict[str, object], definitions[RecordType.COMPILER_EXPERIMENT.value])
    properties = cast(dict[str, object], experiment["properties"])

    assert properties["assurance_status"] == {"type": "null"}
    assert properties["conformance_status"] == {"type": "null"}
    assert properties["language_contract_id"] == {
        "const": "mncs:language:compilation-study-result:0.1"
    }
    assert properties["interpretation"] == {
        "const": "observation_only_not_assurance_or_conformance"
    }
