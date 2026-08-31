"""Project-root containment and authority-boundary checks."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path, PurePosixPath

from .errors import ForgeError

FAMILY_MODULE_ROOTS_MECHANISM = "mncs-forge.family-module-roots.v0.1"


def resolve_family_module_root(project_root: Path, value: str) -> Path:
    """Resolve one declared sibling/package import root.

    Conventional provider isolation cannot see undeclared sibling checkouts.
    This named mechanism allows a project to declare import roots that stay
    inside the workspace parent of the Forge project. The path is hashed and
    recorded by the caller; it is not a silent ``sys.path`` insertion.
    """

    if not isinstance(value, str) or not value or "\x00" in value:
        raise ForgeError("INVALID_PATH", "family module roots must be non-empty strings")
    if Path(value).is_absolute():
        raise ForgeError("ABSOLUTE_PATH", f"absolute family module root is forbidden: {value}")
    root_real = project_root.resolve(strict=True)
    workspace = root_real.parent
    candidate = (root_real / value).resolve(strict=False)
    try:
        candidate.relative_to(workspace)
    except ValueError as exc:
        raise ForgeError(
            "FAMILY_MODULE_ROOT_ESCAPE",
            f"family module root escapes the workspace parent: {value}",
        ) from exc
    if not candidate.is_dir() or candidate.is_symlink():
        raise ForgeError(
            "FAMILY_MODULE_ROOT_MISSING",
            f"family module root is not a real directory: {value}",
        )
    return candidate


FAMILY_MODULE_ROOTS_MECHANISM = "mncs-forge.family-module-roots.v0.1"


def resolve_family_module_root(project_root: Path, value: str) -> Path:
    """Resolve one declared sibling/package import root.

    Conventional provider isolation cannot see undeclared sibling checkouts.
    This named mechanism allows a project to declare import roots that stay
    inside the workspace parent of the Forge project. The path is hashed and
    recorded by the caller; it is not a silent ``sys.path`` insertion.
    """

    if not isinstance(value, str) or not value or "\x00" in value:
        raise ForgeError("INVALID_PATH", "family module roots must be non-empty strings")
    if Path(value).is_absolute():
        raise ForgeError("ABSOLUTE_PATH", f"absolute family module root is forbidden: {value}")
    root_real = project_root.resolve(strict=True)
    workspace = root_real.parent
    candidate = (root_real / value).resolve(strict=False)
    try:
        candidate.relative_to(workspace)
    except ValueError as exc:
        raise ForgeError(
            "FAMILY_MODULE_ROOT_ESCAPE",
            f"family module root escapes the workspace parent: {value}",
        ) from exc
    if not candidate.is_dir() or candidate.is_symlink():
        raise ForgeError(
            "FAMILY_MODULE_ROOT_MISSING",
            f"family module root is not a real directory: {value}",
        )
    return candidate


def validate_relative_path(value: str, *, allow_dot: bool = False) -> PurePosixPath:
    if not isinstance(value, str) or not value:
        raise ForgeError("INVALID_PATH", "configured paths must be non-empty strings")
    path = PurePosixPath(value)
    if path.is_absolute():
        raise ForgeError("ABSOLUTE_PATH", f"absolute project path is forbidden: {value}")
    if any(part == ".." for part in path.parts):
        raise ForgeError("PATH_TRAVERSAL", f"parent traversal is forbidden: {value}")
    if "\x00" in value:
        raise ForgeError("INVALID_PATH", "NUL is forbidden in paths")
    if str(path) == "." and not allow_dot:
        raise ForgeError("INVALID_PATH", "project root is not a valid scoped path")
    return path


def resolve_contained(root: Path, value: str, *, must_exist: bool = False) -> Path:
    rel = validate_relative_path(value, allow_dot=True)
    root_real = root.resolve(strict=True)
    candidate = root_real.joinpath(*rel.parts)
    try:
        resolved = candidate.resolve(strict=must_exist)
    except OSError as exc:
        raise ForgeError("PATH_RESOLUTION", f"cannot resolve {value}: {exc}") from exc
    if not resolved.is_relative_to(root_real):
        raise ForgeError("SYMLINK_ESCAPE", f"path escapes project root: {value}")
    return resolved


def validate_tree_containment(root: Path, path: Path) -> None:
    root_real = root.resolve(strict=True)
    if not path.exists() or path.is_file():
        return
    for child in path.rglob("*"):
        if child.is_symlink() and not child.resolve(strict=False).is_relative_to(root_real):
            raise ForgeError("SYMLINK_ESCAPE", f"symlink escapes project root: {child}")


def is_within(path: PurePosixPath, scopes: Iterable[PurePosixPath]) -> bool:
    return any(path == scope or path.is_relative_to(scope) for scope in scopes)


def validate_scopes_do_not_overlap(
    writable: Iterable[PurePosixPath], protected: Iterable[PurePosixPath]
) -> None:
    for write_scope in writable:
        for protected_scope in protected:
            if write_scope == protected_scope:
                raise ForgeError(
                    "AUTHORITY_OVERLAP",
                    f"writable and protected scopes overlap at {write_scope}",
                )
            if write_scope.is_relative_to(protected_scope) or protected_scope.is_relative_to(
                write_scope
            ):
                raise ForgeError(
                    "AUTHORITY_OVERLAP",
                    f"writable {write_scope} overlaps protected {protected_scope}",
                )
