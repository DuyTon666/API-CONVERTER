# operation_map_builder.py
# Build operation_error_map.json từ 2 nguồn đã có sẵn:
#   1. batch_log_by_module.json → operation_id, method, path, source_file
#   2. parsed_error_tables.json (per-module) → code, http_status per source_file
# Toàn bộ data-driven từ file đã có.

import json
import os
from datetime import datetime

import yaml


def _read_operation_meta_from_yaml(yaml_path: str) -> dict:
    """
    Đọc operationId, method từ file YAML đã sinh.
    path URL không có trong YAML path-level → để trống.
    Trả về dict {operation_id, method, path} hoặc {} nếu đọc thất bại.
    """
    try:
        with open(yaml_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            return {}
        http_methods = ["get", "post", "put", "patch", "delete", "head", "options"]
        for method in http_methods:
            if method in data:
                operation_id = data[method].get("operationId", "")
                if operation_id:
                    return {"operation_id": operation_id, "method": method, "path": ""}
        return {}
    except Exception:
        return {}


def _load_json(path: str) -> dict | list:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _load_overrides(module: str, base_dir: str) -> dict:
    """
    Load http_status_overrides.yaml cho module.
    Trả về dict {code: {http_status, reason}} hoặc {} nếu file không tồn tại.
    """
    path = os.path.join(base_dir, "4.config", "errors", "modules", module, "http_status_overrides.yaml")
    if not os.path.exists(path):
        return{}
    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data.get("overrides", {}) if isinstance(data, dict) else {}
    except Exception:
        return {}


def _load_global_map(base_dir: str) -> dict:
    """
    Load error_code_map.yaml (_global).
    Trả về dict {code: {http_status, message}} hoặc {} nếu lỗi.
    """
    path = os.path.join(base_dir, "4.config", "errors", "error_code_map.yaml")
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data.get("error_codes", {}) if isinstance(data, dict) else {}
    except Exception:
        return {}


def _load_reassign_map(module: str, base_dir: str) -> dict:
    """
    Load resolution reassign từ error_codes_review.json.
    Trả về dict {(source_file, old_code): new_code}.
    """
    path = os.path.join(base_dir, "3.build", "reports", "errors", module, "error_codes_review.json")
    if not os.path.exists(path):
        return {}

    try:
        report = _load_json(path)
    except Exception:
        return {}

    reassign_map = {}
    for entry in report.get("entries", []):
        resolution = entry.get("resolution") or {}
        if resolution.get("decision") != "reassign":
            continue

        source_file = entry.get("source_file", "")
        old_code = str(entry.get("code", ""))
        new_code = str(resolution.get("new_code", "")).strip()

        if source_file and old_code and new_code:
            reassign_map[(source_file, old_code)] = new_code

    return reassign_map


def _should_skip(output_path: str, batch_timestamp: str, parsed_tables_path: str) -> bool:
    """
    Skip nếu operation_error_map.json đã tồn tại, mới hơn batch_log timestamp
    VÀ mới hơn parsed_error_tables.json (tránh dùng map cũ khi parse-errors đã chạy lại).
    """
    if not os.path.exists(output_path):
        return False
    try:
        existing = _load_json(output_path)
        generated_at = existing.get("generated_at", "")
        if generated_at < batch_timestamp:
            return False
        # Kiểm tra thêm: nếu parsed_error_tables.json mới hơn map → rebuild
        if os.path.exists(parsed_tables_path):
            map_mtime = os.path.getmtime(output_path)
            tables_mtime = os.path.getmtime(parsed_tables_path)
            if tables_mtime > map_mtime:
                return False
        return True
    except Exception:
        return False    


def build_for_module(module: str, batch_log_path: str, intermediate_dir: str, force: bool = False) -> None:
    """
    Build operation_error_map.json cho 1 module.
    """
    #Load batch log
    batch_log = _load_json(batch_log_path)
    module_log = batch_log.get("modules", {}).get(module)
    if not module_log:
        print(f"Không tìm thấy module nào '{module}' trong batch log.")
        return

    #batch_log có thể có key mixed hoặc key khác
    batch_data = module_log.get("mixed") or next(iter(module_log.values()), None)    
    if not batch_data:
        print(f"Không có data trong batch_log cho module '{module}'.")
        return

    batch_timestamp = batch_data.get("timestamp", "")
    success_files = batch_data.get("success_files", [])
    if not success_files:
        skipped_files = batch_data.get("skipped_files", [])
        skipped_with_output = [
            f for f in skipped_files
            if f.get("output", "").endswith(".yaml") and os.path.exists(f.get("output", ""))
        ]
        if not skipped_with_output:
            print(f"Không có success_files hoặc skipped_files hợp lệ cho module '{module}'.")
            return
        print(f"    [{module}] success_files rỗng — fallback: đọc {len(skipped_with_output)} skipped_files có output YAML")
        # Dựng success_files từ skipped_files bằng cách đọc operationId từ YAML
        derived = []
        for entry in skipped_with_output:
            meta = _read_operation_meta_from_yaml(entry["output"])
            if not meta.get("operation_id"):
                print(f"    WARNING: không đọc được operationId từ {entry['output']} — bỏ qua")
                continue
            derived.append({
                "file":         entry["file"],
                "operation_id": meta["operation_id"],
                "method":       meta["method"],
                "path":         meta["path"],
                "output":       entry["output"],
            })
        if not derived:
            print(f"Không derive được operation nào từ skipped_files cho module '{module}'.")
            return
        success_files = derived

    module_intermediate = os.path.join(intermediate_dir, module)
    output_path = os.path.join(module_intermediate, "operation_error_map.json")
    parsed_tables_path = os.path.join(module_intermediate, "parsed_error_tables.json")

    if not force and _should_skip(output_path, batch_timestamp, parsed_tables_path):
        print(f"    [{module}] skip - operation_error_map đã mới hơn batch_log và parsed_error_tables")
        return

    parsed_tables_path = os.path.join(module_intermediate, "parsed_error_tables.json")
    if not os.path.exists(parsed_tables_path):
        print(f" Chưa có trong parsed_error_tables.json cho module '{module}'.")
        print(f" Chạy trước khi in mã lỗi")
        return

    parsed_tables = _load_json(parsed_tables_path)
    entries = parsed_tables.get("entries", [])

    # Load override và global map cho bước resolve http_status thiếu
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    overrides = _load_overrides(module, base_dir)
    global_map = _load_global_map(base_dir)
    reassign_map = _load_reassign_map(module, base_dir)

    # Ghi pending_review cho mã thiếu http_status và không có override/global
    pending_review = []

    file_to_errors: dict[str, dict[str, list]] = {}
    for entry in entries:
        source_file = entry.get("source_file", "")
        source_files = entry.get("seen_in_files") or [source_file]
        source_files = [f for f in source_files if f]

        code = str(entry.get("code", ""))
        incoming = entry.get("incoming", {})
        http_status = incoming.get("http_status", "") or ""

        if not source_files or not code:
            continue

        # Resolve http_status nếu thiếu
        resolve_source = "document"
        if not http_status:
            if code in overrides:
                http_status = str(overrides[code]["http_status"])
                resolve_source = "override"
            elif code in global_map and global_map[code].get("http_status"):
                http_status = str(global_map[code]["http_status"])
                resolve_source = "global_map"
            else:
                # Không resolve được → ghi pending cho mọi file đã dùng mã này
                for current_source_file in source_files:
                    pending_review.append({
                        "code": code,
                        "message": incoming.get("message", ""),
                        "source_file": current_source_file,
                        "suggested_status": None,
                    })
                continue

        status_key = str(http_status)
        for current_source_file in source_files:
            if current_source_file not in file_to_errors:
                file_to_errors[current_source_file] = {}
            if status_key not in file_to_errors[current_source_file]:
                file_to_errors[current_source_file][status_key] = []

            effective_code = reassign_map.get((current_source_file, code), code)

            existing_codes = [
                e["code"] for e in file_to_errors[current_source_file][status_key]
            ]
            if effective_code not in existing_codes:
                file_to_errors[current_source_file][status_key].append({
                    "code": effective_code,
                    "category": incoming.get("category", ""),
                    "message": incoming.get("message", ""),
                    "http_status_source": resolve_source,
                })

    # Ghi pending_review.yaml nếu có mã chưa resolve được
    pending_path = os.path.join(module_intermediate, "pending_review.yaml")
    if pending_review:
        # Dedup theo code
        seen = {}
        for item in pending_review:
            seen[item["code"]] = item
        pending_deduped = list(seen.values())
        with open(pending_path, "w", encoding="utf-8") as f:
            yaml.dump(
                {"module": module, "pending": pending_deduped},
                f, allow_unicode=True, sort_keys=False
            )
        print(f"WARNING: {len(pending_deduped)} mã thiếu http_status chưa có override/global → xem {pending_path}")
    elif os.path.exists(pending_path):
        os.remove(pending_path)  

    # Build operation map
    operation_map = {}
    for op in success_files:
        source_file = op.get("file", "")
        operation_id = op.get("operation_id", "")
        method = op.get("method", "").lower()
        path = op.get("path", "")
        output_yaml = op.get("output", "")

        if not operation_id or not source_file:
            continue

        errors = file_to_errors.get(source_file, {})

        operation_map[operation_id] = {
            "method": method,
            "path": path,
            "source_file": source_file,
            "output_yaml": output_yaml,
            "errors": errors,
        }

        status_str = ", ".join(f"{k}:{len(v)}mã" for k, v in errors.items())
        print(f"  {operation_id}: {method.upper()} {path} [{status_str or 'không có mã lỗi'}]")
    
    if not operation_map:
        print(f" Không build được operation nào cho module '{module}'.")
        return

    result = {
        "generated_at": datetime.now().isoformat(),
        "module": module,
        "batch_timestamp": batch_timestamp,
        "operations": operation_map,
    }

    os.makedirs(module_intermediate, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"Ghi {len(operation_map)} operation vào: {output_path}")


def build_all_modules(batch_log_path: str, intermediate_dir: str, force: bool = False) -> None:
    """
    Build operation_error_map.json cho tất cả module có trong batch_log.
    """
    batch_log = _load_json(batch_log_path)
    modules = list(batch_log.get("modules", {}).keys())

    if not modules:
        print("Không có module nào trong batch_log.")
        return

    print(f"Tìm thấy {len(modules)} module: {modules}")

    for module in modules:
        print(f"\n[{module}]")
        build_for_module(module, batch_log_path, intermediate_dir, force=force)