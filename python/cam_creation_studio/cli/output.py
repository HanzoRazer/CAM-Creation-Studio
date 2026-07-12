"""Output formatting for the CLI: JSON and human-readable text.

Commands build a ``(human_text, json_obj)`` pair and hand it to :func:`render`,
which prints one or the other depending on ``--json``. Keeping this in one place
means every command formats consistently and no command reimplements JSON dumps.
"""

from __future__ import annotations

import json
import sys
from typing import Any, Iterable, Optional, Sequence


def dump_json(obj: Any) -> str:
    """Serialize ``obj`` to a stable, human-diffable JSON string."""
    return json.dumps(obj, indent=2, sort_keys=False)


def render(
    *,
    json_mode: bool,
    human_text: str,
    json_obj: Any,
    stream=None,
) -> str:
    """Print the JSON or human form and return the string that was printed."""
    stream = stream or sys.stdout
    payload = dump_json(json_obj) if json_mode else human_text
    print(payload, file=stream)
    return payload


def format_table(headers: Sequence[str], rows: Iterable[Sequence[Any]]) -> str:
    """A minimal fixed-width table (no external dependency)."""
    rows = [[str(c) for c in row] for row in rows]
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))
    line = "  ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
    sep = "  ".join("-" * widths[i] for i in range(len(headers)))
    body = [
        "  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row))
        for row in rows
    ]
    return "\n".join([line, sep, *body])


def kv_block(pairs: Sequence[tuple], title: Optional[str] = None) -> str:
    """A ``label: value`` block, values aligned. ``None`` values render as '-'."""
    label_w = max((len(str(k)) for k, _ in pairs), default=0)
    lines = [
        f"  {str(k).ljust(label_w)}  {'-' if v is None else v}"
        for k, v in pairs
    ]
    return "\n".join(([title] if title else []) + lines)
