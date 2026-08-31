# Task 7B-1 development evidence

Status: bounded implementation increment complete; non-normative local development evidence.

## Contract reference

Forge adapts to the MNCS experimental observation envelope:

- upstream repository: `epi13/machine-native-complexity-standard`;
- reference commit: `6d6380016e174feaaa774c1cf0931095d24b5280`;
- schema: `schemas/mncs-execution-receipt-0.1.schema.json`;
- schema SHA-256: `f2e1860405052a40b100bead7c27dbe0cc3ac11d03dccca3fcb643b350ecab6e`;
- reference fixture SHA-256:
  `2a4f4d687d48326e7b908351dd75e5aa828ec6f496bb7add7deb6c643620c3e6`.

The schema is pinned under `tests/fixtures/` for deterministic CI checking. When the sibling
checkout is present, tests also assert its schema digest and validate a generated receipt with
the sibling `mncs_validator`. Forge does not copy the sibling validator or interpretation logic.

## Dogfood scope

The repository has no honest permanent root `mncs-forge.toml`: its protected authority and
candidate layout are not the same as the committed minimal example, and inventing evaluator
authority would misrepresent the repository. A temporary copy of
`examples/minimal/mncs-forge.toml` was therefore used as a documented bounded dogfood workspace.
Creating that temporary workspace, inspecting source, installing `rfc8785`, and Git/GitHub actions
were bootstrap or environment exceptions.

Through Forge's canonical CLI/operation registry, the workspace performed configuration
validation, inspection, operation inventory, epoch creation, candidate registration, verifier
matching, bounded verifier execution, state inspection, and ledger verification. The lifecycle
correctly exposed missing `inspect` evidence as `UNKNOWN` before the candidate-scoped verifier
run; it did not require hand-edited state or ledger bytes.

## Observation and adapter evidence

`LocalProcessRunner.observe()` uses the same `run_bounded()` implementation as `execute()`. Normal
completion and nonzero exit expose return code, termination category, wall duration, command and
environment identities, runner/runtime facts, and complete bounded stream counts/hashes. Timeout,
start failure, and output-limit paths preserve the stable Forge error categories while their raw
observations leave unknown totals and complete hashes unset when the process was not fully drained.

`build_mncs_execution_receipt()` accepts only a complete observation and caller-supplied subject,
bundle, policy, challenge, harness, and optional placement context. It emits an unpersisted
`mncs-execution-receipt` / `0.1-experimental` envelope with RFC 8785 identities. It never launches
execution, writes Forge records, infers harness `PASS`, or changes any claim-boundary field from
`not-asserted`.

The generated reference receipt passed the pinned JSON Schema and, with the sibling checkout
available, the sibling MNCS validator. Adapter tests cover identity drift, missing context,
incomplete output, termination mapping, fixed claim boundaries, unknown harness status, and the
absence of subprocess access in the adapter layer.

## Validation classification

This is executable local development evidence. It does not establish execution correctness,
conformance, sandbox isolation, resource isolation, protected custody, independence, witnessing,
certification, promotion, or external authority. Persistent Forge receipt integration and
sandbox-capable runners remain deferred.
