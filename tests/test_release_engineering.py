from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _benchmark(*, mean: float, platform: str = "same") -> dict[str, object]:
    metric = {
        "iterations": 25.0,
        "mean_ms": mean,
        "p50_ms": mean - 0.1,
        "p95_ms": mean + 0.2,
        "p99_ms": mean + 0.3,
        "max_ms": mean + 0.4,
    }
    return {
        "schema_version": "0.1",
        "evidence_class": "operator-controlled-development-benchmark",
        "normative": False,
        "forge_version": "0.1.0a2",
        "python": "3.13",
        "platform": platform,
        "setup_ms": mean + 1,
        "ledger_entries": 54,
        "metrics": {"ledger_verify": metric},
    }


def test_benchmark_comparison_is_deterministic_and_non_normative(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.json"
    candidate = tmp_path / "candidate.json"
    baseline.write_text(json.dumps(_benchmark(mean=10.0)), encoding="utf-8")
    candidate.write_text(json.dumps(_benchmark(mean=12.0, platform="different")), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/compare-benchmarks.py",
            str(baseline),
            str(candidate),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result["normative"] is False
    assert result["environment"]["platform"]["same"] is False
    assert result["metrics"]["ledger_verify"]["mean_ms"]["absolute_difference"] == 2.0
    assert result["metrics"]["ledger_verify"]["mean_ms"]["relative_difference_percent"] == 20.0


def test_benchmark_comparison_rejects_normative_or_malformed_input(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.json"
    candidate = tmp_path / "candidate.json"
    baseline.write_text(json.dumps(_benchmark(mean=10.0)), encoding="utf-8")
    malformed = _benchmark(mean=11.0)
    malformed["normative"] = True
    candidate.write_text(json.dumps(malformed), encoding="utf-8")

    completed = subprocess.run(
        [sys.executable, "scripts/compare-benchmarks.py", str(baseline), str(candidate)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode != 0
    assert "non-normative" in completed.stderr
