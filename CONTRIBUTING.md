# Contributing

MNCS Forge is an experimental control plane whose correctness depends as much on preserved
authority and evidence boundaries as on ordinary functional behavior. Keep changes focused and
make every claim no stronger than the evidence produced by the change.

## Development setup

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
./scripts/check.sh
```

The check script verifies formatting, linting, strict type checking, tests, package building, and
whitespace. CI repeats the core checks on Linux, macOS, and Windows with Python 3.11 through 3.13.

## Project invariants

Contributions must preserve:

- separate MNCS and MNCDS statuses;
- explicit `UNKNOWN` for missing, stale, unavailable, malformed, or unsupported evidence;
- `FAIL > UNKNOWN > PASS` aggregation;
- no-shell execution and declared argument-array commands;
- development/evaluator mode separation;
- protected and writable path boundaries;
- append-only history and explicit lineage;
- offline validators as normative MNCS/MNCDS authorities; and
- non-normative positioning for local Forge results.

A configured provider is trusted code unless a runner establishes and records a stronger sandbox
boundary. Local hashes, signatures, or multiple same-operator machines do not automatically create
independence, protected custody, witnessing, certification, or governance approval.

## Choosing a change

Use the [development roadmap](ROADMAP.md) for release sequencing and the
[Codex implementation queue](docs/codex-next-steps.md) for bounded architectural tasks. Do not
combine several numbered architectural tasks into one pull request unless the dependency cannot be
separated and the PR explains why.

Changes to control flow, data flow, authorization, validation, error handling, or process cleanup
require an appropriate declared provider when structural evidence is needed. Use the same provider
and method before and after when comparative evidence is claimed. Joern is optional. Source
reading, grep, and line counts do not replace an unavailable capability; preserve `UNKNOWN` or
report a blocker.

Architecture changes should reference or update the relevant proposed decision under
[`docs/adr/`](docs/adr/). Moving files alone is not an architectural improvement unless dependency
boundaries are also enforced.

## Pull request expectations

A pull request should state:

- what changed and why;
- the roadmap or Codex task it implements, when applicable;
- public CLI, MCP, configuration, record, or Provider Protocol changes;
- migration and compatibility effects;
- security and claim-boundary effects;
- exact validation commands and results; and
- intentionally excluded follow-up work.

Add regression tests before or with the fix. Preserve failed and historical evidence records rather
than rewriting them. Benchmark output is development evidence and must include its environment and
limitations.

## Sensitive and redistributable material

Do not submit secrets, private evidence, protected datasets, or evidence you cannot redistribute.
By contributing intentionally, you agree to license the contribution under Apache-2.0.
