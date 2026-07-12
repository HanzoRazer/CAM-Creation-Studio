"""Geometry subsystem: neutral 2D geometry import (CS-008).

This package ingests 2D DXF geometry into machine-independent dataclasses. It
defines *what geometry exists* — never how it will be machined. There is no
toolpath, feeds/speeds, or G-code logic here, by constitutional boundary.

Public surface::

    from cam_creation_studio.geometry import import_dxf, GeometryCollection

    collection = import_dxf("part.dxf")   # requires the optional 'dxf' extra
    print(summarize(collection))
"""

from __future__ import annotations

from .diagnostics import GeometryDiagnostic
from .importer import DxfImportError, EzdxfNotInstalled, import_dxf
from .layers import by_layer, layer_names, on_layer
from .models import (
    Arc2D,
    Circle2D,
    Entity,
    GeometryCollection,
    ImportMetadata,
    Line2D,
    Polyline2D,
    Spline2D,
)
from .summary import GeometrySummary, summarize

__all__ = [
    # public API
    "import_dxf",
    "GeometryCollection",
    "ImportMetadata",
    "GeometryDiagnostic",
    # entities
    "Line2D",
    "Arc2D",
    "Circle2D",
    "Polyline2D",
    "Spline2D",
    "Entity",
    # utilities
    "summarize",
    "GeometrySummary",
    "layer_names",
    "by_layer",
    "on_layer",
    # errors
    "DxfImportError",
    "EzdxfNotInstalled",
]
