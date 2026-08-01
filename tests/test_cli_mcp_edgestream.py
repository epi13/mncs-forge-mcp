from __future__ import annotations

import asyncio
import subprocess
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from mncs_forge.cli import run
from mncs_forge.edgestream import inspect


def test_cli_smoke(project: Path) -> None:
    code, result = run(["--config", str(project / "mncs-forge.toml"), "config", "validate"])
    assert code == 0
    assert result["ok"] is True
    code, result = run(["--config", str(project / "mncs-forge.toml"), "inspect"])
    assert code == 0
    assert result["mode"] == "development"


def test_direct_mcp_protocol_smoke(project: Path) -> None:
    root = Path(__file__).parents[1]
    executable = Path(sys.executable).with_name("mncs-forge-mcp")
    assert executable.is_file()
    result = subprocess.run(
        [
            sys.executable,
            str(root / "scripts/mcp-smoke.py"),
            str(executable),
            str(project / "mncs-forge.toml"),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert '"expected_tools_present": true' in result.stdout


async def _provider_mcp_calls(executable: Path, config: Path) -> None:
    parameters = StdioServerParameters(
        command=str(executable),
        args=["--config", str(config), "--mode", "development"],
    )
    async with (
        stdio_client(parameters) as (reader, writer),
        ClientSession(reader, writer) as session,
    ):
        await session.initialize()
        tools = await session.list_tools()
        names = {tool.name for tool in tools.tools}
        assert "mncs_forge_providers_list" in names
        assert "mncs_forge_provider_probe" in names
        assert "mncs_forge_capability_blockers" in names
        assert "mncs_forge_final_evaluation_run" not in names
        listing = await session.call_tool("mncs_forge_providers_list", {})
        assert not listing.isError
        probe = await session.call_tool(
            "mncs_forge_provider_probe", {"provider_id": "provider-pass"}
        )
        assert not probe.isError
        assert probe.structuredContent["status"] == "PASS"  # type: ignore[index]
        blockers = await session.call_tool(
            "mncs_forge_capability_blockers",
            {"required_capabilities": ["bounded-structural"]},
        )
        assert not blockers.isError
        assert blockers.structuredContent["status"] == "PASS"  # type: ignore[index]


def test_mcp_provider_list_probe_and_blockers(project: Path) -> None:
    executable = Path(sys.executable).with_name("mncs-forge-mcp")
    asyncio.run(_provider_mcp_calls(executable, project / "mncs-forge.toml"))


def test_edgestream_read_only_integration_fixture(tmp_path: Path) -> None:
    required = [
        "specification/contract.md",
        "reference/edgestream_reference.c",
        "machine/edgestream_generated.c",
        "preregistration.json",
        "mncds/development-record.json",
        "evidence/results/study-summary.json",
    ]
    for relative in required:
        path = tmp_path / "case-studies/edgestream" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}\n", encoding="utf-8")
    before = {
        path.relative_to(tmp_path): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
    result = inspect(tmp_path)
    after = {
        path.relative_to(tmp_path): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
    assert result["status"] == "PASS"
    assert before == after
    assert "protected custody" in str(result["limitations"])
