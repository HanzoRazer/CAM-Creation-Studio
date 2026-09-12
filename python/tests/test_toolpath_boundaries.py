"""Architectural guards for the toolpath package (CS-016).

Canonical motion must not grow G-code, preview, dialect, or planner APIs.
"""

from __future__ import annotations

import ast
from pathlib import Path

from cam_creation_studio.toolpath.enums import MotionKind
from cam_creation_studio.toolpath.models import (
    ArcMotion,
    LinearMotion,
    OperationPath,
    ToolpathPlan,
    ToolpathStrategy,
)

_TOOLPATH = Path(__file__).resolve().parents[1] / "cam_creation_studio" / "toolpath"

_FORBIDDEN_TYPE_NAMES = {
    "ToolpathSegment", "Move", "ArcMove", "MoveType", "GCodeProgram",
}
_FORBIDDEN_VALUES = {
    "G0", "G1", "G2", "G3", "M3", "M5", "dialect", "controller",
    "postprocessor", "machine_ready", "approved",
}
_FORBIDDEN_FUNC_NAMES = {
    "plan_contour", "plan_pocket", "plan_drill", "plan_slot", "plan_engrave",
}


def test_motion_kind_is_not_gcode_words():
    assert set(MotionKind) == {
        MotionKind.TRAVEL, MotionKind.CUT, MotionKind.PLUNGE, MotionKind.RETRACT,
    }
    for kind in MotionKind:
        assert not kind.value.startswith("G")


def test_core_models_do_not_declare_forbidden_fields():
    forbidden = _FORBIDDEN_VALUES | {
        "source_command", "burn", "extrude", "safe_height_mm", "gcode",
    }
    for cls in (ToolpathStrategy, LinearMotion, ArcMotion, OperationPath,
                ToolpathPlan):
        for name in cls.__dataclass_fields__:
            assert name not in forbidden, (cls.__name__, name)
            assert "safe" not in name


_CORE_MODULES = (
    "models.py", "enums.py", "errors.py", "ids.py", "fingerprint.py",
    "validation.py", "builders.py", "serialization.py", "status.py",
)


def _imported_modules(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    return names


def test_core_modules_do_not_import_preview_or_gcode():
    for name in _CORE_MODULES:
        path = _TOOLPATH / name
        if not path.exists():
            continue
        for module in _imported_modules(path):
            parts = module.split(".")
            assert "preview" not in parts, (name, module)
            assert "gcode" not in parts, (name, module)
            assert module != "cam_creation_studio.models"


def test_no_planner_algorithm_functions_in_the_package():
    found: list[str] = []
    for path in _TOOLPATH.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name in _FORBIDDEN_FUNC_NAMES:
                found.append(f"{path.name}:{node.name}")
            if isinstance(node, ast.ClassDef) and node.name in _FORBIDDEN_TYPE_NAMES:
                found.append(f"{path.name}:{node.name}")
    assert found == []


def test_package_does_not_use_uuid4_or_new_id():
    for path in _TOOLPATH.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "uuid4" not in text, path.name
        assert "new_id(" not in text, path.name


def test_package_does_not_import_the_study_probe():
    for path in _TOOLPATH.glob("*.py"):
        for module in _imported_modules(path):
            assert "toolpath_contract_probe" not in module


def test_only_preview_adapter_imports_preview():
    for path in _TOOLPATH.glob("*.py"):
        modules = _imported_modules(path)
        has_preview = any("preview" in name.split(".") for name in modules)
        if path.name == "preview_adapter.py":
            assert has_preview
        else:
            assert not has_preview


def test_toolpath_is_not_reexported_from_package_root():
    root = Path(__file__).resolve().parents[1] / "cam_creation_studio" / "__init__.py"
    text = root.read_text(encoding="utf-8")
    assert "from .toolpath" not in text
    assert "cam_creation_studio.toolpath" not in text

