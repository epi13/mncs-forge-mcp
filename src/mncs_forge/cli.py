"""Human-facing MNCS Forge CLI."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .config import load_config
from .engine import Forge
from .errors import ForgeError


def _verifier_run_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--candidate")
    parser.add_argument("--changed", action="append", default=[])
    parser.add_argument("--scope")
    parser.add_argument("--source-region", help="bounded JSON source-region object")
    parser.add_argument("--contract")
    parser.add_argument("--dependency", action="append", default=[], metavar="NAME=IDENTITY")
    parser.add_argument("--prior-artifact")
    parser.add_argument("--parameters", default="{}", help="JSON object of declared parameters")


def _common_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mncs-forge")
    parser.add_argument("--config", type=Path, default=Path("mncs-forge.toml"))
    parser.add_argument("--mode", choices=("development", "evaluator"), default="development")
    parser.add_argument("--json", action="store_true", help="emit structured JSON (default)")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor")
    commands.add_parser("inspect")
    commands.add_parser("status")
    blockers = commands.add_parser("blockers")
    blockers.add_argument("claim", nargs="?", default="promotion")
    providers = commands.add_parser("providers")
    provider_commands = providers.add_subparsers(dest="provider_command", required=True)
    provider_commands.add_parser("list")
    probe = provider_commands.add_parser("probe")
    probe.add_argument("provider_id")
    capability_blockers = provider_commands.add_parser("blockers")
    capability_blockers.add_argument("capabilities", nargs="*")

    verifier = commands.add_parser("verifier")
    verifier_commands = verifier.add_subparsers(dest="verifier_command", required=True)
    verifier_commands.add_parser("list")
    verifier_describe = verifier_commands.add_parser("describe")
    verifier_describe.add_argument("verifier_id")
    verifier_match = verifier_commands.add_parser("match")
    verifier_match.add_argument("--uncertainty", action="append", default=[])
    verifier_match.add_argument("--language")
    verifier_match.add_argument("--artifact-type")
    verifier_match.add_argument("--changed", action="append", default=[])
    verifier_match.add_argument("--scope")
    verifier_match.add_argument("--maximum-cost", choices=("low", "medium", "high"), default="high")
    verifier_match.add_argument("--category")
    verifier_match.add_argument("--active-mode", choices=("development", "evaluator"))
    verifier_run = verifier_commands.add_parser("run")
    verifier_run.add_argument("verifier_id")
    _verifier_run_arguments(verifier_run)
    verifier_batch = verifier_commands.add_parser("batch")
    verifier_batch.add_argument("verifier_ids", nargs="+")
    _verifier_run_arguments(verifier_batch)
    verifier_explain = verifier_commands.add_parser("explain")
    verifier_explain.add_argument("output_identity")

    epoch = commands.add_parser("epoch")
    epoch_commands = epoch.add_subparsers(dest="epoch_command", required=True)
    begin = epoch_commands.add_parser("begin")
    begin.add_argument("--generator", required=True)
    begin.add_argument("--evaluator", required=True)
    begin.add_argument("--parent")
    begin.add_argument("--authority-overlap", action="append", default=[])

    candidate = commands.add_parser("candidate")
    candidate_commands = candidate.add_subparsers(dest="candidate_command", required=True)
    register = candidate_commands.add_parser("register")
    register.add_argument("--changed", action="append", default=[])
    register.add_argument("--hypothesis", required=True)
    register.add_argument("--generator", required=True)
    register.add_argument("--generator-config", required=True)
    register.add_argument("--parent")
    register.add_argument("--expected-identity")
    compare = candidate_commands.add_parser("compare")
    compare.add_argument("candidate_ids", nargs="+")
    for disposition in ("select", "reject"):
        action = candidate_commands.add_parser(disposition)
        action.add_argument("candidate_id")
        action.add_argument("--reason", required=True)

    check = commands.add_parser("check")
    check_commands = check.add_subparsers(dest="check_command", required=True)
    development = check_commands.add_parser("development")
    development.add_argument("workflows", nargs="+")
    development.add_argument("--candidate")

    explain = commands.add_parser("explain")
    explain.add_argument("--result")
    freeze = commands.add_parser("freeze")
    freeze.add_argument("candidate_id")
    freeze.add_argument("--environment", required=True)
    freeze.add_argument("--evidence-plan", required=True)
    evaluate = commands.add_parser("evaluate")
    evaluate.add_argument("workflows", nargs="+")
    reconcile = commands.add_parser("reconcile")
    reconcile.add_argument("--candidate")
    bundle = commands.add_parser("bundle")
    bundle.add_argument("workflow")
    bundle.add_argument("--candidate")

    ledger = commands.add_parser("ledger")
    ledger_commands = ledger.add_subparsers(dest="ledger_command", required=True)
    ledger_commands.add_parser("verify")
    config = commands.add_parser("config")
    config_commands = config.add_subparsers(dest="config_command", required=True)
    config_commands.add_parser("validate")
    return parser


def _json_object(value: str, label: str) -> dict[str, object]:
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise ForgeError("CLI_INPUT", f"{label} must be a JSON object")
    return {str(key): item for key, item in parsed.items()}


def _dependencies(values: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for value in values:
        name, separator, identity = value.partition("=")
        if not separator or not name or not identity:
            raise ForgeError("CLI_INPUT", "dependency must use NAME=IDENTITY")
        if name in result:
            raise ForgeError("CLI_INPUT", f"duplicate dependency name: {name}")
        result[name] = identity
    return result


def _verifier_inputs(args: argparse.Namespace) -> dict[str, Any]:
    source_region = (
        _json_object(str(args.source_region), "source-region") if args.source_region else None
    )
    return {
        "candidate_identity": args.candidate,
        "changed_paths": list(args.changed),
        "scope": args.scope,
        "source_region": source_region,
        "contract_identity": args.contract,
        "dependency_slice_identities": _dependencies(list(args.dependency)),
        "prior_artifact_identity": args.prior_artifact,
        "question_parameters": _json_object(str(args.parameters), "parameters"),
    }


def _dispatch(forge: Forge, args: argparse.Namespace) -> object:
    command = str(args.command)
    simple: dict[str, Callable[[], object]] = {
        "doctor": forge.doctor,
        "inspect": forge.project_inspect,
        "status": forge.claim_status,
    }
    if command in simple:
        return simple[command]()
    if command == "blockers":
        return forge.claim_blockers(str(args.claim))
    if command == "providers":
        provider_command = str(args.provider_command)
        if provider_command == "list":
            return forge.provider_list()
        if provider_command == "probe":
            return forge.provider_probe(str(args.provider_id))
        return forge.capability_blockers(list(args.capabilities))
    if command == "verifier":
        verifier_command = str(args.verifier_command)
        if verifier_command == "list":
            return forge.verifier_list()
        if verifier_command == "describe":
            return forge.verifier_describe(str(args.verifier_id))
        if verifier_command == "match":
            return forge.verifier_match(
                uncertainty_classes=list(args.uncertainty),
                language=args.language,
                artifact_type=args.artifact_type,
                changed_paths=list(args.changed),
                scope=args.scope,
                maximum_cost=str(args.maximum_cost),
                required_category=args.category,
                active_mode=args.active_mode,
            )
        if verifier_command == "run":
            return forge.verifier_run(str(args.verifier_id), **_verifier_inputs(args))
        if verifier_command == "batch":
            return forge.verifier_batch(list(args.verifier_ids), **_verifier_inputs(args))
        return forge.verifier_explain(str(args.output_identity))
    if command == "epoch":
        return forge.epoch_begin(
            generator_identity=str(args.generator),
            evaluator_identity=str(args.evaluator),
            parent_epoch=args.parent,
            authority_overlap=list(args.authority_overlap),
        )
    if command == "candidate":
        candidate_command = str(args.candidate_command)
        if candidate_command == "register":
            return forge.candidate_register(
                changed_files=list(args.changed),
                hypothesis=str(args.hypothesis),
                generator_identity=str(args.generator),
                generator_config_identity=str(args.generator_config),
                parent_candidate=args.parent,
                expected_identity=args.expected_identity,
            )
        if candidate_command == "compare":
            return forge.candidate_compare(list(args.candidate_ids))
        return forge.candidate_disposition(
            str(args.candidate_id),
            disposition="selected" if candidate_command == "select" else "rejected",
            reason=str(args.reason),
        )
    if command == "check":
        return forge.development_checks_run(list(args.workflows), args.candidate)
    if command == "explain":
        return forge.failure_explain(args.result)
    if command == "freeze":
        return forge.candidate_freeze(
            str(args.candidate_id),
            environment_identity=str(args.environment),
            required_evidence_plan=str(args.evidence_plan),
        )
    if command == "evaluate":
        return forge.final_evaluation_run(list(args.workflows))
    if command == "reconcile":
        return forge.evidence_reconcile(args.candidate)
    if command == "bundle":
        return forge.bundle_build(str(args.workflow), args.candidate)
    if command == "ledger":
        return forge.ledger.verify()
    if command == "config":
        return {
            "ok": True,
            "config": str(forge.config.config_path),
            "project_root": str(forge.config.root),
        }
    raise ForgeError("CLI_COMMAND", f"unsupported command: {command}")


def run(argv: list[str] | None = None) -> tuple[int, dict[str, Any]]:
    args = _common_parser().parse_args(argv)
    try:
        config = load_config(args.config)
        value = _dispatch(Forge(config, mode=args.mode), args)
        if isinstance(value, dict):
            return 0, value
        return 0, {"ok": True, "result": value}
    except ForgeError as exc:
        return 2, exc.as_dict()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        error = ForgeError("UNEXPECTED_INPUT", str(exc))
        return 2, error.as_dict()


def main(argv: list[str] | None = None) -> int:
    code, value = run(argv)
    json.dump(value, sys.stdout, ensure_ascii=False, allow_nan=False, sort_keys=True, indent=2)
    sys.stdout.write("\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
