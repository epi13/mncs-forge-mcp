# Task 6 pre-refactor dispatch inventory

This inventory characterizes merged Task 5 `main` at
`800c23e3becd3c6d0259cb887c1e2fbe7292ae18`. It is a compatibility contract and operator-controlled
development evidence, not evidence of conformance, independent evaluation, or custody.

## Baseline surfaces

The CLI exposed 27 command leaves. Its `_dispatch` function independently selected facade methods,
including four method-reference entries plus 20 direct business calls and local ledger/config
branches. Development MCP exposed 23 tools; evaluator MCP exposed those tools plus final evaluation.
`server.py` independently declared all 24 possible tools and directly invoked facade methods.

| Canonical operation | CLI command | MCP tool | Allowed mode | Mutation | Intentional asymmetry |
| --- | --- | --- | --- | --- | --- |
| `project.doctor` | `doctor` | — | both | read-only | CLI diagnostic |
| `project.inspect` | `inspect` | `mncs_forge_project_inspect` | both | read-only | — |
| `lifecycle.inspect` | `state` | `mncs_forge_state_inspect` | both | read-only | — |
| `claims.status` | `status` | `mncs_forge_claim_status` | both | read-only | — |
| `claims.blockers` | `blockers` | `mncs_forge_claim_blockers` | both | read-only | — |
| `providers.list` | `providers list` | `mncs_forge_providers_list` | both | read-only | — |
| `providers.probe` | `providers probe` | `mncs_forge_provider_probe` | development | mutating | visible but forbidden in evaluator MCP |
| `providers.capability-blockers` | `providers blockers` | `mncs_forge_capability_blockers` | both | read-only | — |
| `verifiers.list` | `verifier list` | `mncs_forge_verifier_list` | both | read-only | — |
| `verifiers.describe` | `verifier describe` | `mncs_forge_verifier_describe` | both | read-only | — |
| `verifiers.match` | `verifier match` | `mncs_forge_verifier_match` | both | read-only | — |
| `verifiers.run` | `verifier run` | `mncs_forge_verifier_run` | both | mutating | verifier declaration further limits mode |
| `verifiers.batch` | `verifier batch` | `mncs_forge_verifier_batch` | both | mutating | verifier declarations further limit mode |
| `verifiers.explain` | `verifier explain` | `mncs_forge_verifier_explain` | both | read-only | — |
| `epochs.begin` | `epoch begin` | `mncs_forge_epoch_begin` | development | mutating | visible but forbidden in evaluator MCP |
| `candidates.register` | `candidate register` | `mncs_forge_candidate_register` | development | mutating | visible but forbidden in evaluator MCP |
| `development.checks.run` | `check development` | `mncs_forge_development_checks_run` | development | mutating | visible but forbidden in evaluator MCP |
| `development.failure.explain` | `explain` | `mncs_forge_failure_explain` | both | read-only | disclosure remains mode-sensitive |
| `candidates.compare` | `candidate compare` | `mncs_forge_candidate_compare` | development | read-only | visible but forbidden in evaluator MCP |
| `candidates.select` | `candidate select` | `mncs_forge_candidate_select` | development | mutating | visible but forbidden in evaluator MCP |
| `candidates.reject` | `candidate reject` | `mncs_forge_candidate_reject` | development | mutating | visible but forbidden in evaluator MCP |
| `candidates.freeze` | `freeze` | `mncs_forge_candidate_freeze` | development | mutating | visible but forbidden in evaluator MCP |
| `evaluation.final.run` | `evaluate` | `mncs_forge_final_evaluation_run` | evaluator | mutating | MCP tool evaluator-only; CLI fails in development |
| `evidence.reconcile` | `reconcile` | `mncs_forge_evidence_reconcile` | both | read-only | — |
| `bundles.build` | `bundle` | `mncs_forge_bundle_build` | both | mutating | mode-specific lifecycle entry |
| `ledger.verify` | `ledger verify` | — | both | read-only | CLI storage diagnostic |
| `config.validate` | `config validate` | — | both | read-only | CLI startup diagnostic |

Task 6 adds `operations.inventory` as the twenty-eighth canonical operation, exposed by the new
`operations` CLI command and `mncs-forge://operations` MCP resource.

## Resource and prompt boundary

Nine baseline resources projected project, lifecycle, candidate, evidence, claim, provider, and
verifier operations. The static usage resource and five prompts are presentation/guidance rather
than business operations. Task 6 retains them separately, routes each operation-backed resource
through canonical invocation, and adds the registry inventory resource. No baseline prompt name or
resource URI was removed or renamed.
