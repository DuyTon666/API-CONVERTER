# error_table_parser.py
# Classify từng row error code so với error_code_map.yaml hiện tại.
# Không ghi gì vào map — chỉ detect và xuất report.

import os
import re
import yaml


def load_global_map(yaml_path: str) -> dict:
    """Đọc 4.config/errors/error_code_map.yaml, trả về dict {code: {http_status, message}}."""
    if not os.path.exists(yaml_path):
        return {}
    with open(yaml_path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("error_codes", {})


def load_module_catalog(catalog_path: str) -> dict:
    """Đọc 4.config/errors/modules/<module>/error_catalog.yaml, trả về dict {code: ...}."""
    if not os.path.exists(catalog_path):
        return {}
    with open(catalog_path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("error_codes", {})


def _normalize_message(msg: str) -> str:
    """Lowercase + strip để so sánh message không phân biệt hoa thường."""
    return msg.strip().lower()


def classify_row(row: dict, global_map: dict, module_catalog: dict) -> dict:
    """
    So 1 row với global_map và module_catalog, gán status + matched_namespace:

      Ưu tiên check global trước:
        - code có trong global, message khớp  → duplicate_ok, namespace=_global
        - code có trong global, message khác  → conflict,     namespace=_global
      Nếu không có trong global, check module catalog:
        - code có trong catalog, message khớp → duplicate_ok, namespace=module
        - code có trong catalog, message khác → conflict,     namespace=module
      Không có ở đâu:
        - new — sẽ được ghi vào module catalog

    http_status KHÔNG quyết định status — chỉ tham khảo.
    """
    code = row["code"]
    incoming_http = row.get("http_status")
    incoming_msg = row.get("message", "")
    missing_http = not str(incoming_http or "").strip()

    for namespace, registry in [("module", module_catalog), ("_global", global_map)]:
        if code not in registry:
            continue
        existing = registry[code]
        existing_msg = existing.get("message", "")
        norm_incoming = _normalize_message(incoming_msg)
        norm_existing = _normalize_message(existing_msg)
        same_situation = (
            norm_incoming == norm_existing
            or norm_existing in norm_incoming
            or norm_incoming in norm_existing
        )
        if same_situation:
            return {**row, "status": "duplicate_ok", "matched_namespace": namespace,
                    "existing_in_map": existing, "missing_http_status": missing_http}
        else:
            return {**row, "status": "conflict", "matched_namespace": namespace,
                    "existing_in_map": existing, "missing_http_status": missing_http}

    return {**row, "status": "new", "matched_namespace": None,
            "existing_in_map": None, "missing_http_status": missing_http}


def detect_intra_batch_conflicts(rows: list[dict]) -> list[dict]:
    """
    Phát hiện conflict GIỮA CÁC FILE MỚI trong cùng 1 lần chạy.
    Nếu 2 row khác file cùng code nhưng khác http hoặc message → đánh dấu intra_batch_conflict.
    Trả về list row đã được bổ sung flag nếu cần.
    """
    seen = {}

    result = []
    for row in rows:
        code = row["code"]
        if code not in seen:
            seen[code] = row
            result.append(row)
        else: 
            first = seen[code]
            http_match = str(row.get("http_status", "")) == str(first.get("http_status"))
            msg_match = _normalize_message(row.get("message", "")) == _normalize_message(first.get("message", ""))
            if not http_match or not msg_match:
                # Đánh dấu cả row hiện tại lẫn row đầu tiên
                for r in result:
                    if r["code"] == code:
                        r["intra_batch_conflict"] = True
                row = {**row, "intra_batch_conflict": True}
            result.append(row)

    return result


def dedup_rows(rows: list[dict]) -> list[dict]:
    """
    Gộp các row trùng code + message lại thành 1.
    Ghi thêm seen_in_files để biết mã xuất hiện ở file nào.
    Nếu cùng code nhưng khác message → giữ nguyên tất cả (để detect_intra_batch_conflicts xử lý).
    """
    seen = {}  # key: (code, message) → row đại diện

    for row in rows:
        key = (row["code"], _normalize_message(row.get("message", "")))
        if key not in seen:
            seen[key] = {**row, "seen_in_files": [row["source_file"]]}
        else:
            if row["source_file"] not in seen[key]["seen_in_files"]:
                seen[key]["seen_in_files"].append(row["source_file"])

    return list(seen.values())


def parse_rows(rows: list[dict], global_map: dict, module_catalog: dict) -> list[dict]:
    rows = dedup_rows(rows)
    rows = detect_intra_batch_conflicts(rows)

    entries = []
    for row in rows:
        entry = classify_row(row, global_map, module_catalog)
        entries.append(entry)

    return entries


def suggest_next_code(conflicting_code: str, error_map: dict) -> str | None:
    """
    Gợi ý mã số trống tiếp theo trong cùng dải với conflicting_code.
    Ví dụ: 4301 đang conflict → tìm số tiếp theo trong 43xx chưa dùng.
    Trả về string mã gợi ý, hoặc None nếu không tìm được.
    """
    if not conflicting_code.isdigit():
        return None

    code_int = int(conflicting_code)
    # Xác định dải: lấy 2 chữ số đầu làm prefix (vd 4301 → prefix 43xx)
    prefix = code_int // 100  # 4301 // 100 = 43

    existing_codes = set(int(c) for c in error_map.keys() if c.isdigit())

    # Tìm số tiếp theo trong dải prefix*100 đến prefix*100+99 chưa dùng
    for candidate in range(prefix * 100, prefix * 100 + 100):
        if candidate not in existing_codes and str(candidate) != conflicting_code:
            return str(candidate)

    return None  