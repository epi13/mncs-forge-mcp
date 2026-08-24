"""Identity-bound Forge persistence for experimental MNCS execution receipts.

The upstream MNCS envelope remains a referenced companion object. This module
records Forge linkage and completeness; it does not reinterpret harness status,
create sandbox assurance, or claim independence.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from ..config import ForgeConfig, Workflow
from ..errors import ForgeError
from ..execution_observations import canonical_sha256
from ..mncs_execution_receipt import ReceiptContext, build_mncs_execution_receipt
from ..ports import ExecutionObservation, ExecutionSession, RecordCommitter, RecordReader
from ..records import (
    ESTABLISHED_PROPERTY_KEYS,
    BundleRecord,
    ExecutionReceiptBindingRecord,
    FinalEvaluationRecord,
    ForgeRecord,
    RecordType,
    WorkflowActionRecord,
    WorkflowResultRecord,
    new_record,
)
from .support import now

ReceiptCompleteness = Literal["complete", "incomplete", "malformed", "unsupported", "unavailable"]
PropertyState = Literal["established", "not-established", "unknown"]
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_INCOMPLETE_TERMINATIONS = frozenset(
    {
        "timeout",
        "output-limit",
        "crash",
        "cancelled",
        "internal-runner-error",
        "policy-rejected",
        "resource-limit",
    }
)


@dataclass(frozen=True, slots=True)
class WorkflowExecution:
    """One declared-workflow invocation and the records it can persist."""

    action: WorkflowActionRecord
    result: WorkflowResultRecord | FinalEvaluationRecord | BundleRecord | None
    session: ExecutionSession
    workflow: Workflow
    epoch_identity: str | None
    error: ForgeError | None


def sha256_digest(value: str | None) -> str | None:
    if value is None:
        return None
    if _SHA256.fullmatch(value):
        return value
    if value.startswith("sha256:") and _SHA256.fullmatch(value[7:]):
        return value[7:]
    if ":" in value:
        tail = value.rsplit(":", 1)[1]
        if _SHA256.fullmatch(tail):
            return tail
    return None


def content_digest(*parts: object) -> str:
    return canonical_sha256(list(parts))


def _bounded_id(prefix: str, value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:40]
    identifier = f"{prefix}{digest}"
    if _ID.fullmatch(identifier) is None:  # pragma: no cover - prefix is static
        raise ForgeError("RECEIPT_CONTEXT", "constructed receipt identifier is invalid")
    return identifier


def _subject_digest(candidate_identity: str) -> str:
    digest = sha256_digest(candidate_identity)
    if digest is not None:
        return digest
    return hashlib.sha256(candidate_identity.encode("utf-8")).hexdigest()


def _candidate_receipt_id(candidate_identity: str) -> str | None:
    if _ID.fullmatch(candidate_identity):
        return candidate_identity
    return None


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _parse_timestamp(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None


def _property(
    *,
    established: bool | None = None,
    unknown: bool = False,
) -> PropertyState:
    if unknown or established is None:
        return "unknown"
    return "established" if established else "not-established"


def established_properties(observation: ExecutionObservation) -> dict[str, PropertyState]:
    completed = observation.termination_category in {"completed", "nonzero-exit", "signal"}
    isolation = observation.capabilities
    return {
        "execution_completed": _property(established=completed, unknown=not completed),
        "local_result_validity": "unknown",
        "runner_capability": _property(
            established=isolation.timeout_enforcement == "enforced"
            and isolation.stdout_limit == "enforced"
            and isolation.stderr_limit == "enforced"
        ),
        "filesystem_isolation": _property(
            established=isolation.filesystem_isolation == "enforced",
            unknown=isolation.filesystem_isolation == "unknown",
        ),
        "network_isolation": _property(
            established=isolation.network_isolation == "enforced",
            unknown=isolation.network_isolation == "unknown",
        ),
        "containerization": _property(established=observation.image_identity is not None),
        "same_operator_execution": _property(
            established=observation.same_operator is True,
            unknown=observation.same_operator is None,
        ),
        "external_anchoring": "not-established",
        "witnessing": "not-established",
        "protected_custody": "not-established",
        "evaluator_independence": "not-established",
        "governance_certification": "not-established",
    }


def _completeness(observation: ExecutionObservation) -> ReceiptCompleteness:
    if observation.termination_category in _INCOMPLETE_TERMINATIONS:
        return "incomplete"
    if observation.started_at is None or observation.ended_at is None:
        return "incomplete"
    if observation.duration_seconds is None:
        return "incomplete"
    if observation.stdout.total_bytes is None or observation.stderr.total_bytes is None:
        return "incomplete"
    if observation.aggregate_output.total_bytes is None:
        return "incomplete"
    if observation.stdout.truncated is None or observation.stderr.truncated is None:
        return "incomplete"
    return "complete"


def binding_for_action(records: RecordReader, action_identity: str) -> ForgeRecord | None:
    for entry in records.records("execution_receipt_binding"):
        if entry.payload.get("action_identity") == action_identity:
            return entry.payload
    return None


def _receipt_context(
    *,
    config: ForgeConfig,
    workflow: Workflow,
    action: WorkflowActionRecord,
    observation: ExecutionObservation,
    result: ForgeRecord | None,
) -> ReceiptContext:
    requested_at = _parse_timestamp(str(action["requested_at"])) or datetime.now(UTC)
    timeout = timedelta(seconds=max(observation.timeout_seconds, 0))
    action_identity = str(action["action_id"])
    candidate_identity = str(action["candidate_identity"])
    bundle_identity = content_digest(
        {
            "kind": "forge-declared-workflow",
            "project_identity": config.project_identity,
            "workflow": workflow.name,
            "command": list(workflow.command),
            "category": workflow.category,
            "subject": workflow.subject,
        }
    )
    policy_identity = content_digest(
        {
            "timeout_seconds": observation.timeout_seconds,
            "stdout_limit": observation.stdout_limit,
            "stderr_limit": observation.stderr_limit,
            "shell": False,
            "environment_keys": sorted(config.environment(workflow)),
            "filesystem_policy": observation.filesystem_policy,
            "network_policy": observation.network_policy,
        }
    )
    harness_identity = content_digest(
        {
            "runner_identity": observation.runner_identity,
            "runner_version": observation.runner_version,
            "runner_kind": observation.capabilities.runner_kind,
        }
    )
    _ = result
    return ReceiptContext(
        record_id=_bounded_id("receipt.", action_identity),
        subject_family="MNCS",
        subject_kind="development-record",
        subject_record_id=_bounded_id("subject.", action_identity),
        subject_canonical_sha256=_subject_digest(candidate_identity),
        candidate_id=_candidate_receipt_id(candidate_identity),
        test_bundle_identity=bundle_identity,
        harness_identity=harness_identity,
        input_snapshot_identity=None,
        execution_policy_identity=policy_identity,
        placement_policy_identity=sha256_digest(observation.placement_identity),
        result_semantics=(
            "Forge records execution provenance only; workflow exit zero is not evidence PASS, "
            "and this receipt does not establish sandbox, independence, or custody."
        ),
        challenge_nonce=_bounded_id("challenge.", action_identity),
        challenge_issued_at=_iso(requested_at),
        challenge_expires_at=_iso(requested_at + timeout + timedelta(seconds=1)),
        observed_at=observation.ended_at or _iso(datetime.now(UTC)),
        harness_status="UNKNOWN",
        command_binding="enforced",
        environment_binding="enforced",
        test_bundle_integrity="unknown",
        result_integrity="unknown",
    )


def _envelope(
    *,
    observation: ExecutionObservation,
    completeness: ReceiptCompleteness,
    context: ReceiptContext,
) -> tuple[dict[str, object] | None, str | None, str | None, ReceiptCompleteness]:
    """Build the upstream MNCS envelope or explain why it cannot be built."""

    if completeness != "complete":
        return None, None, None, completeness
    try:
        receipt = build_mncs_execution_receipt(observation, context)
    except ForgeError as exc:
        if exc.code in {"RECEIPT_CONTEXT", "RECEIPT_OBSERVATION"}:
            return (
                None,
                None,
                None,
                ("malformed" if exc.code == "RECEIPT_CONTEXT" else "incomplete"),
            )
        raise
    identity = receipt.get("receipt_identity")
    if not isinstance(identity, str) or not _SHA256.fullmatch(identity):
        return None, None, None, "malformed"
    version = receipt.get("schema_version")
    schema_version = version if isinstance(version, str) else None
    return receipt, identity, schema_version, completeness


def _binding_record(
    *,
    config: ForgeConfig,
    epoch_identity: str | None,
    candidate_identity: object,
    action_kind: Literal["workflow_action", "verifier_action"],
    action_identity: str,
    request_identity: object,
    workflow_or_verifier: str,
    result_identity: str | None,
    observation: ExecutionObservation,
    receipt: dict[str, object] | None,
    receipt_identity: str | None,
    schema_version: str | None,
    completeness: ReceiptCompleteness,
) -> ExecutionReceiptBindingRecord:
    record = new_record(
        RecordType.EXECUTION_RECEIPT_BINDING,
        {
            "project_identity": config.project_identity,
            "epoch_identity": epoch_identity,
            "candidate_identity": candidate_identity,
            "action_kind": action_kind,
            "action_identity": action_identity,
            "result_identity": result_identity,
            "request_identity": request_identity if isinstance(request_identity, str) else None,
            "workflow_or_verifier": workflow_or_verifier,
            "runner_identity": observation.runner_identity,
            "runner_kind": observation.capabilities.runner_kind,
            "runner_version": observation.runner_version,
            "worker_identity": observation.worker_identity,
            "host_identity": observation.host_identity,
            "os_family": observation.capabilities.os_family,
            "architecture": observation.capabilities.architecture,
            "executable_identity": observation.executable_identity,
            "image_identity": observation.image_identity,
            "environment_identity": observation.environment_identity,
            "execution_scope": observation.capabilities.execution_scope,
            "termination_category": observation.termination_category,
            "receipt_schema_version": schema_version,
            "receipt_identity": receipt_identity,
            "receipt_completeness": completeness,
            "status": "UNKNOWN",
            "established_properties": established_properties(observation),
            "mncs_receipt": receipt,
            "recorded_at": now(),
        },
    )
    if not isinstance(record, ExecutionReceiptBindingRecord):
        raise ForgeError("INTERNAL_RECORD", "execution receipt binding produced an invalid model")
    properties = record["established_properties"]
    if not isinstance(properties, Mapping) or set(properties) != set(ESTABLISHED_PROPERTY_KEYS):
        raise ForgeError("INTERNAL_RECORD", "execution receipt properties are incomplete")
    return record


def bind_workflow_execution(
    *,
    config: ForgeConfig,
    execution: WorkflowExecution,
) -> ExecutionReceiptBindingRecord:
    """Build one identity-bound Forge receipt record from a workflow execution."""

    observation = execution.session.observation
    completeness = _completeness(observation)
    receipt, receipt_identity, schema_version, completeness = _envelope(
        observation=observation,
        completeness=completeness,
        context=_receipt_context(
            config=config,
            workflow=execution.workflow,
            action=execution.action,
            observation=observation,
            result=execution.result,
        ),
    )
    result_identity = None
    if execution.result is not None:
        output = execution.result.get("output_identity")
        result_identity = output if isinstance(output, str) else None
    return _binding_record(
        config=config,
        epoch_identity=execution.epoch_identity,
        candidate_identity=execution.action["candidate_identity"],
        action_kind="workflow_action",
        action_identity=str(execution.action["action_id"]),
        request_identity=execution.action.get("protocol_request_identity"),
        workflow_or_verifier=execution.workflow.name,
        result_identity=result_identity,
        observation=observation,
        receipt=receipt,
        receipt_identity=receipt_identity,
        schema_version=schema_version,
        completeness=completeness,
    )


def bind_verifier_execution(
    *,
    config: ForgeConfig,
    session: ExecutionSession,
    action: Mapping[str, object],
    result_identity: str | None,
    verifier_id: str,
    verifier_version: str,
    provider_id: str,
) -> ExecutionReceiptBindingRecord:
    """Build one identity-bound Forge receipt record from a verifier execution.

    The binding records execution provenance only. It never upgrades the
    underlying verifier status and it cannot become evidence ``PASS``.
    """

    observation = session.observation
    action_identity = str(action["action_id"])
    candidate_identity = str(action["candidate_identity"])
    completeness = _completeness(observation)
    requested_at = _parse_timestamp(str(action["requested_at"])) or datetime.now(UTC)
    timeout = timedelta(seconds=max(observation.timeout_seconds, 0))
    bundle_identity = content_digest(
        {
            "kind": "forge-verifier-action",
            "project_identity": config.project_identity,
            "verifier_id": verifier_id,
            "verifier_version": verifier_version,
            "provider_id": provider_id,
            "method": action.get("method"),
        }
    )
    policy_identity = content_digest(
        {
            "timeout_seconds": observation.timeout_seconds,
            "stdout_limit": observation.stdout_limit,
            "stderr_limit": observation.stderr_limit,
            "shell": False,
            "environment_identity": str(action.get("environment_identity") or ""),
            "filesystem_policy": observation.filesystem_policy,
            "network_policy": observation.network_policy,
        }
    )
    harness_identity = content_digest(
        {
            "runner_identity": observation.runner_identity,
            "runner_version": observation.runner_version,
            "runner_kind": observation.capabilities.runner_kind,
        }
    )
    context = ReceiptContext(
        record_id=_bounded_id("receipt.", f"verifier:{action_identity}"),
        subject_family="MNCS",
        subject_kind="development-record",
        subject_record_id=_bounded_id("subject.", f"verifier:{action_identity}"),
        subject_canonical_sha256=_subject_digest(candidate_identity),
        candidate_id=_candidate_receipt_id(candidate_identity),
        test_bundle_identity=bundle_identity,
        harness_identity=harness_identity,
        input_snapshot_identity=None,
        execution_policy_identity=policy_identity,
        placement_policy_identity=sha256_digest(observation.placement_identity),
        result_semantics=(
            "Forge records verifier execution provenance only; the bound verifier "
            "result retains its own PASS/FAIL/UNKNOWN semantics and this receipt "
            "does not establish sandbox, independence, or custody."
        ),
        challenge_nonce=_bounded_id("challenge.", f"verifier:{action_identity}"),
        challenge_issued_at=_iso(requested_at),
        challenge_expires_at=_iso(requested_at + timeout + timedelta(seconds=1)),
        observed_at=observation.ended_at or _iso(datetime.now(UTC)),
        harness_status="UNKNOWN",
        command_binding="enforced",
        environment_binding="enforced",
        test_bundle_integrity="unknown",
        result_integrity="unknown",
    )
    receipt, receipt_identity, schema_version, completeness = _envelope(
        observation=observation,
        completeness=completeness,
        context=context,
    )
    return _binding_record(
        config=config,
        epoch_identity=str(action["epoch_identity"]) if action.get("epoch_identity") else None,
        candidate_identity=action["candidate_identity"],
        action_kind="verifier_action",
        action_identity=action_identity,
        request_identity=action.get("protocol_request_identity"),
        workflow_or_verifier=verifier_id,
        result_identity=result_identity,
        observation=observation,
        receipt=receipt,
        receipt_identity=receipt_identity,
        schema_version=schema_version,
        completeness=completeness,
    )


RESULT_COMMIT_CONTEXTS: dict[RecordType, tuple[str, str]] = {
    RecordType.WORKFLOW_RESULT: ("results", "result"),
    RecordType.FINAL_EVALUATION: ("evaluations", "evaluation"),
    RecordType.BUNDLE: ("bundles", "bundle"),
}


def persist_workflow_execution(
    *,
    config: ForgeConfig,
    records: RecordReader,
    record_store: RecordCommitter,
    execution: WorkflowExecution,
) -> ExecutionReceiptBindingRecord:
    """Persist action, receipt binding, and optional result without mutating history."""

    action_identity = str(execution.action["action_id"])
    if binding_for_action(records, action_identity) is not None:
        raise ForgeError(
            "RECEIPT_DUPLICATE",
            f"execution receipt binding already exists for {action_identity}",
        )
    record_store.commit("workflow-actions", "workflow_action", execution.action)
    binding = bind_workflow_execution(config=config, execution=execution)
    record_store.commit("execution-receipt-bindings", "execution_receipt_binding", binding)
    if execution.result is not None:
        try:
            group, kind = RESULT_COMMIT_CONTEXTS[execution.result.record_type]
        except KeyError as exc:
            raise ForgeError("INTERNAL_RECORD", "unsupported workflow result type") from exc
        record_store.commit(group, kind, execution.result)
    return binding


def summarize_binding(record: Mapping[str, object]) -> dict[str, object]:
    established = record.get("established_properties")
    if isinstance(established, Mapping):
        established = dict(established)
    return {
        "binding_id": record.get("binding_id"),
        "action_identity": record.get("action_identity"),
        "result_identity": record.get("result_identity"),
        "receipt_identity": record.get("receipt_identity"),
        "receipt_completeness": record.get("receipt_completeness"),
        "status": record.get("status"),
        "termination_category": record.get("termination_category"),
        "runner_kind": record.get("runner_kind"),
        "execution_scope": record.get("execution_scope"),
        "established_properties": established,
    }


def list_bindings(
    records: RecordReader,
    *,
    candidate_identity: str | None = None,
    action_identity: str | None = None,
) -> dict[str, object]:
    bindings: list[dict[str, object]] = []
    for entry in records.records("execution_receipt_binding"):
        payload = entry.payload
        if (
            candidate_identity is not None
            and payload.get("candidate_identity") != candidate_identity
        ):
            continue
        if action_identity is not None and payload.get("action_identity") != action_identity:
            continue
        bindings.append(summarize_binding(payload))
    return {
        "execution_receipts": bindings,
        "count": len(bindings),
        "dominance": "FAIL > UNKNOWN > PASS",
        "note": (
            "A complete receipt binding is provenance, not evidence PASS, sandbox isolation, "
            "independence, or protected custody."
        ),
    }


def get_binding(records: RecordReader, binding_id: str) -> dict[str, object]:
    for entry in reversed(records.records("execution_receipt_binding")):
        payload = entry.payload
        if payload.get("binding_id") == binding_id:
            return payload.to_object_dict()
    raise ForgeError("RECORD_NOT_FOUND", f"no execution receipt binding for {binding_id}")
