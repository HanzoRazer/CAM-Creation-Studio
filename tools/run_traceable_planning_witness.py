#!/usr/bin/env python3
"""Offline traceable-planning witness.

Writes a JSON result under ``--destination``. A refused or blocked run exits
non-zero and does not leave a candidate program. There is no switch that
promotes an experimental fixture to operational export.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "python"))

from cam_creation_studio.traceability.service import run_witness  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", required=True, type=Path)
    parser.add_argument("--destination", required=True, type=Path)
    parser.add_argument("--case", default=None)
    args = parser.parse_args(argv)
    case = args.case or args.package.name
    try:
        result = run_witness(args.package, args.destination, case=case)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    public = {
        "case": result["case"],
        "reason_codes": result["reason_codes"],
        "detail": result["detail"],
        "program_written": result["program_written"],
        "experimental_banner": result["experimental_banner"],
    }
    print(json.dumps(public, indent=2, sort_keys=True))
    return int(result["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
