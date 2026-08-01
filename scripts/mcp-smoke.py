#!/usr/bin/env python3
"""Direct stdio MCP initialize, discovery, and project-inspection smoke."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

EXPECTED = {
    "mncs_forge_project_inspect",
    "mncs_forge_claim_status",
    "mncs_forge_claim_blockers",
    "mncs_forge_providers_list",
    "mncs_forge_provider_probe",
    "mncs_forge_capability_blockers",
    "mncs_forge_epoch_begin",
    "mncs_forge_candidate_register",
    "mncs_forge_development_checks_run",
    "mncs_forge_failure_explain",
    "mncs_forge_candidate_compare",
    "mncs_forge_candidate_select",
    "mncs_forge_candidate_reject",
    "mncs_forge_candidate_freeze",
    "mncs_forge_evidence_reconcile",
    "mncs_forge_bundle_build",
}


async def smoke(executable: Path, config: Path) -> dict[str, object]:
    parameters = StdioServerParameters(
        command=str(executable),
        args=["--config", str(config), "--mode", "development"],
    )
    async with (
        stdio_client(parameters) as (reader, writer),
        ClientSession(reader, writer) as session,
    ):
        initialization = await session.initialize()
        tools = await session.list_tools()
        names = {tool.name for tool in tools.tools}
        missing = sorted(EXPECTED - names)
        if missing:
            raise RuntimeError("missing MCP tools: " + ", ".join(missing))
        result = await session.call_tool("mncs_forge_project_inspect", {})
        if result.isError:
            raise RuntimeError("project inspection MCP call failed")
        providers = await session.call_tool("mncs_forge_providers_list", {})
        if providers.isError:
            raise RuntimeError("provider list MCP call failed")
        blockers = await session.call_tool("mncs_forge_capability_blockers", {})
        if blockers.isError:
            raise RuntimeError("capability blockers MCP call failed")
        return {
            "ok": True,
            "server": initialization.serverInfo.name,
            "protocol_version": initialization.protocolVersion,
            "tool_count": len(names),
            "expected_tools_present": True,
            "project_inspection_succeeded": True,
            "provider_list_succeeded": True,
            "capability_blockers_succeeded": True,
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("executable", type=Path)
    parser.add_argument("config", type=Path)
    args = parser.parse_args()
    result = asyncio.run(
        smoke(args.executable.resolve(strict=True), args.config.resolve(strict=True))
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
