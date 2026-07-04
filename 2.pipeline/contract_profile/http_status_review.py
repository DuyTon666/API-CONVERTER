# http_status_review.py
# Trách nhiệm: xử lý pending HTTP status review cho từng module.
# Không đụng parser, không đụng error catalog.
#
# Flow:
#   1. build-operation-map → ghi pending_review.yaml (code chưa có http_status)
#   2. resolve-http-status  → reviewer điền status + reason → ghi vào pending_review.yaml
#   3. apply-http-status-review → validate → ghi vào http_status_overrides.yaml

import os
from datetime import datetime

import yaml

#PATHS


def _pending_path(base_dir: str, module: str) -> str:
    return os.path.join(base_dir, "3.build", "intermediate", "errors", module, "pending_review.yaml")


def _overrides_path(base_dir: str, module: str) -> str:
    return os.path.join(base_dir, "4.config", "errors", "modules", module, "http_status_overrides.yaml")


def _base_dir() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


#HELPER


def _load_yaml(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _save_yaml(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, sort_keys=False)


def _valid_http_status(status: int) -> bool:
    return 400 <= status <= 599


#CMD REOSOLVE HTTP STATUS


def cmd_resolve_http_status(module: str, code: str, http_status: int, approved_by: str, reason: str) -> None:
    base = _base_dir()
    pending_file = _pending_path(base, module)

    #Validate http_status
    if not _valid_http_status(http_status):
        print(f"[ERROR] http_status={http_status} không hợp lệ. Phải trong khoảng 400-599.")
        return

    #Load pending
    data = _load_yaml(pending_file)
    if not data or  "pending" not in data:
        print(f"[ERROR] Không tìm thấy pending_review.yaml cho module '{module}' tại: {pending_file}")
        return

    pending_list = data["pending"]
    code_str = str(code)

   #Tìm entry
    found = False
    for entry in pending_list:
        if str(entry.get("code")) == code_str:
            if entry.get("suggested_status") is not None:
                print(f"[WARN] Mã {code_str} đã được resolve trước đó (suggested_status={entry['suggested_status']}).")
                print(f"    approved_by: {entry.get('approved_by')}")
                print(f"    reason: {entry.get('reason')}")
                print("     Dùng --force nếu muốn ghi đè.")
                return
            entry["suggested_status"] = http_status
            entry["approved_by"] = approved_by
            entry["reason"] = reason
            entry["suggestion_source"] = "human"
            entry["confidence"] = "confirmed"
            entry["resolved_at"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
            found = True
            break

    if not found:
        print(f"[ERROR] Không tìm thấy mã '{code_str}' trong pending_review.yaml của module '{module}'.")
        pending_codes = [str(e.get("code")) for e in pending_list]
        print(f"    Các mã đang pending: {pending_codes}")
        return

    _save_yaml(pending_file, data)
    print(f"[OK] Resolved mã {code_str} -> http_status={http_status}")
    print(f"    reason: {reason}")
    print(f"    approved_by: {approved_by}")
    print(f"    Ghi vào: {pending_file}")


# CMD APPLY HTTP STATUS REVIEW


def cmd_apply_http_status_review(module: str) -> None:
    base = _base_dir()
    pending_file = _pending_path(base, module)
    overrides_file = _overrides_path(base, module)

    #Load pending
    data = _load_yaml(pending_file)
    if not data or "pending" not in data:
        print(f"[INFO] Không có pending_review.yaml cho module '{module}'. Không cần apply.")
        return
    
    pending_list = data["pending"]

    #kiểm tra còn mã chưa resolve không
    unresolved = [e for e in pending_list if e .get("suggested_status") is None]
    if unresolved:
        print(f"[ERROR] Còn {len(unresolved)} mã chưa được resolve. Phải resolve hết trước khi apply:")
        for e in unresolved:
            print(f"    - {e.get('code')}: {e.get('message')}")
        print()
        print("Dùng lệnh resolved-http-status để điền từng mã.")
        return

    #Load overrides hiện tại
    overrides_data = _load_yaml(overrides_file)
    if not overrides_data:
        overrides_data = {
            "# http_status_overrides.yaml": None,
            "overrides": {}
        }

    if "overrides" not in overrides_data:
        overrides_data["overrides"] = {}

    existing_overrides = overrides_data["overrides"]

    #Merge
    skipped = []
    applied = []
    for entry in pending_list:
        code_str = str(entry["code"])
        if code_str in existing_overrides:
            skipped.append((code_str, existing_overrides[code_str].get("http_status")))
            continue
        existing_overrides[code_str] = {
            "http_status": entry["suggested_status"],
            "reason": entry.get("reason", ""),
        }
        applied.append(code_str)

    overrides_data["overrides"] = existing_overrides
    _save_yaml(overrides_file, overrides_data)

    remaining = [e for e in pending_list if str (e["code"]) in [s[0] for s in skipped]]
    data["pending"] = remaining
    _save_yaml(pending_file, data)

    #Summary
    print(f"[OK] apply-ttp-status-review module '{module}'")
    print(f"    Applied : {len(applied)} mã -> {overrides_file}")
    if applied:
        for c in applied:
            print(f"    + {c}: {existing_overrides[c]['http_status']}")
    if skipped:
        print(f"    Skipped: {len(skipped)} mã (đã có trong overrides, giữ nguyên)")
        for c, s in skipped:
            print(f"    ~ {c}: {s} (existing)")
    if remaining:
        print(f"  Pending còn lại: {len(remaining)} mã (đã skipped, chưa apply)")
    else:
        print("  pending_review.yaml đã sạch.")