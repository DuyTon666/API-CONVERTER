# post_process/run.py
# Orchestrate đúng thứ tự: readonly_tagger TRƯỚC, ref_replacer SAU.
#
# Lý do thứ tự quan trọng:
# ref_replacer replace field thành $ref object — sau đó field không còn
# là dict thông thường nữa, readonly_tagger không thể đánh readOnly vào $ref.

from pathlib import Path
from .readonly_tagger import tag_readonly_fields
from .ref_replacer import replace_common_refs_from_registry

import generator.emitter as emitter

def run(schemas_dir: str) -> None:
    schemas        = Path(schemas_dir)
    readonly_fields = set(emitter._CONFIG.get("response_readonly_fields", []))
    registry        = emitter._CONFIG.get("schema_registry", {})

    print("  → [1/2] Tagging readOnly fields...")
    n1 = tag_readonly_fields(schemas, readonly_fields)
    print(f"         {n1} file updated")

    print("  → [2/2] Replacing common fields with $ref...")
    n2 = replace_common_refs_from_registry(schemas, registry)
    print(f"         {n2} file updated")