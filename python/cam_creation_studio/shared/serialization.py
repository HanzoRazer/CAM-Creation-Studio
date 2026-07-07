"""JSON (de)serialization for the core's dataclasses.

Future GUIs, HTTP APIs, and file export all need to move domain objects across a
boundary as plain data. Rather than hand-write ``to_json``/``from_json`` on every
dataclass, this module offers generic, reflection-based helpers that understand:

  * nested dataclasses,
  * ``str``-based enums (serialized as their value),
  * ``Optional[...]``, ``list``/``tuple``/``dict`` containers,
  * plain JSON scalars.

Usage::

    text = to_json(move)
    move = from_json(Move, text)

The design goal is round-trip fidelity for the core's own dataclasses, not a
general-purpose serializer for arbitrary Python objects.
"""

from __future__ import annotations

import dataclasses
import json
import typing
from enum import Enum
from typing import Any, Type, TypeVar, get_args, get_origin, get_type_hints

T = TypeVar("T")


def to_dict(obj: Any) -> Any:
    """Recursively convert a dataclass/enum/container into JSON-ready data."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: to_dict(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, (list, tuple)):
        return [to_dict(v) for v in obj]
    if isinstance(obj, dict):
        return {k: to_dict(v) for k, v in obj.items()}
    return obj


def to_json(obj: Any, *, indent: int | None = None, sort_keys: bool = False) -> str:
    """Serialize a dataclass (or nested structure) to a JSON string."""
    return json.dumps(to_dict(obj), indent=indent, sort_keys=sort_keys)


def _strip_optional(tp: Any) -> Any:
    """Return the non-None arm of ``Optional[X]``; otherwise ``tp`` unchanged."""
    if get_origin(tp) is typing.Union:
        args = [a for a in get_args(tp) if a is not type(None)]  # noqa: E721
        if len(args) == 1:
            return args[0]
    return tp


def _coerce(value: Any, tp: Any) -> Any:
    """Coerce raw JSON ``value`` into the annotated type ``tp`` (best effort)."""
    if value is None:
        return None

    tp = _strip_optional(tp)
    origin = get_origin(tp)

    if dataclasses.is_dataclass(tp) and isinstance(tp, type):
        return from_dict(tp, value)

    if isinstance(tp, type) and issubclass(tp, Enum):
        return tp(value)

    if origin in (list, typing.List):
        (item_tp,) = get_args(tp) or (Any,)
        return [_coerce(v, item_tp) for v in value]

    if origin in (tuple, typing.Tuple):
        args = get_args(tp)
        if len(args) == 2 and args[1] is Ellipsis:
            return tuple(_coerce(v, args[0]) for v in value)
        if args:
            return tuple(_coerce(v, t) for v, t in zip(value, args))
        return tuple(value)

    if origin in (dict, typing.Dict):
        args = get_args(tp)
        val_tp = args[1] if len(args) == 2 else Any
        return {k: _coerce(v, val_tp) for k, v in value.items()}

    return value


def from_dict(cls: Type[T], data: Any) -> T:
    """Reconstruct a dataclass instance of ``cls`` from a plain ``dict``."""
    if not (dataclasses.is_dataclass(cls) and isinstance(cls, type)):
        raise TypeError(f"from_dict expects a dataclass type, got {cls!r}")
    hints = get_type_hints(cls)
    kwargs = {}
    for f in dataclasses.fields(cls):
        if not f.init:
            continue
        if f.name in data:
            kwargs[f.name] = _coerce(data[f.name], hints.get(f.name, Any))
    return cls(**kwargs)


def from_json(cls: Type[T], text: str) -> T:
    """Deserialize a JSON string into an instance of dataclass ``cls``."""
    return from_dict(cls, json.loads(text))
