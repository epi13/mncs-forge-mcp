# Compatibility

MNCS Forge `0.1.0a2` targets Python 3.11–3.13, official Python MCP SDK `>=1.29,<2`, local stdio
MCP, Codex CLI MCP registration, MNCS Provider Protocol 0.1, MNCS validator public commands, and
MNCDS validator public commands.

Provider-neutral discovery was tested at Forge implementation commit
`7e0599a080a36d3415780ba9e9ff617a7d012fbd` against MNCS tooling commit
`202c13fad2ca613a3d4ad9340d384b2a079beadf` with Codex CLI `0.144.6`. The development stdio
inventory contains 16 tools: the prior development operations plus provider list, probe, and
capability blockers, with final evaluation moved to evaluator mode only.

Historical Joern records remain frozen; Joern is optional and disabled by default. The inspected
host registration named `joern` resolved to a separately installed pipx
`joern-agent-bridge`, not either project checkout, so it was left untouched. Compatibility is
non-normative. Core MNCS validation never launches Forge or a provider, and MNCS CI does not
depend on mutable Forge `main`.
