# apply_review_decisions.py
# Đọc report đã admin điền resolution, validate, ghi vào đúng namespace.
# Chỉ ghi những entry có resolution hợp lệ — không tự quyết gì.

import json
import os
import re
import unicodedata
from datetime import datetime

import yaml


def load_report(report_path: str) -> dict:
    with open(report_path, encoding="utf-8") as f:
        return json.load(f)


def load_yaml_codes(yaml_path: str) -> dict:
    """Đọc file YAML, trả về dict error_codes. Trả về {} nếu file chưa tồn tại."""
    if not os.path.exists(yaml_path):
        return {}
    with open(yaml_path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("error_codes", {})


def save_yaml_codes(yaml_path: str, namespace: str, error_codes: dict) -> None:
    """Ghi dict error_codes ra file YAML với namespace."""
    os.makedirs(os.path.dirname(yaml_path), exist_ok=True)
    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(
            {"namespace": namespace, "error_codes": error_codes},
            f,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=True,
        )


def update_observed_ranges(ranges_path: str, namespace: str, error_codes: dict) -> None:
    """
    Đọc error_code_ranges.yaml, cập nhật observed_ranges cho namespace,
    ghi lại. Tạo file mới nếu chưa tồn tại.
    """
    if os.path.exists(ranges_path):
        with open(ranges_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    else:
        data = {}

    if "namespaces" not in data:
        data["namespaces"] = {}
    if namespace not in data["namespaces"]:
        data["namespaces"][namespace] = {}

    # Tính observed_ranges từ toàn bộ mã hiện có trong catalog
    codes = sorted(int(c) for c in error_codes.keys() if str(c).isdigit())
    ranges = []
    if codes:
        start = codes[0]
        end = codes[0]
        for c in codes[1:]:
            if c == end + 1:
                end = c
            else:
                ranges.append([start, end])
                start = c
                end = c
        ranges.append([start, end])

    data["namespaces"][namespace]["observed_ranges"] = ranges

    os.makedirs(os.path.dirname(ranges_path), exist_ok=True)
    with open(ranges_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=True)


def _remove_accents(text: str) -> str:
    text = (text or "").replace("đ", "d").replace("Đ", "D")
    text = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in text if unicodedata.category(ch) != "Mn")


def _normalize_decision_text(value) -> str:
    text = _remove_accents(str(value or "")).lower()
    text = re.sub(r"[\W_]+", " ", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _entry_decision_key(entry: dict) -> dict:
    incoming = entry.get("incoming") or {}

    return {
        "code": str(entry.get("code") or "").strip(),
        "source_file": str(entry.get("source_file") or "").strip(),
        "incoming_message_key": _normalize_decision_text(incoming.get("message")),
    }


def _decision_key_id(key: dict) -> str:
    return "|".join([
        str(key.get("code") or "").strip(),
        str(key.get("source_file") or "").strip(),
        str(key.get("incoming_message_key") or "").strip(),
    ])


def load_review_decisions(decisions_path: str) -> dict:
    if not decisions_path or not os.path.exists(decisions_path):
        return {}

    with open(decisions_path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    index = {}

    for item in data.get("decisions") or []:
        if not isinstance(item, dict):
            continue

        resolution = item.get("resolution")
        if not isinstance(resolution, dict):
            continue

        key_id = _decision_key_id(item)
        if key_id.strip("|"):
            index[key_id] = resolution

    return index


def apply_persistent_resolutions(report: dict, decisions_path: str) -> int:
    decisions = load_review_decisions(decisions_path)
    if not decisions:
        return 0

    count = 0

    for entry in report.get("entries", []):
        if entry.get("resolution"):
            continue

        key = _entry_decision_key(entry)
        resolution = decisions.get(_decision_key_id(key))

        if resolution:
            entry["resolution"] = resolution
            entry["resolution_source"] = "persistent"
            count += 1

    return count


def save_review_decisions(decisions_path: str, module: str, applied_records: list[dict]) -> int:
    if not decisions_path or not applied_records:
        return 0

    if os.path.exists(decisions_path):
        with open(decisions_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    else:
        data = {}

    data["namespace"] = module

    decisions = data.get("decisions") or []
    if not isinstance(decisions, list):
        decisions = []

    index = {
        _decision_key_id(item): idx
        for idx, item in enumerate(decisions)
        if isinstance(item, dict)
    }

    changed = 0

    for record in applied_records:
        entry = record.get("entry") or {}
        resolution = entry.get("resolution") or {}

        if not resolution:
            continue

        incoming = entry.get("incoming") or {}
        existing = entry.get("existing_in_map") or {}
        key = _entry_decision_key(entry)

        if not key["code"] or not key["incoming_message_key"]:
            continue

        item = {
            **key,
            "matched_namespace": entry.get("matched_namespace"),
            "status": entry.get("status"),
            "incoming_message": incoming.get("message") or "",
            "existing_message": existing.get("message") or "",
            "decision": resolution.get("decision"),
            "resolution": resolution,
            "action": record.get("action"),
            "applied_at": datetime.now().isoformat(),
        }

        key_id = _decision_key_id(key)

        if key_id in index:
            decisions[index[key_id]] = item
        else:
            decisions.append(item)

        changed += 1

    data["decisions"] = decisions

    os.makedirs(os.path.dirname(decisions_path), exist_ok=True)

    with open(decisions_path, "w", encoding="utf-8") as f:
        yaml.dump(
            data,
            f,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
        )

    return changed


def validate_resolution(entry: dict, combined_map: dict) -> tuple[bool, str]:
    """
    Kiểm tra resolution hợp lệ trước khi ghi.
    Trả về (True, "") nếu OK, hoặc (False, lý do) nếu không hợp lệ.
    """
    resolution = entry.get("resolution")
    if not resolution:
        return False, "Chưa có resolution"

    decision = resolution.get("decision")
    valid_decisions = {"reassign", "keep_existing", "approve_new", "repair_existing"}
    if decision not in valid_decisions:
        return False, f"decision không hợp lệ: '{decision}'"

    if not resolution.get("approved_by"):
        return False, "thiếu approved_by"

    if not resolution.get("approved_at"):
        return False, "thiếu approved_at"

    if decision == "reassign":
        new_code = str(resolution.get("new_code", "")).strip()
        if not new_code:
            return False, "decision=reassign nhưng thiếu new_code"
        if not new_code.isdigit():
            return False, f"new_code phải là số: '{new_code}'"
        if new_code in combined_map:
            return False, f"new_code '{new_code}' đã tồn tại trong map"

    return True, ""


def apply_decisions(report_path: str, global_map_path: str, module: str, catalog_path: str, decisions_path: str = None) -> None:
    """
    Entrypoint chính.
    Đọc report → validate từng entry có resolution → ghi vào đúng namespace.
      matched_namespace == '_global' → ghi vào global_map_path
      matched_namespace == 'module' hoặc None (new) → ghi vào catalog_path
    """
    report =  load_report(report_path)
    global_map = load_yaml_codes(global_map_path)    
    module_catalog = load_yaml_codes(catalog_path)
    combined_map = {**global_map, **module_catalog}

    entries = report.get("entries", [])

    applied = []
    skipped = []
    rejected = []
    persisted = []

    global_changed = False
    module_changed = False

    for entry in entries:
        resolution = entry.get("resolution")

        if not resolution:
            skipped.append({"code": entry["code"], "reason": "Chưa có resolution"})
            continue

        ok, reason = validate_resolution(entry, combined_map)
        if not ok:
            rejected.append({"code": entry["code"], "reason": reason})
            continue

        code = str(entry["code"])
        decision = resolution.get("decision")
        namespace = entry.get("matched_namespace")
        incoming = entry.get("incoming", {})

        if decision == "keep_existing":
            applied.append({"code": code, "action": "keep_existing"})
            persisted.append({"entry": entry, "action": "keep_existing"})
        
        elif decision == "repair_existing":
            target_map = global_map if namespace == "_global" else module_catalog

            if code not in target_map:
                rejected.append({"code": code, "reason": "repair_existing nhưng code chưa tồn tại trong namespace"})
                continue

            record = target_map.get(code) or {}
            if not isinstance(record, dict):
                record = {}

            incoming_message = str(incoming.get("message") or "").strip()
            if not incoming_message:
                rejected.append({"code": code, "reason": "repair_existing nhưng incoming.message rỗng"})
                continue

            current_http = str(record.get("http_status") or "").strip()
            incoming_http = str(incoming.get("http_status") or "").strip()

            record["http_status"] = current_http or incoming_http
            record["message"] = incoming_message
            target_map[code] = record

            if namespace == "_global":
                global_changed = True
            else:
                module_changed = True

            applied.append({"code": code, "action": "repair_existing", "namespace": namespace or "module"})
            persisted.append({"entry": entry, "action": "repair_existing"})

        elif decision == "approve_new":
            record = {
                "http_status": str(incoming.get("http_status") or ""),
                "message": incoming.get("message", ""),
            }
            if namespace == "_global":
                global_map[code] = record
                global_changed = True
            else:
                module_catalog[code] = record
                module_changed = True
            applied.append({"code": code, "action": "approve_new", "namespace": namespace or "module"})
            persisted.append({"entry": entry, "action": "approve_new"})

        elif decision == "reassign":
            new_code = str(resolution["new_code"]).strip()
            record = {
                "http_status": str(incoming.get("http_status") or ""),
                "message": incoming.get("message", ""),
            }
            
            # Reassign luôn tạo mã mới ở module hiện tại.
            # Nếu module dùng nhầm mã global cho nghĩa riêng, không được ghi mã mới vào global map.
            module_catalog[new_code] = record
            module_changed = True

            applied.append({"code": code, "action": f"reassign -> {new_code}", "namespace": "module"})
            persisted.append({"entry": entry, "action": f"reassign -> {new_code}"})

    ranges_path = os.path.join(os.path.dirname(global_map_path), "error_code_ranges.yaml")

    if global_changed:
        save_yaml_codes(global_map_path, "_global", global_map)
        update_observed_ranges(ranges_path, "_global", global_map)
        print(f" Đã ghi global map: {global_map_path}")

    if module_changed:
        save_yaml_codes(catalog_path, module, module_catalog)
        update_observed_ranges(ranges_path, module, module_catalog)
        print(f" Đã ghi module catalog: {catalog_path}")

    if decisions_path:
        n_decisions = save_review_decisions(decisions_path, module, persisted)
        if n_decisions:
            print(f" Đã ghi review decisions: {decisions_path} ({n_decisions} entry)")

    print(f"\n--- KẾT QUẢ APPLY ---")
    print(f"Applied : {len(applied)}")
    for a in applied:
        print(f"    [{a['action']}] code {a['code']}")

    print(f"Skipped : {len(skipped)}")
    for s in skipped:
        print(f"    [skip] code {s['code']} - {s['reason']}")

    print(f"Rejected: {len(rejected)}")
    for r in rejected:
        print(f"    [reject] code {r['code']} - {r['reason']}")