import json
import re
import anthropic
from converters.models import ParsedOperation

_client = anthropic.Anthropic()

def enrich(op: ParsedOperation, title: str = "") -> ParsedOperation:
    metadata = _call_llm(title=title, method=op.method, path=op.path)

    op.summary = metadata.get("summary", "") or title
    op.description = metadata.get("description", "")

    operation_id = str(metadata.get("operationId") or "").strip()
    if not operation_id:
        op.review_flags.append("llm_operation_id_missing")
        raise RuntimeError(
            f"LLM không trả operationId; từ chối fallback để tránh drift spec: "
            f"{op.method} {op.path}"
        )

    op.operation_id = operation_id
    return op

def _fallback_operation_id(method: str, path: str) -> str:
    segments = [s for s in path.split('/') if s and s != 'v1']
    last = segments[-1] if segments else ""
    m = (method or '').upper()
    if last.startswith('{'):
        # path ends with {id} → operating on existing item
        resource = segments[-2] if len(segments) >= 2 else "resource"
        resource = resource.rstrip('s')
        verb = {'GET': 'get', 'PUT': 'update', 'PATCH': 'update',
                'DELETE': 'delete', 'POST': 'update'}.get(m, 'do')
    else:
        resource = last
        verb = {'GET': 'list', 'POST': 'create', 'PUT': 'update',
                'PATCH': 'update', 'DELETE': 'delete'}.get(m, 'do')
    parts = re.split(r'[-_]', resource)
    resource_camel = parts[0] + ''.join(p.capitalize() for p in parts[1:])
    return verb + resource_camel[0].upper() + resource_camel[1:] if resource_camel else verb

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
            model="claude-sonnet-4-6",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = response.content[0].text.strip()
        return _parse_json(raw, fallback_title=title)
    except Exception as e:
        print(f"  [WARN] LLM call failed: {e}")
        raise RuntimeError(
            f"LLM metadata generation failed for {method} {path}"
        ) from e

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