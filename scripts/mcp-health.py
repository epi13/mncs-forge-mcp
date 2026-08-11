#!/usr/bin/env python3
"""Probe the real Forge stdio MCP path and classify failures."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from mncs_forge import __version__ as FORGE_VERSION

REQUIRED_TOOLS = {
    "mncs_forge_project_inspect",
    "mncs_forge_providers_list",
    "mncs_forge_capability_blockers",
}
EXIT_CODES = {
    "healthy": 0,
    "configuration_missing": 2,
    "executable_missing": 2,
    "process_start_failed": 3,
    "mcp_initialization_failed": 4,
    "capability_unavailable": 5,
}


def _value(value: object, *names: str) -> object:
    for name in names:
        try:
            return getattr(value, name)
        except AttributeError:
            continue
    return None


def _diagnostic(exc: BaseException) -> str:
    value = str(exc).strip() or type(exc).__name__
    return value[:1000].replace(os.linesep, " ")


async def _probe(executable: Path, config: Path) -> dict[str, Any]:
    parameters = StdioServerParameters(
        command=str(executable),
        args=["--config", str(config), "--mode", "development"],
    )
    try:
        async with (
            stdio_client(parameters) as (reader, writer),
            ClientSession(reader, writer) as session,
        ):
            initialization = await session.initialize()
            tools = await session.list_tools()
            names = {tool.name for tool in tools.tools}
            missing = sorted(REQUIRED_TOOLS - names)
            if missing:
                return {
                    "status": "capability_unavailable",
                    "reachable": True,
                    "missing_capabilities": missing,
                    "server": _value(_value(initialization, "serverInfo", "server_info"), "name"),
                    "version": _value(
                        _value(initialization, "serverInfo", "server_info"), "version"
                    ),
                    "protocol": "MCP",
                    "tool_count": len(names),
                }
            inspection = await session.call_tool("mncs_forge_project_inspect", {})
            if bool(_value(inspection, "isError", "is_error")):
                return {
                    "status": "capability_unavailable",
                    "reachable": True,
                    "diagnostic": "project inspection tool returned an MCP error",
                    "server": _value(_value(initialization, "serverInfo", "server_info"), "name"),
                    "version": _value(
                        _value(initialization, "serverInfo", "server_info"), "version"
                    ),
                    "protocol": "MCP",
                    "tool_count": len(names),
                }
            return {
                "status": "healthy",
                "reachable": True,
                "server": _value(_value(initialization, "serverInfo", "server_info"), "name"),
                "version": _value(_value(initialization, "serverInfo", "server_info"), "version"),
                "protocol": "MCP",
                "protocol_version": _value(initialization, "protocolVersion", "protocol_version"),
                "tool_count": len(names),
                "capabilities": sorted(REQUIRED_TOOLS),
            }
    except (FileNotFoundError, PermissionError) as exc:
        return {
            "status": "process_start_failed",
            "reachable": False,
            "diagnostic": _diagnostic(exc),
        }
    except BaseException as exc:
        return {
            "status": "mcp_initialization_failed",
            "reachable": False,
            "diagnostic": _diagnostic(exc),
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", type=Path)
    parser.add_argument("config", type=Path)
    args = parser.parse_args()
    executable = args.executable.expanduser().resolve(strict=False)
    config = args.config.expanduser().resolve(strict=False)
    result: dict[str, Any] = {
        "configured": config.is_file(),
        "executable": str(executable),
        "config": str(config),
        "protocol": "MCP",
        "forge_version": FORGE_VERSION,
    }
    if not config.is_file():
        result.update(status="configuration_missing", reachable=False)
    elif not executable.is_file() or not os.access(executable, os.X_OK):
        result.update(status="executable_missing", reachable=False)
    else:
        result.update(asyncio.run(_probe(executable, config)))
    print(json.dumps(result, sort_keys=True))
    return EXIT_CODES[str(result["status"])]


if __name__ == "__main__":
    raise SystemExit(main())
