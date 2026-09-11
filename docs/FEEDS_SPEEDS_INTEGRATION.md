# Feeds and Speeds Integration (Manufacturing Planning)

CS-014 connects a bound CS-013 machining definition to CAM-Creation-Studio’s
existing advisory feeds/speeds engine. It answers:

```text
what advisory RPM and feed the existing calculator recommends
for this bound operation, this machine profile, and this requested
operating RPM
```

It does not invent cutter engagement, generate toolpaths, or authorize
a machine to run.

```text
Geometry Workspace
      ↓
Operation Definition
      ↓
Tool + Material Binding
      ↓
Advisory Feeds / Speeds     (this document)
      ↓
Toolpath Planning           (CS-015 architecture; production in CS-016)
```

See [TOOL_MATERIAL_BINDING.md](TOOL_MATERIAL_BINDING.md) for binding
contracts. Catalog objects and the calculator live in
`cam_creation_studio.feeds_speeds`.

## Public API

```python
from cam_creation_studio.operations import (
    recommend_feeds_speeds, replace_feed_recommendation,
    remove_feed_recommendation, recommendation_status,
    summarize_feed_recommendations, operation_plan_to_json,
)

plan = recommend_feeds_speeds(
    plan, definition.id, "genericCncRouter", 12000)
print(plan.recommendations[0].recommendation.feed_rate)
print(recommendation_status(plan, definition.id))
print(summarize_feed_recommendations(plan))
text = operation_plan_to_json(plan)
```

| Helper | Role |
|--------|------|
| `recommend_feeds_speeds(plan, definition_id, machine_profile_id, spindle_rpm, *, id=None)` | Create one recommendation. Rejected if the definition already has one. Returns a v3 plan. |
| `replace_feed_recommendation(plan, recommendation_id, machine_profile_id, spindle_rpm)` | Recalculate. Recommendation ID and `definition_id` are unchanged. |
| `remove_feed_recommendation(plan, recommendation_id)` | Drop the stored advice. Definition and binding remain. |
| `recommendation_status(plan, definition_id, *, machine_profile_id=None)` | `missing` / `current` / `stale`. Does not calculate. |
| `summarize_feed_recommendations` | Counts only. No ready flag. |

A second `recommend_feeds_speeds` on an already-recommended definition is
an error. Replacement is explicit.

## Canonical ownership

There is no planning-specific calculator or recommendation payload.

```text
Tool              → cam_creation_studio.feeds_speeds.tools.Tool
Material          → cam_creation_studio.feeds_speeds.materials.Material
MachineProfile    → cam_creation_studio.feeds_speeds.machines.MachineProfile
FeedRecommendation → cam_creation_studio.feeds_speeds.calculator.FeedRecommendation
```

`OperationFeedRecommendation` stores attribution around the canonical
result:

```text
id
definition_id
binding_id
machine_profile_id
spindle_rpm
input_fingerprint
recommendation
```

`spindle_rpm` is planner/operator input to the request, not a property of
the definition or binding. `MachineProfile.max_rpm` is a constraint. The
calculator’s `FeedRecommendation.rpm` is the rounded output representation.

Machine context belongs to the recommendation, not the binding. There is
no plan-level selected machine.

## Calculator inputs

The adapter calls `calculate_feeds` with:

* `tool_diameter_mm` and `flutes` from the canonical `Tool`
* requested `spindle_rpm`
* `material=<material.id>`
* `max_rpm=machine.max_rpm` only when that field is present

It never passes `doc_mm`, `woc_mm`, `feed_override`, or `max_power_kw`.
It does not parse `MachineProfile.specs`. A machine with `max_rpm is None`
is valid context; the RPM-limit diagnostic simply does not fire.

`target_depth_mm` is final intended operation depth. It is not depth of
cut per pass and is never mapped to `doc_mm`. No operation kind infers
width of cut from tool diameter. Engagement-dependent fields therefore
remain `None` (MRR, power, torque) according to the existing calculator
contract.

Tools with `flutes is None` (`laser_diode`, `drag_knife`) remain valid
CS-013 bindings, but this recommendation engine cannot process them.
That is a `RecommendationError`, not a bad binding.

`REFERENCE` cannot receive a recommendation. Unbound machining
definitions cannot either. Odd but flute-bearing pairings remain
calculable; calculator warnings stay warnings.

## Lifecycle and referential integrity

`remove_binding` and `remove_definition` are rejected while a
recommendation still depends on them. Required sequence:

```text
remove_feed_recommendation → remove_binding → remove_definition
```

There is no cascade and no silent recalculation. `replace_binding` keeps
the stored recommendation and marks it `STALE`.

`RecommendationError` is a subclass of `OperationDefinitionError`.
Catalog and calculator `ValueError`s are wrapped at the operations
boundary.

## Staleness

The input fingerprint is a deterministic JSON serialization of
calculation-driving primitives: definition/binding/tool/material/machine
IDs, `tool.diameter_mm`, `tool.flutes`, `material.chipload_mm`,
`machine.max_rpm`, and the requested `spindle_rpm`. Labels, notes, and
timestamps are omitted.

```text
no stored recommendation → missing
fingerprint matches current binding/catalog/stored machine inputs → current
calculation-driving inputs changed → stale
caller supplies a different machine_profile_id → stale
```

`STALE` means the stored advice no longer corresponds to current
planning inputs. It is not a claim that the advice is unsafe. Status,
summary, and deserialization never call the calculator.

## Persistence

| Event | Document |
|-------|----------|
| Newly built plan | `camstudio_operation_plan_v3` with `bindings` and `recommendations` arrays (possibly empty) |
| Load CS-012 v1 | version stays v1, empty bindings and recommendations |
| Load CS-013 v2 | version stays v2, bindings preserved, recommendations empty |
| Serialize untouched v1/v2 | original version; no `recommendations` key |
| Recommendation mutation | explicit upgrade to v3 |
| Unknown version or catalog ID | fail closed |

Read is not migration and not calculation.

## Boundaries

Not recorded or computed:

* automatic DOC, WOC, stepdown, stepover, pass count
* toolpath, compensation, lead-in/out, tabs
* G-code, post-processor, machine readiness
* suitability matrices
* `machine_ready`, `safe`, or `approved` flags

A stored recommendation is advisory manufacturing guidance. A future
toolpath planner may use it as **input** when choosing a planned path feed.
It remains advisory:

```text
recommended feed ≠ planned path feed
recommended feed ≠ validated execution feed
```

The path contract stores `recommendation_id` plus a separate
`planned_feed_mm_min`. Neither number is an F-word or an execution
authority. See [architecture/TOOLPATH_CONTRACT.md](architecture/TOOLPATH_CONTRACT.md).

A demo lives at
[`../examples/feeds_speeds_planning_demo.py`](../examples/feeds_speeds_planning_demo.py).
