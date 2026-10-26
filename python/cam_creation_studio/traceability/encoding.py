"""Deterministic encodings and exact-byte digests.

Referenced artifacts are hashed as the bytes that were stored. They are not
parsed and written back out before the comparison. Structured fingerprints
use canonical JSON: sorted keys, no insignificant whitespace, UTF-8, and no
non-finite numbers.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any

from .errors import TraceabilityDefect


def sha256_bytes(data: bytes) -> str:
    """Lowercase hex SHA-256 of ``data``."""
    if not isinstance(data, (bytes, bytearray)):
        raise TraceabilityDefect("sha256_bytes expects bytes")
    return hashlib.sha256(bytes(data)).hexdigest()


def _normalize(value: Any, path: str) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        if isinstance(value, bool):
            return value
        if isinstance(value, int) and not isinstance(value, bool):
            return value
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise TraceabilityDefect(f"non-finite number at {path}")
        return value
    if isinstance(value, dict):
        return {
            str(key): _normalize(item, f"{path}.{key}")
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [
            _normalize(item, f"{path}[{index}]")
            for index, item in enumerate(value)
        ]
    raise TraceabilityDefect(
        f"unsupported deterministic value {type(value)!r} at {path}")


def canonical_json(value: Any) -> str:
    """Stable JSON text for a structured fingerprint. Rejects non-finite numbers."""
    normalized = _normalize(value, "$")
    return json.dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        ensure_ascii=True,
    )


def digest_json(value: Any) -> str:
    """SHA-256 of :func:`canonical_json`."""
    return sha256_bytes(canonical_json(value).encode("utf-8"))
