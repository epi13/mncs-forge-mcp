"""Local stdio MCP server for MNCS Forge."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from .config import load_config
from .engine import Forge


def build_server(forge: Forge) -> FastMCP:
    server = FastMCP(
        "MNCS Forge",
        instructions=(
            "Experimental MNCS-native development control plane. Keep MNCS and MNCDS "
            "statuses separate, preserve UNKNOWN, and use offline validators as authorities."
        ),
    )

    @server.tool(name="mncs_forge_project_inspect")
    def project_inspect() -> dict[str, object]:
        """Inspect configured authority, mode, active state, commands, and limitations."""

        return forge.project_inspect()

    @server.tool(name="mncs_forge_state_inspect")
    def state_inspect() -> dict[str, object]:
        """Explain the lifecycle stage, legal next operations, and stable blockers."""

        return forge.state_inspect()

    @server.tool(name="mncs_forge_claim_status")
    def claim_status() -> dict[str, object]:
        """Report separate MNCS, MNCDS, assurance, evidence, and promotion statuses."""

        return forge.claim_status()

    @server.tool(name="mncs_forge_claim_blockers")
    def claim_blockers(requested_claim: str = "promotion") -> dict[str, object]:
        """Explain absent, failed, stale, conflicting, or unsupported claim evidence."""

        return forge.claim_blockers(requested_claim)

    @server.tool(name="mncs_forge_providers_list")
    def providers_list() -> dict[str, object]:
        """List configured providers, declared capabilities, availability, and last probes."""

        return forge.provider_list()

    @server.tool(name="mncs_forge_provider_probe")
    def provider_probe(provider_id: str) -> dict[str, object]:
        """Explicitly probe one provider using bounded Provider Protocol capabilities."""

        return forge.provider_probe(provider_id)

    @server.tool(name="mncs_forge_capability_blockers")
    def capability_blockers(
        required_capabilities: list[str] | None = None,
    ) -> dict[str, object]:
        """Report UNKNOWN blockers for required capabilities not established by a current probe."""

        return forge.capability_blockers(required_capabilities)

    @server.tool(name="mncs_forge_verifier_list")
    def verifier_list() -> dict[str, object]:
        """List declared micro-verifiers without executing providers."""

        return forge.verifier_list()

    @server.tool(name="mncs_forge_verifier_describe")
    def verifier_describe(verifier_id: str) -> dict[str, object]:
        """Describe one declared micro-verifier and its bounded authority."""

        return forge.verifier_describe(verifier_id)

    @server.tool(name="mncs_forge_verifier_match")
    def verifier_match(
        uncertainty_classes: list[str],
        language: str | None = None,
        artifact_type: str | None = None,
        changed_paths: list[str] | None = None,
        scope: str | None = None,
        maximum_cost: str = "high",
        required_category: str | None = None,
        active_mode: str | None = None,
    ) -> dict[str, object]:
        """Deterministically match declared verifiers; never execute a match."""

        return forge.verifier_match(
            uncertainty_classes=uncertainty_classes,
            language=language,
            artifact_type=artifact_type,
            changed_paths=changed_paths,
            scope=scope,
            maximum_cost=maximum_cost,
            required_category=required_category,
            active_mode=active_mode,
        )

    @server.tool(name="mncs_forge_verifier_run")
    def verifier_run(
        verifier_id: str,
        candidate_identity: str | None = None,
        changed_paths: list[str] | None = None,
        scope: str | None = None,
        source_region: dict[str, object] | None = None,
        contract_identity: str | None = None,
        dependency_slice_identities: dict[str, str] | None = None,
        prior_artifact_identity: str | None = None,
        question_parameters: dict[str, object] | None = None,
    ) -> dict[str, object]:
        """Run one declared verifier through bounded Provider Protocol execution."""

        return forge.verifier_run(
            verifier_id,
            candidate_identity=candidate_identity,
            changed_paths=changed_paths,
            scope=scope,
            source_region=source_region,
            contract_identity=contract_identity,
            dependency_slice_identities=dependency_slice_identities,
            prior_artifact_identity=prior_artifact_identity,
            question_parameters=question_parameters,
        )

    @server.tool(name="mncs_forge_verifier_batch")
    def verifier_batch(
        verifier_ids: list[str],
        candidate_identity: str | None = None,
        changed_paths: list[str] | None = None,
        scope: str | None = None,
        source_region: dict[str, object] | None = None,
        contract_identity: str | None = None,
        dependency_slice_identities: dict[str, str] | None = None,
        prior_artifact_identity: str | None = None,
        question_parameters: dict[str, object] | None = None,
    ) -> dict[str, object]:
        """Run an explicit bounded verifier batch and retain every result."""

        return forge.verifier_batch(
            verifier_ids,
            candidate_identity=candidate_identity,
            changed_paths=changed_paths,
            scope=scope,
            source_region=source_region,
            contract_identity=contract_identity,
            dependency_slice_identities=dependency_slice_identities,
            prior_artifact_identity=prior_artifact_identity,
            question_parameters=question_parameters,
        )

    @server.tool(name="mncs_forge_verifier_explain")
    def verifier_explain(output_identity: str) -> dict[str, object]:
        """Explain one verifier result and its current freshness limitations."""

        return forge.verifier_explain(output_identity)

    @server.tool(name="mncs_forge_epoch_begin")
    def epoch_begin(
        generator_identity: str,
        evaluator_identity: str,
        parent_epoch: str | None = None,
        authority_overlap: list[str] | None = None,
    ) -> dict[str, object]:
        """Begin an append-only development epoch without modifying earlier epochs."""

        return forge.epoch_begin(
            generator_identity=generator_identity,
            evaluator_identity=evaluator_identity,
            parent_epoch=parent_epoch,
            authority_overlap=authority_overlap,
        )

    @server.tool(name="mncs_forge_candidate_register")
    def candidate_register(
        changed_files: list[str],
        hypothesis: str,
        generator_identity: str,
        generator_config_identity: str,
        parent_candidate: str | None = None,
        expected_identity: str | None = None,
    ) -> dict[str, object]:
        """Register candidate content and lineage within declared writable paths."""

        return forge.candidate_register(
            changed_files=changed_files,
            hypothesis=hypothesis,
            generator_identity=generator_identity,
            generator_config_identity=generator_config_identity,
            parent_candidate=parent_candidate,
            expected_identity=expected_identity,
        )

    @server.tool(name="mncs_forge_development_checks_run")
    def development_checks_run(
        workflow_names: list[str], candidate_identity: str | None = None
    ) -> dict[str, object]:
        """Run only declared development workflows with bounded execution."""

        return forge.development_checks_run(workflow_names, candidate_identity)

    @server.tool(name="mncs_forge_failure_explain")
    def failure_explain(output_identity: str | None = None) -> dict[str, object]:
        """Return compact decision-oriented FAIL or UNKNOWN information."""

        return forge.failure_explain(output_identity)

    @server.tool(name="mncs_forge_candidate_compare")
    def candidate_compare(candidate_identities: list[str]) -> dict[str, object]:
        """Compare candidates under the predeclared selection policy."""

        return forge.candidate_compare(candidate_identities)

    @server.tool(name="mncs_forge_candidate_select")
    def candidate_select(candidate_identity: str, reason: str) -> dict[str, object]:
        """Select a candidate only when required evidence is comparable PASS."""

        return forge.candidate_disposition(
            candidate_identity, disposition="selected", reason=reason
        )

    @server.tool(name="mncs_forge_candidate_reject")
    def candidate_reject(candidate_identity: str, reason: str) -> dict[str, object]:
        """Reject a candidate while retaining its immutable history."""

        return forge.candidate_disposition(
            candidate_identity, disposition="rejected", reason=reason
        )

    @server.tool(name="mncs_forge_candidate_freeze")
    def candidate_freeze(
        candidate_identity: str,
        environment_identity: str,
        required_evidence_plan: str,
    ) -> dict[str, object]:
        """Freeze candidate and authority identities for evaluator mode."""

        return forge.candidate_freeze(
            candidate_identity,
            environment_identity=environment_identity,
            required_evidence_plan=required_evidence_plan,
        )

    if forge.mode == "evaluator":

        @server.tool(name="mncs_forge_final_evaluation_run")
        def final_evaluation_run(workflow_names: list[str]) -> dict[str, object]:
            """Run frozen evaluator workflows without repair feedback."""

            return forge.final_evaluation_run(workflow_names)

    @server.tool(name="mncs_forge_evidence_reconcile")
    def evidence_reconcile(candidate_identity: str | None = None) -> dict[str, object]:
        """Aggregate validated local evidence with FAIL > UNKNOWN > PASS."""

        return forge.evidence_reconcile(candidate_identity)

    @server.tool(name="mncs_forge_bundle_build")
    def bundle_build(
        workflow_name: str, candidate_identity: str | None = None
    ) -> dict[str, object]:
        """Orchestrate a declared public MNCS/MNCDS package workflow."""

        return forge.bundle_build(workflow_name, candidate_identity)

    @server.resource("mncs-forge://project/authority-map")
    def authority_map() -> str:
        return json.dumps(forge.project_inspect(), sort_keys=True)

    @server.resource("mncs-forge://state/active-epoch")
    def active_epoch() -> str:
        return json.dumps(forge.project_inspect()["current_epoch"], sort_keys=True)

    @server.resource("mncs-forge://state/lifecycle")
    def lifecycle_state() -> str:
        return json.dumps(forge.state_inspect(), sort_keys=True)

    @server.resource("mncs-forge://state/active-candidate")
    def active_candidate() -> str:
        return json.dumps(forge.project_inspect()["active_candidate"], sort_keys=True)

    @server.resource("mncs-forge://evidence/latest-summary")
    def evidence_summary() -> str:
        return json.dumps(forge.evidence_reconcile(), sort_keys=True)

    @server.resource("mncs-forge://claims/blockers")
    def blockers_resource() -> str:
        return json.dumps(forge.claim_blockers("promotion"), sort_keys=True)

    @server.resource("mncs-forge://providers/configured")
    def configured_providers() -> str:
        return json.dumps(forge.provider_list(), sort_keys=True)

    @server.resource("mncs-forge://providers/capability-blockers")
    def provider_blockers_resource() -> str:
        return json.dumps(forge.capability_blockers(), sort_keys=True)

    @server.resource("mncs-forge://verifiers/declared")
    def declared_verifiers() -> str:
        return json.dumps(forge.verifier_list(), sort_keys=True)

    @server.resource("mncs-forge://guide/usage")
    def usage_guide() -> str:
        return (
            "Inspect authority, begin an epoch, register candidates, run declared development "
            "checks or explicitly selected bounded micro-verifiers, compare under policy, select, "
            "freeze, then start a separate evaluator-mode server. Never use final evaluation as "
            "repair feedback. MNCS/MNCDS validators remain offline authorities; missing evidence "
            "stays UNKNOWN."
        )

    @server.prompt(name="start_controlled_machine_native_epoch")
    def start_epoch_prompt() -> str:
        return (
            "Inspect the Forge project and claim boundaries. Begin a development epoch with "
            "explicit generator/evaluator identities and authority overlap. Modify only declared "
            "candidate/generated paths and register every candidate identity."
        )

    @server.prompt(name="evaluate_and_compare_candidates")
    def compare_prompt() -> str:
        return (
            "Run only declared development checks, reconcile FAIL > UNKNOWN > PASS, then compare "
            "candidate identities under the configured selection policy. Do not select from one "
            "benchmark observation or when evidence is missing or incomparable."
        )

    @server.prompt(name="explain_unknown_claim")
    def explain_unknown_prompt() -> str:
        return (
            "Read separate claim statuses and blockers. State the exact unresolved fact, affected "
            "claim, provider limitation, required evidence class, and whether external authority "
            "is required. Never silently promote UNKNOWN to PASS."
        )

    @server.prompt(name="prepare_candidate_for_freeze")
    def freeze_prompt() -> str:
        return (
            "Verify candidate identity, complete declared required evidence, compare under the "
            "predeclared rule, record selection, and freeze contract/reference/evaluator/policy/"
            "environment identities. Final evaluation belongs to evaluator mode and is not repair "
            "feedback for the same epoch."
        )

    @server.prompt(name="review_failed_development_check")
    def failed_check_prompt() -> str:
        return (
            "Use the compact failure explanation, inspect only disclosed witnesses and locations, "
            "repair within declared writable paths, register a descendant candidate, and rerun the "
            "declared check. Preserve the failed record."
        )

    return server


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="mncs-forge-mcp")
    parser.add_argument("--config", type=Path, default=Path("mncs-forge.toml"))
    parser.add_argument("--mode", choices=("development", "evaluator"), default="development")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    forge = Forge(load_config(args.config), mode=args.mode)
    build_server(forge).run(transport="stdio")


if __name__ == "__main__":
    main()
