from __future__ import annotations

import ast
from pathlib import Path

PACKAGE = Path(__file__).parents[1] / "src" / "mncs_forge"
APPLICATION = PACKAGE / "application"


def imports(path: Path) -> list[tuple[str, str | None]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[tuple[str, str | None]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend((item.name, None) for item in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = "." * node.level + (node.module or "")
            found.extend((module, item.name) for item in node.names)
    return found


def test_application_imports_point_inward() -> None:
    forbidden_modules = {
        "argparse",
        "subprocess",
        "mcp",
        "mncs_forge.cli",
        "mncs_forge.server",
        "mncs_forge.engine",
        "mncs_forge.adapters",
    }
    failures: list[str] = []
    for path in sorted(APPLICATION.glob("*.py")):
        for module, name in imports(path):
            normalized = module.lstrip(".")
            if normalized in forbidden_modules or name in {
                "Forge",
                "LocalRecordStore",
                "run_bounded",
            }:
                failures.append(f"{path.name}: forbidden import {module}:{name}")
    assert failures == []


def test_domain_modules_do_not_import_interfaces_or_concrete_adapters() -> None:
    failures: list[str] = []
    for name in ("records.py", "state_machine.py"):
        for module, imported_name in imports(PACKAGE / name):
            normalized = module.lstrip(".")
            if normalized in {
                "cli",
                "server",
                "adapters",
                "record_store",
                "argparse",
                "subprocess",
                "mcp",
            }:
                failures.append(f"{name}: forbidden import {module}:{imported_name}")
    assert failures == []


def test_services_never_depend_on_forge_or_local_execution_function() -> None:
    service_paths = [*APPLICATION.glob("*.py"), PACKAGE / "micro_verifiers.py"]
    failures: list[str] = []
    for path in service_paths:
        source = path.read_text(encoding="utf-8")
        if "from .engine import" in source or "from ..engine import" in source:
            failures.append(f"{path.name}: imports engine")
        if "run_bounded(" in source:
            failures.append(f"{path.name}: calls concrete run_bounded")
        if "from .identity import" in source or "from ..identity import" in source:
            failures.append(f"{path.name}: imports concrete filesystem identity implementation")
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name == "__init__"
                and any(argument.arg == "forge" for argument in node.args.args)
            ):
                failures.append(f"{path.name}:{node.lineno}: constructor receives Forge")
    assert failures == []


def test_facade_composes_services_and_services_do_not_import_facade() -> None:
    engine_imports = imports(PACKAGE / "engine.py")
    application_imports = {
        module for module, _ in engine_imports if module.startswith(".application.")
    }
    assert {
        ".application.candidates",
        ".application.evaluation",
        ".application.evidence",
        ".application.project",
        ".application.providers",
        ".application.recovery",
        ".application.workflows",
    }.issubset(application_imports)
    assert all(
        not any(module.lstrip(".") == "engine" for module, _ in imports(path))
        for path in APPLICATION.glob("*.py")
    )


def test_new_application_import_graph_is_acyclic() -> None:
    modules = {path.stem: path for path in APPLICATION.glob("*.py")}
    graph: dict[str, set[str]] = {name: set() for name in modules}
    for name, path in modules.items():
        for module, _ in imports(path):
            if module.startswith("."):
                target = module.lstrip(".").split(".")[-1]
                if target in modules:
                    graph[name].add(target)

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(name: str, trail: tuple[str, ...]) -> None:
        if name in visiting:
            raise AssertionError("application import cycle: " + " -> ".join((*trail, name)))
        if name in visited:
            return
        visiting.add(name)
        for target in sorted(graph[name]):
            visit(target, (*trail, name))
        visiting.remove(name)
        visited.add(name)

    for name in sorted(graph):
        visit(name, ())


def test_record_and_execution_boundaries_have_no_application_bypass() -> None:
    application_source = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(APPLICATION.glob("*.py"))
    )
    assert "ledger.append(" not in application_source
    assert "_write_immutable(" not in application_source
    assert "LocalRecordStore(" not in application_source
    direct_execution = sorted(
        path.relative_to(PACKAGE).as_posix()
        for path in PACKAGE.rglob("*.py")
        if "run_bounded(" in path.read_text(encoding="utf-8")
    )
    assert direct_execution == ["adapters.py", "execution.py"]
