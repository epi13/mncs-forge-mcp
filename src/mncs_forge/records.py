"""Frozen Forge record models, canonical identities, and deterministic migrations."""

from __future__ import annotations

import math
import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType
from typing import TypeAlias, cast

from .errors import ForgeError
from .serialization import local_json_identity, read_json

CURRENT_SCHEMA_VERSION = "1"
LEGACY_SCHEMA_VERSION = "0.1-unversioned"

JsonScalar: TypeAlias = None | bool | int | float | str
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]
JsonObject: TypeAlias = dict[str, JsonValue]
FrozenJsonValue: TypeAlias = (
    JsonScalar | tuple["FrozenJsonValue", ...] | Mapping[str, "FrozenJsonValue"]
)


class RecordType(StrEnum):
    EPOCH = "epoch"
    CANDIDATE = "candidate"
    PROVIDER_PROBE = "provider_probe"
    WORKFLOW_ACTION = "workflow_action"
    WORKFLOW_RESULT = "workflow_result"
    VERIFIER_ACTION = "verifier_action"
    VERIFIER_RESULT = "verifier_result"
    CANDIDATE_DISPOSITION = "candidate_disposition"
    FREEZE = "freeze"
    FINAL_EVALUATION = "final_evaluation"
    RECONCILIATION = "reconciliation"
    BUNDLE = "bundle"
    LEDGER_ENTRY = "ledger_entry"


@dataclass(frozen=True, slots=True)
class RecordSpec:
    required: frozenset[str]
    optional: frozenset[str] = frozenset({"extensions"})
    identity_field: str | None = None
    identity_prefix: str | None = None
    identity_exclusions: frozenset[str] = frozenset()
    status_field: str | None = None

    @property
    def allowed(self) -> frozenset[str]:
        return self.required | self.optional


WORKFLOW_RESULT_FIELDS = frozenset(
    {
        "candidate_identity",
        "subject_type",
        "provider_or_evaluator_identity",
        "method",
        "workflow",
        "category",
        "scope",
        "environment",
        "duration_seconds",
        "status",
        "witnesses_or_counterexamples",
        "limitations",
        "unsupported_constructs",
        "stderr_diagnostic",
        "returncode",
        "recorded_at",
        "protocol_request_identity",
        "output_identity",
    }
)

RECORD_SPECS: dict[RecordType, RecordSpec] = {
    RecordType.EPOCH: RecordSpec(
        required=frozenset(
            {
                "baseline_identity",
                "generator_identity",
                "evaluator_identity",
                "contract_identity",
                "objective_identity",
                "visible_partition_identities",
                "authority_identities",
                "declared_authority_overlap",
                "parent_epoch",
                "created_at",
                "epoch_id",
            }
        ),
        identity_field="epoch_id",
        identity_prefix="epoch:",
    ),
    RecordType.CANDIDATE: RecordSpec(
        required=frozenset(
            {
                "candidate_id",
                "parent_candidate",
                "changed_files",
                "declared_hypothesis",
                "generator_identity",
                "generator_configuration_identity",
                "source_epoch",
                "registered_at",
                "current_file_identities",
                "useful_benefit_objective",
                "objective_identity",
                "supersedes",
            }
        )
    ),
    RecordType.PROVIDER_PROBE: RecordSpec(
        required=frozenset(
            {
                "provider_id",
                "name",
                "declared_identity",
                "declared_version",
                "command",
                "transport",
                "required",
                "declared_capabilities",
                "supported_constructs",
                "unsupported_constructs",
                "limitations",
                "expected_executable_identity",
                "descriptor",
                "availability",
                "status",
                "probe_kind",
                "provider_identity",
                "executable",
                "executable_identity",
                "probed_capabilities",
                "recorded_at",
                "output_identity",
            }
        ),
        optional=frozenset(
            {
                "protocol_statuses",
                "cancellation",
                "health_checks",
                "duration_seconds",
                "stderr_diagnostic",
                "returncode",
                "error_code",
                "extensions",
            }
        ),
        identity_field="output_identity",
        identity_prefix="forge-json-sha256-v1:",
        status_field="status",
    ),
    RecordType.WORKFLOW_ACTION: RecordSpec(
        required=frozenset(
            {
                "workflow",
                "candidate_identity",
                "mode",
                "protocol_request_identity",
                "requested_at",
            }
        )
    ),
    RecordType.WORKFLOW_RESULT: RecordSpec(
        required=WORKFLOW_RESULT_FIELDS,
        identity_field="output_identity",
        identity_prefix="forge-json-sha256-v1:",
        status_field="status",
    ),
    RecordType.VERIFIER_ACTION: RecordSpec(
        required=frozenset(
            {
                "verifier_id",
                "verifier_version",
                "verifier_identity",
                "provider_id",
                "provider_configuration_identity",
                "method",
                "mode",
                "epoch_identity",
                "candidate_identity",
                "candidate_parent_identity",
                "freeze_identity",
                "supersedes_output_identity",
                "scope",
                "changed_paths",
                "source_region",
                "input_identities",
                "configuration_identity",
                "policy_identity",
                "environment_identity",
                "requested_at",
                "protocol_request_identity",
                "action_id",
            }
        ),
        identity_field="action_id",
        identity_prefix="verifier-action:",
        identity_exclusions=frozenset({"protocol_request_identity"}),
    ),
    RecordType.VERIFIER_RESULT: RecordSpec(
        required=frozenset(
            {
                "action_id",
                "verifier_id",
                "verifier_version",
                "verifier_identity",
                "claim",
                "category",
                "provider_id",
                "provider_configuration_identity",
                "provider_executable_identity",
                "provider_identity",
                "provider_response_identity",
                "method",
                "mode",
                "evidence_class",
                "independent_evaluation",
                "iterative_development_overlap",
                "epoch_identity",
                "candidate_identity",
                "candidate_parent_identity",
                "freeze_identity",
                "supersedes_output_identity",
                "input_identities",
                "configuration_identity",
                "policy_identity",
                "environment_identity",
                "status",
                "summary",
                "witnesses",
                "assumptions",
                "limitations",
                "unsupported_constructs",
                "dependency_envelope",
                "duration_seconds",
                "stderr_diagnostic",
                "returncode",
                "operational_error",
                "disclosure",
                "recorded_at",
                "output_identity",
            }
        ),
        identity_field="output_identity",
        identity_prefix="forge-json-sha256-v1:",
        status_field="status",
    ),
    RecordType.CANDIDATE_DISPOSITION: RecordSpec(
        required=frozenset(
            {
                "candidate_identity",
                "disposition",
                "reason",
                "selection_rule",
                "selection_policy_identity",
                "evidence_status",
                "recorded_at",
                "disposition_id",
            }
        ),
        identity_field="disposition_id",
        identity_prefix="disposition:",
        status_field="evidence_status",
    ),
    RecordType.FREEZE: RecordSpec(
        required=frozenset(
            {
                "candidate_identity",
                "contract_identity",
                "reference_identity",
                "evaluator_identity",
                "acceptance_policy_identity",
                "protected_identity",
                "selection_record",
                "environment",
                "required_evidence_plan",
                "required_evidence_plan_identity",
                "frozen_path_sets",
                "frozen_at",
                "freeze_id",
            }
        ),
        identity_field="freeze_id",
        identity_prefix="freeze:",
    ),
    RecordType.FINAL_EVALUATION: RecordSpec(
        required=WORKFLOW_RESULT_FIELDS,
        identity_field="output_identity",
        identity_prefix="forge-json-sha256-v1:",
        status_field="status",
    ),
    RecordType.RECONCILIATION: RecordSpec(
        required=frozenset(
            {
                "candidate_identity",
                "required_gate_aggregation",
                "categories",
                "conflicting_evidence",
                "stale_identities",
                "claim_limitations",
                "unresolved_blockers",
                "dominance",
                "normative_logic_delegated",
            }
        ),
        status_field="required_gate_aggregation",
    ),
    RecordType.BUNDLE: RecordSpec(
        required=WORKFLOW_RESULT_FIELDS,
        identity_field="output_identity",
        identity_prefix="forge-json-sha256-v1:",
        status_field="status",
    ),
}

LEDGER_REQUIRED = frozenset(
    {"sequence", "timestamp", "kind", "previous_hash", "payload", "entry_hash"}
)

LEDGER_KIND_TYPES: dict[str, RecordType] = {
    "epoch": RecordType.EPOCH,
    "candidate": RecordType.CANDIDATE,
    "provider_probe": RecordType.PROVIDER_PROBE,
    "result": RecordType.WORKFLOW_RESULT,
    "verifier_action": RecordType.VERIFIER_ACTION,
    "verifier_result": RecordType.VERIFIER_RESULT,
    "disposition": RecordType.CANDIDATE_DISPOSITION,
    "freeze": RecordType.FREEZE,
    "evaluation": RecordType.FINAL_EVALUATION,
    "bundle": RecordType.BUNDLE,
}

RECORD_GROUP_TYPES: dict[str, RecordType] = {
    "epochs": RecordType.EPOCH,
    "candidates": RecordType.CANDIDATE,
    "provider-probes": RecordType.PROVIDER_PROBE,
    "results": RecordType.WORKFLOW_RESULT,
    "verifier-actions": RecordType.VERIFIER_ACTION,
    "verifier-results": RecordType.VERIFIER_RESULT,
    "dispositions": RecordType.CANDIDATE_DISPOSITION,
    "freezes": RecordType.FREEZE,
    "evaluations": RecordType.FINAL_EVALUATION,
    "bundles": RecordType.BUNDLE,
}


@dataclass(frozen=True, slots=True)
class PersistedRecordContext:
    """Trusted storage context for a ledger-backed immutable record."""

    group: str
    ledger_kind: str
    record_type: RecordType
    identity_field: str


PERSISTED_RECORD_CONTEXTS: dict[str, PersistedRecordContext] = {
    "epoch": PersistedRecordContext("epochs", "epoch", RecordType.EPOCH, "epoch_id"),
    "candidate": PersistedRecordContext(
        "candidates", "candidate", RecordType.CANDIDATE, "candidate_id"
    ),
    "provider_probe": PersistedRecordContext(
        "provider-probes", "provider_probe", RecordType.PROVIDER_PROBE, "output_identity"
    ),
    "result": PersistedRecordContext(
        "results", "result", RecordType.WORKFLOW_RESULT, "output_identity"
    ),
    "verifier_action": PersistedRecordContext(
        "verifier-actions", "verifier_action", RecordType.VERIFIER_ACTION, "action_id"
    ),
    "verifier_result": PersistedRecordContext(
        "verifier-results", "verifier_result", RecordType.VERIFIER_RESULT, "output_identity"
    ),
    "disposition": PersistedRecordContext(
        "dispositions",
        "disposition",
        RecordType.CANDIDATE_DISPOSITION,
        "disposition_id",
    ),
    "freeze": PersistedRecordContext("freezes", "freeze", RecordType.FREEZE, "freeze_id"),
    "evaluation": PersistedRecordContext(
        "evaluations", "evaluation", RecordType.FINAL_EVALUATION, "output_identity"
    ),
    "bundle": PersistedRecordContext("bundles", "bundle", RecordType.BUNDLE, "output_identity"),
}


def persisted_record_context(*, group: str, ledger_kind: str) -> PersistedRecordContext:
    """Resolve and cross-check the complete immutable/ledger storage context."""

    try:
        context = PERSISTED_RECORD_CONTEXTS[ledger_kind]
    except KeyError as exc:
        raise ForgeError("RECORD_CONTEXT", f"unsupported ledger kind: {ledger_kind}") from exc
    if context.group != group:
        raise ForgeError(
            "RECORD_CONTEXT",
            f"ledger kind {ledger_kind} requires immutable group {context.group}, got {group}",
        )
    return context


def immutable_record_path(state_dir: Path, group: str, identity: str) -> Path:
    """Return the canonical contained path for an immutable record identity."""

    safe_identity = safe_record_identity(identity)
    return state_dir / "records" / group / f"{safe_identity}.json"


def safe_record_identity(identity: str) -> str:
    """Encode an evidence identity as one portable local filename component."""

    if not identity or identity in {".", ".."}:
        raise ForgeError("RECORD_IDENTITY", "immutable record identity is empty or invalid")
    safe_identity = re.sub(r"[^A-Za-z0-9._-]", "_", identity)
    if not safe_identity:
        raise ForgeError("RECORD_IDENTITY", "immutable record identity has no safe path form")
    return safe_identity


REQUIRED_STRING_FIELDS: dict[RecordType, frozenset[str]] = {
    RecordType.EPOCH: frozenset(
        {
            "baseline_identity",
            "generator_identity",
            "evaluator_identity",
            "contract_identity",
            "objective_identity",
            "created_at",
            "epoch_id",
        }
    ),
    RecordType.CANDIDATE: frozenset(
        {
            "candidate_id",
            "declared_hypothesis",
            "generator_identity",
            "generator_configuration_identity",
            "source_epoch",
            "registered_at",
            "useful_benefit_objective",
            "objective_identity",
        }
    ),
    RecordType.PROVIDER_PROBE: frozenset(
        {
            "provider_id",
            "name",
            "transport",
            "availability",
            "status",
            "probe_kind",
            "recorded_at",
            "output_identity",
        }
    ),
    RecordType.WORKFLOW_ACTION: frozenset(
        {"workflow", "candidate_identity", "mode", "requested_at"}
    ),
    RecordType.WORKFLOW_RESULT: frozenset(
        {
            "candidate_identity",
            "subject_type",
            "method",
            "workflow",
            "category",
            "scope",
            "status",
            "recorded_at",
            "output_identity",
        }
    ),
    RecordType.VERIFIER_ACTION: frozenset(
        {
            "verifier_id",
            "verifier_version",
            "verifier_identity",
            "provider_id",
            "provider_configuration_identity",
            "method",
            "mode",
            "epoch_identity",
            "candidate_identity",
            "scope",
            "configuration_identity",
            "policy_identity",
            "environment_identity",
            "requested_at",
            "protocol_request_identity",
            "action_id",
        }
    ),
    RecordType.VERIFIER_RESULT: frozenset(
        {
            "action_id",
            "verifier_id",
            "verifier_version",
            "verifier_identity",
            "claim",
            "category",
            "provider_id",
            "provider_configuration_identity",
            "method",
            "mode",
            "evidence_class",
            "epoch_identity",
            "candidate_identity",
            "configuration_identity",
            "policy_identity",
            "environment_identity",
            "status",
            "summary",
            "disclosure",
            "recorded_at",
            "output_identity",
        }
    ),
    RecordType.CANDIDATE_DISPOSITION: frozenset(
        {
            "candidate_identity",
            "disposition",
            "reason",
            "selection_rule",
            "selection_policy_identity",
            "evidence_status",
            "recorded_at",
            "disposition_id",
        }
    ),
    RecordType.FREEZE: frozenset(
        {
            "candidate_identity",
            "contract_identity",
            "reference_identity",
            "evaluator_identity",
            "acceptance_policy_identity",
            "protected_identity",
            "selection_record",
            "environment",
            "required_evidence_plan",
            "required_evidence_plan_identity",
            "frozen_at",
            "freeze_id",
        }
    ),
    RecordType.FINAL_EVALUATION: frozenset(
        {
            "candidate_identity",
            "subject_type",
            "method",
            "workflow",
            "category",
            "scope",
            "status",
            "recorded_at",
            "output_identity",
        }
    ),
    RecordType.RECONCILIATION: frozenset(
        {
            "required_gate_aggregation",
            "dominance",
            "normative_logic_delegated",
        }
    ),
    RecordType.BUNDLE: frozenset(
        {
            "candidate_identity",
            "subject_type",
            "method",
            "workflow",
            "category",
            "scope",
            "status",
            "recorded_at",
            "output_identity",
        }
    ),
}

REQUIRED_OBJECT_FIELDS: dict[RecordType, frozenset[str]] = {
    RecordType.EPOCH: frozenset({"visible_partition_identities", "authority_identities"}),
    RecordType.CANDIDATE: frozenset({"current_file_identities"}),
    RecordType.WORKFLOW_RESULT: frozenset({"environment"}),
    RecordType.VERIFIER_ACTION: frozenset({"input_identities"}),
    RecordType.VERIFIER_RESULT: frozenset({"input_identities", "dependency_envelope"}),
    RecordType.FREEZE: frozenset({"frozen_path_sets"}),
    RecordType.FINAL_EVALUATION: frozenset({"environment"}),
    RecordType.RECONCILIATION: frozenset({"categories"}),
    RecordType.BUNDLE: frozenset({"environment"}),
}


def _freeze_json(value: JsonValue) -> FrozenJsonValue:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze_json(child) for key, child in value.items()})
    if isinstance(value, list):
        return tuple(_freeze_json(child) for child in value)
    return value


def _thaw_json(value: FrozenJsonValue) -> JsonValue:
    if isinstance(value, Mapping):
        return {key: _thaw_json(child) for key, child in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json(child) for child in value]
    return value


def _as_json_value(value: object, *, path: str = "$", depth: int = 0) -> JsonValue:
    if depth > 64:
        raise ForgeError("RECORD_MALFORMED", f"record JSON exceeds nesting limit at {path}")
    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ForgeError("RECORD_MALFORMED", f"record has non-finite number at {path}")
        return value
    if isinstance(value, (list, tuple)):
        return [
            _as_json_value(child, path=f"{path}[{index}]", depth=depth + 1)
            for index, child in enumerate(value)
        ]
    if isinstance(value, Mapping):
        result: JsonObject = {}
        for key, child in value.items():
            if not isinstance(key, str):
                raise ForgeError("RECORD_MALFORMED", f"record object key is not text at {path}")
            result[key] = _as_json_value(child, path=f"{path}.{key}", depth=depth + 1)
        return result
    raise ForgeError("RECORD_MALFORMED", f"record has non-JSON value at {path}")


def json_object(value: object, *, label: str = "record") -> JsonObject:
    normalized = _as_json_value(value, path=label)
    if not isinstance(normalized, dict):
        raise ForgeError("RECORD_MALFORMED", f"{label} must be a JSON object")
    return normalized


@dataclass(frozen=True, slots=True)
class ForgeRecord(Mapping[str, FrozenJsonValue]):
    """Immutable normalized record with JSON-compatible explicit codecs."""

    record_type: RecordType
    schema_version: str
    _fields: Mapping[str, FrozenJsonValue]
    source_schema_version: str = CURRENT_SCHEMA_VERSION

    def __getitem__(self, key: str) -> FrozenJsonValue:
        if key == "record_type":
            return self.record_type.value
        if key == "schema_version":
            return self.schema_version
        return self._fields[key]

    def __iter__(self) -> Iterator[str]:
        yield "record_type"
        yield "schema_version"
        yield from self._fields

    def __len__(self) -> int:
        return len(self._fields) + 2

    def to_json(self) -> JsonObject:
        result: JsonObject = {
            "record_type": self.record_type.value,
            "schema_version": self.schema_version,
        }
        result.update({key: _thaw_json(value) for key, value in self._fields.items()})
        return result

    def to_object_dict(self) -> dict[str, object]:
        """Return a mutable JSON object for CLI, MCP, or generic Python boundaries."""

        return cast(dict[str, object], self.to_json())

    @property
    def status(self) -> str | None:
        field = RECORD_SPECS[self.record_type].status_field
        value = self._fields.get(field) if field is not None else None
        return value if isinstance(value, str) else None

    @property
    def identity(self) -> str | None:
        field = RECORD_SPECS[self.record_type].identity_field
        value = self._fields.get(field) if field is not None else None
        return value if isinstance(value, str) else None


@dataclass(frozen=True, slots=True)
class EpochRecord(ForgeRecord):
    pass


@dataclass(frozen=True, slots=True)
class CandidateRecord(ForgeRecord):
    pass


@dataclass(frozen=True, slots=True)
class ProviderProbeRecord(ForgeRecord):
    pass


@dataclass(frozen=True, slots=True)
class WorkflowActionRecord(ForgeRecord):
    pass


@dataclass(frozen=True, slots=True)
class WorkflowResultRecord(ForgeRecord):
    pass


@dataclass(frozen=True, slots=True)
class VerifierActionRecord(ForgeRecord):
    pass


@dataclass(frozen=True, slots=True)
class VerifierResultRecord(ForgeRecord):
    pass


@dataclass(frozen=True, slots=True)
class CandidateDispositionRecord(ForgeRecord):
    pass


@dataclass(frozen=True, slots=True)
class FreezeRecord(ForgeRecord):
    pass


@dataclass(frozen=True, slots=True)
class FinalEvaluationRecord(ForgeRecord):
    pass


@dataclass(frozen=True, slots=True)
class ReconciliationRecord(ForgeRecord):
    pass


@dataclass(frozen=True, slots=True)
class BundleRecord(ForgeRecord):
    pass


MODEL_TYPES: dict[RecordType, type[ForgeRecord]] = {
    RecordType.EPOCH: EpochRecord,
    RecordType.CANDIDATE: CandidateRecord,
    RecordType.PROVIDER_PROBE: ProviderProbeRecord,
    RecordType.WORKFLOW_ACTION: WorkflowActionRecord,
    RecordType.WORKFLOW_RESULT: WorkflowResultRecord,
    RecordType.VERIFIER_ACTION: VerifierActionRecord,
    RecordType.VERIFIER_RESULT: VerifierResultRecord,
    RecordType.CANDIDATE_DISPOSITION: CandidateDispositionRecord,
    RecordType.FREEZE: FreezeRecord,
    RecordType.FINAL_EVALUATION: FinalEvaluationRecord,
    RecordType.RECONCILIATION: ReconciliationRecord,
    RecordType.BUNDLE: BundleRecord,
}


def _record_type(value: RecordType | str) -> RecordType:
    try:
        return value if isinstance(value, RecordType) else RecordType(value)
    except ValueError as exc:
        raise ForgeError("RECORD_TYPE_UNKNOWN", f"unknown Forge record type: {value}") from exc


def _status_is_valid(record_type: RecordType, fields: JsonObject) -> None:
    status_field = RECORD_SPECS[record_type].status_field
    if status_field is None:
        return
    status = fields.get(status_field)
    if status not in {"PASS", "FAIL", "UNKNOWN"}:
        raise ForgeError(
            "RECORD_STATUS",
            f"{record_type.value}.{status_field} must be PASS, FAIL, or UNKNOWN",
        )


def _validate_fields(record_type: RecordType, fields: JsonObject) -> None:
    spec = RECORD_SPECS[record_type]
    missing = sorted(spec.required.difference(fields))
    if missing:
        raise ForgeError(
            "RECORD_MISSING_FIELD",
            f"{record_type.value} is missing required fields: {', '.join(missing)}",
        )
    unknown = sorted(set(fields).difference(spec.allowed))
    if unknown:
        raise ForgeError(
            "RECORD_UNKNOWN_FIELD",
            f"{record_type.value} has unexpected fields: {', '.join(unknown)}",
        )
    extensions = fields.get("extensions")
    if extensions is not None and not isinstance(extensions, dict):
        raise ForgeError("RECORD_MALFORMED", "record extensions must be an object")
    invalid_strings = sorted(
        field
        for field in REQUIRED_STRING_FIELDS.get(record_type, frozenset())
        if not isinstance(fields.get(field), str) or not fields[field]
    )
    if invalid_strings:
        raise ForgeError(
            "RECORD_MALFORMED",
            f"{record_type.value} requires non-empty text fields: {', '.join(invalid_strings)}",
        )
    invalid_objects = sorted(
        field
        for field in REQUIRED_OBJECT_FIELDS.get(record_type, frozenset())
        if not isinstance(fields.get(field), dict)
    )
    if invalid_objects:
        raise ForgeError(
            "RECORD_MALFORMED",
            f"{record_type.value} requires object fields: {', '.join(invalid_objects)}",
        )
    mode = fields.get("mode")
    if mode is not None and mode not in {"development", "evaluator"}:
        raise ForgeError("RECORD_MALFORMED", f"{record_type.value} mode is invalid")
    _status_is_valid(record_type, fields)
    if record_type is RecordType.CANDIDATE_DISPOSITION and fields["disposition"] not in {
        "selected",
        "rejected",
    }:
        raise ForgeError("RECORD_MALFORMED", "candidate disposition is invalid")
    if record_type is RecordType.VERIFIER_RESULT and fields["independent_evaluation"] is not False:
        raise ForgeError(
            "RECORD_AUTHORITY",
            "local verifier records cannot claim independent evaluation",
        )


def identity_projection(record_type: RecordType | str, fields: Mapping[str, object]) -> JsonObject:
    """Return the explicit current-version self-identity projection."""

    resolved = _record_type(record_type)
    spec = RECORD_SPECS[resolved]
    if spec.identity_field is None:
        raise ForgeError("RECORD_IDENTITY", f"{resolved.value} has no record-derived identity")
    projection: JsonObject = {
        "record_type": resolved.value,
        "schema_version": CURRENT_SCHEMA_VERSION,
    }
    for key, value in fields.items():
        if key not in {spec.identity_field, *spec.identity_exclusions}:
            projection[key] = _as_json_value(value, path=f"identity.{key}")
    return projection


def derive_record_identity(record_type: RecordType | str, fields: Mapping[str, object]) -> str:
    resolved = _record_type(record_type)
    prefix = RECORD_SPECS[resolved].identity_prefix
    if prefix is None:
        raise ForgeError("RECORD_IDENTITY", f"{resolved.value} has no record-derived identity")
    digest = local_json_identity(identity_projection(resolved, fields)).split(":", 1)[1]
    return prefix + digest


def _legacy_identity(
    record_type: RecordType,
    fields: JsonObject,
    *,
    restore_preserved_unknowns: bool,
) -> str:
    spec = RECORD_SPECS[record_type]
    if spec.identity_field is None or spec.identity_prefix is None:
        raise ForgeError("RECORD_IDENTITY", f"{record_type.value} has no record-derived identity")
    projection = {
        key: value
        for key, value in fields.items()
        if key not in {spec.identity_field, *spec.identity_exclusions}
    }
    extensions = projection.get("extensions")
    if (
        restore_preserved_unknowns
        and isinstance(extensions, dict)
        and isinstance(extensions.get("legacy_unknown_fields"), dict)
    ):
        restored_unknown = cast(JsonObject, extensions["legacy_unknown_fields"])
        remaining_extensions = {
            key: value for key, value in extensions.items() if key != "legacy_unknown_fields"
        }
        if remaining_extensions:
            projection["extensions"] = remaining_extensions
        else:
            projection.pop("extensions")
        projection.update(restored_unknown)
    digest = local_json_identity(projection).split(":", 1)[1]
    return spec.identity_prefix + digest


def _model(
    record_type: RecordType,
    fields: JsonObject,
    *,
    source_schema_version: str,
) -> ForgeRecord:
    frozen = cast(
        Mapping[str, FrozenJsonValue],
        _freeze_json(cast(JsonValue, fields)),
    )
    model_type = MODEL_TYPES[record_type]
    return model_type(
        record_type=record_type,
        schema_version=source_schema_version,
        _fields=frozen,
        source_schema_version=source_schema_version,
    )


def new_record(record_type: RecordType | str, fields: Mapping[str, object]) -> ForgeRecord:
    """Construct a current record; callers cannot supply or spoof metadata."""

    resolved = _record_type(record_type)
    if "record_type" in fields or "schema_version" in fields:
        raise ForgeError(
            "RECORD_METADATA_SPOOF",
            "record_type and schema_version are assigned by the Forge record model",
        )
    normalized = json_object(fields)
    spec = RECORD_SPECS[resolved]
    if spec.identity_field is not None:
        supplied = normalized.get(spec.identity_field)
        expected = derive_record_identity(resolved, normalized)
        if supplied is None:
            normalized[spec.identity_field] = expected
        elif supplied != expected:
            raise ForgeError(
                "RECORD_IDENTITY",
                f"{resolved.value} record-derived identity does not reproduce",
            )
    _validate_fields(resolved, normalized)
    return _model(resolved, normalized, source_schema_version=CURRENT_SCHEMA_VERSION)


class MigrationRegistry:
    """Explicit deterministic migration registry for trusted record contexts."""

    def normalize(
        self,
        raw: Mapping[str, object],
        *,
        expected_type: RecordType | str,
    ) -> ForgeRecord:
        expected = _record_type(expected_type)
        data = json_object(raw)
        declared_type = data.pop("record_type", None)
        declared_version = data.pop("schema_version", None)
        if declared_type is None and declared_version is None:
            return self._legacy(expected, data, restore_preserved_unknowns=False)
        if declared_type is None or declared_version is None:
            raise ForgeError("RECORD_METADATA", "record metadata is incomplete")
        if declared_type != expected.value:
            raise ForgeError(
                "RECORD_TYPE_MISMATCH",
                f"trusted context expects {expected.value}, record declares {declared_type}",
            )
        if declared_version == LEGACY_SCHEMA_VERSION:
            return self._legacy(expected, data, restore_preserved_unknowns=True)
        if declared_version != CURRENT_SCHEMA_VERSION:
            raise ForgeError(
                "UNSUPPORTED_RECORD_VERSION",
                f"unsupported {expected.value} schema version: {declared_version}",
            )
        _validate_fields(expected, data)
        spec = RECORD_SPECS[expected]
        if spec.identity_field is not None:
            supplied = data.get(spec.identity_field)
            if supplied != derive_record_identity(expected, data):
                raise ForgeError(
                    "RECORD_IDENTITY",
                    f"{expected.value} record-derived identity does not reproduce",
                )
        return _model(expected, data, source_schema_version=CURRENT_SCHEMA_VERSION)

    def _legacy(
        self,
        record_type: RecordType,
        data: JsonObject,
        *,
        restore_preserved_unknowns: bool,
    ) -> ForgeRecord:
        spec = RECORD_SPECS[record_type]
        if spec.identity_field is not None:
            supplied = data.get(spec.identity_field)
            if supplied != _legacy_identity(
                record_type,
                data,
                restore_preserved_unknowns=restore_preserved_unknowns,
            ):
                raise ForgeError(
                    "RECORD_IDENTITY",
                    f"legacy {record_type.value} identity does not reproduce historically",
                )
        unknown = sorted(set(data).difference(spec.allowed))
        if unknown:
            preserved = {key: data.pop(key) for key in unknown}
            existing = data.get("extensions")
            if existing is not None and not isinstance(existing, dict):
                raise ForgeError("RECORD_MALFORMED", "record extensions must be an object")
            extensions = dict(existing) if isinstance(existing, dict) else {}
            if "legacy_unknown_fields" in extensions:
                raise ForgeError(
                    "RECORD_EXTENSION_CONFLICT",
                    "legacy extensions conflict with the migration preservation key",
                )
            extensions["legacy_unknown_fields"] = preserved
            data["extensions"] = extensions
        _validate_fields(record_type, data)
        return _model(record_type, data, source_schema_version=LEGACY_SCHEMA_VERSION)


MIGRATIONS = MigrationRegistry()


def parse_record(raw: Mapping[str, object], *, expected_type: RecordType | str) -> ForgeRecord:
    return MIGRATIONS.normalize(raw, expected_type=expected_type)


def load_record_file(
    path: Path,
    *,
    expected_type: RecordType | str | None = None,
    group: str | None = None,
    byte_cap: int = 4_000_000,
) -> ForgeRecord:
    if (expected_type is None) == (group is None):
        raise ForgeError("RECORD_CONTEXT", "supply exactly one trusted record context")
    if group is not None:
        try:
            expected_type = RECORD_GROUP_TYPES[group]
        except KeyError as exc:
            raise ForgeError("RECORD_CONTEXT", f"unknown immutable record group: {group}") from exc
    raw = read_json(path, byte_cap=byte_cap)
    if not isinstance(raw, dict):
        raise ForgeError("RECORD_MALFORMED", "record file must contain a JSON object")
    return parse_record(raw, expected_type=cast(RecordType | str, expected_type))


@dataclass(frozen=True, slots=True)
class LedgerEntry(Mapping[str, object]):
    sequence: int
    timestamp: str
    kind: str
    previous_hash: str
    payload: ForgeRecord
    entry_hash: str
    schema_version: str = CURRENT_SCHEMA_VERSION
    source_schema_version: str = CURRENT_SCHEMA_VERSION

    @property
    def record_type(self) -> RecordType:
        return RecordType.LEDGER_ENTRY

    def __getitem__(self, key: str) -> object:
        if key == "record_type":
            return self.record_type.value
        if key == "schema_version":
            return self.schema_version
        if key == "sequence":
            return self.sequence
        if key == "timestamp":
            return self.timestamp
        if key == "kind":
            return self.kind
        if key == "previous_hash":
            return self.previous_hash
        if key == "payload":
            return self.payload
        if key == "entry_hash":
            return self.entry_hash
        raise KeyError(key)

    def __iter__(self) -> Iterator[str]:
        return iter(self.to_json())

    def __len__(self) -> int:
        return 8

    def to_json(self) -> JsonObject:
        return {
            "record_type": RecordType.LEDGER_ENTRY.value,
            "schema_version": self.schema_version,
            "sequence": self.sequence,
            "timestamp": self.timestamp,
            "kind": self.kind,
            "previous_hash": self.previous_hash,
            "payload": self.payload.to_json(),
            "entry_hash": self.entry_hash,
        }


def normalize_ledger_entry(raw: Mapping[str, object]) -> LedgerEntry:
    data = json_object(raw, label="ledger_entry")
    declared_type = data.pop("record_type", None)
    declared_version = data.pop("schema_version", None)
    source = CURRENT_SCHEMA_VERSION
    if declared_type is None and declared_version is None:
        source = LEGACY_SCHEMA_VERSION
    else:
        if declared_type != RecordType.LEDGER_ENTRY.value:
            raise ForgeError(
                "RECORD_TYPE_MISMATCH",
                "trusted ledger context requires record_type ledger_entry",
            )
        if declared_version == LEGACY_SCHEMA_VERSION:
            source = LEGACY_SCHEMA_VERSION
        elif declared_version != CURRENT_SCHEMA_VERSION:
            raise ForgeError(
                "UNSUPPORTED_RECORD_VERSION",
                f"unsupported ledger_entry schema version: {declared_version}",
            )
    missing = sorted(LEDGER_REQUIRED.difference(data))
    unknown = sorted(set(data).difference(LEDGER_REQUIRED))
    if missing:
        raise ForgeError("RECORD_MISSING_FIELD", f"ledger_entry is missing: {', '.join(missing)}")
    if unknown:
        raise ForgeError(
            "RECORD_UNKNOWN_FIELD", f"ledger_entry has unexpected fields: {', '.join(unknown)}"
        )
    sequence = data["sequence"]
    timestamp = data["timestamp"]
    kind = data["kind"]
    previous_hash = data["previous_hash"]
    entry_hash = data["entry_hash"]
    payload_raw = data["payload"]
    if (
        not isinstance(sequence, int)
        or isinstance(sequence, bool)
        or not isinstance(timestamp, str)
        or not isinstance(kind, str)
        or not isinstance(previous_hash, str)
        or not isinstance(entry_hash, str)
        or not isinstance(payload_raw, dict)
    ):
        raise ForgeError("RECORD_MALFORMED", "ledger_entry fields have invalid types")
    try:
        payload_type = LEDGER_KIND_TYPES[kind]
    except KeyError as exc:
        raise ForgeError("RECORD_CONTEXT", f"unsupported ledger kind: {kind}") from exc
    payload = parse_record(payload_raw, expected_type=payload_type)
    return LedgerEntry(
        sequence=sequence,
        timestamp=timestamp,
        kind=kind,
        previous_hash=previous_hash,
        payload=payload,
        entry_hash=entry_hash,
        schema_version=source,
        source_schema_version=source,
    )
