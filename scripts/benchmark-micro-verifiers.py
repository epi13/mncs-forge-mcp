#!/usr/bin/env python3
"""Measure Forge control-plane overhead with the committed minimal provider.

This is a development benchmark, not conformance evidence. It reports cold setup
separately and p50/p95/p99 warm-operation latency for discovery, matching, execution,
ledger verification, and freshness explanation.
"""

from __future__ import annotations

import argparse
import json
import platform
import shutil
import statistics
import sys
import tempfile
import time
from pathlib import Path
from typing import Callable

from mncs_forge import __version__
from mncs_forge.config import load_config
from mncs_forge.engine import Forge

ROOT = Path(__file__).resolve().parents[1]


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(round((len(ordered) - 1) * fraction))))
    return ordered[index]


def measure(iterations: int, operation: Callable[[], object]) -> dict[str, float]:
    samples: list[float] = []
    for _ in range(iterations):
        started = time.perf_counter()
        operation()
        samples.append((time.perf_counter() - started) * 1000)
    return {
        "iterations": float(iterations),
        "mean_ms": round(statistics.fmean(samples), 6),
        "p50_ms": round(percentile(samples, 0.50), 6),
        "p95_ms": round(percentile(samples, 0.95), 6),
        "p99_ms": round(percentile(samples, 0.99), 6),
        "max_ms": round(max(samples), 6),
    }


def run(iterations: int) -> dict[str, object]:
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="mncs-forge-benchmark-") as temporary:
        project = Path(temporary) / "minimal"
        shutil.copytree(ROOT / "examples" / "minimal", project)
        config = load_config(project / "mncs-forge.toml")
        forge = Forge(config)
        forge.epoch_begin(
            generator_identity="benchmark-generator",
            evaluator_identity="benchmark-evaluator",
        )
        candidate = forge.candidate_register(
            changed_files=["candidate/generated.py"],
            hypothesis="bounded Forge benchmark",
            generator_identity="benchmark-generator",
            generator_config_identity="benchmark-generator-config",
        )
        setup_ms = (time.perf_counter() - started) * 1000
        candidate_identity = str(candidate["candidate_id"])
        last_result: dict[str, object] = forge.verifier_run(
            "python.bounded-add-equivalence",
            candidate_identity=candidate_identity,
            changed_paths=["candidate/generated.py"],
            scope="function",
        )

        def execute() -> object:
            nonlocal last_result
            last_result = forge.verifier_run(
                "python.bounded-add-equivalence",
                candidate_identity=candidate_identity,
                changed_paths=["candidate/generated.py"],
                scope="function",
            )
            return last_result

        metrics = {
            "verifier_list": measure(iterations, forge.verifier_list),
            "verifier_match": measure(
                iterations,
                lambda: forge.verifier_match(
                    uncertainty_classes=["bounded-equivalence"],
                    language="python",
                    artifact_type="source",
                    changed_paths=["candidate/generated.py"],
                    scope="function",
                    maximum_cost="low",
                ),
            ),
            "verifier_run": measure(iterations, execute),
            "ledger_verify": measure(iterations, forge.ledger.verify),
            "verifier_explain": measure(
                iterations,
                lambda: forge.verifier_explain(str(last_result["output_identity"])),
            ),
        }
        ledger = forge.ledger.verify()
        return {
            "schema_version": "0.1",
            "evidence_class": "operator-controlled-development-benchmark",
            "normative": False,
            "forge_version": __version__,
            "python": platform.python_version(),
            "platform": platform.platform(),
            "setup_ms": round(setup_ms, 6),
            "metrics": metrics,
            "ledger_entries": ledger["entries"],
            "limitations": [
                "single-host local benchmark",
                "minimal example provider rather than production analyzers",
                "latency does not establish correctness, conformance, or independence",
            ],
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=25)
    arguments = parser.parse_args()
    if arguments.iterations < 1 or arguments.iterations > 1000:
        parser.error("--iterations must be between 1 and 1000")
    print(json.dumps(run(arguments.iterations), sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
