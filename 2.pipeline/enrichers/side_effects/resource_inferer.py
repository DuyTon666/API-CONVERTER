# 2.pipeline/enrichers/side_effects/resource_inferer.py
"""
Suy luận {resource} từ entry trong human_review_queue.json.

Thứ tự ưu tiên (cao -> thấp):
  1. http_path thật (detail.path)
  2. filename
  3. operationId (nếu có YAML data được truyền vào)
  4. module name (fallback)
  5. None (không suy luận được)

Mỗi kết quả trả về kèm evidence để trace ngược.
Không hard-code danh sách resource trong Python -- dùng resource_vocabulary
từ side_effects_rules.yaml.
"""

import re
from .config_loader import get_resource_vocabulary


def _build_lookup() -> dict:
    """
    Build dict ngược: {alias: canonical_singular}
    vd: {"tickets": "ticket", "ticket": "ticket", "services": "service", ...}
    """
    vocab = get_resource_vocabulary()
    lookup = {}
    for canonical, aliases in vocab.items():
        for alias in aliases:
            lookup[alias.lower()] = canonical
    return lookup


def _match_token(token: str, lookup: dict) -> str | None:
    """Khớp 1 token (đã lowercase) với resource_vocabulary."""
    return lookup.get(token.lower())


def _from_path(http_path: str, lookup: dict) -> str | None:
    """
    Tách path thành segments, bỏ qua placeholder {} và version (/v1),
    tìm segment khớp resource_vocabulary -- ưu tiên segment GẦN CUỐI nhất
    (gần action verb hơn = liên quan trực tiếp hơn).

    vd: "/v1/users/{}/tickets/{}/change-assignee"
        segments: ["v1", "users", "{}", "tickets", "{}", "change-assignee"]
        -> "tickets" khớp -> "ticket"
    """
    if not http_path:
        return None

    segments = [s for s in http_path.strip("/").split("/") if s and s != "{}"]

    # Quét từ cuối về đầu -- segment gần action nhất ưu tiên hơn
    for seg in reversed(segments):
        # Bỏ qua segment có dạng action (chứa "-") vì đó là action, không phải resource
        if "-" in seg:
            continue
        match = _match_token(seg, lookup)
        if match:
            return match

    return None


def _from_filename(filename: str, lookup: dict) -> str | None:
    """
    Tách filename theo "_", tìm token khớp resource_vocabulary.
    Ưu tiên token xuất hiện sau cùng (gần cuối tên file thường là resource chính).

    vd: "change_ticket_assignee.yaml"
        tokens: ["change", "ticket", "assignee"]
        -> "ticket" khớp -> "ticket"
    """
    if not filename:
        return None

    stem = filename.rsplit(".", 1)[0]  # bỏ .yaml
    tokens = stem.split("_")

    for token in reversed(tokens):
        match = _match_token(token, lookup)
        if match:
            return match

    return None


def _from_operation_id(operation_id: str, lookup: dict) -> str | None:
    """
    Tách operationId theo camelCase, tìm token khớp resource_vocabulary.

    vd: "changeTicketAssignee"
        tokens: ["change", "Ticket", "Assignee"]
        -> "ticket" khớp -> "ticket"
    """
    if not operation_id:
        return None

    # Tách camelCase: "changeTicketAssignee" -> ["change", "Ticket", "Assignee"]
    tokens = re.findall(r"[A-Z]?[a-z0-9]+", operation_id)

    for token in reversed(tokens):
        match = _match_token(token, lookup)
        if match:
            return match

    return None


def _from_module(module: str, lookup: dict) -> str | None:
    """Fallback cuối: dùng module name, normalize qua vocabulary nếu có."""
    if not module:
        return None
    return _match_token(module, lookup) or module.lower()


def infer_resource(entry: dict, operation_id: str | None = None) -> tuple[str | None, dict]:
    """
    Suy luận resource cho 1 entry trong human_review_queue.json.

    Args:
        entry: dict entry từ queue (có 'detail', 'file', 'module')
        operation_id: optional, lấy từ YAML đã load (nếu enricher đã đọc file)

    Returns:
        (resource, evidence)
        resource: str (dạng số ít) hoặc None nếu không suy luận được
        evidence: dict {"resource_source": "path"|"filename"|"operation_id"|"module"|None}
    """
    lookup = _build_lookup()

    http_path = entry.get("detail", {}).get("path", "")
    filename = entry.get("file", "")
    module = entry.get("module", "")

    # 1. http_path
    resource = _from_path(http_path, lookup)
    if resource:
        return resource, {"resource_source": "path", "matched_from": http_path}

    # 2. filename
    resource = _from_filename(filename, lookup)
    if resource:
        return resource, {"resource_source": "filename", "matched_from": filename}

    # 3. operationId
    if operation_id:
        resource = _from_operation_id(operation_id, lookup)
        if resource:
            return resource, {"resource_source": "operation_id", "matched_from": operation_id}

    # 4. module fallback
    resource = _from_module(module, lookup)
    if resource:
        return resource, {"resource_source": "module", "matched_from": module}

    # 5. không suy luận được
    return None, {"resource_source": None, "matched_from": None}