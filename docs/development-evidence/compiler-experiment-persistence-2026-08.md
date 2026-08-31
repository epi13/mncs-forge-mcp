# Compiler experiment persistence validation — 2026-08

## Scope and claim boundary

This evidence covers version-1 `compiler_experiment` persistence, exact language-record retention, normalized observation projection, idempotent identity, ledger integration, record/list/compare operations, CLI/MCP/resource exposure, and compatibility snapshot updates.

It does not establish compiler correctness, semantic equivalence, independent custody, assurance, conformance, a regression verdict, or distributed execution.

## Validation commands

```bash
scripts/check.sh
PATH="$PWD/.venv/bin:$PATH" python scripts/generate-record-schema.py
.venv/bin/python scripts/generate-compatibility-snapshot.py --check
```

Results:

- Ruff formatting/lint and strict mypy passed;
- all 410 tests passed;
- source distribution and wheel builds passed;
- diff whitespace and the regenerated `0.1.0b1` semantic compatibility snapshot passed; and
- integration tests recorded the exact language object, verified the hash-linked ledger, listed the observation without a verdict, compared persisted studies, retained frontend stages, and rejected observation laundering.

## Joern method

The same Joern version, Python source frontend, source scope, and focused persistence query were used on the pre-edit and post-edit graphs. The earlier observation query was repeated against the post graph.

```bash
joern --script scripts/joern/compiler-experiment-persistence.sc \
  --param cpgFile=workspace/compiler-persistence-baseline.cpg.bin --nocolors
joern-parse src/mncs_forge \
  -o workspace/compiler-persistence-post.cpg.bin --language pythonsrc
joern --script scripts/joern/compiler-experiment-persistence.sc \
  --param cpgFile=workspace/compiler-persistence-post.cpg.bin --nocolors
joern --script scripts/joern/compiler-evolution-observation.sc \
  --param cpgFile=workspace/compiler-persistence-post.cpg.bin --nocolors

joern-parse scripts -o workspace/schema-generator-baseline.cpg.bin --language pythonsrc
joern --script scripts/joern/record-schema-generator.sc \
  --param cpgFile=workspace/schema-generator-baseline.cpg.bin --nocolors
joern-parse scripts -o workspace/schema-generator-post.cpg.bin --language pythonsrc
joern --script scripts/joern/record-schema-generator.sc \
  --param cpgFile=workspace/schema-generator-post.cpg.bin --nocolors
```

The queries ran from `/tmp` with absolute paths to avoid Joern project-directory collisions.

## Comparative graph findings

- baseline had no compiler study `record`, `list`, `_get`, or compiler facade/operation methods; post has one service writer, one list projection, one bounded lookup, and two protocol/implementation declarations for each facade method;
- the new `record` method has one bounded existing-record scan and one identity branch for idempotent retries; otherwise it calls only language-record validation/projection, `new_record`, and transactional `commit` before serialization;
- list has one bounded record iteration; `_get` has one iteration and one identity branch; compiler comparison calls only `_get`, observation reconstruction, and `compare_compiler_experiments`;
- shared `new_record` remained one method with `IF=4`; transactional `commit` remained three declarations/implementations with the same `IF=7`, `WHILE=1`, `TRY=1`, `FINALLY=1`, and `CONTINUE=1`; and shared registry `invoke` remained two methods with `IF=6`, `WHILE=1`;
- `_validate_fields` retained its two bounded scans while moving from `IF=11` to `IF=15`; the four new branches select the compiler record type and fail closed on a competing language contract, a stronger interpretation, or non-null assurance/conformance status;
- the only new callers into persistence are the compiler study writer's `new_record` and `commit` edges; and
- no call edge connects `compiler_studies.py` to candidate disposition, freeze, final evaluation, verifier execution, lifecycle promotion, assurance, or conformance behavior.

The schema-generator graph adds four bounded `property_schema` branches (`IF=13` to `IF=17`) for null verdict fields, pinned contract/interpretation constants, and the completion-status enum. `record_schema` remained `WHILE=1` and generator `main` remained `WHILE=2`, with no new I/O or authority call boundary.

## Analyzer failures and uncertainty

- Joern emitted JVM native-access/deprecation warnings, Python CFG fallback warnings for `continue`, `break`, and `try` recovery, and conservative `Path(__file__).resolve().parents` recovery warnings in generator scripts; graph creation and queries completed.
- Python type recovery reports protocol declarations and concrete implementations separately, so method counts are boundary counts rather than unique runtime dispatch targets.
- Static graph results do not prove storage crash safety or semantic non-interference; the existing transactional/fault suites and new integration tests supply separate behavioral evidence.
- Generated CPGs remain ignored local artifacts.

## Residual uncertainty

Forge validates the pinned comparison projection but does not independently recompute Rust compiler semantics. Future assurance must attach a separate language-owned verifier result and policy identity. Feature/profile compatibility, regression gates, benchmark records, and Fabric distribution remain follow-on work.
