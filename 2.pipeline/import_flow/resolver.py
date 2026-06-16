import sys
import json
import shutil
import unicodedata
import datetime
from pathlib import Path

import yaml

from module_resolution import suggest_module, append_observation, append_module_approval
from converters.docx.parser import parse_text

from import_flow.config import (
    CONFIG_DIR,
    REPORT_DIR,
    RUNNER,
    MODULE_RESOLUTION_CONFIG,
    load_import_config,
    load_yaml,
    get_source_root,
    get_output_root,
    get_schemas_root,
    supported_extensions,
    ignore_dirs,
)
from import_flow.scanner import scan_source_root, read_contract, parse_segments
from import_flow.registry import register_module


def cmd_suggest_root() -> None:
    cfg         = load_import_config()
    source_root = get_source_root(cfg)
    extensions  = supported_extensions(cfg)
    ignore      = ignore_dirs(cfg)

    module_cfg       = load_yaml(MODULE_RESOLUTION_CONFIG)
    endpoint_rules   = module_cfg.get("endpoint_rules", {})
    ignored_segments = module_cfg.get("ignored_segments", [])

    result = scan_source_root(source_root, extensions, ignore)
    files  = result["unassigned"]

    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    suggestions = {
        "source_root": str(source_root),
        "total": len(files),
        "modules": {},
        "items": [],
    }

    print(f"Source root    : {source_root}")
    print(f"Unassigned file: {len(files)}")
    print()

    for file_path in files:
        try:
            text, source_format = read_contract(file_path)
            text = unicodedata.normalize("NFC", text)
            op   = parse_text(text)

            endpoint = getattr(op, "path",    "") or ""
            service  = getattr(op, "service", "") or ""
            method   = getattr(op, "method",  "") or ""
            version  = getattr(op, "version", "") or ""

            suggest_result = suggest_module(
                segments=parse_segments(endpoint, ignored_segments),
                endpoint=endpoint,
                endpoint_rules=endpoint_rules,
                service_in_doc=service,
                user_selected=None,
            )

            module = (
                suggest_result.final_module
                or suggest_result.suggested_module
                or "unknown"
            )

            append_observation(module, endpoint)
            append_module_approval(suggest_result)

            item = {
                "file": file_path.name,
                "path": str(file_path),
                "source_format": source_format,
                "method": method,
                "endpoint": endpoint,
                "service_in_doc": service,
                "version": version,
                "suggested_module": suggest_result.suggested_module,
                "final_module": module,
                "confidence_score": suggest_result.confidence_score,
                "confidence_label": suggest_result.confidence_label,
                "status": suggest_result.status,
                "review_type": suggest_result.review_type,
                "conflict": suggest_result.conflict,
                "conflict_reason": suggest_result.conflict_reason,
                "reason": suggest_result.reason,
                "approval_status": "pending",
                "approved_module": None,
                "approved_by": None,
                "approved_at": None,
            }

            suggestions["items"].append(item)
            suggestions["modules"].setdefault(module, {"count": 0, "files": []})
            suggestions["modules"][module]["count"] += 1
            suggestions["modules"][module]["files"].append(file_path.name)

            print(f"[OK] {file_path.name}")
            print(f"     endpoint         = {endpoint}")
            print(f"     suggested_module = {suggest_result.suggested_module}")
            print(f"     final_module     = {module}")
            print(f"     confidence       = {suggest_result.confidence_score} ({suggest_result.confidence_label})")
            print()

        except Exception as e:
            item = {
                "file": file_path.name,
                "path": str(file_path),
                "status": "failed_suggest",
                "final_module": "unknown",
                "error": str(e),
                "approval_status": "pending",
                "approved_module": None,
                "approved_by": None,
                "approved_at": None,
            }
            suggestions["items"].append(item)
            suggestions["modules"].setdefault("unknown", {"count": 0, "files": []})
            suggestions["modules"]["unknown"]["count"] += 1
            suggestions["modules"]["unknown"]["files"].append(file_path.name)
            print(f"[ERROR] {file_path.name}: {e}")
            print()

    out = REPORT_DIR / "import_suggestions.json"
    out.write_text(json.dumps(suggestions, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Suggestions: {out}")
    print()
    print("Module summary:")
    for module, info in suggestions["modules"].items():
        print(f"  {module:20s} {info['count']} files")
    print()
    print(f"  {RUNNER} review-suggestions")
    print(f"  {RUNNER} approve-suggestions --all")
    print(f"  {RUNNER} apply-suggestions")


def cmd_review_suggestions(suggestions_path: str) -> None:
    suggestions_file = Path(suggestions_path)
    if not suggestions_file.exists():
        print(f"[ERROR] Khong tim thay: {suggestions_file}")
        sys.exit(1)

    data  = json.loads(suggestions_file.read_text(encoding="utf-8"))
    items = data.get("items", [])

    if not items:
        print("Khong co item nao.")
        return

    groups  = {}
    for item in items:
        s = item.get("approval_status", "pending")
        groups.setdefault(s, []).append(item)

    total    = len(items)
    pending  = len(groups.get("pending", []))
    approved = len(groups.get("approved", []))
    rejected = len(groups.get("rejected", []))

    print(f"Suggestions file : {suggestions_file}")
    print(f"Total            : {total} (pending={pending}, approved={approved}, rejected={rejected})")
    print()

    for idx, item in enumerate(items, 1):
        approval  = item.get("approval_status", "pending")
        module    = item.get("approved_module") or item.get("final_module") or "unknown"
        suggested = item.get("suggested_module", "")
        conflict  = item.get("conflict", False)
        status    = item.get("status", "")
        endpoint  = item.get("endpoint", "")
        service   = item.get("service_in_doc", "")
        fmt       = item.get("source_format", "")
        score     = item.get("confidence_score", "")
        label     = item.get("confidence_label", "")
        icon      = {"approved": "v", "rejected": "x", "pending": "?"}.get(approval, "?")

        print(f"[{idx:02d}] [{icon}] {item.get('file')}")
        print(f"      format           = {fmt}")
        print(f"      endpoint         = {endpoint}")
        print(f"      suggested_module = {suggested}")
        print(f"      final_module     = {module}")
        print(f"      confidence       = {score} ({label})")
        print(f"      status           = {status}  |  conflict={conflict}")
        print(f"      approval_status  = {approval}")
        print()

    print(f"  {RUNNER} approve-suggestions --all")


def cmd_approve_suggestions(
    suggestions_path: str,
    approve_all: bool = False,
    module_filter: str | None = None,
    file_name: str | None = None,
    override_module: str | None = None,
) -> None:
    suggestions_file = Path(suggestions_path)
    if not suggestions_file.exists():
        print(f"[ERROR] Khong tim thay: {suggestions_file}")
        sys.exit(1)

    data  = json.loads(suggestions_file.read_text(encoding="utf-8"))
    items = data.get("items", [])

    if not items:
        print("Khong co item nao.")
        return

    now        = datetime.datetime.now().isoformat(timespec="seconds")
    n_approved = 0
    n_skipped  = 0

    for item in items:
        if item.get("approval_status") == "approved":
            n_skipped += 1
            continue

        should_approve = False
        new_module     = None

        if approve_all:
            should_approve = True
            new_module     = item.get("final_module") or item.get("suggested_module") or "unknown"

        elif file_name and item.get("file") == file_name:
            should_approve = True
            new_module = (
                override_module
                or module_filter
                or item.get("final_module")
                or item.get("suggested_module")
                or "unknown"
            )

        elif module_filter:
            candidate = item.get("final_module") or item.get("suggested_module") or "unknown"
            if candidate == module_filter:
                should_approve = True
                new_module     = override_module or candidate

        if not should_approve:
            n_skipped += 1
            continue

        if new_module == "unknown" or item.get("status") == "failed_suggest":
            print(f"[WARN] Bo qua {item.get('file')} -- module=unknown hoac failed_suggest")
            n_skipped += 1
            continue

        item["approval_status"] = "approved"
        item["approved_module"] = new_module
        item["approved_by"]     = "cli"
        item["approved_at"]     = now
        n_approved += 1
        print(f"[APPROVED] {item.get('file')}  ->  module={new_module}")

    suggestions_file.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print()
    print(f"Approved : {n_approved}")
    print(f"Skipped  : {n_skipped}")
    print(f"  {RUNNER} apply-suggestions")


def cmd_apply_suggestions(
    suggestions_path: str,
    move_files: bool = False,
    convert: bool = False,
) -> None:
    cfg          = load_import_config()
    source_root  = get_source_root(cfg)
    output_root  = get_output_root(cfg)
    schemas_root = get_schemas_root(cfg)

    suggestions_file = Path(suggestions_path)
    if not suggestions_file.exists():
        print(f"[ERROR] Khong tim thay: {suggestions_file}")
        sys.exit(1)

    data  = json.loads(suggestions_file.read_text(encoding="utf-8"))
    items = data.get("items", [])

    registry_path = CONFIG_DIR / "module_registry.yaml"
    raw           = registry_path.read_text(encoding="utf-8").strip() if registry_path.exists() else ""
    registry      = yaml.safe_load(raw) if raw else {}
    registry.setdefault("modules", {})

    applied = []
    skipped = []

    print(f"Suggestions file: {suggestions_file}")
    print(f"Total items: {len(items)}")
    print(f"Move files: {move_files}")
    print()

    for item in items:
        if item.get("approval_status") != "approved":
            skipped.append({**item, "skip_reason": "not_approved"})
            print(f"[SKIP] {item.get('file')} - chua approve")
            continue

        module = (
            item.get("approved_module")
            or item.get("final_module")
            or item.get("suggested_module")
            or "unknown"
        )

        if module == "unknown" or item.get("status") == "failed_suggest":
            skipped.append({**item, "skip_reason": "unknown_or_failed_suggest"})
            print(f"[SKIP] {item.get('file')} - module=unknown hoac failed_suggest")
            continue

        source_path = Path(item.get("path", ""))
        if not source_path.is_absolute():
            source_path = CONFIG_DIR.parent / source_path

        if not source_path.exists():
            skipped.append({**item, "skip_reason": "source_file_not_found"})
            print(f"[SKIP] {item.get('file')} - khong tim thay file")
            continue

        module_source_dir  = source_root  / module
        module_output_dir  = output_root  / module
        module_schemas_dir = schemas_root / module

        module_source_dir.mkdir(parents=True, exist_ok=True)
        module_output_dir.mkdir(parents=True, exist_ok=True)
        module_schemas_dir.mkdir(parents=True, exist_ok=True)

        target_path = module_source_dir / source_path.name

        if source_path.resolve() == target_path.resolve():
            action = "already_in_place"
        elif target_path.exists():
            skipped.append({**item, "skip_reason": "target_file_exists", "target_path": str(target_path)})
            print(f"[SKIP] {item.get('file')} - da ton tai o {target_path}")
            register_module(registry, module, module_source_dir, module_output_dir, module_schemas_dir)
            continue
        else:
            if move_files:
                shutil.move(str(source_path), str(target_path))
                action = "moved"
            else:
                shutil.copy2(source_path, target_path)
                action = "copied"

        register_module(registry, module, module_source_dir, module_output_dir, module_schemas_dir)

        applied.append({
            "file":             item.get("file"),
            "module":           module,
            "source_path":      str(source_path),
            "target_path":      str(target_path),
            "action":           action,
            "status":           item.get("status"),
            "confidence_score": item.get("confidence_score"),
            "confidence_label": item.get("confidence_label"),
        })
        print(f"[{action.upper()}] {item.get('file')} -> {module}/")

    registry_path.write_text(
        yaml.safe_dump(registry, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORT_DIR / "import_applied_suggestions.json"
    report_path.write_text(
        json.dumps({"source": str(suggestions_file), "applied": applied, "skipped": skipped},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print()
    print(f"Applied : {len(applied)} files")
    print(f"Skipped : {len(skipped)} files")
    print(f"Registry: {registry_path}")
    print(f"Report  : {report_path}")

    if convert:
        from import_flow.converter import cmd_import
        cmd_import()