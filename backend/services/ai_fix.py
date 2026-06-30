from core.errors import ErrorCode, http_error
from utils.yaml_line import indent_of, extract_key, find_block_end


# Parse XML từ `redocly lint --format checkstyle` thành list dict {ruleId, message, line, column}
# — cần vì Redocly bản JSON thường không có line/column thật, chỉ có JSON Pointer khó dùng.
def _parse_checkstyle_output(xml_text: str) -> list[dict]:
    import xml.etree.ElementTree as ET

    issues = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return issues

    for file_elem in root.findall("file"):
        for error_elem in file_elem.findall("error"):
            issues.append(
                {
                    "ruleId": error_elem.get("source", ""),
                    "message": error_elem.get("message", ""),
                    "line": int(error_elem.get("line", 0)),
                    "column": int(error_elem.get("column", 0)),
                }
            )
    return issues


# Gộp các range lỗi chồng lấn nhau thành 1 patch duy nhất — tránh trường hợp 2 patch
# độc lập đè lên cùng vùng text, áp cả 2 vào sẽ làm hỏng/lệch nội dung file.
def _merge_overlapping_ranges(ranges: list[dict]) -> list[dict]:
    if not ranges:
        return []

    sorted_ranges = sorted(ranges, key=lambda r: r["start_line"])

    merged: list[dict] = []
    for r in sorted_ranges:
        if merged and r["start_line"] <= merged[-1]["end_line"]:
            merged[-1]["end_line"] = max(merged[-1]["end_line"], r["end_line"])
            merged[-1]["issues"].extend(r["issues"])
        else:
            merged.append(
                {
                    "start_line": r["start_line"],
                    "end_line": r["end_line"],
                    "issues": list(r["issues"]),
                }
            )
    return merged


# Ghép toàn bộ patch thành 1 prompt duy nhất gửi cho Claude — chỉ gọi AI 1 lần dù
# có bao nhiêu lỗi, thay vì gọi riêng cho từng lỗi (chậm + tốn).
def _build_batch_prompt(patches: list[dict]) -> str:
    conventions = (
        "- operationId: camelCase, bắt đầu bằng động từ\n"
        "- Không dùng inline schema, mọi schema phải $ref tới components/schemas\n"
        "- Field do server quản lý (id, created_at, updated_at): readOnly: true ở response, "
        "không xuất hiện ở request\n"
        "- Mọi response lỗi phải $ref tới response chuẩn trong components/responses\n"
    )

    blocks = []
    for p in patches:
        issues_text = "\n".join(
            f"  - [{i['source']}] {i.get('code') or i.get('ruleId')}: {i['message']}"
            for i in p["issues"]
        )
        parent_section = (
            f"Object cha (các field/sibling khác cùng entity, tham khảo để viết nhất quán):\n"
            f"```yaml\n{p['parent_text']}\n```\n"
            if p["parent_text"] else ""
        )
        blocks.append(
            f"### LOCATION_ID: {p['id']}\n"
            f"Vị trí: {p['breadcrumb']}\n"
            f"{parent_section}"
            f"Lỗi tại vị trí này:\n{issues_text}\n"
            f"Đoạn YAML gốc (giữ NGUYÊN số khoảng trắng đầu dòng/indentation hiện có):\n"
            f"```yaml\n{p['original_text']}\n```\n"
        )


    return (
        "Bạn là kỹ sư OpenAPI. Dưới đây là NHIỀU đoạn YAML trích từ một file OpenAPI 3.1 lớn hơn, "
        "mỗi đoạn có lỗi lint riêng. Hãy sửa CHỈ đoạn đó để hết lỗi, KHÔNG thêm/xoá dòng nằm ngoài "
        "đoạn, giữ nguyên thụt lề (indentation) tương đối của đoạn gốc — đoạn sửa sẽ được ghép thẳng "
        "vào đúng vị trí cũ trong file lớn nên PHẢI là YAML hợp lệ khi đặt lại đúng vị trí đó. "
        "Khi sửa summary/description, hãy tham khảo breadcrumb (vị trí) và object cha (các field "
        "khác cùng entity) để mô tả đúng ngữ cảnh và giữ nhất quán văn phong. "
        "Tuân theo quy ước project:\n" + conventions + "\n"
        "KHÔNG sửa nội dung không liên quan tới lỗi đã nêu của từng đoạn. "
        "Trả lời CHỈ bằng JSON theo cấu trúc sau, không thêm chữ nào khác, không bọc trong dấu ```:\n"
        '{"patches": [{"id": "<LOCATION_ID>", "fixed_text": "<đoạn YAML đã sửa, dùng \\n cho xuống dòng>"}]}\n\n'
        + "\n".join(blocks)
    )


# Bóc JSON ra khỏi chữ Claude trả về — có fallback bằng regex nếu Claude lỡ thêm
# chữ thừa trước/sau JSON (đôi khi AI không tuân thủ đúng 100% "chỉ trả JSON").
def _parse_ai_json(raw: str) -> dict:
    import json
    import re

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
    return {}


# Hàm tổng: nhận content (toàn bộ bundle YAML) + lỗi Spectral/Redocly, trả về
# {patches, unresolved, failed} — patch là vị trí AI đã sửa xong và validate hợp lệ,
# unresolved là lỗi không xác định được vị trí, failed là lỗi AI sửa nhưng không hợp lệ.
def run(content: str, spectral: list[dict], redocly: list[dict]) -> dict:
    import anthropic
    import yaml as _yaml

    lines = content.split("\n")

    resolved = []
    unresolved = []

    # Spectral đã có range chính xác sẵn -> dùng trực tiếp, không cần tính toán gì thêm
    for issue in spectral:
        rng = issue.get("range")
        if not rng:
            unresolved.append(
                {
                    "source": "spectral",
                    "code": issue.get("code", ""),
                    "message": issue.get("message", ""),
                    "reason": "Không có range, không xác định được vị trí sửa",
                }
            )
            continue
        resolved.append(
            {
                "start_line": rng["start"]["line"],
                "end_line": rng["end"]["line"],
                "issues": [
                    {
                        "source": "spectral",
                        "code": issue.get("code", ""),
                        "message": issue.get("message", ""),
                    }
                ],
            }
        )

    # Redocly cần line/column do bước enrich (checkstyle) gắn vào trước khi tới đây
    for issue in redocly:
        line = issue.get("line")
        if line is None:
            unresolved.append(
                {
                    "source": "redocly",
                    "code": issue.get("ruleId", ""),
                    "message": issue.get("message", ""),
                    "reason": "Không xác định được vị trí (thiếu line/column) — cần sửa tay",
                }
            )
            continue
        resolved.append(
            {
                "start_line": line,
                "end_line": find_block_end(lines, line),
                "issues": [
                    {
                        "source": "redocly",
                        "code": issue.get("ruleId", ""),
                        "message": issue.get("message", ""),
                    }
                ],
            }
        )

    if not resolved:
        return {"patches": [], "unresolved": unresolved, "failed": []}

    merged = _merge_overlapping_ranges(resolved)

    # Gắn id + cắt sẵn original_text cho từng patch, để gửi cho AI và để so sánh sau
    draft_patches = [
        {
            "id": f"loc-{i}",
            "start_line": m["start_line"],
            "end_line": m["end_line"],
            "issues": m["issues"],
            "original_text": "\n".join(lines[m["start_line"] : m["end_line"] + 1]),
            "breadcrumb": _get_breadcrumb(lines, m["start_line"]),
            "parent_text": _get_parent_block(lines, m["start_line"]),
        }
        for i, m in enumerate(merged)
    ]

    prompt = _build_batch_prompt(draft_patches)

    try:
        client = anthropic.Anthropic()
        response = client.messages.create(
            model="cc/claude-sonnet-4-6",
            max_tokens=8192,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()
    except Exception as e:
        raise http_error(502, ErrorCode.AI_CALL_FAILED, f"Lỗi gọi AI: {e}")

    suggestion = _parse_ai_json(raw)
    fixed_by_id = {
        item["id"]: item["fixed_text"]
        for item in (suggestion.get("patches") or [])
        if isinstance(item, dict)
        and item.get("id")
        and isinstance(item.get("fixed_text"), str)
    }

    # Validate từng fixed_text bằng cách ghép thử vào bản full-document gốc rồi parse YAML
    # — chỉ trong bộ nhớ, không ghi file. Patch nào không hợp lệ thì loại, không fail cả request.
    patches = []
    failed = []
    for p in draft_patches:
        fixed_text = fixed_by_id.get(p["id"])
        valid = False
        if fixed_text is not None:
            candidate_lines = (
                lines[: p["start_line"]]
                + fixed_text.split("\n")
                + lines[p["end_line"] + 1 :]
            )
            try:
                parsed = _yaml.safe_load("\n".join(candidate_lines))
                valid = isinstance(parsed, dict)
            except Exception:
                valid = False

        if valid:
            patches.append(
                {
                    "id": p["id"],
                    "start_line": p["start_line"],
                    "end_line": p["end_line"],
                    "original_text": p["original_text"],
                    "fixed_text": fixed_text,
                    "issues": p["issues"],
                }
            )
        else:
            reason = "AI không trả về kết quả hợp lệ cho vị trí này"
            for issue in p["issues"]:
                failed.append({**issue, "reason": reason})

    return {"patches": patches, "unresolved": unresolved, "failed": failed}


# Validate content/lỗi đầu vào rồi gọi run() — logic rút từ route POST /docs/bundle/ai-fix
# (router chỉ còn parse Body + gọi hàm này).
def fix_bundle(payload: dict) -> dict:
    content = payload.get("content") or ""
    spectral = payload.get("spectral") or []
    redocly = payload.get("redocly") or []

    if not content.strip():
        raise http_error(400, ErrorCode.EMPTY_BUNDLE, "Bundle rỗng, không có gì để sửa")
    if not spectral and not redocly:
        return {"patches": [], "unresolved": [], "failed": []}

    return run(content, spectral, redocly)


def _get_breadcrumb(lines: list[str], target_line: int) -> str:
    target_indent = indent_of(lines[target_line]) or 0
    breadcrumb = [extract_key(lines[target_line])]
    current_indent = target_indent

    for i in range(target_line - 1, -1, -1):
        indent = indent_of(lines[i])
        if indent is None:
            continue
        if indent < current_indent:
            breadcrumb.insert(0, extract_key(lines[i]))
            current_indent = indent
        if current_indent == 0:
            break

    return ".".join(breadcrumb)


# Đi ngược lên 2 cấp dedent: cấp 1 là field trực tiếp chứa target_line (vd "status"),
# cấp 2 là entity chứa field đó cùng các sibling khác (vd "properties" chứa cả
# "status" và "priority") — lấy cấp 2 để AI thấy field cạnh bên mà viết mô tả nhất
# quán, thay vì chỉ thấy mỗi field đang sửa.
def _get_parent_block(lines: list[str], target_line: int) -> str:
    target_indent = indent_of(lines[target_line]) or 0

    # Cấp 1: dòng dedent đầu tiên tính từ target_line
    level1_indent = None
    level1_line = target_line
    for i in range(target_line - 1, -1, -1):
        indent = indent_of(lines[i])
        if indent is None:
            continue
        if indent < target_indent:
            level1_indent = indent
            level1_line = i
            break

    if level1_indent is None:
        return ""

    # Cấp 2: tiếp tục dedent thêm 1 lần nữa, tính từ chỗ cấp 1 vừa dừng
    parent_start_line = None
    for i in range(level1_line - 1, -1, -1):
        indent = indent_of(lines[i])
        if indent is None:
            continue
        if indent < level1_indent:
            parent_start_line = i
            break

    if parent_start_line is None:
        return ""

    parent_end_line = find_block_end(lines, parent_start_line)

    return "\n".join(lines[parent_start_line : parent_end_line + 1])
