"""Structural errors for manufacturing operation definitions (CS-012).

Broken IDs, dangling intent references, unknown vocabulary, invalid
dimensional values, and malformed operation-plan documents are
programming/document errors — not advisory import findings and not
machining judgements. One exception type is the authority; helpers,
deserialization, and validation all raise it.
"""

from __future__ import annotations


class OperationDefinitionError(ValueError):
    """Invalid operation-definition structure or reference."""
