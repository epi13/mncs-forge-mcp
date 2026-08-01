# Forge Cell execution assurance foundation

Forge Cell is the proposed execution boundary for running declared tests and evidence providers with
stronger isolation than Forge's current bounded local subprocess runner. This document defines the
reference artifacts and claim vocabulary added before any operating-system sandbox is implemented.

> The current implementation validates documents and assesses declared assurance. It does not
> create namespaces, apply seccomp or Landlock, enable `fs-verity`, produce TPM quotes, launch a
> confidential VM, or establish external custody.

## Security objective

Forge Cell does not attempt to make a host administrator powerless. A root administrator controls
the ordinary host kernel and can usually replace files, processes, clocks, logs, or policy unless a
stronger trust anchor is used.

The intended objective is narrower and testable:

> A changed test, runner, policy, candidate, environment, or challenge must not be silently accepted
> as the originally requested execution. A requested assurance property that was not established
> remains `UNKNOWN`, even when the test itself reports `PASS`.

This separates two independent questions:

1. **Test result:** did the declared test return `PASS`, `FAIL`, or `UNKNOWN`?
2. **Execution assurance:** were the requested policy, isolation, integrity, attestation, and custody
   properties actually established?

A test `PASS` never upgrades an assurance `UNKNOWN`.

## Reference artifacts

Three JSON Schema Draft 2020-12 resources are packaged with Forge:

| Resource | Purpose |
| --- | --- |
| `forge-cell-policy-0.1.schema.json` | Declares command, environment, filesystem, network, resource, platform, and attestation requirements. |
| `forge-cell-test-bundle-0.1.schema.json` | Identifies test material, harness entrypoint, expected outputs, custody declaration, and optional signatures. |
| `forge-cell-execution-record-0.1.schema.json` | Records request identity, fresh challenge, material identities, execution outcome, assurance properties, outputs, and attestation evidence. |

The schemas are specification artifacts. They do not make a runner enforce the declared values.
Runtime implementations must record only properties they actually established.

Reference documents are under [`examples/forge-cell/`](../examples/forge-cell/).

## Assurance vocabulary

Forge Cell uses explicit, composable properties rather than one ambiguous `sandboxed` flag.

| Property | Required meaning |
| --- | --- |
| `policy-bound` | The executed request was bound to the declared command, environment, limits, and material identities. |
| `process-isolated` | A runner enforced an operating-system process, filesystem, network, and resource boundary described in its receipt. |
| `verity-enforced` | Relevant immutable files were read through an integrity mechanism whose enforced digest is recorded. |
| `platform-attested` | A verifier accepted fresh platform measurement evidence bound to the request challenge. |
| `confidential-attested` | A verifier accepted fresh evidence for a hardware-isolated guest or equivalent confidential execution boundary. |
| `external-custody` | Test or evaluator custody was controlled by a declared external holder rather than the candidate operator. |

These properties are not automatically transitive. For example:

- `process-isolated` does not establish protection from hostile host root;
- `platform-attested` does not establish organizational independence;
- `external-custody` does not prove that the external evaluator is competent; and
- a signature proves control of a key under a declared policy, not truth of the signed claim.

## Validation API

`mncs_forge.forge_cell` exposes:

- `validate_forge_cell_document(...)` for offline schema validation; and
- `assess_execution_assurance(...)` for fail-closed comparison of one execution record with one
  requested policy and optional verifier challenge.

Example:

```python
import json
from pathlib import Path

from mncs_forge.forge_cell import assess_execution_assurance

root = Path("examples/forge-cell")
policy = json.loads((root / "policy.json").read_text(encoding="utf-8"))
record = json.loads((root / "execution-record.json").read_text(encoding="utf-8"))
assessment = assess_execution_assurance(
    policy,
    record,
    expected_nonce="reference-nonce-0000000000000001",
)
assert record["result"] == "PASS"
assert assessment.status == "UNKNOWN"
```

The reference record intentionally reports `PASS` for the test and `UNKNOWN` for execution
assurance because process isolation was requested but not established.

## Fail-closed assessment rules

The reference assessor returns:

- `FAIL` for identity or challenge contradictions, changed requested assurance, overlapping
  enforced/unmet claims, or unrequested assurance claims;
- `UNKNOWN` when a requested property is missing or explicitly unmet, or when attested assurance
  lacks verified challenge-bound evidence; and
- `PASS` only when every requested assurance property is accounted for and enforced without a
  contradiction.

Schema-invalid evidence raises `ForgeCellValidationError`. A caller integrating this module into
Forge must map unavailable or malformed evidence according to Forge's existing explicit
`FAIL > UNKNOWN > PASS` and error-classification rules; it must not infer assurance `PASS`.

## Intended Linux cell

The first real runner is expected to enforce, where supported:

- new user, mount, PID, IPC, UTS, and network namespaces;
- a read-only root filesystem and read-only candidate/test mounts;
- a small declared writable output mount;
- `pivot_root`, no inherited file descriptors, and `no_new_privs`;
- a strict seccomp profile and Landlock filesystem restrictions;
- cgroup v2 CPU, memory, PID, and I/O limits;
- fixed argument arrays and an allowlisted environment;
- disabled networking by default; and
- bounded output and process-tree termination.

Those properties remain future work until a runner implements them and adversarial tests verify the
receipt against observed behavior.

## Root and custody boundary

A local Linux cell can constrain a candidate or provider. It cannot honestly claim resistance to a
host administrator who controls the same kernel and keys. Stronger levels require a trust anchor
outside ordinary host root, such as:

- an evaluator machine controlled by a separate operator;
- TPM-backed measured boot and fresh quote verification;
- a confidential VM with remotely verified measurements and challenge-bound key release; or
- externally held encrypted tests released only to an accepted measured evaluator.

Root may still cause denial of service. The stronger goal is that root cannot produce a
verifier-accepted false result without an identity, measurement, signature, challenge, or custody
failure.

## Required attack study

A complete Forge Cell implementation must exercise deliberate attempts to:

- replace or modify tests before and during execution;
- replace the runner, policy, root filesystem, executable, or candidate;
- escape through symlinks, mounts, file descriptors, devices, or namespace configuration;
- access undeclared network endpoints;
- exhaust processes, memory, CPU, output, or storage;
- forge, truncate, replace, or replay execution records;
- reuse a previous `PASS` with a new challenge;
- combine a legitimate runner with the wrong test or candidate; and
- falsify results from host root at each declared assurance level.

Expected outcomes must differ by level. A local runner must disclose host-root trust. A
challenge-bound platform or external evaluator must reject stale, mismatched, or unauthorized
evidence.

## Implementation handoff

The ordered coding-agent work is maintained in
[`docs/codex-forge-cell-next-steps.md`](codex-forge-cell-next-steps.md). The proposed architectural
decision is [ADR 0005](adr/0005-forge-cell-assurance-and-attestation.md).
