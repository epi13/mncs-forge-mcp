# CLI and MCP interfaces

Run `mncs-forge --help` and `mncs-forge-mcp --help` for the installed interface.

MCP tools:

- `mncs_forge_project_inspect`
- `mncs_forge_claim_status`
- `mncs_forge_claim_blockers`
- `mncs_forge_providers_list`
- `mncs_forge_provider_probe`
- `mncs_forge_capability_blockers`
- `mncs_forge_epoch_begin`
- `mncs_forge_candidate_register`
- `mncs_forge_development_checks_run`
- `mncs_forge_failure_explain`
- `mncs_forge_candidate_compare`
- `mncs_forge_candidate_select`
- `mncs_forge_candidate_reject`
- `mncs_forge_candidate_freeze`
- `mncs_forge_evidence_reconcile`
- `mncs_forge_bundle_build`

The development inventory contains the 16 tools above. A separately started evaluator-mode
server additionally exposes `mncs_forge_final_evaluation_run`; the development registration
cannot use final evaluation as repair feedback.

All structured statuses remain separate. A declared command exit of zero is `UNKNOWN` unless it
emits a recognized structured status; command completion alone is not evidence `PASS`.

CLI equivalents are `mncs-forge providers list`, `mncs-forge providers probe PROVIDER_ID`, and
`mncs-forge providers blockers [CAPABILITY ...]`. Read-only resources include configured
providers and capability blockers.
