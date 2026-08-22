#!/usr/bin/env python3
"""Regenerate the committed Draft 2020-12 Forge record schema snapshot."""

from __future__ import annotations

import json
from pathlib import Path

from mncs_forge.records import (
    CURRENT_SCHEMA_VERSION,
    LEDGER_KIND_TYPES,
    LEDGER_REQUIRED,
    RECORD_SPECS,
    REQUIRED_OBJECT_FIELDS,
    REQUIRED_STRING_FIELDS,
    RecordType,
)

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "src/mncs_forge/resources/forge-records-1.schema.json"

STRING_FIELDS = {
    "action_id",
    "action_identity",
    "action_kind",
    "architecture",
    "binding_id",
    "bundle_id",
    "candidate_id",
    "candidate_identity",
    "category",
    "created_at",
    "disposition_id",
    "evidence_status",
    "execution_scope",
    "freeze_id",
    "frozen_at",
    "method",
    "mode",
    "os_family",
    "output_identity",
    "probe_kind",
    "project_identity",
    "receipt_completeness",
    "recorded_at",
    "requested_at",
    "runner_identity",
    "runner_kind",
    "runner_version",
    "schema_version",
    "status",
    "termination_category",
    "verifier_id",
    "workflow",
    "workflow_or_verifier",
}
NULLABLE_STRING_FIELDS = {
    "executable_identity",
    "host_identity",
    "image_identity",
    "receipt_identity",
    "receipt_schema_version",
    "request_identity",
    "result_identity",
    "worker_identity",
}
for required_fields in REQUIRED_STRING_FIELDS.values():
    STRING_FIELDS.update(required_fields)


def property_schema(record_type: RecordType, field: str) -> dict[str, object]:
    spec = RECORD_SPECS[record_type]
    if record_type is RecordType.COMPILER_EXPERIMENT and field in {
        "assurance_status",
        "conformance_status",
    }:
        return {"type": "null"}
    if record_type is RecordType.COMPILER_EXPERIMENT and field == "language_contract_id":
        return {
            "enum": [
                "mncs:language:compilation-study-result:0.1",
                "mncs:language:experiment-result:0.1",
            ]
        }
    if record_type is RecordType.COMPILER_EXPERIMENT and field == "interpretation":
        return {"const": "observation_only_not_assurance_or_conformance"}
    if record_type is RecordType.COMPILER_EXPERIMENT and field == "compilation_status":
        return {"enum": ["completed", "completed_with_unresolved_obligations", "failed"]}
    if record_type is RecordType.COMPILER_CANDIDATE and field in {
        "assurance_status",
        "conformance_status",
        "benchmark_observation",
        "validation",
    }:
        return (
            {"type": ["object", "null"]}
            if field
            in {
                "benchmark_observation",
                "validation",
            }
            else {"type": "null"}
        )
    if record_type is RecordType.COMPILER_CANDIDATE and field == "interpretation":
        return {"const": "search_observation_not_language_correctness"}
    if record_type is RecordType.COMPILER_CANDIDATE and field == "semantic_status":
        return {"enum": ["UNVALIDATED", "PASS", "FAIL", "UNKNOWN"]}
    if record_type is RecordType.COMPILER_CANDIDATE and field == "policy_disposition":
        return {"enum": ["accept", "reject", "retain_unresolved"]}
    if record_type is RecordType.COMPILER_CANDIDATE and field == "protected_properties":
        return {"type": "array", "items": {"type": "string"}}
    if record_type is RecordType.COMPILER_CANDIDATE and field in {
        "isolated",
        "generator_certified",
    }:
        return {"type": "boolean"}
    if field == "protocol_request_identity" and record_type in {
        RecordType.WORKFLOW_ACTION,
        RecordType.WORKFLOW_RESULT,
        RecordType.FINAL_EVALUATION,
        RecordType.BUNDLE,
    }:
        return {"type": ["string", "null"]}
    if field == "epoch_identity" and record_type is RecordType.EXECUTION_RECEIPT_BINDING:
        return {"type": ["string", "null"]}
    if field in NULLABLE_STRING_FIELDS:
        return {"type": ["string", "null"]}
    if field == "mncs_receipt":
        return {"type": ["object", "null"]}
    if field == "action_kind":
        return {"enum": ["workflow_action", "verifier_action"]}
    if field == "receipt_completeness":
        return {"enum": ["complete", "incomplete", "malformed", "unsupported", "unavailable"]}
    if field == "extensions":
        return {
            "type": "object",
            "description": (
                "Non-normative extension data. It round-trips and participates in current "
                "record-derived identities, but cannot affect authority or status semantics."
            ),
        }
    if field == spec.status_field:
        return {"enum": ["PASS", "FAIL", "UNKNOWN"]}
    if field == "disposition":
        return {"enum": ["selected", "rejected"]}
    if field == "mode":
        return {"enum": ["development", "evaluator"]}
    if field == "independent_evaluation":
        return {"const": False}
    if field in REQUIRED_OBJECT_FIELDS.get(record_type, frozenset()):
        return {"type": "object"}
    if field in STRING_FIELDS or field.endswith("_at"):
        return {"type": "string"}
    return {}


def record_schema(record_type: RecordType) -> dict[str, object]:
    spec = RECORD_SPECS[record_type]
    fields = sorted(spec.allowed)
    properties: dict[str, object] = {
        "record_type": {"const": record_type.value},
        "schema_version": {"const": CURRENT_SCHEMA_VERSION},
    }
    properties.update({field: property_schema(record_type, field) for field in fields})
    return {
        "type": "object",
        "required": ["record_type", "schema_version", *sorted(spec.required)],
        "properties": properties,
        "additionalProperties": False,
    }


def ledger_schema() -> dict[str, object]:
    persisted = sorted(set(LEDGER_KIND_TYPES.values()), key=lambda value: value.value)
    conditions = [
        {
            "if": {"properties": {"kind": {"const": kind}}, "required": ["kind"]},
            "then": {"properties": {"payload": {"$ref": f"#/$defs/{record_type.value}"}}},
        }
        for kind, record_type in sorted(LEDGER_KIND_TYPES.items())
    ]
    return {
        "type": "object",
        "required": ["record_type", "schema_version", *sorted(LEDGER_REQUIRED)],
        "properties": {
            "record_type": {"const": RecordType.LEDGER_ENTRY.value},
            "schema_version": {"const": CURRENT_SCHEMA_VERSION},
            "sequence": {"type": "integer", "minimum": 1},
            "timestamp": {"type": "string"},
            "kind": {"enum": sorted(LEDGER_KIND_TYPES)},
            "previous_hash": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
            "payload": {
                "oneOf": [{"$ref": f"#/$defs/{record_type.value}"} for record_type in persisted]
            },
            "entry_hash": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
        },
        "allOf": conditions,
        "additionalProperties": False,
    }


def main() -> None:
    definitions = {record_type.value: record_schema(record_type) for record_type in RECORD_SPECS}
    definitions[RecordType.LEDGER_ENTRY.value] = ledger_schema()
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "urn:mncs-forge:schema:forge-records-1",
        "title": "MNCS Forge record schema set version 1",
        "description": (
            "Public snapshots for current Forge persistent and typed interface records. "
            "The Python parser remains authoritative at runtime."
        ),
        "oneOf": [
            {"$ref": f"#/$defs/{record_type.value}"}
            for record_type in [*RECORD_SPECS, RecordType.LEDGER_ENTRY]
        ],
        "$defs": definitions,
    }
    OUTPUT.write_text(
        json.dumps(schema, ensure_ascii=False, allow_nan=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
