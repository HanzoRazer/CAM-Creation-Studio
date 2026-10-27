# CS-017 results

Recorded 2026-10-26 (America/Chicago). No material was cut. Nothing was
merged or deployed. The program text below is experimental fixture output.

## Repository

| Item | Value |
|---|---|
| URL | `https://github.com/HanzoRazer/CAM-Creation-Studio` |
| Base branch | `main` |
| Base SHA | `374fa5832e571cebb470c5dc2e57f43b71e71226` |
| Requested branch name | `cs-017-rectangular-contour-witness` |
| Working branch | `cursor/cs-017-rectangular-contour-witness-39ad` |
| Verified implementation | `f96a9dd29bccb8d5b49cc86b98cd1760d8b3e330` |
| Draft pull request | #36, not merged |

Stage 0 on this machine, before the planner edits: `python3 -m pytest -q --tb=line`
from `python/` reported `1110 passed, 21 skipped`. That is the count for this
environment. The historical `1117 passed, 14 skipped` figure was not reused.
Open pull requests at intake: none. No remote CS-017 branch was present.
Closed #34 was not stacked and its motion predicates were not reapplied.

Python 3.12.3. Package version `0.1.0`. The tree already imported
`cam_creation_studio`; the suite was run from `python/` against that tree.

## Commands

```text
cd python
python3 -m pytest tests/test_rectangular_contour_planner.py tests/test_planned_witness.py tests/test_traceable_planning.py tests/test_traceable_review_regressions.py -q --tb=short
```

`125 passed, 7 skipped`.

```text
cd python
python3 -m pytest -q --tb=line
```

`1159 passed, 21 skipped in 4.00s`.

`git diff --check` produced no output.

## Witness CLI

From the repository root. Verify is the default and does not read planner
inputs.

```text
python3 tools/run_traceable_planning_witness.py \
  --package python/tests/fixtures/traceable_planning/rectangle_planned \
  --destination <verify-dir> \
  --mode verify \
  --case rectangle_planned
```

Exit 1. `reason_codes` is `UNSUPPORTED_CAPABILITY`. `program_written` is
false. No candidate file is written.

```text
python3 tools/run_traceable_planning_witness.py \
  --package python/tests/fixtures/traceable_planning/rectangle_planned \
  --destination <prepare-dir> \
  --mode prepare \
  --case rectangle_planned
```

Exit 1. `planning_status=candidate_ready`, `export_status=blocked`,
`reason_codes=["REVIEW_REQUIRED"]`. `candidate_plan.json`, `preview.json`,
and `result.json` are written. No program is written.
`program_exported` and `human_approval` on the candidate are false.

```text
python3 tools/run_traceable_planning_witness.py \
  --package python/tests/fixtures/traceable_planning/rectangle_planned \
  --destination <export-dir> \
  --mode export \
  --review <fixture-review.json> \
  --case rectangle_planned
```

Exit 0 only when the review binds the prepared plan digest and the local
policy. This run wrote `program.gcode` and `manifest.json`.

| Item | Value |
|---|---|
| Plan digest | `01b2e014a4d163e82713eda1594e1f5800874981154acbadda36973ac2de8a81` |
| Program SHA-256 | `222d06b0a231b730f17f4d57711356f1fe2e07a7efee58f78e7d4aab3d04b0a6` |
| Manifest `program_sha256` | the same digest |
| Planner | `creation-studio.rectangle-centerline` version `1` |
| Motion source | `rectangular_centerline_planner` |
| Manifest contract | `creation-studio.traceable-export-manifest/2` |

The program begins `(EXPERIMENTAL — NOT FOR MACHINING)`, rapids to the
clearance pose `(20, 15, 5)`, plunges to `Z-1` at `F300`, cuts the
rectangle at `F800`, and retracts. The candidate's embedded toolpath
version remains `camstudio_toolpath_v1`.

`--mode export` without `--review`, and `--mode prepare` with `--review`,
exit 2. There is no operational, approve, or force switch.

## What this increment does

The planner turns one explicit Z0 rectangle into two paths and twelve
linear motions for depths 1 mm and 2 mm. Horizontal cutting distance is
240 mm. The canonical plan uses the operation plan's definition, binding,
and geometry ids. The 1/4 inch catalog tool (`endmill_1_4`, 6.35 mm) and
`hardwood` are the binding. A stored feed recommendation is present and
not selected. Independent bounds checks accept the plan and refuse a
corrupted endpoint. Preview is a lossy projection of that plan. A separate
fixture review allows one labeled offline program.

## What remains

Canonical upstream admission and trust, a governed review of real
artifacts, offset and pocket and drill planning, and operational export.
This order does not lift real-tonewood evidence requirements in other
repositories and does not authorize physical machining.
