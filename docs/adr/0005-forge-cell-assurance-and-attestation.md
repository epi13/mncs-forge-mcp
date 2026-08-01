# ADR 0005: Forge Cell assurance and challenge-bound attestation

- **Status:** Proposed
- **Target:** `0.2.x` through `0.3.x`

## Context

Forge currently provides bounded no-shell execution, path controls, identity recording, output
limits, and hash-linked history, but configured executables retain the ambient permissions of the
Forge process. The current security documentation correctly states that Forge is not an operating-
system or network sandbox.

A stronger execution boundary must not introduce a vague `sandboxed` claim. It must also account for
the fact that ordinary host root can replace local tests, runners, policies, outputs, logs, and
keys. Containers and namespaces can constrain a candidate while still trusting the host operator.

## Decision

Forge Cell will separate the program's test result from execution assurance. Every controlled run
will bind a versioned policy, test bundle, candidate, runner, root filesystem, executable,
environment, output manifest, and fresh verifier challenge.

Assurance will be represented as explicit properties:

- `policy-bound`;
- `process-isolated`;
- `verity-enforced`;
- `platform-attested`;
- `confidential-attested`; and
- `external-custody`.

The execution record will list requested, enforced, and unmet properties. A requested property that
was not established remains `UNKNOWN` independently of the test result. Identity or fresh-challenge
contradictions are failures. Attested properties require verified challenge-bound evidence.

The first implementation will be a Linux-specific runner behind the replaceable runner protocol.
TPM, confidential-VM, and external-custody backends will remain separate adapters with separate
trust and operational assumptions.

## Consequences

Positive consequences:

- a test `PASS` cannot silently promote missing isolation or custody evidence;
- receipts become comparable across local, container, measured, confidential, and external
  execution;
- replay and substitution attempts have explicit identity and challenge checks; and
- stronger backends can be added without redefining local execution as independent.

Costs and risks:

- platform-specific launchers and attestation verifiers substantially increase the security review
  surface;
- a compromised host can still deny service and may defeat local-only isolation claims;
- measurement allowlists, key rotation, revocation, and verifier policy require lifecycle design;
- confidential computing does not remove all side-channel or supply-chain risks; and
- external custody is an organizational fact that code cannot manufacture.

## Required evidence before acceptance

- all three versioned reference artifacts are integrated into typed records and migrations;
- one Linux launcher enforces and records the declared namespace, filesystem, network, syscall, and
  resource properties;
- challenge replay, policy substitution, candidate substitution, test mutation, and output
  substitution tests fail closed;
- requested but unsupported assurance remains `UNKNOWN`;
- an independent offline verifier validates material identities and challenge binding;
- security documentation lists the trusted computing base for every backend; and
- no local backend is described as resistant to hostile host root without external or hardware-
  backed evidence.
