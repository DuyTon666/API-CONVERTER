import json
import re
import anthropic
from converters.models import ParsedOperation

_client = anthropic.Anthropic()

def enrich(op: ParsedOperation, title: str = "") -> ParsedOperation:
    metadata = _call_llm(title=title, method=op.method, path=op.path)
    op.summary = metadata.get("summary", "")
    op.operation_id = metadata.get("operationId", "")
    op.description = metadata.get("description", "")
    return op

def _call_llm(title: str, method: str, path: str) -> dict:
    prompt = (
        "You are an OpenAPI documentation engineer.\n"
        f"Function name: {title}\n"
        f"HTTP Method: {method}\n"
        f"Path: {path}\n"
        "Return JSON with 3 fields:\n"
        "- summary: short Vietnamese description under 10 words\n"
        "- operationId: camelCase starting with English verb\n"
        "- description: 1-2 sentences Vietnamese, include business context and constraints\n"
        "Return JSON only, no explanation.\n"
        "Example: {\"summary\": \"Dong ticket\", \"operationId\": \"closeTicket\"}"
        "Do not include any text before or after the JSON object"    
    )

    try:
        response = _client.messages.create(
            model="cc/claude-sonnet-4-6",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = response.content[0].text.strip()
        return _parse_json(raw, fallback_title=title)
    except Exception as e:
        print(f"  [WARN] LLM call failed: {e}")
        return {"summary": title, "operationId": "", "description": ""}

def _parse_json(raw: str, fallback_title: str) -> dict:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
    return {"summary": fallback_title, "operationId": "", "description": ""}