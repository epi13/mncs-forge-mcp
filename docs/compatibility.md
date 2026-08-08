# Compatibility

MNCS Forge `0.1.0a2` targets Python 3.11–3.13, official Python MCP SDK `>=1.29,<2`, local stdio
MCP, Codex CLI MCP registration, MNCS Provider Protocol 0.1, MNCS validator public commands, and
MNCDS validator public commands.

Provider-neutral discovery was tested at Forge implementation commit
`7e0599a080a36d3415780ba9e9ff617a7d012fbd` against MNCS tooling commit
`202c13fad2ca613a3d4ad9340d384b2a079beadf` with Codex CLI `0.144.6`. The development stdio
inventory now includes the prior development operations, provider list/probe/blockers, and six
micro-verifier tools, with final evaluation available in evaluator mode only.

Historical Joern records remain frozen; Joern is optional and disabled by default. The inspected
host registration named `joern` resolved to a separately installed pipx
`joern-agent-bridge`, not either project checkout, so it was left untouched. Compatibility is
non-normative. Core MNCS validation never launches Forge or a provider, and MNCS CI does not
depend on mutable Forge `main`.

The micro-verifier configuration is optional. Version-1 project files without `[[verifiers]]` or
`[verifier_limits]` continue to validate. The implementation uses Provider Protocol 0.1 extension
objects and adds no runtime dependency or generic Joern dependency.

Task 2 adds current persisted-record schema version `"1"` while retaining the historical
unversioned `0.1` state format as `"0.1-unversioned"` during normalization. The committed
pre-Task-2 fixture ledger is verified with its historical bytes and hash projection before payload
migration. Historical files are not rewritten. Unsupported explicit future record versions fail
with `UNSUPPORTED_RECORD_VERSION`, and trusted-context type mismatches fail with
`RECORD_TYPE_MISMATCH`. Public persistent record objects may now contain `record_type` and
`schema_version`; operation and Provider Protocol argument shapes are otherwise unchanged.

Task 3 adds the read-only `state` CLI command, `mncs_forge_state_inspect` MCP tool, lifecycle MCP
resource, and an embedded `project_inspect.lifecycle` summary. Existing records and the immutable
legacy corpus are not rewritten. Prospective transitions are stricter: successor epochs and
candidates require current parents, dispositions are terminal, selection requires the policy's
declared candidate evidence, and freeze/evaluator entry requires coherent current selection.
