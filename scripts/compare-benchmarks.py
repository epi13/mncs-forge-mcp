#!/usr/bin/env python3
"""Compare two non-normative Forge benchmark JSON documents."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

REQUIRED_ROOT_FIELDS = {"schema_version", "evidence_class", "normative", "metrics"}
REQUIRED_METRIC_FIELDS = {"mean_ms", "p50_ms", "p95_ms", "p99_ms"}
ENVIRONMENT_FIELDS = ("forge_version", "python", "platform", "schema_version", "ledger_entries")


def _number(value: object, label: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
        raise ValueError(f"{label} must be a finite number")
    return float(value)


def load_benchmark(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read benchmark {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"benchmark {path} must be a JSON object")
    missing = sorted(REQUIRED_ROOT_FIELDS.difference(value))
    if missing:
        raise ValueError(f"benchmark {path} is missing: {', '.join(missing)}")
    if value["schema_version"] != "0.1":
        raise ValueError(f"benchmark {path} has unsupported schema_version")
    if value["evidence_class"] != "operator-controlled-development-benchmark":
        raise ValueError(f"benchmark {path} has an unsupported evidence_class")
    if value["normative"] is not False:
        raise ValueError(f"benchmark {path} must remain non-normative")
    metrics = value["metrics"]
    if not isinstance(metrics, dict) or not metrics:
        raise ValueError(f"benchmark {path} metrics must be a non-empty object")
    for name, metric in metrics.items():
        if not isinstance(name, str) or not isinstance(metric, dict):
            raise ValueError(f"benchmark {path} contains an invalid metric")
        missing_metric = sorted(REQUIRED_METRIC_FIELDS.difference(metric))
        if missing_metric:
            raise ValueError(
                f"benchmark {path} metric {name} is missing: {', '.join(missing_metric)}"
            )
        for field in REQUIRED_METRIC_FIELDS:
            _number(metric[field], f"benchmark {path} metric {name}.{field}")
    if "setup_ms" in value:
        _number(value["setup_ms"], f"benchmark {path}.setup_ms")
    if "ledger_entries" in value and (
        not isinstance(value["ledger_entries"], int) or isinstance(value["ledger_entries"], bool)
    ):
        raise ValueError(f"benchmark {path}.ledger_entries must be an integer")
    return value


def _delta(baseline: object, candidate: object) -> dict[str, float | None]:
    baseline_value = _number(baseline, "baseline metric")
    candidate_value = _number(candidate, "candidate metric")
    absolute = candidate_value - baseline_value
    relative = None if baseline_value == 0 else (absolute / baseline_value) * 100
    return {
        "baseline": baseline_value,
        "candidate": candidate_value,
        "absolute_difference": absolute,
        "relative_difference_percent": relative,
    }


def compare(baseline: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    baseline_metrics = baseline["metrics"]
    candidate_metrics = candidate["metrics"]
    names = sorted(set(baseline_metrics).intersection(candidate_metrics))
    if not names:
        raise ValueError("benchmarks have no matching metrics")
    environment = {
        field: {
            "baseline": baseline.get(field),
            "candidate": candidate.get(field),
            "same": baseline.get(field) == candidate.get(field),
        }
        for field in ENVIRONMENT_FIELDS
        if field in baseline or field in candidate
    }
    metrics = {
        name: {
            field: _delta(baseline_metrics[name].get(field), candidate_metrics[name].get(field))
            for field in ("mean_ms", "p50_ms", "p95_ms", "p99_ms")
        }
        for name in names
    }
    result: dict[str, Any] = {
        "schema_version": "0.1",
        "evidence_class": "operator-controlled-development-benchmark-comparison",
        "normative": False,
        "environment": environment,
        "metrics": metrics,
        "limitations": [
            "comparison is non-normative single-host development telemetry",
            "environment differences and system load can dominate small timing changes",
            "a faster or slower benchmark does not establish correctness or conformance",
        ],
    }
    if "setup_ms" in baseline and "setup_ms" in candidate:
        result["setup_ms"] = _delta(baseline["setup_ms"], candidate["setup_ms"])
    if "ledger_entries" in baseline or "ledger_entries" in candidate:
        result["ledger_entries"] = {
            "baseline": baseline.get("ledger_entries"),
            "candidate": candidate.get("ledger_entries"),
            "same": baseline.get("ledger_entries") == candidate.get("ledger_entries"),
        }
    return result


def _text_report(result: dict[str, Any]) -> str:
    lines = [
        "Forge benchmark comparison (non-normative development telemetry)",
        "Environment differences:",
    ]
    for field, values in result["environment"].items():
        if not values["same"]:
            lines.append(f"  {field}: {values['baseline']!r} -> {values['candidate']!r}")
    if all(values["same"] for values in result["environment"].values()):
        lines.append("  none")
    lines.append("Metrics (candidate - baseline):")
    for name, metrics in result["metrics"].items():
        mean = metrics["mean_ms"]
        lines.append(
            f"  {name}: mean {mean['absolute_difference']:.6f} ms "
            f"({mean['relative_difference_percent']!s}%); "
            f"p50 {metrics['p50_ms']['absolute_difference']:.6f} ms; "
            f"p95 {metrics['p95_ms']['absolute_difference']:.6f} ms; "
            f"p99 {metrics['p99_ms']['absolute_difference']:.6f} ms"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--format", choices=("json", "text"), default="json")
    arguments = parser.parse_args(argv)
    try:
        result = compare(load_benchmark(arguments.baseline), load_benchmark(arguments.candidate))
    except ValueError as exc:
        print(f"benchmark comparison error: {exc}", file=sys.stderr)
        return 2
    if arguments.format == "text":
        print(_text_report(result))
    else:
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
