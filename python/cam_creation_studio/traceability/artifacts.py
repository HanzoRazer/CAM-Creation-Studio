"""Resolve package-local artifacts and capture their exact bytes.

The resolver refuses absolute paths, parent segments, remote references,
symlinks, missing files, and unreadable files. Digests are computed from
the bytes read here, never from a reserialization.
"""

from __future__ import annotations

from pathlib import Path

from . import codes
from .compatibility import MAX_ARTIFACT_BYTES
from .encoding import sha256_bytes
from .errors import TraceabilityDefect
from .models import ArtifactRef, ArtifactSnapshot, Refusal, StoredBytes
from .parsing import (
    _ParseFailure,
    load_bounded_json,
    parse_admission,
    parse_geometry,
    parse_proposal,
    parse_subject,
    parse_validation,
)

_PARSERS = {
    "proposal": parse_proposal,
    "validation": parse_validation,
    "admission": parse_admission,
    "geometry": parse_geometry,
    "subject": parse_subject,
}


def resolve_package_ref(
    package_root: Path, package_ref: str,
) -> tuple[Path | None, Refusal | None]:
    """Return a regular file strictly inside ``package_root``."""
    if not isinstance(package_root, Path):
        raise TraceabilityDefect("package_root must be a Path")
    if not isinstance(package_ref, str) or package_ref.strip() == "" or package_ref != package_ref.strip():
        return None, Refusal(
            codes.REFERENCE_UNRESOLVED, "package reference is blank or padded")
    if "\\" in package_ref or "://" in package_ref or package_ref.startswith("//"):
        return None, Refusal(
            codes.REFERENCE_UNRESOLVED,
            f"remote or non-local reference {package_ref!r}",
        )
    if package_ref.startswith("/") or Path(package_ref).is_absolute():
        return None, Refusal(
            codes.REFERENCE_UNRESOLVED,
            f"absolute reference {package_ref!r}",
        )
    parts = package_ref.split("/")
    if any(part in ("", ".", "..") for part in parts):
        return None, Refusal(
            codes.REFERENCE_UNRESOLVED,
            f"package reference {package_ref!r} escapes the package root",
        )
    if not package_root.exists():
        return None, Refusal(
            codes.REFERENCE_UNRESOLVED, "package root does not exist")
    if package_root.is_symlink():
        return None, Refusal(
            codes.REFERENCE_UNRESOLVED, "package root is a symlink")
    if not package_root.is_dir():
        return None, Refusal(
            codes.REFERENCE_UNRESOLVED, "package root is not a directory")
    current = package_root
    for part in parts:
        current = current / part
        if current.is_symlink():
            return None, Refusal(
                codes.REFERENCE_UNRESOLVED,
                f"symlink is not a package-local artifact: {package_ref}",
            )
        if not current.exists():
            return None, Refusal(
                codes.REFERENCE_UNRESOLVED,
                f"missing artifact {package_ref}",
            )
    if not current.is_file():
        return None, Refusal(
            codes.REFERENCE_UNRESOLVED,
            f"artifact {package_ref} is not a regular file",
        )
    try:
        current.relative_to(package_root)
    except ValueError:
        return None, Refusal(
            codes.REFERENCE_UNRESOLVED,
            f"artifact {package_ref} is outside the package root",
        )
    return current, None


def read_exact(path: Path) -> tuple[bytes | None, Refusal | None]:
    try:
        data = path.read_bytes()
    except (OSError, PermissionError) as exc:
        return None, Refusal(
            codes.REFERENCE_UNRESOLVED, f"unreadable artifact: {exc.strerror or exc}")
    if len(data) > MAX_ARTIFACT_BYTES:
        return None, Refusal(
            codes.REFERENCE_UNRESOLVED, "artifact exceeds the size limit")
    return data, None


def load_package(
    package_root: Path,
    refs: tuple[ArtifactRef, ...],
    request_raw: bytes,
) -> tuple[ArtifactSnapshot | None, dict | None, Refusal | None]:
    """Read each declared artifact, verify its digest, and parse its profile."""
    stored: list[StoredBytes] = []
    parsed: dict = {}
    for ref in refs:
        path, refusal = resolve_package_ref(package_root, ref.package_ref)
        if refusal is not None or path is None:
            return None, None, refusal
        raw, refusal = read_exact(path)
        if refusal is not None or raw is None:
            return None, None, refusal
        actual = sha256_bytes(raw)
        if actual != ref.sha256:
            return None, None, Refusal(
                codes.DIGEST_MISMATCH,
                f"{ref.role} bytes do not match the declared SHA-256",
            )
        try:
            document = load_bounded_json(raw)
            record = _PARSERS[ref.role](document)
        except _ParseFailure as exc:
            return None, None, Refusal(exc.code, f"{ref.role}: {exc.detail}")
        if record.artifact_id != ref.artifact_id:
            return None, None, Refusal(
                codes.DIGEST_MISMATCH,
                f"{ref.role} artifact_id does not match the request reference",
            )
        stored.append(StoredBytes(
            role=ref.role,
            package_ref=ref.package_ref,
            sha256=actual,
            raw=raw,
        ))
        parsed[ref.role] = record
    root_text = str(package_root.absolute())
    snapshot = ArtifactSnapshot(
        package_root=root_text,
        request_raw=bytes(request_raw),
        request_sha256=sha256_bytes(request_raw),
        artifacts=tuple(stored),
    )
    return snapshot, parsed, None


def reverify_snapshot(
    snapshot: ArtifactSnapshot, package_root: Path,
) -> Refusal | None:
    """Re-read the captured paths. Changed bytes refuse export."""
    if package_root.is_symlink() or not package_root.is_dir():
        return Refusal(
            codes.REFERENCE_UNRESOLVED, "package root changed before export")
    if str(package_root.absolute()) != snapshot.package_root:
        return Refusal(
            codes.SNAPSHOT_CHANGED, "export package root is not the verified root")
    request_path, refusal = resolve_package_ref(package_root, "request.json")
    if refusal is not None or request_path is None:
        return refusal
    raw, refusal = read_exact(request_path)
    if refusal is not None or raw is None:
        return refusal
    if raw != snapshot.request_raw or sha256_bytes(raw) != snapshot.request_sha256:
        return Refusal(
            codes.SNAPSHOT_CHANGED,
            "request bytes changed after verification",
        )
    for item in snapshot.artifacts:
        path, refusal = resolve_package_ref(package_root, item.package_ref)
        if refusal is not None or path is None:
            return refusal
        current, refusal = read_exact(path)
        if refusal is not None or current is None:
            return refusal
        if current != item.raw or sha256_bytes(current) != item.sha256:
            return Refusal(
                codes.SNAPSHOT_CHANGED,
                f"{item.role} bytes changed after verification",
            )
    return None
