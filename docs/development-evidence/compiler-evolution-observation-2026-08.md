# Compiler evolution observation validation — 2026-08

## Scope

This evidence covers Forge's observation-only consumer for `mncs:language:compilation-study-result:0.1` and the structural comparison of compiler stage fingerprints and pass statuses.

It does not cover operation-registry integration, compiler experiment persistence, distributed execution, semantic equivalence, independent assurance, promotion, or MNCS conformance.

## Validation commands

```bash
.venv/bin/ruff format --check .
.venv/bin/ruff check .
.venv/bin/mypy src
.venv/bin/pytest
.venv/bin/python -m build
git diff --check
```

Results:

- formatting, lint, and strict type checking passed;
- 404 Forge tests passed, including 6 compiler-evolution tests;
- source distribution and wheel builds passed; and
- diff whitespace validation passed.

The compiler-evolution tests cover contract acceptance, rejection of a competing contract, rejection of observation laundering, earliest SSA divergence, pass-status change retention, and identical omission of target/backend artifacts.

## Joern method

The same Joern version, Python source frontend, source scope, script, and query bounds were used before and after source changes.

```bash
joern-parse src/mncs_forge \
  -o workspace/compiler-evolution-baseline.cpg.bin --language pythonsrc
joern --script scripts/joern/compiler-evolution-observation.sc \
  --param cpgFile=workspace/compiler-evolution-baseline.cpg.bin --nocolors

joern-parse src/mncs_forge \
  -o workspace/compiler-evolution-post.cpg.bin --language pythonsrc
joern --script scripts/joern/compiler-evolution-observation.sc \
  --param cpgFile=workspace/compiler-evolution-post.cpg.bin --nocolors
```

The query was executed from `/tmp` with absolute paths to avoid Joern's local project-directory collision with repository CPG paths.

## Comparative graph findings

- baseline contained no `from_language_record` or `compare_compiler_experiments` methods.
- post-change contains two bounded `from_language_record` class methods and one comparison function in `compiler_evolution.py`.
- the consumer calls parsing helpers and constructs frozen observation/comparison values; it does not call `new_record`, `parse_record`, lifecycle services, workflow execution, evaluator services, reconciliation, freeze, disposition, or promotion paths.
- existing `new_record`, `parse_record`, workflow `execute`, and service `run` call/control inventories were unchanged.
- no new call edge connects compiler comparison to Forge persistence or authority. This matches ADR 0013: the implemented slice is an observation consumer, not a new evidence record or lifecycle transition.

## Failures and unsupported features

- the first parse attempt used `--language python` and failed because this Joern installation has no `py2cpg.sh`; retrying with the installed `pythonsrc` frontend succeeded. Both baseline and post snapshots use `pythonsrc`.
- Joern emitted JVM deprecation/native-access warnings and Python type-recovery logs; graph creation and focused queries completed.
- Joern's Python recovery is conservative and does not prove runtime type safety or semantic non-interference.
- compiler experiment persistence, operation-registry exposure, verifier attachment, compatibility matrices, and Fabric distribution are not implemented in this slice.
- generated CPGs are retained locally under ignored `workspace/` paths and are not committed.

## Residual uncertainty

The consumer validates only the pinned projection required for comparison; it does not independently recompute the Rust record's content identity or validate compiler semantics. A future persisted integration must bind the raw language artifact identity, validator identity, and assurance policy without changing existing Forge authority semantics.

## Windows CI baseline repair

The PR matrix reproduced an existing `main` failure in all Windows jobs: `test_codex_launcher_uses_relocatable_module_entrypoint` attempted to execute the Bash `scripts/codex-mcp` file directly and failed with `WinError 193`. The same failure is present in `main` run `32280197735`; it was not introduced by the compiler consumer.

The test now invokes the launcher through `bash` on Windows and skips only when no Bash implementation is installed. Linux/macOS retain direct execution. Focused local tests passed.

The graph-sensitive test change used same-scope baseline/post CPGs over `tests/`:

```bash
joern-parse tests -o workspace/windows-launcher-test-baseline.cpg.bin --language pythonsrc
joern --script scripts/joern/windows-launcher-test.sc \
  --param cpgFile=workspace/windows-launcher-test-baseline.cpg.bin --nocolors
joern-parse tests -o workspace/windows-launcher-test-post.cpg.bin --language pythonsrc
joern --script scripts/joern/windows-launcher-test.sc \
  --param cpgFile=workspace/windows-launcher-test-post.cpg.bin --nocolors
```

The focused method changed from no control structures to two bounded `IF` branches: Windows platform selection and Bash availability. New calls are limited to `which`, `insert`, and `skip`; subprocess execution and assertions remain in the same test method. This repair changes test execution routing only and does not alter Forge runtime authority or launcher behavior.
