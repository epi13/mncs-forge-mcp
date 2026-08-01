"""Hardened micro-verifier lifecycle extensions.

The base service retains matching, provider execution, disclosure, and freshness
semantics. This layer adds deletion-aware identities, terminal UNKNOWN records for
started actions, and heterogeneous bounded batch parameters.
"""

from __future__ import annotations

import time
from typing import Any

from .errors import ForgeError
from .micro_verifiers import MicroVerifierService
from .serialization import canonical_bytes, local_json_identity
from .verifier_support import (
    changed_path_identity,
    parameters_for_verifier,
    resolve_batch_parameters,
    terminal_unknown_result,
    unrecorded_batch_unknown,
)


class HardenedMicroVerifierService(MicroVerifierService):
    """Preserve terminal lineage and represent deleted paths explicitly."""

    def run(
        self,
        verifier_id: str,
        *,
        candidate_identity: str | None = None,
        changed_paths: list[str] | None = None,
        scope: str | None = None,
        source_region: dict[str, object] | None = None,
        contract_identity: str | None = None,
        dependency_slice_identities: dict[str, str] | None = None,
        prior_artifact_identity: str | None = None,
        question_parameters: dict[str, object] | None = None,
        timeout_cap: float | None = None,
    ) -> dict[str, object]:
        verifier = self._verifier(verifier_id)
        if self.forge.mode not in verifier.modes:
            raise ForgeError(
                "VERIFIER_MODE",
                f"verifier {verifier_id} is not declared for {self.forge.mode} mode",
            )
        workflow = self.config.workflows[verifier.workflow]
        provider = self.config.providers[verifier.provider_id]
        if self.forge.mode == "development":
            if not bool(self.config.raw["authority"]["development"]["may_run_providers"]):
                raise ForgeError(
                    "VERIFIER_AUTHORITY",
                    "development authority does not permit provider execution",
                )
            candidate = self.forge._candidate(candidate_identity)
            freeze: dict[str, Any] | None = None
        else:
            freeze = self.forge._latest_payload("freeze")
            if freeze is None:
                raise ForgeError("NO_FREEZE", "evaluator-mode verifier requires a frozen candidate")
            self.forge._verify_freeze(freeze)
            frozen_candidate = str(freeze["candidate_identity"])
            if candidate_identity is not None and candidate_identity != frozen_candidate:
                raise ForgeError(
                    "STALE_CANDIDATE",
                    "verifier candidate differs from the frozen candidate identity",
                )
            candidate = self.forge._record_by_id("candidate", frozen_candidate, "candidate_id")

        selected_scope = self._scope(verifier, scope)
        selected_paths = self._validate_changed_paths(changed_paths or [], require_files=False)
        region = self._validate_source_region(verifier, source_region)
        dependencies = self._validate_dependency_identities(dependency_slice_identities or {})
        parameters = self._validate_parameters(verifier, question_parameters or {})
        self._validate_input_kinds(
            verifier,
            changed_paths=selected_paths,
            source_region=region,
            contract_identity=contract_identity,
            dependency_slice_identities=dependencies,
            prior_artifact_identity=prior_artifact_identity,
            question_parameters=parameters,
        )
        current_contract_identity = self._contract_identity()
        if contract_identity is not None and contract_identity != current_contract_identity:
            raise ForgeError(
                "CONTRACT_IDENTITY",
                "declared contract identity does not match current configured contracts",
            )
        path_identities = {
            value: changed_path_identity(self.config.root, value) for value in selected_paths
        }
        input_identities: dict[str, object] = {
            "candidate_identity": candidate["candidate_id"],
            "changed_path_identities": path_identities,
            "contract_identity": contract_identity,
            "dependency_slice_identities": dependencies,
            "prior_artifact_identity": prior_artifact_identity,
            "question_parameters_identity": local_json_identity(parameters),
        }
        environment = self.config.environment(workflow)
        identities = self._material_identities(verifier, provider, workflow, environment)
        supersedes_output_identity = self._superseded_result(
            verifier.verifier_id,
            str(candidate["candidate_id"]),
            candidate.get("parent_candidate"),
        )
        action: dict[str, object] = {
            "verifier_id": verifier.verifier_id,
            "verifier_version": verifier.version,
            "verifier_identity": identities["verifier_identity"],
            "provider_id": provider.provider_id,
            "provider_configuration_identity": identities["provider_configuration_identity"],
            "method": verifier.method,
            "mode": self.forge.mode,
            "epoch_identity": candidate["source_epoch"],
            "candidate_identity": candidate["candidate_id"],
            "candidate_parent_identity": candidate.get("parent_candidate"),
            "freeze_identity": freeze["freeze_id"] if freeze else None,
            "supersedes_output_identity": supersedes_output_identity,
            "scope": selected_scope,
            "changed_paths": selected_paths,
            "source_region": region,
            "input_identities": input_identities,
            "configuration_identity": identities["configuration_identity"],
            "policy_identity": identities["policy_identity"],
            "environment_identity": identities["environment_identity"],
            "requested_at": self._now(),
        }
        action["action_id"] = "verifier-action:" + local_json_identity(action).split(":", 1)[1]
        request = self._request(
            verifier,
            action,
            selected_paths=selected_paths,
            region=region,
            dependencies=dependencies,
            contract_identity=contract_identity,
            prior_artifact_identity=prior_artifact_identity,
            parameters=parameters,
        )
        request_bytes = canonical_bytes(request) + b"\n"
        if len(request_bytes) > int(self.config.verifier_limits["request_bytes"]):
            raise ForgeError(
                "VERIFIER_REQUEST_LIMIT",
                "verifier request exceeds the configured byte limit",
            )
        action["protocol_request_identity"] = local_json_identity(request)
        self.forge._write_immutable("verifier-actions", str(action["action_id"]), action)
        self.forge.ledger.append("verifier_action", action)

        started = time.monotonic()
        try:
            result = self._execute(
                verifier,
                workflow,
                provider,
                candidate,
                action,
                request,
                request_bytes,
                identities,
                environment,
                freeze,
                timeout_cap,
            )
        except ForgeError as exc:
            result = terminal_unknown_result(
                action=action,
                verifier=verifier,
                provider=provider,
                identities=identities,
                code=exc.code,
                message=exc.message,
                recorded_at=self._now(),
                duration_seconds=time.monotonic() - started,
            )
        self.forge._write_immutable("verifier-results", str(result["output_identity"]), result)
        self.forge.ledger.append("verifier_result", result)
        return self._disclose_result(result)

    def batch(
        self,
        verifier_ids: list[str],
        *,
        candidate_identity: str | None = None,
        changed_paths: list[str] | None = None,
        scope: str | None = None,
        source_region: dict[str, object] | None = None,
        contract_identity: str | None = None,
        dependency_slice_identities: dict[str, str] | None = None,
        prior_artifact_identity: str | None = None,
        question_parameters: dict[str, object] | None = None,
    ) -> dict[str, object]:
        limits = self.config.verifier_limits
        if not verifier_ids:
            raise ForgeError("VERIFIER_BATCH", "batch requires at least one verifier")
        if len(verifier_ids) > int(limits["max_batch"]):
            raise ForgeError(
                "VERIFIER_BATCH_LIMIT",
                f"batch exceeds the {int(limits['max_batch'])}-verifier limit",
            )
        if len(set(verifier_ids)) != len(verifier_ids):
            raise ForgeError("VERIFIER_BATCH", "batch verifier IDs must be unique")
        verifiers = [self._verifier(verifier_id) for verifier_id in verifier_ids]
        configured_duration = sum(verifier.timeout_seconds for verifier in verifiers)
        total_limit = float(limits["batch_timeout_seconds"])
        if configured_duration > total_limit:
            raise ForgeError(
                "VERIFIER_BATCH_LIMIT",
                "sum of verifier timeouts exceeds the configured batch duration",
            )
        try:
            shared, per_verifier = resolve_batch_parameters(verifier_ids, question_parameters)
        except ValueError as exc:
            raise ForgeError("VERIFIER_BATCH_PARAMETERS", str(exc)) from exc
        batch_request: dict[str, object] = {
            "verifier_ids": verifier_ids,
            "candidate_identity": candidate_identity,
            "changed_paths": changed_paths or [],
            "scope": scope,
            "source_region": source_region,
            "contract_identity": contract_identity,
            "dependency_slice_identities": dependency_slice_identities or {},
            "prior_artifact_identity": prior_artifact_identity,
            "question_parameters": question_parameters or {},
        }
        if len(canonical_bytes(batch_request)) > int(limits["request_bytes"]):
            raise ForgeError(
                "VERIFIER_REQUEST_LIMIT",
                "batch request exceeds the configured byte limit",
            )

        started = time.monotonic()
        results: list[dict[str, object]] = []
        for verifier in verifiers:
            remaining = total_limit - (time.monotonic() - started)
            if remaining <= 0:
                results.append(
                    unrecorded_batch_unknown(
                        verifier.verifier_id,
                        "VERIFIER_BATCH_LIMIT",
                        "batch duration exhausted before action recording",
                    )
                )
                continue
            parameters = parameters_for_verifier(
                verifier.verifier_id,
                shared,
                per_verifier,
            )
            try:
                result = self.run(
                    verifier.verifier_id,
                    candidate_identity=candidate_identity,
                    changed_paths=changed_paths,
                    scope=scope,
                    source_region=source_region,
                    contract_identity=contract_identity,
                    dependency_slice_identities=dependency_slice_identities,
                    prior_artifact_identity=prior_artifact_identity,
                    question_parameters=parameters,
                    timeout_cap=remaining,
                )
            except ForgeError as exc:
                result = unrecorded_batch_unknown(
                    verifier.verifier_id,
                    exc.code,
                    exc.message,
                )
            results.append(result)
        statuses = [str(result.get("status", "UNKNOWN")) for result in results]
        recorded_count = sum(bool(result.get("output_identity")) for result in results)
        return {
            "results": results,
            "aggregate_status": self._aggregate(statuses),
            "individual_results_retained": True,
            "recorded_result_count": recorded_count,
            "unrecorded_result_count": len(results) - recorded_count,
            "partial_execution_explicit": True,
            "dominance": "FAIL > UNKNOWN > PASS",
            "duration_seconds": round(time.monotonic() - started, 6),
        }

    def _contract_identity(self) -> str:
        from .identity import content_identity

        return content_identity(self.config.root, self.config.paths("contracts"))

    def _superseded_result(
        self,
        verifier_id: str,
        candidate_identity: str,
        parent_candidate: object,
    ) -> str | None:
        lineage = {candidate_identity}
        if parent_candidate is not None:
            lineage.add(str(parent_candidate))
        for entry in reversed(self.forge._records("verifier_result")):
            payload = entry["payload"]
            if (
                payload.get("verifier_id") == verifier_id
                and payload.get("mode") == self.forge.mode
                and payload.get("candidate_identity") in lineage
            ):
                return str(payload["output_identity"])
        return None

    @staticmethod
    def _aggregate(statuses: list[str]) -> str:
        order = {"PASS": 0, "UNKNOWN": 1, "FAIL": 2}
        values = [value for value in statuses if value in order]
        return max(values, key=order.__getitem__) if values else "UNKNOWN"
