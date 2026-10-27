#!/usr/bin/env python3
"""Offline traceable-planning witness.

``--mode verify`` (the default) only verifies a package. It does not read
planner inputs and it does not write a program.

``--mode prepare`` verifies planner inputs and writes a candidate, a
preview, and a result. It does not accept a review and it does not write
a program.

``--mode export`` reverifies those inputs and, with a fixture-binding
review, writes a labeled experimental program. It is not human approval
and it is not operational export.

A refused run exits non-zero. There is no switch that promotes an
experimental fixture to operational export.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "python"))

from cam_creation_studio.traceability.service import (  # noqa: E402
    export_planned_witness,
    prepare_planned_witness,
    run_witness,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", required=True, type=Path)
    parser.add_argument("--destination", required=True, type=Path)
    parser.add_argument("--case", default=None)
    parser.add_argument(
        "--mode", choices=("verify", "prepare", "export"), default="verify")
    parser.add_argument("--review", type=Path, default=None)
    args = parser.parse_args(argv)
    case = args.case or args.package.name
    if args.mode == "verify" and args.review is not None:
        print("error: verify does not accept --review", file=sys.stderr)
        return 2
    if args.mode == "prepare" and args.review is not None:
        print("error: prepare does not accept a review", file=sys.stderr)
        return 2
    if args.mode == "export" and args.review is None:
        print("error: export requires --review", file=sys.stderr)
        return 2
    try:
        if args.mode == "verify":
            result = run_witness(args.package, args.destination, case=case)
        elif args.mode == "prepare":
            result = prepare_planned_witness(
                args.package, args.destination, case=case)
        else:
            review_bytes = args.review.read_bytes()
            result = export_planned_witness(
                args.package, args.destination, review_bytes, case=case)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3
    if args.mode == "verify":
        public = {
            "case": result["case"],
            "reason_codes": result["reason_codes"],
            "detail": result["detail"],
            "program_written": result["program_written"],
            "experimental_banner": result["experimental_banner"],
        }
    else:
        public = {
            "case": result["case"],
            "detail": result["detail"],
            "experimental_banner": result["experimental_banner"],
            "export_status": result["export_status"],
            "planning_status": result["planning_status"],
            "program_written": result["program_written"],
            "reason_codes": result["reason_codes"],
        }
    print(json.dumps(public, indent=2, sort_keys=True))
    return int(result["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
