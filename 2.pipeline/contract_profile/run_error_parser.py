# run_error_parser.py
# Được gọi từ run_api_import.py — không chạy trực tiếp.
# cmd_parse_errors: đọc bảng error code trong module, xuất report.
# cmd_apply_errors: ghi error code đã approve vào map chính thức.

import json
import os
import yaml
from datetime import datetime

from contract_profile.operation_map_builder import build_for_module, build_all_modules
from contract_profile.format_adapters import load_profiles, extract_tables
from contract_profile.error_table_parser import load_global_map, load_module_catalog, parse_rows, suggest_next_code
from contract_profile.apply_review_decisions import apply_decisions, load_yaml_codes, validate_resolution, apply_persistent_resolutions

BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "..")
PROFILES_PATH = os.path.join(BASE_DIR, "4.config", "table_format_profiles.yaml")
ERRORS_DIR = os.path.join(BASE_DIR, "4.config", "errors")
GLOBAL_MAP_PATH = os.path.join(ERRORS_DIR, "error_code_map.yaml")
REPORTS_DIR = os.path.join(BASE_DIR, "3.build", "reports", "errors")
SOURCE_ROOT = os.path.join(BASE_DIR, "1.docs", "source", "api_contract")


def _report_path(module: str) -> str:
    """Path report per-module: 3.build/reports/errors/<module>/error_codes_review.json"""
    return os.path.join(REPORTS_DIR, module, "error_codes_review.json")


def _review_decisions_path(module: str) -> str:
    """Path persistent review decisions per-module."""
    return os.path.join(ERRORS_DIR, "modules", module, "review_decisions.yaml")


def build_report(entries: list[dict], source_files: list[str]) -> dict:
    summary = {
        "total": len(entries),
        "new": sum(1 for e in entries if e.get("status") == "new"),
        "duplicate_ok": sum(1 for e in entries if e.get("status") == "duplicate_ok"),
        "conflict": sum(1 for e in entries if e.get("status") == "conflict"),
        "needs_review": sum(1 for e in entries if e.get("status") == "needs_review"),
        "intra_batch_conflict": sum(1 for e in entries if e.get("intra_batch_conflict")),
        "missing_http_status": sum(1 for e in entries if e.get("missing_http_status")),
    }
    clean_entries = []
    for e in entries:
        clean_entries.append({
            "code": e["code"],
            "status": e.get("status"),
            "matched_namespace": e.get("matched_namespace"),
            "intra_batch_conflict": e.get("intra_batch_conflict", False),
            "missing_http_status": e.get("missing_http_status", False),
            "source_file": e.get("source_file"),
            "seen_in_files": e.get("seen_in_files") or [e.get("source_file")],
            "table_index": e.get("table_index"),
            "incoming": {
                "http_status": e.get("http_status"),
                "category": e.get("category"),
                "message": e.get("message"),
            },
            "existing_in_map": e.get("existing_in_map"),
            "resolution": None,
        })
    return {
        "generated_at": datetime.now().isoformat(),
        "source_files": [os.path.basename(f) for f in source_files],
        "summary": summary,
        "entries": clean_entries,
    }


def update_global_usage(usage_path: str, module: str, entries: list[dict]) -> int:
    """
    Ghi nhận 1 run mới vào global_usage.yaml — chỉ APPEND, không ghi đè lịch sử cũ
    (khác error_code_ranges.yaml — file đó luôn tính lại từ đầu mỗi lần).
    Chỉ lấy entry có matched_namespace == "_global" (module đang dùng mã global nào).
    Trả về số mã global ghi nhận trong run này (0 nếu module không dùng global code nào).
    """
    global_entries = [e for e in entries if e.get("matched_namespace") == "_global"]
    if not global_entries:
        return 0
    
    if os.path.exists(usage_path):
        with open(usage_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    else:
        data = {}

    data.setdefault("namespace", module)
    data.setdefault("runs", [])

    used_by = [
        {
            "code": e["code"],
            "source_file": e.get("source_file"),
            "message_in_document": e.get("message", ""),
        }
        for e in global_entries
    ]

    data["runs"].append({
        "timestamp": datetime.now().isoformat(),
        "used_by": used_by,
    })

    os.makedirs(os.path.dirname(usage_path), exist_ok=True)
    with open(usage_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    return len(used_by)


def cmd_parse_errors(module: str, dry_run: bool = False) -> None:
    module_dir = os.path.join(SOURCE_ROOT, module)
    if not os.path.isdir(module_dir):
        print(f"⚠ Không tìm thấy module: {module_dir}")
        return

    all_files = sorted([
        os.path.join(module_dir, f)
        for f in os.listdir(module_dir)
        if f.lower().endswith((".docx", ".pdf"))
    ])
    if not all_files:
        print(f"Không có file DOCX/PDF nào trong module: {module}")
        return

    print(f"[1/4] Load profiles: {PROFILES_PATH}")
    profiles = load_profiles(PROFILES_PATH)
    print(f"      {len(profiles)} profile: {[p['name'] for p in profiles]}")

    catalog_path = os.path.join(ERRORS_DIR, "modules", module, "error_catalog.yaml")

    print(f"[2/4] Load global map: {GLOBAL_MAP_PATH}")
    global_map = load_global_map(GLOBAL_MAP_PATH)
    print(f"      {len(global_map)} mã global")

    print(f"      Load module catalog: {catalog_path}")
    module_catalog = load_module_catalog(catalog_path)
    print(f"      {len(module_catalog)} mã module")

    print(f"[3/4] Đọc {len(all_files)} file...")
    all_rows = []
    for file_path in all_files:
        rows = extract_tables(file_path, profiles)
        print(f"      {os.path.basename(file_path)}: {len(rows)} row")
        all_rows.extend(rows)

    if not all_rows:
        print("Không có row nào được đọc. Kiểm tra lại profiles.")
        return

    print(f"[4/4] Classify {len(all_rows)} row...")
    entries = parse_rows(all_rows, global_map, module_catalog)
    report = build_report(entries, all_files)

    persisted_count = apply_persistent_resolutions(report, _review_decisions_path(module))
    if persisted_count:
        print(f"      Applied persisted review decisions: {persisted_count}")

    # Tự ghi mã new vào module catalog
    new_entries = [e for e in entries if e["status"] == "new"]
    if new_entries and not dry_run:
        os.makedirs(os.path.dirname(catalog_path), exist_ok=True)
        existing_catalog = load_module_catalog(catalog_path)
        for e in new_entries:
            existing_catalog[e["code"]] = {
                "http_status": e.get("http_status") or "",
                "message": e.get("message", ""),
            }
        with open(catalog_path, "w", encoding="utf-8") as f:
            yaml.dump(
                {"namespace": module, "error_codes": existing_catalog},
                f, allow_unicode=True, default_flow_style=False, sort_keys=True,
            )
        print(f" Đã ghi {len(new_entries)} mã mới vào: {catalog_path}")

    if not dry_run:
        usage_path = os.path.join(ERRORS_DIR, "modules", module, "global_usage.yaml")
        n_global = update_global_usage(usage_path, module, entries)
        if n_global:
            print(f" Đã ghi global_usage ({n_global} mã global) vào: {usage_path}")


    s = report["summary"]
    print(f"\n=== SUMMARY ===")
    print(f"  total               : {s['total']}")
    print(f"  new                 : {s['new']}")
    print(f"  duplicate_ok        : {s['duplicate_ok']}")
    print(f"  conflict            : {s['conflict']}")
    print(f"  needs_review        : {s['needs_review']}")
    print(f"  intra_batch_conflict: {s['intra_batch_conflict']}")
    print(f"  missing_http_status : {s['missing_http_status']}")

    conflicts = [
    e for e in report["entries"]
    if e["status"] == "conflict" and not e.get("resolution")
]
    if conflicts:
        print(f"\n=== CONFLICT CẦN XỬ LÝ ===")
        for e in conflicts:
            combined_map = {**global_map, **module_catalog}
            suggestion = suggest_next_code(e['code'], combined_map)
            print(f"  code {e['code']}:")
            print(f"    incoming : http={e['incoming']['http_status']} | {e['incoming']['message']}")
            print(f"    existing : http={e['existing_in_map'].get('http_status')} | {e['existing_in_map'].get('message')}")
            print(f"    gợi ý mã mới: {suggestion if suggestion else 'không có số trống trong dải này'}")

    missing_http = [
    e for e in report["entries"]
    if e["missing_http_status"] and not e.get("resolution")
]
    if missing_http:
        print(f"\n=== THIẾU HTTP STATUS (cần bổ sung tay) ===")
        for e in missing_http:
            print(f"  code {e['code']} [{e['status']}]: {e['incoming']['message']}")

    if dry_run:
        print("\n[dry-run] Không ghi file.")
        return

    report_path = _report_path(module)
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n Report đã ghi: {report_path}")
    print(f"  Mở file, điền 'resolution' vào các entry cần xử lý,")
    print(f"  sau đó chạy: python3 2.pipeline/run_api_import.py apply-errors")

    # Ghi parsed_error_tables.json per-module — dùng cho build-operation-map
    # Không bị ghi đè khi module khác chạy parse-errors
    parsed_tables_path = os.path.join(
        BASE_DIR, "3.build", "intermediate", "errors", module, "parsed_error_tables.json"
    )
    os.makedirs(os.path.dirname(parsed_tables_path), exist_ok=True)
    with open(parsed_tables_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"Parsed tables đã ghi: {parsed_tables_path}")


def cmd_apply_errors(report_path: str = None, module: str = None) -> None:
    path = report_path or _report_path(module)
    if not os.path.exists(path):
        print(f" Không tìm thấy report: {path}")
        return
    if not module:
        print(f" Thiếu --module. Dùng: apply-errors --module <tên>")
        return
    catalog_path = os.path.join(ERRORS_DIR, "modules", module, "error_catalog.yaml")
    apply_decisions(
        report_path=path,
        global_map_path=GLOBAL_MAP_PATH,
        module=module,
        catalog_path=catalog_path,
        decisions_path=_review_decisions_path(module),
    )


def cmd_resolve_error(module: str, code: str, decision: str, approved_by: str,
                       new_code: str = None, source_file: str = None,
                       report_path: str = None) -> None:
    """
    Điền resolution cho 1 entry trong report — CHỈ sửa report JSON,
    không ghi gì vào catalog/global map. Ghi thật vẫn do apply-errors đảm nhiệm.
    """
    path = report_path or _report_path(module)
    if not os.path.exists(path):
        print(f" Không tìm thấy report: {path}")
        return

    with open(path, encoding="utf-8") as f:
        report = json.load(f)

    entries = report.get("entries", [])
    matches = [e for e in entries if str(e["code"]) == str(code)]
    if source_file:
        matches = [e for e in matches if e.get("source_file") == source_file]

    if not matches:
        extra = f" trong file {source_file}" if source_file else ""
        print(f" Không tìm thấy entry nào với code {code}{extra} trong report.")
        return

    if len(matches) > 1:
        print(f" Có {len(matches)} entry trùng code {code}, thêm --source-file để chọn đúng:")
        for e in matches:
            print(f"    source_file={e.get('source_file')} | status={e.get('status')} | message={e['incoming']['message']}")
        return

    entry = matches[0]

    if decision == "reassign" and not new_code:
        print(" decision=reassign nhưng thiếu --new-code")
        return

    resolution = {
        "decision": decision,
        "approved_by": approved_by,
        "approved_at": datetime.now().isoformat(),
    }
    if decision == "reassign":
        resolution["new_code"] = new_code

    catalog_path = os.path.join(ERRORS_DIR, "modules", module, "error_catalog.yaml")
    global_map = load_yaml_codes(GLOBAL_MAP_PATH)
    module_catalog = load_yaml_codes(catalog_path)
    combined_map = {**global_map, **module_catalog}

    entry_check = {**entry, "resolution": resolution}
    ok, reason = validate_resolution(entry_check, combined_map)
    if not ok:
        print(f" resolution không hợp lệ: {reason}")
        return

    entry["resolution"] = resolution

    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    extra = f", new_code={new_code}" if decision == "reassign" else ""
    print(f" Đã ghi resolution cho code {code}: decision={decision}{extra}")
    print(f"  Report: {path}")
    print(f"  Khi resolve xong hết entry cần xử lý, chạy: python3 2.pipeline/run_api_import.py apply-errors --module {module}")


def cmd_audit_global_usage() -> None:
    from contract_profile.global_usage_auditor import audit_global_usage
    report_path = os.path.join(BASE_DIR, "3.build", "reports", "global_usage_review.json")
    print(f"Audit global usage across all modules...")
    audit_global_usage(ERRORS_DIR, report_path)


def cmd_build_operation_map(module: str = None, force: bool = False) -> None:
    batch_log_path = os.path.join(BASE_DIR, "3.build", "reports", "batch_log_by_module.json")
    intermediate_dir = os.path.join(BASE_DIR, "3.build", "intermediate", "errors")
    if module:
        print(f"Build operation_error_map cho module: {module}")
        build_for_module(module, batch_log_path, intermediate_dir, force=force)
    else:
        print(f"Build operation_error_map cho tất cả module")
        build_all_modules(batch_log_path, intermediate_dir, force=force)