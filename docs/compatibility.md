# Compatibility

MNCS Forge `0.1.0a1` targets Python 3.11–3.13, official Python MCP SDK 1.29.x, local stdio MCP,
Codex CLI MCP registration, MNCS Provider Protocol 0.1, MNCS validator public commands, and MNCDS
validator public commands.

The initial integration is tested against the `main` history of
`epi13/machine-native-complexity-standard` at commit
`57b2b93b` (full identity recorded by the MNCS integration compatibility record before
publication). Compatibility is non-normative. Core MNCS validation never launches Forge, and
MNCS CI does not depend on mutable Forge `main`.
