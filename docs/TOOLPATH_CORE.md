# Toolpath Core Contracts

The `toolpath` package is the production form of the CS-015 Candidate B
architecture. It answers:

```text
what ordered, controller-neutral cutter-center motion was planned for
one operation definition, and whether that stored plan still matches
its upstream inputs
```

It does not answer how a contour, pocket, or hole should be generated.
There is no offset algorithm, no pocket clear, no canned cycle, no
G-code emission, and no machine-readiness claim here.

```text
GeometryCollection
      ↓
GeometryWorkspace          (CS-011)
      ↓
OperationDefinition
  + OperationBinding
  + OperationFeedRecommendation   (CS-012–CS-014)
      ↓
ToolpathStrategy
      ↓
ToolpathPlan               (this document)
      ↓
preview projection         → existing ToolpathSegment
      ↓
future G-code adapter      → Move / ArcMove  (not in this package)
```

See [architecture/TOOLPATH_CONTRACT.md](architecture/TOOLPATH_CONTRACT.md)
for the ratified type names and forbidden vocabulary. This document is
the CS-016 implementation contract.

## Public API

```python
from cam_creation_studio.toolpath import (
    MotionKind, ToolpathStrategy,
    make_linear_motion, make_arc_motion, make_operation_path,
    make_toolpath_plan, build_toolpath_plan,
    toolpath_to_json, toolpath_from_json,
    toolpath_status, toolpath_to_preview,
)

strategy = ToolpathStrategy(travel_height_mm=5.0, stepdown_mm=3.0, label="pass 1")
motions = (
    make_linear_motion(MotionKind.TRAVEL, start, approach, index=0),
    make_linear_motion(MotionKind.PLUNGE, approach, cut_start, index=1,
                       planned_feed_mm_min=300.0),
    make_linear_motion(MotionKind.CUT, cut_start, cut_end, index=2,
                       planned_feed_mm_min=800.0),
    make_arc_motion(cut_end, arc_end, center, clockwise=False, index=3,
                    planned_feed_mm_min=800.0),
    make_linear_motion(MotionKind.RETRACT, arc_end, retract, index=4),
)
plan = make_toolpath_plan(
    operation_definition_id="def-1",
    geometry_ids=("geom-a",),
    binding_id="bind-1",
    strategy=strategy,
    paths=(make_operation_path(motions, existing_count=0, depth_mm=3.0),),
    geometry_digest="...",
    definition_digest="...",
    planned_feed_mm_min=800.0,
)
text = toolpath_to_json(plan)
segments = toolpath_to_preview(plan)
```

`build_toolpath_plan(operation_plan, definition_id, strategy, paths)` wires
lineage (geometry ids, binding, recommendation, digests) from an
`OperationPlan` onto **already-constructed** paths. It does not generate
those paths.

Import the package as `cam_creation_studio.toolpath`. It is not re-exported
from `cam_creation_studio`.

A demo lives at
[`../examples/toolpath_contract_demo.py`](../examples/toolpath_contract_demo.py).

## Canonical types

| Type | Role |
|------|------|
| `ToolpathStrategy` | Descriptive planning inputs. `label` is presentation-only. |
| `LinearMotion` | Explicit millimetre pose-to-pose segment. |
| `ArcMotion` | Analytic XY arc (center, radius, clockwise, signed sweep). |
| `OperationPath` | Ordered motions for one pass or approach. `depth_mm` is a pass magnitude, not `target_depth_mm`. |
| `ToolpathPlan` | Versioned sibling document (`camstudio_toolpath_v1`). |

`MotionKind` is `travel` / `cut` / `plunge` / `retract`. There is no
`burn`, `extrude`, or G-word.

Travel height is `travel_height_mm`. It is a planned Z, not a safety
rating.

## What this package will not do

* Generate contour, pocket, slot, or drill geometry (`plan_contour` and
  relatives are forbidden).
* Expand pecks as a production helper. Drilling remains ordinary linear
  motions when a later planner emits them.
* Emit G-code, dialects, or `source_command`.
* Store preview `ToolpathSegment`, `Move`, or `ArcMove` on the plan.
* Collapse recommended feed, planned feed, and execution feed.

## Persistence and staleness

A stored plan carries `strategy_fingerprint` and `upstream_fingerprint`.
Unknown document versions fail closed. Motion order is not sorted.

```text
missing   — no stored path
current   — upstream_fingerprint matches
stale     — stored path exists; fingerprint does not match
```

`STALE` is structural. It does not regenerate motion. Strategy `label`
and recommendation notes do not stale a plan. Geometry coordinates,
definition computational fields, binding identity, tool diameter/flutes,
material chipload, recommendation identity, strategy computational
fields, and `planned_feed_mm_min` do.

## Preview projection

`toolpath_to_preview` maps into the existing preview model:

| Planned kind | Preview type | Feed |
|---|---|---|
| travel, retract | `travel` | `None` |
| cut, plunge | `cut` | planned feed when set |
| open `ArcMotion` | `arc` | planned feed when set |
| full-circle `ArcMotion` | tessellated linear `cut`/`travel` | as above |

`source_command` is left empty. Full-circle tessellation is a view of an
unchanged canonical arc.

## Identifiers

Deterministic `stable_id` values (`lin-`, `arc-`, `path-`, `tp-`,
`strat-`, `up-`). No `uuid4`.
