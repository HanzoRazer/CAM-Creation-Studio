# Operation Definition (Manufacturing Planning v1)

The `operations` package is the first authorized manufacturing-planning
layer above a CS-011 geometry workspace. It answers:

```text
what machining operation the user intends, and which geometry-relative
parameters describe that operation
```

It does not answer how the cutter will travel. There is no tool assignment,
material assignment, feeds/speeds, toolpath, compensation calculation,
G-code, or machine-readiness claim here.

```text
GeometryCollection
      ↓
GeometryWorkspace          (CS-011)
      ↓
GeometrySelection
      ↓
OperationIntent            (category only)
      ↓
OperationDefinition v1     (this document)
      ↓
OperationPlan              (workspace + definitions)
```

See [GEOMETRY_WORKSPACE.md](GEOMETRY_WORKSPACE.md) for intent, selection, and
workspace identity. This document is the operation-definition contract.

## Public API

```python
from cam_creation_studio.workspace import (
    build_workspace, create_selection, assign_operation, OperationKind,
)
from cam_creation_studio.operations import (
    define_contour, build_operation_plan,
    ContourRelation, CutDirection,
    operation_plan_to_json, summarize_operation_plan,
)

workspace = build_workspace(collection)
workspace = create_selection(workspace, "profile", [entity_id])
workspace = assign_operation(
    workspace, "outer", OperationKind.CONTOUR, workspace.selections[0].id)
definition = define_contour(
    workspace, workspace.operations[0].id, 6.0,
    relation=ContourRelation.OUTSIDE,
    direction=CutDirection.CLIMB,
)
plan = build_operation_plan(workspace, (definition,))
print(summarize_operation_plan(plan))
text = operation_plan_to_json(plan)
```

Builders (`define_contour`, `define_pocket`, `define_drill`,
`define_engrave`, `define_slot`, `define_reference`) return a definition.
They do not mutate or return an `OperationPlan`. Plan helpers are:

| Helper | Role |
|--------|------|
| `build_operation_plan(workspace, definitions=())` | Validated aggregate. |
| `add_definition` / `replace_definition` / `remove_definition` | Immutable plan updates. |
| `validate_operation_definition` / `validate_operation_definitions` | Structural authority. Returns normally or raises `OperationDefinitionError`. |
| `summarize_operation_plan` | Deterministic counts. |
| `operation_plan_to_json` / `operation_plan_from_json` | Versioned document. |

## Intent versus definition

`OperationIntent` remains a CS-011 object. Its meaning is unchanged:

> User-declared operation category associated with a geometry selection.

An `OperationDefinition` adds planning parameters for that intent:

```text
"I intend this to be a contour"
        ↓
"I intend an outside contour to 6 mm depth"
```

Canonical relationship:

```text
OperationDefinition.intent_id  →  OperationIntent.id
```

The definition does not copy selection IDs, geometry IDs, or operation kind.
The intent remains the ownership link. At most one definition may name a
given intent. A second definition for the same `intent_id` is an
`OperationDefinitionError`.

## Contracts

| Kind | Definition | Planning fields |
|------|------------|-----------------|
| `CONTOUR` | `ContourDefinition` | `target_depth_mm`, `relation`, `direction`, optional `stock_allowance_mm` |
| `POCKET` | `PocketDefinition` | `target_depth_mm`, `direction`, optional wall/floor allowances |
| `DRILL` | `DrillDefinition` | `target_depth_mm`, optional `retract_height_mm`, optional `peck_depth_mm` |
| `ENGRAVE` | `EngraveDefinition` | `target_depth_mm` only |
| `SLOT` | `SlotDefinition` | `target_depth_mm`, `relation` (`ON_PATH`), optional finished `slot_width_mm`, `direction` |
| `REFERENCE` | `ReferenceDefinition` | identity only — no machining dimensions |

Intent kind and definition type must agree. `ContourDefinition` on a
`POCKET` intent is a structural error, not a machining judgement.

## Units and depth

All dimensional fields are millimetres internally. There is no parallel
inch dataclass. Depth is a **positive magnitude**:

```text
target_depth_mm = 6.0
```

means 6 mm of intended machining depth. It is not `Z = -6`. Machine-coordinate
sign belongs downstream.

For machining kinds, `target_depth_mm > 0`. Zero and negative depths are
invalid. `REFERENCE` has no depth.

Optional parameters use `None` for unspecified. Do not use `0` to mean
"not set". When a value *is* supplied:

| Field | Rule |
|-------|------|
| `stock_allowance_mm`, `wall_allowance_mm`, `floor_allowance_mm` | finite, `>= 0` |
| `peck_depth_mm`, `slot_width_mm` | finite, `> 0` |
| `retract_height_mm` | finite, `>= 0` (`0` means retract to the planning reference) |
| NaN / ±Inf | always rejected |

Allowances are material intentionally left for a later finishing operation.
Negative allowance is not supported in v1. `peck_depth_mm` is not compared
to `target_depth_mm`: a peck larger than target depth may be odd, but that
is a feasibility question, not structural validity.

`slot_width_mm` is intended finished slot width. It is not cutter diameter
and does not imply one-pass eligibility.

## Declarative vocabularies

Closed `str` enums. Unknown serialized values fail at reconstruction.
`UNSPECIFIED` is only a legitimate member of `CutDirection`.

```text
ContourRelation:  on | inside | outside
CutDirection:     climb | conventional | unspecified
SlotRelation:     on_path
```

Contour relationship and cut direction are preferences. No offset, winding
direction, or toolpath is computed from them. Slot relation is included even
with a single legal value so the contract is explicit.

## Identity

Definition IDs follow CS-011 creation-context identity:

```text
stable_id(definition_type, intent_id, existing_count)
```

Helpers accept optional `id=`. `uuid4()` / `new_id()` are not used.
`replace_definition` keeps the existing ID. It may change `intent_id` only
to an intent not already owned by another definition.

## Package ownership

Definitions belong to `cam_creation_studio.operations`, not
`workspace.models`. `GeometryWorkspace` is unchanged. The persistence
document is:

```text
camstudio_operation_plan_v1
```

It embeds a CS-011 workspace document. Dependency direction:

```text
operations → workspace
```

`workspace` does not import `operations`. Removing or replacing an intent
that a definition still names is therefore not intercepted by workspace
helpers. Remove the definition first, then the intent. Plan validation is
the authority for missing intents, kind mismatch, duplicate definition IDs,
and duplicate `intent_id` ownership.

A CS-011 workspace document created before CS-012 remains valid. It is not
an operation-plan document.

## Structural validation

Broken IDs, dangling intent references, unknown versions or vocabulary,
duplicate IDs, one-definition-per-intent violations, and invalid dimensions
raise `OperationDefinitionError`. They are not advisory import findings.

Geometry suitability is out of scope. `DRILL` on a `LINE`, `POCKET` on an
open polyline, and `CONTOUR` on a circle are structurally accepted when the
intent kind matches.

## Boundaries

Not recorded, computed, or implied:

* tool / tool ID / cutter diameter / tool number
* material / material ID
* feed, RPM, chipload, surface speed
* stepdown, stepover, pass count, ramp, helix, lead-in/out, tabs
* cutter compensation geometry
* pocket-clearing algorithm, drilling cycles, slot/contour toolpaths
* G-code, post-processor, machine profile, machine readiness

`definitions_without_tool_count` on the summary equals the definition count
in v1. That is descriptive. Tools being absent is not an error; CS-013 owns
tool and material binding. See
[TOOL_MATERIAL_BINDING.md](TOOL_MATERIAL_BINDING.md).

A demo lives at
[`../examples/operation_definition_demo.py`](../examples/operation_definition_demo.py).
