from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

import pytest

from mncs_forge.config import ForgeConfig
from mncs_forge.engine import Forge
from mncs_forge.errors import ForgeError
from mncs_forge.records import (
    CURRENT_SCHEMA_VERSION,
    RecordType,
    new_record,
    parse_record,
)
from mncs_forge.serialization import canonical_bytes


def begin(forge: Forge) -> dict[str, object]:
    return forge.epoch_begin(generator_identity="generator-v1", evaluator_identity="evaluator-v1")


def register(forge: Forge) -> dict[str, object]:
    return forge.candidate_register(
        changed_files=["candidate/main.py"],
        hypothesis="receipt integration",
        generator_identity="generator-v1",
        generator_config_identity="generator-config-v1",
    )


def test_declared_workflow_persists_action_binding_and_result(config: ForgeConfig) -> None:
    forge = Forge(config)
    begin(forge)
    candidate = register(forge)

    result = forge.development_checks_run(["pass-check"], str(candidate["candidate_id"]))

    assert result["aggregate_status"] == "PASS"
    receipts = result["execution_receipts"]
    assert isinstance(receipts, list) and len(receipts) == 1
    summary = receipts[0]
    assert isinstance(summary, dict)
    assert summary["receipt_completeness"] == "complete"
    assert summary["status"] == "UNKNOWN"
    assert summary["termination_category"] == "completed"
    assert summary["runner_kind"] == "local-process"
    properties = summary["established_properties"]
    assert isinstance(properties, Mapping)
    assert properties["same_operator_execution"] == "established"
    assert properties["filesystem_isolation"] == "not-established"
    assert properties["network_isolation"] == "not-established"
    assert properties["protected_custody"] == "not-established"
    assert properties["evaluator_independence"] == "not-established"
    assert properties["governance_certification"] == "not-established"

    actions = forge.ledger.records("workflow_action")
    bindings = forge.ledger.records("execution_receipt_binding")
    results = forge.ledger.records("result")
    assert len(actions) == 1
    assert len(bindings) == 1
    assert len(results) == 1
    binding = bindings[0].payload
    assert binding["action_identity"] == actions[0].payload["action_id"]
    assert binding["result_identity"] == results[0].payload["output_identity"]
    assert binding["candidate_identity"] == candidate["candidate_id"]
    assert binding["epoch_identity"] == candidate["source_epoch"]
    assert binding["mncs_receipt"]["schema_version"] == "0.1-experimental"
    assert binding["mncs_receipt"]["receipt_identity"] == binding["receipt_identity"]
    assert all(
        value == "not-asserted" for value in binding["mncs_receipt"]["claim_boundary"].values()
    )

    listed = forge.execution_receipts_list(str(candidate["candidate_id"]))
    assert listed["count"] == 1
    fetched = forge.execution_receipts_get(str(binding["binding_id"]))
    assert fetched["binding_id"] == binding["binding_id"]
    assert fetched["receipt_identity"] == binding["receipt_identity"]


def test_nonzero_exit_persists_fail_result_and_complete_receipt(config: ForgeConfig) -> None:
    forge = Forge(config)
    begin(forge)
    register(forge)
    result = forge.development_checks_run(["fail-check"])
    assert result["aggregate_status"] == "FAIL"
    binding = forge.ledger.records("execution_receipt_binding")[0].payload
    assert binding["receipt_completeness"] == "complete"
    assert binding["status"] == "UNKNOWN"
    assert binding["termination_category"] == "nonzero-exit"
    assert result["results"][0]["status"] == "FAIL"


@pytest.mark.parametrize(
    ("workflow", "code", "termination"),
    [
        ("timeout-check", "TIMEOUT", "timeout"),
        ("output-check", "OUTPUT_LIMIT", "output-limit"),
    ],
)
def test_interrupted_execution_persists_incomplete_binding(
    config: ForgeConfig, workflow: str, code: str, termination: str
) -> None:
    forge = Forge(config)
    begin(forge)
    register(forge)
    with pytest.raises(ForgeError) as issue:
        forge.development_checks_run([workflow])
    assert issue.value.code == code
    assert forge.ledger.records("result") == []
    bindings = forge.ledger.records("execution_receipt_binding")
    assert len(bindings) == 1
    binding = bindings[0].payload
    assert binding["receipt_completeness"] == "incomplete"
    assert binding["receipt_identity"] is None
    assert binding["mncs_receipt"] is None
    assert binding["status"] == "UNKNOWN"
    assert binding["termination_category"] == termination
    assert binding["result_identity"] is None


def test_altered_persisted_receipt_fails_closed(config: ForgeConfig) -> None:
    forge = Forge(config)
    begin(forge)
    register(forge)
    forge.development_checks_run(["pass-check"])
    binding = forge.ledger.records("execution_receipt_binding")[0].payload
    tampered = binding.to_object_dict()
    receipt = tampered["mncs_receipt"]
    assert isinstance(receipt, dict)
    receipt["process"] = {**receipt["process"], "harness_status": "PASS"}  # type: ignore[index]
    with pytest.raises(ForgeError) as issue:
        parse_record(tampered, expected_type=RecordType.EXECUTION_RECEIPT_BINDING)
    assert issue.value.code == "RECORD_IDENTITY"


def test_complete_binding_cannot_claim_evidence_pass(config: ForgeConfig) -> None:
    forge = Forge(config)
    begin(forge)
    register(forge)
    forge.development_checks_run(["pass-check"])
    binding = forge.ledger.records("execution_receipt_binding")[0].payload
    fields = {
        key: value
        for key, value in binding.to_object_dict().items()
        if key not in {"record_type", "schema_version", "binding_id"}
    }
    fields["status"] = "PASS"
    with pytest.raises(ForgeError) as issue:
        new_record(RecordType.EXECUTION_RECEIPT_BINDING, fields)
    assert issue.value.code == "RECORD_AUTHORITY"


def test_unsupported_future_binding_version_fails_closed(config: ForgeConfig) -> None:
    forge = Forge(config)
    begin(forge)
    register(forge)
    forge.development_checks_run(["pass-check"])
    binding = forge.ledger.records("execution_receipt_binding")[0].payload.to_object_dict()
    binding["schema_version"] = "2"
    with pytest.raises(ForgeError) as issue:
        parse_record(binding, expected_type=RecordType.EXECUTION_RECEIPT_BINDING)
    assert issue.value.code == "UNSUPPORTED_RECORD_VERSION"


def test_historical_state_remains_readable_without_receipts(config: ForgeConfig) -> None:
    from pathlib import Path

    legacy = Path("tests/fixtures/legacy-0.1/complete-state")
    ledger_kinds = {
        json.loads(line)["kind"]
        for line in (legacy / "ledger.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    }
    assert "execution_receipt_binding" not in ledger_kinds
    assert "workflow_action" not in ledger_kinds
    forge = Forge(config)
    verified = forge.ledger_verify()
    assert verified["ok"] is True
    assert CURRENT_SCHEMA_VERSION == "1"


def test_wrong_candidate_filter_does_not_return_other_receipts(config: ForgeConfig) -> None:
    forge = Forge(config)
    begin(forge)
    candidate = register(forge)
    forge.development_checks_run(["pass-check"], str(candidate["candidate_id"]))
    listed = forge.execution_receipts_list("forge-tree-sha256-v1:" + "0" * 64)
    assert listed["count"] == 0
    with pytest.raises(ForgeError) as issue:
        forge.execution_receipts_get("execution-receipt-binding:" + "0" * 64)
    assert issue.value.code == "RECORD_NOT_FOUND"


def test_interrupted_binding_commit_recovers(tmp_path: Path) -> None:
    from mncs_forge.ledger import Ledger
    from mncs_forge.record_store import LocalRecordStore

    class InjectedFailure(RuntimeError):
        pass

    def inject(name: str) -> None:
        if name == "after_prepared":
            raise InjectedFailure(name)

    record = new_record(
        RecordType.EXECUTION_RECEIPT_BINDING,
        {
            "project_identity": "fixture-v1",
            "epoch_identity": None,
            "candidate_identity": "project:fixture-v1",
            "action_kind": "workflow_action",
            "action_identity": "workflow-action:" + "1" * 64,
            "result_identity": None,
            "request_identity": None,
            "workflow_or_verifier": "pass-check",
            "runner_identity": "runner.local-process-v1",
            "runner_kind": "local-process",
            "runner_version": "1",
            "worker_identity": None,
            "host_identity": None,
            "os_family": "linux",
            "architecture": "x86_64",
            "executable_identity": None,
            "image_identity": None,
            "environment_identity": "a" * 64,
            "execution_scope": "local",
            "termination_category": "timeout",
            "receipt_schema_version": None,
            "receipt_identity": None,
            "receipt_completeness": "incomplete",
            "status": "UNKNOWN",
            "established_properties": {
                "execution_completed": "unknown",
                "local_result_validity": "unknown",
                "runner_capability": "established",
                "filesystem_isolation": "not-established",
                "network_isolation": "not-established",
                "containerization": "not-established",
                "same_operator_execution": "established",
                "external_anchoring": "not-established",
                "witnessing": "not-established",
                "protected_custody": "not-established",
                "evaluator_independence": "not-established",
                "governance_certification": "not-established",
            },
            "mncs_receipt": None,
            "recorded_at": "2026-01-01T00:00:00+00:00",
        },
    )
    with pytest.raises(InjectedFailure):
        LocalRecordStore(tmp_path, failpoint=inject).commit(
            "execution-receipt-bindings", "execution_receipt_binding", record
        )
    recovered = LocalRecordStore(tmp_path)
    verification = Ledger(tmp_path).verify()
    assert verification["ok"] is True
    assert verification["entries"] == 1
    assert recovered.recover() == {"completed": 0, "abandoned": 0}


def test_canonical_binding_bytes_round_trip(config: ForgeConfig) -> None:
    forge = Forge(config)
    begin(forge)
    register(forge)
    forge.development_checks_run(["pass-check"])
    binding = forge.ledger.records("execution_receipt_binding")[0].payload
    encoded = canonical_bytes(binding.to_json())
    parsed = parse_record(json.loads(encoded), expected_type=RecordType.EXECUTION_RECEIPT_BINDING)
    assert parsed.to_json() == binding.to_json()


def test_verifier_run_persists_verifier_action_receipt_binding(
    config: ForgeConfig,
) -> None:
    forge = Forge(config)
    begin(forge)
    candidate = register(forge)

    result = forge.verifier_run(
        "verify-pass",
        changed_paths=["candidate/main.py"],
        scope="file",
    )

    assert result["status"] == "PASS"
    summary = result["execution_receipt"]
    assert isinstance(summary, dict)
    assert summary["receipt_completeness"] == "complete"
    assert summary["status"] == "UNKNOWN"
    assert summary["termination_category"] == "completed"
    assert summary["result_identity"] == result["output_identity"]
    bindings = forge.ledger.records("execution_receipt_binding")
    assert len(bindings) == 1
    binding = bindings[0].payload
    assert binding["action_kind"] == "verifier_action"
    assert binding["workflow_or_verifier"] == "verify-pass"
    assert binding["candidate_identity"] == candidate["candidate_id"]
    assert binding["result_identity"] == result["output_identity"]
    assert isinstance(binding["mncs_receipt"], Mapping)
    assert forge.ledger.verify()["ok"] is True
    listed = forge.execution_receipts_list()
    assert listed["count"] == 1


def test_timeout_verifier_run_persists_incomplete_binding(config: ForgeConfig) -> None:
    forge = Forge(config)
    begin(forge)
    register(forge)

    result = forge.verifier_run(
        "verify-timeout",
        changed_paths=["candidate/main.py"],
        scope="file",
    )

    assert result["status"] == "UNKNOWN"
    summary = result.get("execution_receipt")
    assert isinstance(summary, dict)
    assert summary["receipt_completeness"] == "incomplete"
    assert summary["termination_category"] == "timeout"
    assert summary["status"] == "UNKNOWN"
    properties = summary["established_properties"]
    assert isinstance(properties, Mapping)
    assert properties["execution_completed"] == "unknown"


def test_tampered_verifier_binding_fails_closed(config: ForgeConfig) -> None:
    forge = Forge(config)
    begin(forge)
    register(forge)
    forge.verifier_run(
        "verify-pass",
        changed_paths=["candidate/main.py"],
        scope="file",
    )
    binding = forge.ledger.records("execution_receipt_binding")[0].payload
    tampered = binding.to_object_dict()
    receipt = tampered["mncs_receipt"]
    assert isinstance(receipt, dict)
    process = receipt["process"]
    if isinstance(process, dict):
        process["harness_status"] = "PASS"  # type: ignore[index]
    with pytest.raises(ForgeError) as issue:
        parse_record(tampered, expected_type=RecordType.EXECUTION_RECEIPT_BINDING)
    assert issue.value.code == "RECORD_IDENTITY"
