"""Human-facing MNCS Forge CLI."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .config import load_config
from .engine import Forge
from .errors import ForgeError
from .operations import (
    DEFAULT_OPERATION_REGISTRY,
    CliDecoder,
    OperationInterface,
)


def _cli_command(operation_id: str, part: int = -1) -> str:
    operation = DEFAULT_OPERATION_REGISTRY.resolve(operation_id)
    if operation.cli is None:  # pragma: no cover - registry metadata is validated at import
        raise RuntimeError(f"operation is not exposed through CLI: {operation_id}")
    return operation.cli.command[part]


def _register(parser: argparse.ArgumentParser, operation_id: str) -> argparse.ArgumentParser:
    parser.set_defaults(operation_id=operation_id)
    return parser


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
    _register(commands.add_parser(_cli_command("project.doctor")), "project.doctor")
    _register(commands.add_parser(_cli_command("project.inspect")), "project.inspect")
    _register(commands.add_parser(_cli_command("lifecycle.inspect")), "lifecycle.inspect")
    _register(commands.add_parser(_cli_command("claims.status")), "claims.status")
    blockers = _register(commands.add_parser(_cli_command("claims.blockers")), "claims.blockers")
    blockers.add_argument("claim", nargs="?", default="promotion")
    providers = commands.add_parser(_cli_command("providers.list", 0))
    provider_commands = providers.add_subparsers(dest="provider_command", required=True)
    _register(provider_commands.add_parser(_cli_command("providers.list")), "providers.list")
    probe = _register(
        provider_commands.add_parser(_cli_command("providers.probe")), "providers.probe"
    )
    probe.add_argument("provider_id")
    capability_blockers = _register(
        provider_commands.add_parser(_cli_command("providers.capability-blockers")),
        "providers.capability-blockers",
    )
    capability_blockers.add_argument("capabilities", nargs="*")

    verifier = commands.add_parser(_cli_command("verifiers.list", 0))
    verifier_commands = verifier.add_subparsers(dest="verifier_command", required=True)
    _register(verifier_commands.add_parser(_cli_command("verifiers.list")), "verifiers.list")
    verifier_describe = _register(
        verifier_commands.add_parser(_cli_command("verifiers.describe")),
        "verifiers.describe",
    )
    verifier_describe.add_argument("verifier_id")
    verifier_match = _register(
        verifier_commands.add_parser(_cli_command("verifiers.match")), "verifiers.match"
    )
    verifier_match.add_argument("--uncertainty", action="append", default=[])
    verifier_match.add_argument("--language")
    verifier_match.add_argument("--artifact-type")
    verifier_match.add_argument("--changed", action="append", default=[])
    verifier_match.add_argument("--scope")
    verifier_match.add_argument("--maximum-cost", choices=("low", "medium", "high"), default="high")
    verifier_match.add_argument("--category")
    verifier_match.add_argument("--active-mode", choices=("development", "evaluator"))
    verifier_run = _register(
        verifier_commands.add_parser(_cli_command("verifiers.run")), "verifiers.run"
    )
    verifier_run.add_argument("verifier_id")
    _verifier_run_arguments(verifier_run)
    verifier_batch = _register(
        verifier_commands.add_parser(_cli_command("verifiers.batch")), "verifiers.batch"
    )
    verifier_batch.add_argument("verifier_ids", nargs="+")
    _verifier_run_arguments(verifier_batch)
    verifier_explain = _register(
        verifier_commands.add_parser(_cli_command("verifiers.explain")), "verifiers.explain"
    )
    verifier_explain.add_argument("output_identity")

    epoch = commands.add_parser(_cli_command("epochs.begin", 0))
    epoch_commands = epoch.add_subparsers(dest="epoch_command", required=True)
    begin = _register(epoch_commands.add_parser(_cli_command("epochs.begin")), "epochs.begin")
    begin.add_argument("--generator", required=True)
    begin.add_argument("--evaluator", required=True)
    begin.add_argument("--parent")
    begin.add_argument("--authority-overlap", action="append", default=[])

    candidate = commands.add_parser(_cli_command("candidates.register", 0))
    candidate_commands = candidate.add_subparsers(dest="candidate_command", required=True)
    register = _register(
        candidate_commands.add_parser(_cli_command("candidates.register")),
        "candidates.register",
    )
    register.add_argument("--changed", action="append", default=[])
    register.add_argument("--hypothesis", required=True)
    register.add_argument("--generator", required=True)
    register.add_argument("--generator-config", required=True)
    register.add_argument("--parent")
    register.add_argument("--expected-identity")
    compare = _register(
        candidate_commands.add_parser(_cli_command("candidates.compare")),
        "candidates.compare",
    )
    compare.add_argument("candidate_ids", nargs="+")
    for disposition in ("select", "reject"):
        operation_id = f"candidates.{disposition}"
        action = _register(candidate_commands.add_parser(_cli_command(operation_id)), operation_id)
        action.add_argument("candidate_id")
        action.add_argument("--reason", required=True)

    check = commands.add_parser(_cli_command("development.checks.run", 0))
    check_commands = check.add_subparsers(dest="check_command", required=True)
    development = _register(
        check_commands.add_parser(_cli_command("development.checks.run")),
        "development.checks.run",
    )
    development.add_argument("workflows", nargs="+")
    development.add_argument("--candidate")

    explain = _register(
        commands.add_parser(_cli_command("development.failure.explain")),
        "development.failure.explain",
    )
    explain.add_argument("--result")
    freeze = _register(commands.add_parser(_cli_command("candidates.freeze")), "candidates.freeze")
    freeze.add_argument("candidate_id")
    freeze.add_argument("--environment", required=True)
    freeze.add_argument("--evidence-plan", required=True)
    evaluate = _register(
        commands.add_parser(_cli_command("evaluation.final.run")), "evaluation.final.run"
    )
    evaluate.add_argument("workflows", nargs="+")
    reconcile = _register(
        commands.add_parser(_cli_command("evidence.reconcile")), "evidence.reconcile"
    )
    reconcile.add_argument("--candidate")
    bundle = _register(commands.add_parser(_cli_command("bundles.build")), "bundles.build")
    bundle.add_argument("workflow")
    bundle.add_argument("--candidate")

    ledger = commands.add_parser(_cli_command("ledger.verify", 0))
    ledger_commands = ledger.add_subparsers(dest="ledger_command", required=True)
    _register(ledger_commands.add_parser(_cli_command("ledger.verify")), "ledger.verify")
    config = commands.add_parser(_cli_command("config.validate", 0))
    config_commands = config.add_subparsers(dest="config_command", required=True)
    _register(config_commands.add_parser(_cli_command("config.validate")), "config.validate")
    _register(commands.add_parser(_cli_command("operations.inventory")), "operations.inventory")
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


def _cli_payload(args: argparse.Namespace) -> dict[str, object]:
    operation = DEFAULT_OPERATION_REGISTRY.resolve(str(args.operation_id))
    if operation.cli is None:  # pragma: no cover - parser uses only CLI operations
        raise ForgeError("OPERATION_NOT_EXPOSED", "operation is not exposed through CLI")
    payload: dict[str, object] = {}
    for binding in operation.cli.bindings:
        value = getattr(args, binding.namespace_name)
        if binding.decoder is CliDecoder.JSON_OBJECT and value is not None:
            value = _json_object(str(value), binding.namespace_name.replace("_", "-"))
        elif binding.decoder is CliDecoder.DEPENDENCIES:
            value = _dependencies(list(value))
        payload[binding.input_name] = value
    return payload


def _dispatch(forge: Forge, args: argparse.Namespace) -> object:
    return DEFAULT_OPERATION_REGISTRY.invoke(
        forge,
        str(args.operation_id),
        _cli_payload(args),
        interface=OperationInterface.CLI,
    )


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
