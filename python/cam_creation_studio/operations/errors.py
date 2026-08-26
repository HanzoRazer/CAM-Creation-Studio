"""Structural errors for manufacturing operation definitions (CS-012/CS-013).

Broken IDs, dangling intent references, unknown vocabulary, invalid
dimensional values, unknown tool/material IDs, and malformed operation-plan
documents are programming/document errors — not advisory import findings
and not machining judgements. :class:`OperationDefinitionError` is the
family; :class:`BindingError` is the binding-specific member. Helpers,
deserialization, and validation all raise this family.
"""

from __future__ import annotations


class OperationDefinitionError(ValueError):
    """Invalid operation-definition structure or reference."""


class BindingError(OperationDefinitionError):
    """Invalid operation/tool/material planning binding."""
