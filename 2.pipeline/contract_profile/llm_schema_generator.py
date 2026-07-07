"""
LLM Schema Generator
--------------------
Sinh JSON Schema cho response data từ docx text.
Gọi LLM với context từ docx, trả về schema YAML file.

Dùng trong apply-contract-hints khi hints_builder detect json_wrapper response
nhưng schema data chưa có trong components.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import anthropic
import yaml

_client = anthropic.Anthropic()

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _call_llm(doc_text: str, operation_id: str, module: str) -> dict | None:
    """Gọi LLM sinh JSON Schema cho response data field."""
    prompt = (
        "You are an OpenAPI schema engineer.\n"
        "Read the API documentation below and extract the JSON schema "
        "for the 'data' field in the JSON success response (200 OK, format=json).\n"
        "Focus on the actual JSON response example in the documentation, "
        "NOT the ZIP bundle contents.\n\n"
        f"API operationId: {operation_id}\n"
        f"Module: {module}\n\n"
        "Documentation:\n"
        "---\n"
        f"{doc_text}\n"
        "---\n\n"
        "Return a JSON object representing the OpenAPI schema for the 'data' field only.\n"
        "Include: type, description, properties (with type, description for each), required array.\n"
        "Return JSON only, no explanation, no markdown.\n"
        "All descriptions must be in Vietnamese.\n"
        "Example: {\"type\": \"object\", \"properties\": {\"id\": {\"type\": \"integer\"}}}"
    )
    try:
        response = _client.messages.create(
            model="cc/claude-sonnet-4-6",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = response.content[0].text.strip()
        # Strip markdown nếu có
        raw = re.sub(r"```json|```", "", raw).strip()
        return json.loads(raw)
    except Exception as e:
        print(f"  [WARN] LLM schema generation failed: {e}")
        return None


def generate_response_schema(
    doc_text: str,
    operation_id: str,
    module: str,
    schema_name: str,
) -> Path | None:
    """
    Sinh schema YAML cho response data, ghi vào components/schemas/<module>/<schema_name>.yaml.
    Trả về Path nếu thành công, None nếu thất bại.
    """
    schema_dir  = PROJECT_ROOT / "5.openapi/components/schemas" / module
    schema_path = schema_dir / f"{schema_name}.yaml"

    # Skip nếu đã có
    if schema_path.exists():
        print(f"  [schema_gen] Đã có: {schema_path.name} — bỏ qua")
        return schema_path

    print(f"  [schema_gen] Đang sinh schema: {schema_name}...")
    schema_data = _call_llm(doc_text, operation_id, module)
    if not schema_data:
        return None

    schema_dir.mkdir(parents=True, exist_ok=True)
    schema_path.write_text(
        yaml.dump(schema_data, allow_unicode=True, sort_keys=False, indent=2),
        encoding="utf-8",
    )
    print(f"  [schema_gen] Đã ghi: {schema_path}")
    return schema_path
