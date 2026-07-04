# 2.pipeline/converters/request_body/schema_models.py

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SchemaNode:
    type: str = "object"
    properties: dict[str, SchemaNode] = field(default_factory=dict)
    required: list[str] = field(default_factory=list)
    items: SchemaNode | None = None
    nullable: bool = False
    description: str | None = None
    format: str | None = None
    enum: list[Any] = field(default_factory=list)
    has_default: bool = False
    default: Any = None
    has_example: bool = False
    example: Any = None
    constraints: dict[str, Any] = field(default_factory=dict)


@dataclass
class SchemaParseResult:
    root: SchemaNode | None = None
    warnings: list[str] = field(default_factory=list)
    review_required: bool = False