"""Public DXF import entry point (CS-008).

:func:`import_dxf` is the one call the rest of the system uses to turn a DXF file
into a neutral :class:`~cam_creation_studio.geometry.models.GeometryCollection`.
It reads the file, normalizes units to millimetres, translates every supported
entity in source order, and records advisory diagnostics for anything it cannot
fully represent — without generating a single toolpath.

``ezdxf`` is an *optional* dependency. The core installs with zero required
runtime deps; DXF support is the ``dxf`` extra. Calling :func:`import_dxf`
without ``ezdxf`` present raises :class:`EzdxfNotInstalled` with an actionable
install hint rather than a bare ``ImportError`` from deep in the stack.
"""

from __future__ import annotations

import os
from typing import Optional

from ..shared.units import dxf_scale_to_mm, dxf_units_name
from . import diagnostics as diag
from .entities import translate
from .models import GeometryCollection, ImportMetadata

_INSTALL_HINT = (
    "DXF import requires the optional 'ezdxf' dependency, which is not installed. "
    "Install it with:  pip install cam-creation-studio[dxf]"
)


class EzdxfNotInstalled(ImportError):
    """Raised by :func:`import_dxf` when the optional ``ezdxf`` extra is absent."""


class DxfImportError(Exception):
    """Raised when a DXF file is missing, unreadable, or structurally corrupt."""


def _require_ezdxf():
    """Import and return the ``ezdxf`` module, or raise :class:`EzdxfNotInstalled`.

    Kept as a tiny indirection so tests can simulate the dependency being absent
    by monkeypatching this function.
    """
    try:
        import ezdxf  # noqa: PLC0415  (intentional lazy import — optional dep)
    except ImportError as exc:  # pragma: no cover - exercised via monkeypatch
        raise EzdxfNotInstalled(_INSTALL_HINT) from exc
    return ezdxf


def import_dxf(path: str) -> GeometryCollection:
    """Import a 2D DXF file into a :class:`GeometryCollection`.

    Args:
        path: Filesystem path to a ``.dxf`` file.

    Returns:
        A collection of neutral geometry entities in source order, with import
        metadata and advisory diagnostics.

    Raises:
        EzdxfNotInstalled: The optional ``ezdxf`` dependency is not available.
        DxfImportError: The path is missing, unreadable, or not a valid DXF.
    """
    if not os.path.isfile(path):
        raise DxfImportError(f"DXF file not found: {path}")

    ezdxf = _require_ezdxf()

    try:
        doc = ezdxf.readfile(path)
    except (ezdxf.DXFError, IOError, ValueError) as exc:
        raise DxfImportError(f"Could not read DXF {path!r}: {exc}") from exc

    diagnostics = []

    # --- units → millimetre scale --------------------------------------- #
    insunits = doc.header.get("$INSUNITS", None)
    scale = dxf_scale_to_mm(insunits)
    units_name = dxf_units_name(insunits)
    if scale is None or insunits in (None, 0):
        diagnostics.append(diag.info(
            diag.UNKNOWN_UNITS,
            "Drawing units are absent or unitless; assuming a 1:1 scale to mm.",
        ))
        scale = scale if scale is not None else 1.0
        units_name = units_name or "unknown"

    # --- translate entities in source order ----------------------------- #
    msp = doc.modelspace()
    # The document's layer-table names, so translation can tell a layer that is
    # merely unusual from one the file never defines. Read once; a missing or
    # unreadable table yields None, which makes the check skip rather than guess.
    known_layers = _layer_table_names(doc)
    entities = []
    seen_handles: set = set()
    raw_count = 0
    unsupported_count = 0

    for ordinal, entity in enumerate(msp):
        raw_count += 1
        handle = getattr(getattr(entity, "dxf", None), "handle", None)
        if handle is not None:
            if handle in seen_handles:
                diagnostics.append(diag.warning(
                    diag.DUPLICATE_HANDLE,
                    f"Duplicate entity handle {handle!r}.",
                    entity_type=entity.dxftype(), handle=handle))
            else:
                seen_handles.add(handle)

        # The ordinal is the modelspace position, so a dropped entity leaves a
        # gap in the imported sequence rather than being silently closed over.
        model, ediags = translate(entity, scale, ordinal, known_layers)
        diagnostics.extend(ediags)
        if model is not None:
            entities.append(model)
        else:
            # translate() returns None only for unsupported entity types.
            unsupported_count += 1

    if raw_count == 0:
        diagnostics.append(diag.info(
            diag.EMPTY_FILE, "DXF modelspace contains no entities."))

    metadata = ImportMetadata(
        source_path=str(path),
        source_units=units_name or "unknown",
        unit_scale=float(scale),
        dxf_version=_dxf_version(doc),
        entity_count=len(entities),
        raw_entity_count=raw_count,
        unsupported_entity_count=unsupported_count,
    )
    return GeometryCollection(
        entities=entities, metadata=metadata, diagnostics=diagnostics)


def _dxf_version(doc) -> Optional[str]:
    return getattr(doc, "dxfversion", None)


def _layer_table_names(doc) -> Optional[frozenset]:
    """Names defined in the document's layer table, or ``None`` if unreadable.

    ``None`` rather than an empty set on failure: an empty set would mean "this
    document defines no layers", which would make every entity look like an
    unknown reference. Absence of evidence is not evidence of absence, so the
    check is skipped instead.
    """
    try:
        return frozenset(layer.dxf.name for layer in doc.layers)
    except Exception:  # noqa: BLE001 - a table we cannot read is not a failure
        return None
