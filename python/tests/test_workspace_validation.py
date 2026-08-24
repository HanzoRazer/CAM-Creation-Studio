"""Structural validation is a WorkspaceError authority, not findings (CS-011)."""

from __future__ import annotations

import pytest

from cam_creation_studio.geometry.models import GeometryCollection, Line2D
from cam_creation_studio.shared.geometry import Point
from cam_creation_studio.workspace.builder import build_workspace
from cam_creation_studio.workspace.errors import WorkspaceError
from cam_creation_studio.workspace.models import (
    WORKSPACE_VERSION,
    GeometryGroup,
    GeometryRef,
    GeometrySelection,
    GeometryWorkspace,
    OperationIntent,
    OperationKind,
)
from cam_creation_studio.workspace.validation import validate_workspace


def _line():
    return Line2D(start=Point(0, 0), end=Point(4, 0))


def _workspace(*, refs=None, selections=(), groups=(), operations=(),
               version=WORKSPACE_VERSION, extra_entities=0):
    entities = [_line() for _ in range(1 + extra_entities)]
    collection = GeometryCollection(entities=entities)
    if refs is None:
        refs = tuple(
            GeometryRef(id=f"geom-{i}", entity_index=i)
            for i in range(len(entities))
        )
    return GeometryWorkspace(
        version=version,
        geometry=collection,
        geometry_refs=refs,
        selections=selections,
        groups=groups,
        operations=operations,
    )


def test_valid_workspace_returns_none():
    workspace = build_workspace(GeometryCollection(entities=[_line()]))
    assert validate_workspace(workspace) is None


def test_unknown_version_is_structural():
    workspace = _workspace(version="camstudio_geometry_workspace_v0")
    with pytest.raises(WorkspaceError, match="unknown workspace version"):
        validate_workspace(workspace)


def test_geometry_ref_count_must_match_entities():
    workspace = _workspace(refs=())
    with pytest.raises(WorkspaceError, match="does not match entity count"):
        validate_workspace(workspace)


def test_geometry_ref_indexes_must_be_source_order():
    workspace = _workspace(
        refs=(
            GeometryRef(id="geom-1", entity_index=1),
            GeometryRef(id="geom-0", entity_index=0),
        ),
        extra_entities=1,
    )
    with pytest.raises(WorkspaceError, match="source order"):
        validate_workspace(workspace)


def test_geometry_ref_index_out_of_range_is_structural():
    collection = GeometryCollection(entities=[_line()])
    workspace = GeometryWorkspace(
        version=WORKSPACE_VERSION,
        geometry=collection,
        geometry_refs=(GeometryRef(id="geom-0", entity_index=3),),
    )
    with pytest.raises(WorkspaceError, match="source order"):
        validate_workspace(workspace)


def test_duplicate_geometry_ref_ids_are_rejected():
    workspace = _workspace(
        refs=(
            GeometryRef(id="dup", entity_index=0),
            GeometryRef(id="dup", entity_index=1),
        ),
        extra_entities=1,
    )
    with pytest.raises(WorkspaceError, match="duplicate geometry-ref ID"):
        validate_workspace(workspace)


def test_empty_geometry_ref_id_is_rejected():
    workspace = _workspace(refs=(GeometryRef(id="", entity_index=0),))
    with pytest.raises(WorkspaceError, match="must not be empty"):
        validate_workspace(workspace)


def test_duplicate_selection_ids_are_rejected():
    workspace = _workspace(selections=(
        GeometrySelection(id="s1", name="a", entity_ids=("geom-0",)),
        GeometrySelection(id="s1", name="b", entity_ids=("geom-0",)),
    ))
    with pytest.raises(WorkspaceError, match="duplicate selection ID"):
        validate_workspace(workspace)


def test_empty_selection_is_rejected():
    workspace = _workspace(selections=(
        GeometrySelection(id="s1", name="empty", entity_ids=()),
    ))
    with pytest.raises(WorkspaceError, match="is empty"):
        validate_workspace(workspace)


def test_duplicate_entity_ids_inside_a_selection_are_rejected():
    workspace = _workspace(selections=(
        GeometrySelection(id="s1", name="dup", entity_ids=("geom-0", "geom-0")),
    ))
    with pytest.raises(WorkspaceError, match="duplicate entity IDs"):
        validate_workspace(workspace)


def test_selection_missing_entity_is_rejected():
    workspace = _workspace(selections=(
        GeometrySelection(id="s1", name="gone", entity_ids=("missing",)),
    ))
    with pytest.raises(WorkspaceError, match="missing entity"):
        validate_workspace(workspace)


def test_empty_group_is_rejected():
    workspace = _workspace(groups=(
        GeometryGroup(id="g1", name="empty", entity_ids=()),
    ))
    with pytest.raises(WorkspaceError, match="is empty"):
        validate_workspace(workspace)


def test_duplicate_group_ids_are_rejected():
    workspace = _workspace(groups=(
        GeometryGroup(id="g1", name="a", entity_ids=("geom-0",)),
        GeometryGroup(id="g1", name="b", entity_ids=("geom-0",)),
    ))
    with pytest.raises(WorkspaceError, match="duplicate group ID"):
        validate_workspace(workspace)


def test_group_missing_entity_is_rejected():
    workspace = _workspace(groups=(
        GeometryGroup(id="g1", name="gone", entity_ids=("missing",)),
    ))
    with pytest.raises(WorkspaceError, match="missing entity"):
        validate_workspace(workspace)


def test_duplicate_operation_ids_are_rejected():
    workspace = _workspace(
        selections=(GeometrySelection(id="s1", name="a", entity_ids=("geom-0",)),),
        operations=(
            OperationIntent(id="op1", name="a", kind=OperationKind.CONTOUR,
                            selection_id="s1"),
            OperationIntent(id="op1", name="b", kind=OperationKind.DRILL,
                            selection_id="s1"),
        ),
    )
    with pytest.raises(WorkspaceError, match="duplicate operation ID"):
        validate_workspace(workspace)


def test_operation_unknown_kind_is_rejected():
    workspace = _workspace(
        selections=(GeometrySelection(id="s1", name="a", entity_ids=("geom-0",)),),
        operations=(
            OperationIntent(id="op1", name="a", kind="plunge",  # type: ignore[arg-type]
                            selection_id="s1"),
        ),
    )
    with pytest.raises(WorkspaceError, match="unknown kind"):
        validate_workspace(workspace)


def test_operation_missing_selection_is_rejected():
    workspace = _workspace(operations=(
        OperationIntent(id="op1", name="a", kind=OperationKind.CONTOUR,
                        selection_id="missing"),
    ))
    with pytest.raises(WorkspaceError, match="missing selection"):
        validate_workspace(workspace)
