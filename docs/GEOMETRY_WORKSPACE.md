# Geometry Workspace (Neutral Geometry Consumer)

The `workspace` package is the first authorized application-layer consumer of a
`GeometryCollection`. It answers planning questions only:

```text
what is loaded → what was selected → how it was grouped → what category is intended
```

It does not answer machining questions. There is no toolpath, offset, feed,
depth, compensation, G-code, machine readiness, CAM Assist, or Luthier domain
object here.

```text
DXF  ─▶  import_dxf()  ─▶  GeometryCollection  ─▶  build_workspace()  ─▶  GeometryWorkspace
                                                      inspect / select / group / intend
                                                      serialize / reload
```

See [GEOMETRY_IMPORT.md](GEOMETRY_IMPORT.md) for the importer contract. This
document is the consumer contract.

## Public API

```python
from cam_creation_studio.workspace import (
    build_workspace, inspect_entity, inspect_workspace,
    create_selection, create_group, assign_operation,
    validate_workspace, summarize,
    workspace_to_json, workspace_from_json,
)

workspace = build_workspace(collection)
```

| Helper | Role |
|--------|------|
| `build_workspace(collection)` | Wrap imported geometry. Geometry is stored, not copied or transformed. |
| `inspect_entity` / `inspect_workspace` | Descriptive facts, provenance, bounds, and import-loss evidence. |
| `create_selection` / `replace_selection` / `remove_selection` | Ordered named selections. |
| `create_group` / `replace_group` / `remove_group` | Organizational groups (not manufacturing features). |
| `assign_operation` / `replace_operation` / `remove_operation` | Non-executable operation category on a selection. |
| `validate_workspace(workspace) -> None` | Structural authority. Returns normally or raises `WorkspaceError`. |
| `summarize(workspace)` | Deterministic counts. |
| `workspace_to_json` / `workspace_from_json` | Versioned document. |

Helpers return a new `GeometryWorkspace`. The imported collection object is
never mutated.

## Identity

Two ID kinds live in the workspace and must not be conflated:

```text
GeometryRef IDs:
deterministic identity of imported geometry

Selection / Group / Operation IDs:
deterministic workspace-object identity generated from creation context
```

`GeometryRef` IDs are derived from source order and provenance:

```text
stable_id(entity_index, handle or "", "" if ordinal is None else ordinal, prefix="geom-")
```

The same collection always yields the same refs. `ordinal=0` is a valid
provenance value, not a missing sentinel.

Selection, group, and operation helpers accept optional `id=`. If omitted, the
ID is:

```text
stable_id(kind, name, *member_ids, existing_count)
```

`existing_count` is how many objects of that kind already exist. Equivalent
helper sequences therefore produce equivalent workspaces. This is **not**
content-addressed identity in the `GeometryRef` sense: renaming or
reconstructing a selection does not automatically preserve its ID. `replace_*`
keeps the existing ID; a later `create_*` with the same members mints a new one
because the creation context changed.

`uuid4()` / `new_id()` are not used.

IDs are unique within each collection (refs, selections, groups, operations).
**Names need not be unique.**

## Selections and groups

Both store an ordered tuple of workspace geometry IDs.

- Empty selections and empty groups are rejected. A named container with no
  members has no useful geometry organization.
- Duplicate member IDs are rejected. Caller order is preserved exactly; silent
  deduplication would mutate user intent.
- Groups store `entity_ids` directly, not a selection id.
- Duplicate names are allowed.

## Removing a referenced selection

`remove_selection` is rejected when any operation still names that selection.
There is no cascade and no dangling reference. The error identifies the
dependent operation IDs. Delete operations first, then the selection.

## Operation intent

`OperationKind` is a closed vocabulary owned by the workspace package:

| Value | Meaning |
|-------|---------|
| `contour` | Intended as a contour. |
| `pocket` | Intended as a pocket. |
| `drill` | Intended as a drill. |
| `engrave` | Intended as an engrave. |
| `slot` | Intended as a slot. |
| `reference` | Present, not currently designated for machining. |

There is no `UNKNOWN`. An unknown serialized value fails at reconstruction.

An intent is `id`, `name`, `kind`, and `selection_id` only. It is not a
machining operation: no tool, feed, rpm, depth, side, climb/conventional, or
G-code fields. Shape suitability is not judged. `DRILL` on a `LINE` is a valid
intent. The same selection may carry more than one intent.

## Diagnostic attachment

Inspection attaches a diagnostic to a retained entity only when:

```text
diagnostic.handle is not None
and
entity.source is not None
and
diagnostic.handle == entity.source.handle
```

Layer and DXF type are not used to infer association. Collection-level findings
(no handle) stay collection-level. If two retained entities legitimately share a
source handle, the finding attaches to each.

Two loss surfaces remain distinct, as in the importer:

| Surface | Means |
|---------|-------|
| `inspect_workspace(...).has_lossy_import` | `metadata.has_lossy_import` — an entity was dropped |
| `inspect_workspace(...).import_loss_count` | `collection.report().loss_count` — source information did not survive |

A mesh/polyface `POLYLINE` that is retained as flattened `Polyline2D` can show
entity-level loss and a non-zero import-loss count while `has_lossy_import` is
still false.

## Structural validation

Broken IDs, dangling references, unknown versions or operation kinds, duplicate
IDs, and malformed workspace documents are programming/document errors. They
raise `WorkspaceError`. They are not advisory import findings.

```python
validate_workspace(workspace) -> None
```

returns normally when the document is valid. Helpers, `workspace_from_dict`, and
explicit validation all use this function. There is no second findings-based
validation authority.

## Serialization

Version token:

```text
camstudio_geometry_workspace_v1
```

The document embeds the geometry collection via `GeometryCollection.to_dict` /
`from_dict` so heterogeneous entities round-trip. Enums serialize as their
value. JSON is deterministic: no timestamps, keys sorted by default.

A `GeometryCollection` document is **not** a workspace document (it has no
workspace version). Unknown versions and unknown operation kinds raise
`WorkspaceError`.

There is no workspace title or notes field. Source path, when present, lives on
`geometry.metadata`.

## Future layers

Later increments may interpret this planning state as machining work. That work
is out of scope here and must not be smuggled into these contracts. In
particular this package must not grow toolpath generation, feeds/speeds,
post-processing, or domain objects from CAM Assist or the Luthiers Toolbox.
