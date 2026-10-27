# Rectangular centerline planner

**Order:** CS-017
**Status:** Experimental. Not for machining.

`cam_creation_studio.planning` expands one explicit rectangular cutter
centerline into a CS-016 `ToolpathPlan`. `cam_creation_studio.toolpath`
remains the motion contract and does not contain this algorithm. The
planner does not offset geometry and does not copy an instrument algorithm
from another repository.

## Identity

| Field | Value |
|---|---|
| Planner id | `creation-studio.rectangle-centerline` |
| Planner version | `1` |
| Motion source | `rectangular_centerline_planner` |
| Planner input | `creation-studio.rectangular-planner-input/1` |
| Generated plan wrapper | `creation-studio.traceable-plan/2` |
| Generated export manifest | `creation-studio.traceable-export-manifest/2` |
| Canonical toolpath | `camstudio_toolpath_v1` |

Explicit linear motion supplied by a caller stays
`explicit_linear_motion` with planner identity `unavailable`. A
`motion_source` string on a caller object is not generated provenance.
The generated seal is assigned only by the traceability adapter after
`expand_rectangular_contour`.

## Supported shape

One operation plan, one contour definition, one binding, and one selection
of exactly four `Line2D` edges. The edges are axis-aligned, lie in Z0, and
match the four full sides of their own axis-aligned box exactly once.
Matching is undirected and exact. Gaps, repeated edges, diagonals, rotated
shapes, curves, and non-planar edges are refused.

Traversal starts at `(xmin, ymin)` and continues
`(xmax, ymin) → (xmax, ymax) → (xmin, ymax) → (xmin, ymin)`, viewed from
+Z. Relation must be `on`. Direction must be `unspecified`. Stock allowance
must be exactly zero. Climb and conventional requests are refused rather
than ignored.

The binding must resolve to a catalog end mill. The verified request must
name that same tool id and diameter, `flat_end_mill`, fixed orientation,
and the same material id. The existing 6 mm synthetic coupon tool is not
treated as the 1/4 inch catalog tool.

## Passes

For each supplied depth `d`:

1. Vertical plunge from `(xmin, ymin, travel_height_mm)` to `(xmin, ymin, -d)`
   at the selected plunge feed.
2. Four horizontal cuts around the rectangle at the selected cut feed.
3. Vertical retract to the same travel-height pose.

Each pass is one `OperationPath` with `depth_mm = d`. Motion and path ids
come from the CS-016 builders. The end of one pass is the start of the next.
No zero-length travel segment is inserted.

Travel height must be at or above clearance. Depth levels must be positive,
finite, and strictly increasing. The last level must equal the definition
target depth. A step larger than the declared stepdown is refused. A level
greater than the declared removal maximum is refused. The `1e-9` mm matching
tolerance in the bounds checker is not applied to that maximum.

The plan-level `planned_feed_mm_min` stores the selected cut feed. Plunge
feed is stored on the plunge motions and in the generated digest. Neither
value is taken from stored feed advice unless `recommendation_id` names that
advice explicitly.

## Local limits

These constants live in `cam_creation_studio.planning.limits`. A request,
planner-input field, or CLI flag cannot raise them. One pass is six motions.

| Limit | Value | Refusal |
|---|---|---|
| Depth levels | 8 | `UNSUPPORTED_CAPABILITY` before motion allocation |
| Motions | 18 | `UNSUPPORTED_CAPABILITY` before motion allocation |
| Planner-input bytes | 262144 | `UNSUPPORTED_CAPABILITY` before expansion |

The same numbers are part of the traceability policy digest, so changing a
limit invalidates a fixture review.

## Witness

`tools/run_traceable_planning_witness.py` keeps `--mode verify` as the
default. Verify does not read `planner-inputs.json`.

Prepare (`--mode prepare`) verifies the package and planner inputs, builds
and checks the canonical plan, and writes `candidate_plan.json`,
`preview.json`, and `result.json`. It exits 1 with
`planning_status=candidate_ready`, `export_status=blocked`, and
`REVIEW_REQUIRED`. It does not write a program and it does not accept a
review.

Export (`--mode export --review PATH`) reverifies the prepared input
digests, regenerates the plan, and binds the review. A matching
fixture-binding review writes `program.gcode` and `manifest.json` and
exits 0. The program is experimental. The review is not human approval.
Operational mode stays `EXPERIMENTAL_ONLY`.

If the operation plan or planner input changes after prepare, export
refuses with `SNAPSHOT_CHANGED`, writes no program, and removes the stale
candidate and preview. Fixture-review bytes are created only by the test
helper `tests/support/fixture_review.py`.

## Still unsupported

Polylines that are not four full sides, holes, islands, inside and outside
offsets, tabs, ramps, helices, arcs, pockets, drills, cutter compensation,
controller-specific posts, and physical optimization. Canonical upstream
admission and a governed real-artifact review workflow remain future work.
This planner does not activate production policy.
