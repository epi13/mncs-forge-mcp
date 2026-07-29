# EdgeStream read-only integration

EdgeStream is the primary real example. Copy the example configuration to the root of the
current MNCS checkout, or use the configuration supplied by its non-normative integration.

The configuration identifies the contract, reference, generated candidate, evaluator,
preregistration/acceptance policy, development evidence, MNCDS record, and outputs. The
`edgestream-read-only-inspect` workflow only verifies expected visible paths and returns its
limitations. It does not regenerate or rewrite historical evidence.

```bash
mncs-forge --config mncs-forge.toml inspect
mncs-forge --config mncs-forge.toml status
mncs-forge --config mncs-forge.toml blockers promotion
mncs-forge --config mncs-forge.toml epoch begin \
  --generator future-generator-id --evaluator development-evaluator-id
```

The final command demonstrates how a future epoch is opened and writes new local Forge state. Do
not use it when merely inspecting the checked-in case study. The example has repository-visible
development evidence and explicitly has no protected holdout or independent evaluator. Those
classes remain `UNKNOWN`. Evaluator mode is a separate `--mode evaluator` process and cannot run
until a newly selected candidate has been frozen.
