# Tool and Material Binding (Manufacturing Planning)

CS-013 adds a planning-layer contract that binds an existing CS-012
`OperationDefinition` to one canonical `Tool` and one canonical `Material`.
It answers:

```text
which cutter and workpiece material the user intends for this operation
```

It does not answer whether that combination is a good idea, or what feeds,
speeds, or toolpaths should follow.

```text
Geometry Workspace
      ↓
Operation Definition
      ↓
Tool + Material Binding     (this document)
      ↓
Feeds / Speeds              (CS-014)
      ↓
Toolpath Planning           (CS-015 architecture; production in CS-016)
```

See [OPERATION_DEFINITION.md](OPERATION_DEFINITION.md) for definition
contracts. Catalog objects live in `cam_creation_studio.feeds_speeds`.

## Public API

```python
from cam_creation_studio.operations import (
    bind_operation, replace_binding, remove_binding,
    resolve_tool, resolve_material, summarize_bindings,
    operation_plan_to_json,
)

plan = bind_operation(plan, definition.id, "endmill_1_4", "hardwood")
tool = resolve_tool(plan.bindings[0])       # canonical catalog Tool
material = resolve_material(plan.bindings[0])
print(summarize_bindings(plan))
text = operation_plan_to_json(plan)
```

| Helper | Role |
|--------|------|
| `bind_operation(plan, definition_id, tool_id, material_id, *, id=None)` | Add one binding. Rejected if the definition is already bound. Returns a v2 plan. |
| `replace_binding(plan, binding_id, tool_id, material_id)` | Change tool/material. Binding ID and `definition_id` are unchanged. |
| `remove_binding(plan, binding_id)` | Drop the binding. Definition, intent, selection, and geometry remain. |
| `resolve_tool` / `resolve_material` | Catalog lookup. Unknown IDs are `BindingError`. |
| `summarize_bindings` | Bound vs unbound counts. No ready flag. |

A second `bind_operation` on an already-bound definition is an error.
Replacement is explicit.

## Canonical ownership

There is no planning-specific tool or material model.

```text
Tool      → cam_creation_studio.feeds_speeds.tools.Tool
Material  → cam_creation_studio.feeds_speeds.materials.Material
```

`OperationBinding` stores IDs only:

```text
id
definition_id
tool_id
material_id
```

Diameter, flute count, kind, notes, and chipload stay on the catalog objects.
Resolve them with `get_tool` / `get_material` (wrapped as `resolve_tool` /
`resolve_material` so unknown IDs raise `BindingError` rather than a bare
`ValueError`).

Machine profiles are not bound here. CS-014 introduces machine context when
it produces an advisory `FeedRecommendation`.

## Cardinality and REFERENCE

Each definition has **zero or one** binding. Unbound machining definitions
are structurally valid incomplete planning context, not an error.

`ReferenceDefinition` cannot be bound. That is structural: the category is
explicitly non-machining.

## Suitability is out of scope

These are structurally valid:

```text
DRILL + endmill_1_4 + hardwood
ENGRAVE + ballnose + stainless
CONTOUR + laser_diode + mild_steel
```

No tool-kind × operation-kind matrix. No diameter-vs-geometry check. All
catalogued materials are bindable to machining definitions.

## Lifecycle and referential integrity

`remove_definition` is rejected while a binding still names that definition.
The error lists the dependent binding IDs. Required sequence:

```text
remove_binding → remove_definition
```

There is no cascade. `replace_definition` that keeps the same definition ID
leaves the binding in place. A binding whose `definition_id` is missing is
invalid.

`BindingError` is a subclass of `OperationDefinitionError`. Plan callers can
catch the family or the binding-specific type.

## Persistence

| Event | Document |
|-------|----------|
| Newly built plan | `camstudio_operation_plan_v2` with a `bindings` array (possibly empty) |
| Load CS-012 v1 | version stays v1, `bindings = ()` |
| Serialize untouched v1 | v1, no `bindings` key |
| `bind_operation` / `replace_binding` on v1 | explicit upgrade to v2 |
| Unknown version or catalog ID | fail closed; no placeholder resources |

Read is not migration. There is no silent `from_dict` upgrade helper.

## Boundaries

Not recorded or computed:

* machine / machine ID
* feed, RPM, chipload calculation, surface speed
* stepdown, stepover, pass count, entry strategy
* toolpath, G-code, post-processor, machine readiness
* compatibility matrices, cutter-diameter validation, tool reach

A bound plan is not safe or machine-ready. CS-014 consumes
`OperationDefinition + OperationBinding + Tool + Material + MachineProfile`
plus an explicit requested `spindle_rpm` to produce an **advisory**
`FeedRecommendation`. See
[FEEDS_SPEEDS_INTEGRATION.md](FEEDS_SPEEDS_INTEGRATION.md).

A future `ToolpathPlan` retains `binding_id` as lineage and resolves cutter
radius from the canonical `Tool` at generation time. Binding semantics do
not change: this document still does not compute compensation, feeds, or
paths. See [architecture/TOOLPATH_CONTRACT.md](architecture/TOOLPATH_CONTRACT.md).

A demo lives at
[`../examples/tool_material_binding_demo.py`](../examples/tool_material_binding_demo.py).
