# 2.pipeline/enrichers/side_effects/schema_validator.py
"""
Validate dict x-side-effects theo JSON Schema trước khi inject vào YAML.

Dùng jsonschema. Nếu package chưa cài:
    pip install jsonschema --break-system-packages
"""

import json
from pathlib import Path
from functools import lru_cache

import jsonschema

_SCHEMA_PATH = (
    Path(__file__).resolve().parents[3] / "4.config" / "schemas" / "x_side_effects.schema.json"
)


@lru_cache(maxsize=1)
def _load_schema() -> dict:
    if not _SCHEMA_PATH.exists():
        raise FileNotFoundError(f"Không tìm thấy schema: {_SCHEMA_PATH}")
    with open(_SCHEMA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def validate(x_side_effects: dict) -> tuple[bool, str | None]:
    """
    Validate dict x-side-effects theo schema.

    Returns:
        (is_valid, error_message)
        error_message là None nếu valid.
    """
    schema = _load_schema()
    try:
        jsonschema.validate(instance=x_side_effects, schema=schema)
        return True, None
    except jsonschema.ValidationError as e:
        # e.message + path đến field lỗi -- giúp debug nhanh
        path = " -> ".join(str(p) for p in e.absolute_path)
        return False, f"{path}: {e.message}" if path else e.message