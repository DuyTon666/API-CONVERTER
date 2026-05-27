import anthropic
import json

client = anthropic.Anthropic()

def fill_metadata(title: str, method: str, path: str) -> dict:
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

    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=200,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    raw = response.content[0].text.strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        import re
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        return {"summary": title, "operationId": ""}