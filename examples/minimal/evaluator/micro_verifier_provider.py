#!/usr/bin/env python3
"""Two intentionally narrow Provider Protocol 0.1 micro-verifier examples."""

from __future__ import annotations

import ast
import json
import sys
from itertools import product
from pathlib import Path, PurePosixPath
from typing import Any

PROVIDER = {
    "id": "minimal-micro-verifier-provider",
    "name": "minimal-micro-verifier-provider",
    "identity": "minimal-micro-verifier-provider-v1",
    "version": "0.1",
}
METHODS = ["evidence-change-impact", "python-bounded-equivalence"]


def response(
    request: dict[str, Any],
    status: str,
    summary: str,
    *,
    witnesses: list[object] | None = None,
    limitations: list[str] | None = None,
    unsupported: list[str] | None = None,
    dependency_paths: list[str] | None = None,
    complete: bool = False,
) -> dict[str, object]:
    return {
        "protocol_version": "0.1",
        "type": "analysis_response",
        "request_id": request["request_id"],
        "provider": PROVIDER,
        "status": status,
        "summary": summary,
        "witnesses": witnesses or [],
        "limitations": limitations or [],
        "extensions": {
            "unsupported_constructs": unsupported or [],
            "mncs_forge": {
                "assumptions": ["the request paths and identities name the intended artifacts"],
                "dependency_envelope": {
                    "paths": dependency_paths or [],
                    "identities": {},
                    "complete": complete,
                },
            },
        },
    }


def safe_relative_path(value: object) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    path = PurePosixPath(value)
    allowed = ("candidate", "generated-output", "contract", "reference", "evidence")
    if path.is_absolute() or ".." in path.parts or not path.parts or path.parts[0] not in allowed:
        return None
    return path.as_posix()


def change_impact(request: dict[str, Any]) -> dict[str, object]:
    component = request.get("component", {})
    extension = request.get("extensions", {}).get("mncs_forge", {})
    parameters = extension.get("question_parameters", {})
    changed = component.get("changed_paths", [])
    dependencies = parameters.get("dependency_paths", [])
    if not isinstance(changed, list) or not isinstance(dependencies, list) or not dependencies:
        return response(
            request,
            "UNKNOWN",
            "dependency impact was not established",
            limitations=["dependency_paths must be a non-empty declared parameter"],
            unsupported=["missing-dependency-envelope"],
        )
    normalized_changed = [safe_relative_path(value) for value in changed]
    normalized_dependencies = [safe_relative_path(value) for value in dependencies]
    if any(value is None for value in [*normalized_changed, *normalized_dependencies]):
        return response(
            request,
            "UNKNOWN",
            "dependency impact used an unsupported path",
            limitations=["only declared minimal-example path families are supported"],
            unsupported=["unsupported-path"],
        )
    changed_paths = [str(value) for value in normalized_changed]
    dependency_paths = [str(value) for value in normalized_dependencies]
    overlap = sorted(
        changed_path
        for changed_path in changed_paths
        if any(
            changed_path == dependency
            or changed_path.startswith(dependency + "/")
            or dependency.startswith(changed_path + "/")
            for dependency in dependency_paths
        )
    )
    if overlap:
        return response(
            request,
            "FAIL",
            "a changed path intersects the declared evidence dependency envelope",
            witnesses=[{"affected_path": value} for value in overlap],
            dependency_paths=dependency_paths,
            complete=False,
        )
    return response(
        request,
        "PASS",
        "no changed path intersects the declared evidence dependency envelope",
        limitations=[
            "path separation does not prove semantic independence",
            "the result depends on the caller-declared dependency_paths envelope",
        ],
        dependency_paths=dependency_paths,
        complete=False,
    )


def function_expression(path: Path) -> tuple[list[str], ast.expr] | None:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    functions = [
        node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "add"
    ]
    if len(functions) != 1:
        return None
    function = functions[0]
    if (
        function.args.posonlyargs
        or function.args.vararg
        or function.args.kwonlyargs
        or function.args.kwarg
        or len(function.body) != 1
        or not isinstance(function.body[0], ast.Return)
        or function.body[0].value is None
    ):
        return None
    return [argument.arg for argument in function.args.args], function.body[0].value


def evaluate(expression: ast.expr, values: dict[str, int]) -> int:
    if isinstance(expression, ast.Name) and expression.id in values:
        return values[expression.id]
    if (
        isinstance(expression, ast.Constant)
        and isinstance(expression.value, int)
        and not isinstance(expression.value, bool)
    ):
        return expression.value
    if isinstance(expression, ast.UnaryOp) and isinstance(expression.op, ast.USub):
        return -evaluate(expression.operand, values)
    if isinstance(expression, ast.BinOp):
        left = evaluate(expression.left, values)
        right = evaluate(expression.right, values)
        if isinstance(expression.op, ast.Add):
            return left + right
        if isinstance(expression.op, ast.Sub):
            return left - right
        if isinstance(expression.op, ast.Mult):
            return left * right
    raise ValueError("unsupported expression")


def bounded_equivalence(request: dict[str, Any]) -> dict[str, object]:
    candidate_path = Path("candidate/generated.py")
    reference_path = Path("reference/reference.py")
    dependency_paths = [candidate_path.as_posix(), reference_path.as_posix()]
    try:
        candidate = function_expression(candidate_path)
        reference = function_expression(reference_path)
        if candidate is None or reference is None or candidate[0] != reference[0]:
            return response(
                request,
                "UNKNOWN",
                "the add function shape is unsupported",
                limitations=["exactly one simple two-argument add function is required"],
                unsupported=["unsupported-function-shape"],
                dependency_paths=dependency_paths,
            )
        names = candidate[0]
        for inputs in product(range(-2, 3), repeat=len(names)):
            values = dict(zip(names, inputs, strict=True))
            candidate_value = evaluate(candidate[1], values)
            reference_value = evaluate(reference[1], values)
            if candidate_value != reference_value:
                return response(
                    request,
                    "FAIL",
                    "candidate and reference differ in the bounded integer domain",
                    witnesses=[
                        {
                            "input": values,
                            "candidate_output": candidate_value,
                            "reference_output": reference_value,
                        }
                    ],
                    dependency_paths=dependency_paths,
                    complete=True,
                )
    except (OSError, SyntaxError, UnicodeError, ValueError) as exc:
        return response(
            request,
            "UNKNOWN",
            "bounded equivalence could not decide the supported expression subset",
            limitations=[str(exc)],
            unsupported=["unsupported-python-expression"],
            dependency_paths=dependency_paths,
        )
    return response(
        request,
        "PASS",
        "candidate and reference agree for integer pairs in [-2, 2]",
        limitations=[
            "the method covers one pure expression function and a finite integer domain only"
        ],
        dependency_paths=dependency_paths,
        complete=True,
    )


def main() -> int:
    request = json.loads(sys.stdin.readline())
    if request.get("type") == "capabilities":
        result: dict[str, object] = {
            "protocol_version": "0.1",
            "type": "capabilities",
            "request_id": request["request_id"],
            "provider": PROVIDER,
            "analyses": METHODS,
            "statuses": ["PASS", "FAIL", "UNKNOWN"],
            "cancellation": False,
            "health_checks": False,
            "extensions": {
                "supported_constructs": ["bounded-path-overlap", "simple-python-expression"],
                "unsupported_constructs": ["dynamic-dispatch", "whole-program-semantics"],
                "limitations": ["example provider with two narrow methods"],
            },
        }
    elif request.get("type") == "analysis_request":
        method = request.get("analysis")
        if method == "evidence-change-impact":
            result = change_impact(request)
        elif method == "python-bounded-equivalence":
            result = bounded_equivalence(request)
        else:
            result = response(
                request,
                "UNKNOWN",
                "requested method is unsupported",
                unsupported=["unsupported-method"],
            )
    else:
        result = response(
            request,
            "UNKNOWN",
            "request type is unsupported",
            unsupported=["unsupported-request-type"],
        )
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
