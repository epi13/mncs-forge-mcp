# Forge `0.1.0b1` compatibility boundary

This document closes the modular-control-plane compatibility gate without changing the installed
package version. It is a Forge release-engineering contract, not MNCS/MNCDS conformance evidence,
certification, governance approval, independent evaluation, protected custody, or witnessing.

## Frozen public surfaces

The committed snapshot
[`tests/compatibility/0.1.0b1.json`](../tests/compatibility/0.1.0b1.json) characterizes only
externally meaningful semantics:

- configuration and record JSON Schema validation digests, recognized definitions, fields, and
  required fields;
- canonical operation IDs, modes, mutation/authority/lifecycle/disclosure metadata, interface
  exposure, and resource projections through the operation-inventory digest;
- CLI command nesting, arguments, flags, arity, requiredness, choices, defaults, value kinds, and
  registry input/decoder bindings;
- development/evaluator MCP tool inventories, semantic input/output schema digests, required
  inputs, property names, and resource URI/media-type inventory;
- every public `Forge` constructor/method signature and the public status-aggregation helper; and
- package name, Python range, dependency bounds, and console entry points.

The current record schema remains
[`forge-records-1.schema.json`](../src/mncs_forge/resources/forge-records-1.schema.json); the
configuration contract remains
[`mncs-forge-config.schema.json`](../schemas/mncs-forge-config.schema.json). The aggregate snapshot
does not replace either schema. Provider Protocol 0.1 request envelopes and Forge extensions are
characterized by executable field/value assertions in
[`test_provider_protocol_compatibility.py`](../tests/test_provider_protocol_compatibility.py).
No Provider Protocol version was added.

The compiler-evolution increment is an intentional additive extension to this pre-release snapshot: it adds the `compiler_experiment` record definition, three canonical operations, three CLI leaves, three MCP tools, and one resource. Existing record fields, operation semantics, CLI leaves, MCP inputs, and historical-state migrations are unchanged. The regenerated snapshot makes that public surface explicit for review rather than treating it as an internal implementation detail.

Generate or check the aggregate snapshot deterministically with:

```bash
PATH="$PWD/.venv/bin:$PATH" python scripts/generate-compatibility-snapshot.py --write
PATH="$PWD/.venv/bin:$PATH" python scripts/generate-compatibility-snapshot.py --check
```

An intentional compatibility change must change the implementation or authoritative schema first,
regenerate the snapshot, review the semantic diff, add migration or fail-closed coverage where
needed, and explain the compatibility impact in the changelog. Never update the artifact merely
to make its check pass.

## Deliberately unfrozen details

The snapshot omits human help and error prose, MCP prompts and descriptions, timestamps,
filesystem-specific paths, environment values, object/function representations, internal module
or service layout behind `Forge`, dictionary ordering already governed by canonical JSON,
performance telemetry, and the package release version. These are either presentation,
environmental data, implementation details, or release bookkeeping rather than this compatibility
contract.

## Persistent-state matrix

| Stored input | Current behavior | Compatibility requirement |
| --- | --- | --- |
| early unversioned `0.1` result without `subject_type` | add the historical candidate-only default in memory | preserve identity/status and never infer project authority |
| later unversioned `0.1` state | verify raw ledger bytes, then migrate in memory | preserve identities/statuses and never rewrite historical files |
| current schema `"1"` | parse, validate, and serialize canonically | byte-stable canonical round trip and identity reproduction |
| unsupported explicit future version | reject | `UNSUPPORTED_RECORD_VERSION` |
| incomplete metadata or trusted type/context mismatch | reject | `RECORD_METADATA` or `RECORD_TYPE_MISMATCH` |
| raw-valid legacy ledger with invalid migrated semantics | accept raw chain only, then reject semantic projection | raw verification precedes `RECORD_STATUS` or another specific semantic error |

Unknown legacy fields remain non-normative extensions. Current unknown top-level fields remain
rejected. Migration cannot create `PASS`, independence, authority, custody, witnessing,
certification, promotion, or governance meaning.

## Installed-package upgrade expectation

An installed wheel must verify and read the frozen `tests/fixtures/legacy-0.1/` corpus, preserve
the historical ledger prefix and immutable files, append current versioned records only through
the transactional store, verify mixed legacy/current history, preserve historical identities, and
reject future versions. The historical fixture corpus and its `SHA256SUMS` are immutable inputs;
they are not generated by the aggregate snapshot command.

## Boundary conclusion

Tasks 1–6 plus this compatibility closure complete the `0.1.0b1` architectural gate. Runner
receipts, `LocalProcessRunner`, sandbox-capable adapters, containers, SSH, Forge Cell runtime
isolation, external anchoring, distributed execution, micro-debugging runtime, intent-aware
security runtime, and caching remain explicitly outside this boundary.
