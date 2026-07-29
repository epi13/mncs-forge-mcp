"""Content identities for local Forge state."""

from __future__ import annotations

import hashlib
from pathlib import Path

from .errors import ForgeError


def file_identity(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
    except OSError as exc:
        raise ForgeError("IDENTITY_READ", f"cannot hash {path}: {exc}") from exc
    return "sha256:" + digest.hexdigest()


def content_identity(root: Path, paths: list[Path]) -> str:
    """Hash a sorted, length-delimited file inventory.

    The identity is deliberately named ``forge-tree-sha256-v1`` and is not represented
    as canonical JSON or as an MNCS canonical-document identity.
    """

    root_real = root.resolve(strict=True)
    inventory: list[tuple[str, str]] = []
    for configured in paths:
        resolved = configured.resolve(strict=False)
        if not resolved.is_relative_to(root_real):
            raise ForgeError("PATH_ESCAPE", f"identity path escapes root: {configured}")
        if not resolved.exists():
            inventory.append((resolved.relative_to(root_real).as_posix(), "MISSING"))
            continue
        if resolved.is_file():
            inventory.append((resolved.relative_to(root_real).as_posix(), file_identity(resolved)))
            continue
        for child in sorted(resolved.rglob("*")):
            if child.is_symlink():
                target = child.resolve(strict=False)
                if not target.is_relative_to(root_real):
                    raise ForgeError("SYMLINK_ESCAPE", f"symlink escapes root: {child}")
            if child.is_file():
                inventory.append((child.relative_to(root_real).as_posix(), file_identity(child)))
    digest = hashlib.sha256()
    for name, identity in sorted(inventory):
        name_bytes = name.encode("utf-8")
        identity_bytes = identity.encode("ascii")
        digest.update(len(name_bytes).to_bytes(8, "big"))
        digest.update(name_bytes)
        digest.update(len(identity_bytes).to_bytes(8, "big"))
        digest.update(identity_bytes)
    return "forge-tree-sha256-v1:" + digest.hexdigest()


def identity_map(root: Path, paths: list[Path]) -> dict[str, str]:
    root_real = root.resolve(strict=True)
    result: dict[str, str] = {}
    for path in paths:
        resolved = path.resolve(strict=False)
        name = resolved.relative_to(root_real).as_posix()
        result[name] = content_identity(root_real, [resolved])
    return result
