"""Claim reporting, reconciliation, and evidence-bundle application service."""

from __future__ import annotations

import json

from ..config import ForgeConfig
from ..errors import ForgeError
from ..ports import RecordCommitter
from ..records import BundleRecord, RecordType, new_record
from ..serialization import read_json
from .lifecycle import LifecycleContext
from .support import CLAIM_CLASSES, aggregate_status
from .workflows import DevelopmentWorkflowService, WorkflowExecutor


class EvidenceService:
    def __init__(
        self,
        *,
        config: ForgeConfig,
        mode: str,
        record_store: RecordCommitter,
        lifecycle: LifecycleContext,
        development: DevelopmentWorkflowService,
        workflows: WorkflowExecutor,
    ) -> None:
        self.config = config
        self.mode = mode
        self.record_store = record_store
        self.lifecycle = lifecycle
        self.development = development
        self.workflows = workflows

    @staticmethod
    def _extract_statuses(value: object) -> list[str]:
        statuses: list[str] = []
        if isinstance(value, dict):
            for key, child in value.items():
                if key in {"status", "result", "overall_status", "aggregate_status"}:
                    if isinstance(child, str) and child in {"PASS", "FAIL", "UNKNOWN"}:
                        statuses.append(child)
                elif isinstance(child, (dict, list)):
                    statuses.extend(EvidenceService._extract_statuses(child))
        elif isinstance(value, list):
            for child in value:
                statuses.extend(EvidenceService._extract_statuses(child))
        return statuses

    @staticmethod
    def _classify_record(path: str) -> str:
        lowered = path.lower()
        if "mncds" in lowered or "development-record" in lowered:
            return "mncds_development_process_result"
        if "independent" in lowered:
            return "independent_evaluation"
        if "holdout" in lowered or "protected" in lowered:
            return "protected_holdout"
        if "witness" in lowered:
            return "witnessed_evidence"
        if "operational" in lowered or "monitor" in lowered:
            return "operational_evidence"
        if "governance" in lowered or "approval" in lowered:
            return "governance_approval"
        if "reproduction" in lowered:
            return "local_reproduction"
        return "mncs_implementation_result"

    def _structured_statuses(self) -> list[dict[str, str]]:
        records: list[dict[str, str]] = []
        seen = 0
        for root in [*self.config.paths("development_evidence"), *self.config.paths("outputs")]:
            paths = (
                [root] if root.is_file() else sorted(root.rglob("*.json")) if root.exists() else []
            )
            for path in paths:
                if seen >= 1000:
                    break
                seen += 1
                try:
                    value = read_json(path, byte_cap=self.config.output_cap)
                except (OSError, ValueError, json.JSONDecodeError):
                    continue
                for status in self._extract_statuses(value):
                    relative = path.relative_to(self.config.root).as_posix()
                    records.append(
                        {
                            "source": relative,
                            "status": status,
                            "claim_class": self._classify_record(relative),
                        }
                    )
        return records

    def claim_status(self) -> dict[str, object]:
        source_records = self._structured_statuses()
        statuses: dict[str, str] = {}
        sources: dict[str, list[str]] = {}
        for claim_class in CLAIM_CLASSES:
            matching = [item for item in source_records if item["claim_class"] == claim_class]
            statuses[claim_class] = aggregate_status(item["status"] for item in matching)
            sources[claim_class] = sorted({item["source"] for item in matching})[:20]
        statuses["operator_controlled_reproduction"] = "UNKNOWN"
        statuses["promotion_disposition"] = (
            "REVIEW_REQUIRED"
            if all(value == "PASS" for value in statuses.values())
            else "NOT_PROMOTABLE"
        )
        return {
            "statuses": statuses,
            "sources": sources,
            "dominance": "FAIL > UNKNOWN > PASS",
            "promotion_note": "REVIEW_REQUIRED is a workflow disposition, not an MNCS result",
            "missing_is_pass": False,
        }

    def claim_blockers(self, requested_claim: str) -> dict[str, object]:
        status = self.claim_status()
        raw_statuses = status["statuses"]
        if not isinstance(raw_statuses, dict):
            raise ForgeError("INTERNAL_STATUS", "claim status map is invalid")
        statuses = {str(key): str(value) for key, value in raw_statuses.items()}
        mapping = {
            "mncs": ["mncs_implementation_result"],
            "mncds": ["mncds_development_process_result"],
            "independent": ["independent_evaluation"],
            "protected": ["protected_holdout"],
            "promotion": list(CLAIM_CLASSES),
        }
        required = mapping.get(requested_claim, [requested_claim])
        category_map = {
            "mncs_implementation_result": "locally_executable_work",
            "mncds_development_process_result": "locally_executable_work",
            "local_reproduction": "locally_executable_work",
            "operator_controlled_reproduction": "physical_machine_work",
            "independent_evaluation": "independent_evaluator_work",
            "protected_holdout": "protected_custody_work",
            "witnessed_evidence": "witnessed_work",
            "operational_evidence": "operational_work",
            "governance_approval": "governance_work",
        }
        blockers = [
            {
                "claim_class": name,
                "status": statuses.get(name, "UNKNOWN"),
                "problem": (
                    "failed evidence"
                    if statuses.get(name, "UNKNOWN") == "FAIL"
                    else "absent or unsupported evidence"
                ),
                "work_class": category_map.get(name, "unsupported_work"),
            }
            for name in required
            if statuses.get(name, "UNKNOWN") != "PASS"
        ]
        return {
            "requested_claim": requested_claim,
            "blockers": blockers,
            "blocked": bool(blockers),
            "stale_or_conflicting": [
                item["source"]
                for item in self._structured_statuses()
                if item["status"] in {"FAIL", "UNKNOWN"}
            ][:20],
            "boundary": "Forge reports blockers; it cannot create external authority or promotion",
        }

    def reconcile(self, candidate_id: str | None = None) -> dict[str, object]:
        resolved_candidate = self.lifecycle.machine().authorize_reconciliation(candidate_id)
        selected_results = self.development.result_records(resolved_candidate)
        if resolved_candidate is None:
            selected_results = [
                record for record in selected_results if record.get("subject_type") == "project"
            ]
        results = [record.to_object_dict() for record in selected_results]
        by_category: dict[str, list[dict[str, object]]] = {}
        for result in results:
            by_category.setdefault(str(result["category"]), []).append(result)
        categories: dict[str, object] = {}
        conflicts: list[str] = []
        for category, items in sorted(by_category.items()):
            values = {str(item["status"]) for item in items}
            if len(values) > 1:
                conflicts.append(category)
            unsupported_values = [
                str(value)
                for item in items
                for value in (
                    item["unsupported_constructs"]
                    if isinstance(item["unsupported_constructs"], list)
                    else []
                )
            ]
            categories[category] = {
                "status": aggregate_status(values),
                "dependencies": [],
                "records": [item["output_identity"] for item in items],
                "unsupported": sorted(set(unsupported_values)),
            }
        aggregate = aggregate_status(
            str(value["status"]) for value in categories.values() if isinstance(value, dict)
        )
        return new_record(
            RecordType.RECONCILIATION,
            {
                "candidate_identity": resolved_candidate,
                "required_gate_aggregation": aggregate,
                "categories": categories,
                "conflicting_evidence": conflicts,
                "stale_identities": [],
                "claim_limitations": (
                    ["one or more required gates are not PASS"] if aggregate != "PASS" else []
                ),
                "unresolved_blockers": [
                    name
                    for name, value in categories.items()
                    if isinstance(value, dict) and value["status"] != "PASS"
                ],
                "dominance": "FAIL > UNKNOWN > PASS",
                "normative_logic_delegated": (
                    "MNCS and MNCDS validators remain offline authorities"
                ),
            },
        ).to_object_dict()

    def build_bundle(
        self, workflow_name: str, candidate_id: str | None = None
    ) -> dict[str, object]:
        candidate = self.lifecycle.machine().authorize_bundle(candidate_id)
        workflow = self.workflows.workflow(workflow_name, self.mode)
        if workflow.category not in {"mncs_bundle_validation", "mncds_record_validation"}:
            raise ForgeError("WORKFLOW_CATEGORY", "bundle requires an MNCS or MNCDS workflow")
        result = self.workflows.run(
            workflow,
            candidate,
            evaluator=self.mode == "evaluator",
            record_type=RecordType.BUNDLE,
        )
        if not isinstance(result, BundleRecord):
            raise ForgeError("INTERNAL_RECORD", "bundle produced an invalid record model")
        self.record_store.commit("bundles", "bundle", result)
        integrity = str(result["status"])
        return {
            "package_creation": "COMPLETED" if result["returncode"] == 0 else "FAILED",
            "package_integrity": integrity,
            "schema_validity": integrity,
            "cryptographic_validity": "UNKNOWN",
            "trust": "UNKNOWN",
            "certification_eligibility": "UNKNOWN",
            "operational_disposition": "REVIEW_REQUIRED",
            "result_reference": result["output_identity"],
            "note": "a valid package or signature is not proof of correctness",
        }
