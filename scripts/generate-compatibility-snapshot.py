#!/usr/bin/env python3
"""Generate the semantic public compatibility snapshot for the 0.1.0b1 boundary."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import inspect
import json
import sys
import tomllib
from collections.abc import Mapping
from pathlib import Path
from types import SimpleNamespace
from typing import cast

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mncs_forge.cli import _common_parser  # noqa: E402
from mncs_forge.engine import Forge, aggregate_status  # noqa: E402
from mncs_forge.operations import (  # noqa: E402
    DEFAULT_OPERATION_REGISTRY,
    canonical_operation_inventory,
)
from mncs_forge.server import build_server  # noqa: E402

OUTPUT = ROOT / "tests/compatibility/0.1.0b1.json"
SCHEMA_ANNOTATIONS = frozenset({"$id", "$schema", "description", "title"})


def _json_value(value: object) -> object:
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, tuple | frozenset | set):
        return [_json_value(item) for item in value]
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in sorted(value.items())}
    if value is None or isinstance(value, bool | int | float | str):
        return value
    raise TypeError(f"snapshot value is not deterministic JSON: {type(value).__name__}")


def _semantic_schema(value: object) -> object:
    if isinstance(value, dict):
        return {
            str(key): _semantic_schema(item)
            for key, item in sorted(value.items())
            if key not in SCHEMA_ANNOTATIONS
        }
    if isinstance(value, list):
        return [_semantic_schema(item) for item in value]
    return value


def _without_explanatory_prose(value: object) -> object:
    if isinstance(value, dict):
        return {
            str(key): _without_explanatory_prose(item)
            for key, item in sorted(value.items())
            if key != "reason"
        }
    if isinstance(value, list):
        return [_without_explanatory_prose(item) for item in value]
    return value


def _canonical_digest(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _parser_action(action: argparse.Action) -> dict[str, object]:
    # `argparse.Action.required` is interpreter-dependent for positional `nargs="*"`
    # actions (Python 3.11 reports true while newer versions report false). Capture
    # the public CLI grammar instead of that implementation detail.
    if action.option_strings:
        required = bool(action.required)
    else:
        required = action.nargs not in ("?", "*", argparse.REMAINDER)
    result: dict[str, object] = {
        "destination": action.dest,
        "options": list(action.option_strings),
        "required": required,
        "nargs": _json_value(action.nargs),
        "default": _json_value(action.default),
    }
    if action.choices is not None:
        result["choices"] = [_json_value(item) for item in action.choices]
    if action.const is not None:
        result["const"] = _json_value(action.const)
    if action.metavar is not None:
        result["metavar"] = _json_value(action.metavar)
    if action.type is not None:
        result["value_type"] = "path" if action.type is Path else action.type.__name__
    return result


def _ordinary_actions(parser: argparse.ArgumentParser) -> list[dict[str, object]]:
    return [
        _parser_action(action)
        for action in parser._actions
        if not isinstance(action, argparse._SubParsersAction) and action.dest != "help"
    ]


def _cli_contract() -> dict[str, object]:
    root = _common_parser()
    leaves: dict[str, object] = {}

    def visit(parser: argparse.ArgumentParser, prefix: tuple[str, ...] = ()) -> None:
        operation_id = parser.get_default("operation_id")
        if isinstance(operation_id, str):
            leaves[" ".join(prefix)] = {
                "operation_id": operation_id,
                "arguments": _ordinary_actions(parser),
            }
        for action in parser._actions:
            if isinstance(action, argparse._SubParsersAction):
                for name, child in sorted(action.choices.items()):
                    visit(child, (*prefix, name))

    visit(root)
    bindings = {
        operation.operation_id: [
            {
                "input": binding.input_name,
                "namespace": binding.namespace_name,
                "decoder": binding.decoder.value,
            }
            for binding in operation.cli.bindings
        ]
        for operation in DEFAULT_OPERATION_REGISTRY.for_cli()
        if operation.cli is not None
    }
    return {
        "global_arguments": _ordinary_actions(root),
        "commands": leaves,
        "bindings": bindings,
    }


async def _mcp_mode(mode: str) -> dict[str, object]:
    forge = cast(Forge, SimpleNamespace(mode=mode))
    server = build_server(forge)
    tools = await server.list_tools()
    resources = await server.list_resources()
    return {
        "tools": {
            tool.name: {
                "input_schema_sha256": _canonical_digest(_semantic_schema(tool.inputSchema)),
                "required_inputs": sorted(tool.inputSchema.get("required", [])),
                "input_properties": sorted(tool.inputSchema.get("properties", {})),
                "output_schema_sha256": _canonical_digest(_semantic_schema(tool.outputSchema)),
            }
            for tool in tools
        },
        "resources": sorted(
            [
                {
                    "uri": str(resource.uri),
                    "mime_type": resource.mimeType,
                }
                for resource in resources
            ],
            key=lambda item: item["uri"],
        ),
    }


def _facade_contract() -> dict[str, object]:
    methods = {
        name: str(inspect.signature(value))
        for name, value in Forge.__dict__.items()
        if callable(value) and (name == "__init__" or not name.startswith("_"))
    }
    return {
        "class": "mncs_forge.engine.Forge",
        "methods": dict(sorted(methods.items())),
        "aggregate_status": str(inspect.signature(aggregate_status)),
    }


def _schema_contract(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    semantic = _semantic_schema(value)
    definitions = value.get("$defs", {})
    return {
        "semantic_sha256": _canonical_digest(semantic),
        "root_required": sorted(value.get("required", [])),
        "root_properties": sorted(value.get("properties", {})),
        "definitions": {
            name: {
                "required": sorted(definition.get("required", [])),
                "properties": sorted(definition.get("properties", {})),
            }
            for name, definition in sorted(definitions.items())
            if isinstance(definition, dict)
        },
    }


def _package_contract() -> dict[str, object]:
    with (ROOT / "pyproject.toml").open("rb") as stream:
        project = tomllib.load(stream)["project"]
    return {
        "name": project["name"],
        "requires_python": project["requires-python"],
        "dependencies": sorted(project["dependencies"]),
        "scripts": dict(sorted(project["scripts"].items())),
    }


def snapshot() -> dict[str, object]:
    operation_inventory = canonical_operation_inventory()
    semantic_operations = _without_explanatory_prose(operation_inventory)
    return {
        "boundary": "0.1.0b1",
        "snapshot_schema": "1",
        "configuration": _schema_contract(ROOT / "schemas/mncs-forge-config.schema.json"),
        "records": _schema_contract(ROOT / "src/mncs_forge/resources/forge-records-1.schema.json"),
        "operations": {
            "semantic_sha256": _canonical_digest(semantic_operations),
            "schema_version": operation_inventory["schema_version"],
            "operation_ids": [
                operation["operation_id"] for operation in operation_inventory["operations"]
            ],
        },
        "cli": _cli_contract(),
        "mcp": {
            "development": asyncio.run(_mcp_mode("development")),
            "evaluator": asyncio.run(_mcp_mode("evaluator")),
        },
        "python_facade": _facade_contract(),
        "packaging": _package_contract(),
        "intentional_exclusions": [
            "human-readable help and error prose",
            "MCP prompts and tool descriptions",
            "timestamps, filesystem paths, and environment values",
            "Python callables, module layout behind Forge, and object representations",
            "performance telemetry and package release version",
        ],
    }


def _encoded(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, indent=2) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--check", action="store_true")
    group.add_argument("--write", action="store_true")
    args = parser.parse_args()
    encoded = _encoded(snapshot())
    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_text(encoding="utf-8") != encoded:
            print(f"compatibility snapshot is stale: {OUTPUT}", file=sys.stderr)
            return 1
        return 0
    if args.write:
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(encoded, encoding="utf-8")
        return 0
    sys.stdout.write(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
