import sys
import argparse
import json
import re
import shutil
import unicodedata
from pathlib import Path

import yaml

sys.path.insert(0, "2.pipeline")

from pipeline_API import run_batch

from converters.pdf.reader import read_pdf
from converters.docx.reader import read_docx, read_text
from converters.docx.parser import parse_text

from module_resolution import (
    parse_endpoint,
    suggest_module,
    append_observation,
    append_module_approval,
)


CONFIG_DIR             = Path(__file__).resolve().parent.parent / "4.config"
IMPORT_FLOW_CONFIG     = CONFIG_DIR / "import_flow.yaml"
MODULE_RESOLUTION_CONFIG = CONFIG_DIR / "module_resolution.yaml"
PDF_CONFIG             = CONFIG_DIR / "sources" / "pdf_sections.yaml"
REPORT_DIR             = CONFIG_DIR.parent / "3.build" / "reports"

RUNNER = "python3 2.pipeline/run_api_import.py"
MODULE_STATUS_ICONS        = {"active": "●", "draft": "○", "deprecated": "✕"}
MODULE_STATUS_ICON_DEFAULT = "?"

# ─────────────────────────────────────────
# Config helpers
# ─────────────────────────────────────────

def _load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _load_import_config() -> dict:
    if not IMPORT_FLOW_CONFIG.exists():
        print(f"[ERROR] Không tìm thấy: {IMPORT_FLOW_CONFIG}")
        sys.exit(1)
    return yaml.safe_load(IMPORT_FLOW_CONFIG.read_text(encoding="utf-8")) or {}


def _get_source_root(cfg: dict) -> Path:
    return CONFIG_DIR.parent / cfg["source_root"]


def _get_output_root(cfg: dict) -> Path:
    return CONFIG_DIR.parent / cfg["output_root"]


def _get_schemas_root(cfg: dict) -> Path:
    return CONFIG_DIR.parent / cfg["schemas_root"]

def _relative_to_project(path: Path) -> str:
    project_root = CONFIG_DIR.parent
    try:
        return str(path.resolve().relative_to(project_root.resolve()))
    except ValueError:
        return str(path)

def _supported_extensions(cfg: dict) -> list[str]:
    return cfg.get("supported_extensions", [".pdf", ".docx", ".txt", ".md"])


def _ignore_dirs(cfg: dict) -> set[str]:
    return set(cfg.get("ignore_dirs", []))


# ─────────────────────────────────────────
# File helpers
# ─────────────────────────────────────────

def _read_contract(file_path: Path) -> tuple[str, str]:
    ext = file_path.suffix.lower()
    if ext == ".pdf":
        return read_pdf(str(file_path), str(PDF_CONFIG)), "pdf"
    if ext == ".docx":
        return read_docx(str(file_path)), "docx"
    if ext in (".txt", ".md"):
        return read_text(str(file_path)), ext.strip(".")
    raise ValueError(f"Unsupported file type: {ext}")


def _parse_segments(endpoint: str, ignored_segments: list[str]) -> list[str]:
    try:
        parsed = parse_endpoint(endpoint, ignored_segments)
        if isinstance(parsed, dict):
            segments = parsed.get("segments", [])
            return segments if isinstance(segments, list) else []
        if isinstance(parsed, list):
            return parsed
    except Exception:
        pass

    return [
        s for s in str(endpoint or "").strip("/").split("/")
        if s and not re.fullmatch(r"\{.*?\}", s)
    ]


# ─────────────────────────────────────────
# Scan
# ─────────────────────────────────────────

def _scan_source_root(source_root: Path, extensions: list[str], ignore_dirs: set[str]) -> dict:
    """
    Scan source_root:
    - folder con → module candidate
    - file ở root level → unassigned

    Return:
      {
        "modules": [
          {"name": "ticket", "path": Path(...), "files": [...]},
          ...
        ],
        "unassigned": [Path(...), ...]
      }
    """
    if not source_root.exists():
        print(f"[ERROR] Không tìm thấy source_root: {source_root}")
        sys.exit(1)

    modules    = []
    unassigned = []

    for item in sorted(source_root.iterdir()):
        if item.is_dir():
            if item.name in ignore_dirs:
                continue

            files = [
                f for f in sorted(item.iterdir())
                if f.is_file() and f.suffix.lower() in extensions
            ]

            modules.append({
                "name": item.name,
                "path": item,
                "files": files,
            })

        elif item.is_file():
            if item.suffix.lower() in extensions:
                unassigned.append(item)

    return {"modules": modules, "unassigned": unassigned}


# ─────────────────────────────────────────
# Commands
# ─────────────────────────────────────────

def cmd_scan() -> None:
    """
    Scan source_root, in bảng module folders và unassigned files.
    """
    cfg         = _load_import_config()
    source_root = _get_source_root(cfg)
    extensions  = _supported_extensions(cfg)
    ignore      = _ignore_dirs(cfg)

    result = _scan_source_root(source_root, extensions, ignore)

    print(f"Source root: {source_root}\n")

    if result["modules"]:
        print("Module folders:")
        for m in result["modules"]:
            count_by_ext = {}
            for f in m["files"]:
                ext = f.suffix.lower()
                count_by_ext[ext] = count_by_ext.get(ext, 0) + 1

            ext_summary = ", ".join(
                f"{ext.strip('.')}: {count}"
                for ext, count in sorted(count_by_ext.items())
            )
            total = len(m["files"])
            print(f"  {m['name']:20s} {total} file  ({ext_summary})")
    else:
        print("Không tìm thấy folder module nào.")

    print()

    if result["unassigned"]:
        print(f"Unassigned files ({len(result['unassigned'])} file ở root — chưa được phân module):")
        for f in result["unassigned"]:
            print(f"  {f.name}")
        print()
        print("Để suggest module cho file unassigned, chạy:")
        print(f"  {RUNNER} suggest-root")
        print()
        print("Để convert file unassigned với module chỉ định, chạy:")
        print(f"  {RUNNER} convert-root --module <tên_module>")
    else:
        print("Không có file unassigned ở root.")

    print()

    if result["modules"]:
        print("Để convert từng module, chạy:")
        for m in result["modules"]:
            print(
                f"  {RUNNER} convert-folder "
                f"--folder {m['path']} --module {m['name']}"
            )
        print()
        print("Hoặc convert tất cả module một lúc:")
        print(f"  {RUNNER} import")


def cmd_suggest_root() -> None:
    """
    Suggest module cho các file nằm trực tiếp ở source_root.
    Không convert YAML. Không move/copy file.

    Output:
      3.build/reports/import_suggestions.json
      3.build/reports/module_observations.json
      3.build/reports/module_approval_queue.json
    """
    cfg         = _load_import_config()
    source_root = _get_source_root(cfg)
    extensions  = _supported_extensions(cfg)
    ignore      = _ignore_dirs(cfg)

    module_cfg       = _load_yaml(MODULE_RESOLUTION_CONFIG)
    endpoint_rules   = module_cfg.get("endpoint_rules", {})
    ignored_segments = module_cfg.get("ignored_segments", [])

    result = _scan_source_root(source_root, extensions, ignore)
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
            text, source_format = _read_contract(file_path)
            text = unicodedata.normalize("NFC", text)
            op   = parse_text(text)

            endpoint = getattr(op, "path",    "") or ""
            service  = getattr(op, "service", "") or ""
            method   = getattr(op, "method",  "") or ""
            version  = getattr(op, "version", "") or ""

            suggest_result = suggest_module(
                segments=_parse_segments(endpoint, ignored_segments),
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
            print(f"     service_in_doc   = {service}")
            print(f"     suggested_module = {suggest_result.suggested_module}")
            print(f"     final_module     = {module}")
            print(f"     confidence       = {suggest_result.confidence_score} ({suggest_result.confidence_label})")
            print(f"     status           = {suggest_result.status}")
            print(f"     review_type      = {suggest_result.review_type}")
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
    out.write_text(
        json.dumps(suggestions, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Suggestions: {out}")
    print()
    print("Module summary:")
    for module, info in suggestions["modules"].items():
        print(f"  {module:20s} {info['count']} files")
    print()
    print("Bước tiếp theo:")
    print(f"  {RUNNER} review-suggestions")
    print(f"  {RUNNER} approve-suggestions --all")
    print(f"  {RUNNER} apply-suggestions")

def cmd_review_suggestions(suggestions_path: str) -> None:
    suggestions_file = Path(suggestions_path)
    if not suggestions_file.exists():
        print(f"[ERROR] Không tìm thấy: {suggestions_file}")
        print(f"Chạy trước: {RUNNER} suggest-root")
        sys.exit(1)

    data = json.loads(suggestions_file.read_text(encoding="utf-8"))
    items = data.get("items", [])

    if not items:
        print("Không có item nào trong suggestions file.")
        return

    groups = {}
    for item in items:
        status = item.get("approval_status", "pending")
        groups.setdefault(status, []).append(item)
    
    total = len(items)
    pending = len(groups.get("pending", []))
    approved = len(groups.get("approved", []))
    rejected = len(groups.get("rejected", []))

    print(f"Suggestions file : {suggestions_file}")
    print(f"Total            : {total} (pending={pending}, approved={approved}, rejecteds={rejected})")
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

        icon = {"approved": "✓", "rejected": "✗", "pending": "?"}.get(approval, "?")

        print(f"[{idx:02d}] [{icon}] {item.get('file')}")
        print(f"      format           = {fmt}")
        print(f"      endpoint         = {endpoint}")
        print(f"      service_in_doc   = {service}")
        print(f"      suggested_module = {suggested}")
        print(f"      final_module     = {module}")
        print(f"      confidence       = {score} ({label})")
        print(f"      status           = {status}  |  conflict={conflict}")
        print(f"      approval_status  = {approval}")
        if approval == "approved":
            print(f"      approved_by      = {item.get('approved_by')}  at {item.get('approved_at')}")
        print()

    print("Để approve, chạy:")
    print(f"  {RUNNER} approve-suggestions --all")
    print(f"  {RUNNER} approve-suggestions --module ticket")
    print(f"  {RUNNER} approve-suggestions --file \"<tên file>\" --module <module>")


def cmd_approve_suggestions(
    suggestions_path: str,
    approve_all: bool = False,
    module_filter: str | None = None,
    file_name: str | None = None,
    override_module: str | None = None,
) -> None:
    """
    Approve items trong import_suggestions.json.
    Modes:
      --all                          → approve tất cả item pending
      --module ticket                → approve item có suggested/final_module = ticket
      --file "tên.pdf" --module svc  → approve 1 file, override module
    """
    import datetime

    suggestions_file = Path(suggestions_path)

    if not suggestions_file.exists():
        print(f"[ERROR] Không tìm thấy: {suggestions_file}")
        print(f"Chạy trước:  {RUNNER} suggest-root")
        sys.exit(1)

    data  = json.loads(suggestions_file.read_text(encoding="utf-8"))
    items = data.get("items", [])

    if not items:
        print("Không có item nào.")
        return

    now        = datetime.datetime.now().isoformat(timespec="seconds")
    n_approved = 0
    n_skipped  = 0

    for item in items:
        # Chỉ xử lý item đang pending
        if item.get("approval_status") == "approved":
            n_skipped += 1
            continue

        # Xác định item này có được approve không
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

        # Skip unknown / failed — không approve
        if new_module == "unknown" or item.get("status") == "failed_suggest":
            print(f"[WARN] Bỏ qua {item.get('file')} — module=unknown hoặc failed_suggest")
            n_skipped += 1
            continue

        item["approval_status"]  = "approved"
        item["approved_module"]  = new_module
        item["approved_by"]      = "cli"
        item["approved_at"]      = now
        n_approved += 1

        print(f"[APPROVED] {item.get('file')}  →  module={new_module}")

    # Ghi lại file
    suggestions_file.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print()
    print(f"Approved : {n_approved}")
    print(f"Skipped  : {n_skipped}  (đã approve trước đó hoặc không match filter)")
    print()
    print("Bước tiếp theo:")
    print(f"  {RUNNER} apply-suggestions")

def cmd_apply_suggestions(
    suggestions_path: str,
    move_files: bool = False,
    convert: bool = False,
) -> None:

    cfg = _load_import_config()
    source_root = _get_source_root(cfg)
    output_root = _get_output_root(cfg)
    schemas_root = _get_schemas_root(cfg)

    suggestions_file = Path(suggestions_path)

    if not suggestions_file.exists():
        print(f"[ERROR] không tìm thấy: {suggestions_file}")
        print(f"Chạy trước:  {RUNNER} suggest-root")
        sys.exit(1)

    data = json.loads(suggestions_file.read_text(encoding="utf-8"))
    items = data.get("items", [])

# ── Load registry
    registry_path   = CONFIG_DIR / "module_registry.yaml"
    raw             = registry_path.read_text(encoding="utf-8").strip() if registry_path.exists() else ""
    registry        = yaml.safe_load(raw) if raw else {}
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
            print(f"[SKIP] {item.get('file')} - chưa approve (approval_status={item.get('approval_status')})")
            continue

        module = (
            item.get("approved_module")
            or item.get("final_module")
            or item.get("suggested_module")
            or "unknown"
        )

# ── Skip unknown / failed
        if module == "unknown" or item.get("status") == "failed_suggest":            
            skipped.append({**item, "skip_reason": "unknown_or_failed_suggest"})
            print(f"[SKIP] {item.get('file')} - module=unknown hoặc failed_suggest")
            continue

# ── Resolve source path
        source_path = Path(item.get("path", ""))
        if not source_path.is_absolute():
            source_path = CONFIG_DIR.parent / source_path

        if not source_path.exists():
            skipped.append({**item, "skip_reason": "source_file_not_found"})
            print(f"[SKIP] {item.get('file')} - Không tìm thấy file: {source_path}")
            continue

# ── Tạo folder module 
        module_source_dir = source_root / module
        module_output_dir =  output_root / module
        module_schemas_dir = schemas_root / module

        module_source_dir.mkdir(parents=True, exist_ok=True)
        module_output_dir.mkdir(parents=True, exist_ok=True)
        module_schemas_dir.mkdir(parents=True, exist_ok=True)

        target_path = module_source_dir / source_path.name

# ── Tạo folder module 
        if source_path.resolve() == target_path.resolve():
            action = "already_in_place"

        elif target_path.exists():
            skipped.append({
                **item,
                "skip_reason": "target_file_exists",
                "target_path": str(target_path),
            })

            print(f"[SKIP] {item.get('file')} - đã tồn tại ở {target_path}")
            _register_module(registry, module, module_source_dir, module_output_dir, module_schemas_dir)
            continue

        else:
            if move_files:
                shutil.move(str(source_path), str(target_path))
                action = "moved"

            else:
                shutil.copy2(source_path, target_path)
                action = "copied"

# ── Register module vào registry
        _register_module(registry, module, module_source_dir, module_output_dir, module_schemas_dir)

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
        yaml.safe_dump(registry, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORT_DIR / "import_applied_suggestions.json"
    report_path.write_text(
        json.dumps(
            {"source": str(suggestions_file), "applied": applied, "skipped": skipped},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print()
    print(f"Applied : {len(applied)} files")
    print(f"Skipped : {len(skipped)} files")
    print(f"Registry : {registry_path}")
    print(f"Report : {report_path}")

    if convert:
        print()
        print("-" * 40)
        print("Bắt đầu convert các module đã apply..")
        print("-" * 40)
        cmd_import()

def _register_module(
    registry: dict,
    module: str,
    source_dir: Path,
    output_dir: Path,
    schemas_dir: Path,
    actor: str = "cli",
) -> None:
    import datetime

    if module not in registry["modules"]:
        cfg        = _load_import_config()
        extensions = _supported_extensions(cfg)
        file_count = len([
            f for f in source_dir.iterdir()
            if f.is_file() and f.suffix.lower() in extensions
        ]) if source_dir.exists() else 0

        registry["modules"][module] = {
            "status":             "draft",
            "source_dir":         _relative_to_project(source_dir),
            "output_dir":         _relative_to_project(output_dir),
            "schemas_dir":        _relative_to_project(schemas_dir),
            "created_at":         datetime.datetime.now().isoformat(timespec="seconds"),
            "created_by":         actor,
            "activated_at":       None,
            "activated_by":       None,
            "deprecated_at":      None,
            "deprecated_by":      None,
            "file_count":         file_count,
            "endpoint_count":     0,
            "last_import_at":     None,
            "last_import_status": None,
            "notes":              None,
        }

def cmd_activate_module(module: str, actor: str = "cli") -> None:
    """
    Chuyển module từ draft → active.
    Kiểm tra source_dir, output_dir, schemas_dir tồn tại trước khi activate.
    """
    import datetime

    registry_path = CONFIG_DIR / "module_registry.yaml"

    if not registry_path.exists():
        print(f"[ERROR] Không tìm thấy registry: {registry_path}")
        sys.exit(1)

    registry = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
    modules  = registry.get("modules", {})

    if module not in modules:
        print(f"[ERROR] Module '{module}' không có trong registry.")
        print(f"Chạy trước: {RUNNER} list-modules")
        sys.exit(1)

    info   = modules[module]
    status = info.get("status", "draft")

    if status == "active":
        print(f"[INFO] Module '{module}' đã ở trạng thái active.")
        return

    if status == "deprecated":
        print(f"[WARN] Module '{module}' đang deprecated. Dùng reactivate-module để kích hoạt lại.")
        sys.exit(1)

    # Validate paths tồn tại
    project_root = CONFIG_DIR.parent
    errors = []

    for field in ("source_dir", "output_dir", "schemas_dir"):
        dir_path = project_root / info.get(field, "")
        if not dir_path.exists():
            errors.append(f"  {field}: {info.get(field)} — không tồn tại")

    if errors:
        print(f"[ERROR] Module '{module}' có path không hợp lệ, không thể activate:")
        for e in errors:
            print(e)
        print()
        print("Kiểm tra lại module_registry.yaml và sửa path trước khi activate.")
        sys.exit(1)

    # Activate
    info["status"]       = "active"
    info["activated_at"] = datetime.datetime.now().isoformat(timespec="seconds")
    info["activated_by"] = actor

    registry_path.write_text(
        yaml.safe_dump(registry, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    print(f"[ACTIVATED] {module}")
    print(f"  source_dir  : {info['source_dir']}")
    print(f"  output_dir  : {info['output_dir']}")
    print(f"  schemas_dir : {info['schemas_dir']}")
    print(f"  activated_at: {info['activated_at']}")

def cmd_deactivate_module(module: str, actor: str = "cli") -> None:
    """
    Chuyển module từ active → deprecated.
    """
    import datetime

    registry_path = CONFIG_DIR / "module_registry.yaml"

    if not registry_path.exists():
        print(f"[ERROR] Không tìm thấy registry: {registry_path}")
        sys.exit(1)

    registry = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
    modules  = registry.get("modules", {})

    if module not in modules:
        print(f"[ERROR] Module '{module}' không có trong registry.")
        print(f"Chạy trước: {RUNNER} list-modules")
        sys.exit(1)

    info   = modules[module]
    status = info.get("status", "draft")

    if status == "deprecated":
        print(f"[INFO] Module '{module}' đã ở trạng thái deprecated.")
        return

    if status == "draft":
        print(f"[WARN] Module '{module}' đang draft. Chưa cần deactivate.")
        print("Hãy dùng activate-module sau khi verify, hoặc thêm remove-module sau này nếu muốn bỏ module draft.")
        sys.exit(1)

    if status != "active":
        print(f"[ERROR] Trạng thái module không hợp lệ: {status}")
        sys.exit(1)

    info["status"]        = "deprecated"
    info["deprecated_at"] = datetime.datetime.now().isoformat(timespec="seconds")
    info["deprecated_by"] = actor

    registry_path.write_text(
        yaml.safe_dump(registry, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    print(f"[DEPRECATED] {module}")
    print(f"  deprecated_at: {info['deprecated_at']}")
    print()
    print(f"Module '{module}' sẽ không được import khi dùng --active-only.")
    print(f"Để kích hoạt lại, chạy: {RUNNER} reactivate-module --module {module}")


def cmd_reactivate_module(module: str, actor: str = "cli") -> None:
    """
    Chuyển module từ deprecated → active.
    """
    import datetime

    registry_path = CONFIG_DIR / "module_registry.yaml"

    if not registry_path.exists():
        print(f"[ERROR] Không tìm thấy registry: {registry_path}")
        sys.exit(1)

    registry = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
    modules  = registry.get("modules", {})

    if module not in modules:
        print(f"[ERROR] Module '{module}' không có trong registry.")
        print(f"Chạy trước: {RUNNER} list-modules")
        sys.exit(1)

    info   = modules[module]
    status = info.get("status", "draft")

    if status == "active":
        print(f"[INFO] Module '{module}' đã ở trạng thái active.")
        return

    if status == "draft":
        print(f"[WARN] Module '{module}' đang draft. Dùng activate-module thay vì reactivate-module.")
        sys.exit(1)

    if status != "deprecated":
        print(f"[ERROR] Trạng thái module không hợp lệ: {status}")
        sys.exit(1)

    # Validate paths
    project_root = CONFIG_DIR.parent
    errors = []

    for field in ("source_dir", "output_dir", "schemas_dir"):
        dir_path = project_root / info.get(field, "")
        if not dir_path.exists():
            errors.append(f"  {field}: {info.get(field)} — không tồn tại")

    if errors:
        print(f"[ERROR] Module '{module}' có path không hợp lệ:")
        for e in errors:
            print(e)
        sys.exit(1)

    info["status"]        = "active"
    info["activated_at"]  = datetime.datetime.now().isoformat(timespec="seconds")
    info["activated_by"]  = actor
    info["deprecated_at"] = None
    info["deprecated_by"] = None

    registry_path.write_text(
        yaml.safe_dump(registry, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    print(f"[REACTIVATED] {module}")
    print(f"  activated_at: {info['activated_at']}")

def cmd_list_modules() -> None:
    """
    In bảng tất cả module trong registry với status và stats.
    """
    import datetime

    registry_path = CONFIG_DIR / "module_registry.yaml"

    if not registry_path.exists():
        print("Chưa có module nào trong registry.")
        print(f"Chạy trước: {RUNNER} apply-suggestions")
        return

    registry = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
    modules  = registry.get("modules", {})

    if not modules:
        print("Chưa có module nào trong registry.")
        return

    def _fmt_dt(value, fmt="%Y-%m-%d"):
        if not value:
            return "-"
        try:
            return datetime.datetime.fromisoformat(str(value)).strftime(fmt)
        except ValueError:
            return str(value)

    print(f"{'MODULE':<20} {'STATUS':<12} {'FILES':>6} {'ENDPOINTS':>10} {'LAST IMPORT':<24} {'CREATED'}")
    print("-" * 90)

    for name, info in modules.items():
        status         = info.get("status", "draft")
        file_count     = info.get("file_count", 0)
        endpoint_count = info.get("endpoint_count", 0)
        last_import_at = _fmt_dt(info.get("last_import_at"), fmt="%Y-%m-%d %H:%M")
        last_status    = info.get("last_import_status") or ""
        created_at     = _fmt_dt(info.get("created_at"))

        last_import_col = f"{last_import_at} ({last_status})" if last_status else last_import_at
        icon            = MODULE_STATUS_ICONS.get(status, MODULE_STATUS_ICON_DEFAULT)

        print(f"{icon} {name:<19} {status:<12} {file_count:>6} {endpoint_count:>10} {last_import_col:<24} {created_at}")

    print()
    total = len(modules)
    counts = {}
    for m in modules.values():
        s = m.get("status", "draft")
        counts[s] = counts.get(s, 0) + 1

    summary = ", ".join(f"{s}={c}" for s, c in sorted(counts.items()))
    print(f"Total: {total}  ({summary})")
    print()
    print("Để activate module, chạy:")
    print(f"  {RUNNER} activate-module --module <tên_module>")

def cmd_convert_folder(folder: str, module: str) -> None:
    """
    Convert tất cả file trong 1 folder với module user chọn.
    """
    cfg          = _load_import_config()
    output_root  = _get_output_root(cfg)
    schemas_root = _get_schemas_root(cfg)

    output_dir  = str(output_root  / module)
    schemas_dir = str(schemas_root / module)

    print(f"Convert folder : {folder}")
    print(f"Module         : {module}")
    print(f"Output dir     : {output_dir}")
    print(f"Schemas dir    : {schemas_dir}")
    print()

    run_batch(
        input_dir=folder,
        module=module,
        output_dir=output_dir,
        schemas_dir=schemas_dir,
    )


def cmd_convert_root(module: str) -> None:
    """
    Convert file nằm trực tiếp ở source_root (unassigned)
    với module user chọn.
    """
    cfg          = _load_import_config()
    source_root  = _get_source_root(cfg)
    output_root  = _get_output_root(cfg)
    schemas_root = _get_schemas_root(cfg)

    output_dir  = str(output_root  / module)
    schemas_dir = str(schemas_root / module)

    print(f"Convert root   : {source_root}")
    print(f"Module         : {module}")
    print(f"Output dir     : {output_dir}")
    print(f"Schemas dir    : {schemas_dir}")
    print()

    run_batch(
        input_dir=str(source_root),
        module=module,
        output_dir=output_dir,
        schemas_dir=schemas_dir,
    )


def cmd_import(active_only: bool = True, module_filter: str | None = None) -> None:    
    """
    Auto convert folder con trong source_root.
    Mỗi folder con = 1 module (module name = folder name).

    active_only=True (default): chỉ convert module có status=active trong registry.
    active_only=False         : convert tất cả folder, bỏ qua check registry.
    """
    import datetime

    cfg          = _load_import_config()
    source_root  = _get_source_root(cfg)
    output_root  = _get_output_root(cfg)
    schemas_root = _get_schemas_root(cfg)
    extensions   = _supported_extensions(cfg)
    ignore       = _ignore_dirs(cfg)

    result = _scan_source_root(source_root, extensions, ignore)

    if not result["modules"]:
        print("Không tìm thấy folder module nào để convert.")
        if result["unassigned"]:
            print(f"\n{len(result['unassigned'])} file unassigned ở root.")
            print(f"Chạy: {RUNNER} suggest-root")
            print(f"Sau đó: {RUNNER} apply-suggestions")
        return

    if result["unassigned"]:
        print(
            f"[WARN] {len(result['unassigned'])} file unassigned ở root "
            f"sẽ không được convert.\n"
            f"       Chạy '{RUNNER} suggest-root' rồi '{RUNNER} apply-suggestions' nếu cần.\n"
        )

    # Load registry nếu active_only
    registry_path = CONFIG_DIR / "module_registry.yaml"
    registry_modules: dict = {}

    if active_only:
        if registry_path.exists():
            raw = registry_path.read_text(encoding="utf-8").strip()
            registry_data = yaml.safe_load(raw) if raw else {}
            registry_modules = registry_data.get("modules", {})
        else:
            print("[WARN] Không tìm thấy module_registry.yaml — chạy tất cả module (không filter).")
            active_only = False

    # Lọc module sẽ chạy
    to_run = []
    for m in result["modules"]:
        if not m["files"]:
            print(f"[SKIP] {m['name']} — không có file hợp lệ")
            continue
        if module_filter and m["name"] != module_filter:
            continue

        if active_only:
            reg_info = registry_modules.get(m["name"])
            if reg_info is None:
                print(f"[SKIP] {m['name']} — không có trong registry (chạy apply-suggestions trước)")
                continue
            status = reg_info.get("status", "draft")
            if status != "active":
                print(f"[SKIP] {m['name']} — status={status} (cần activate-module trước)")
                continue

        to_run.append(m)

    if module_filter and not to_run:
        print(f"[ERROR] Không tìm thấy module '{module_filter}' trong source_root.")
        print(f"Kiểm tra folder: {source_root}")
        return

    if not to_run:
        print()
        print("Không có module nào để convert.")
        if active_only:
            print(f"Kiểm tra status với: {RUNNER} list-modules")
            print(f"Activate module với: {RUNNER} activate-module --module <tên_module>")
        return

    print(f"\nBắt đầu import {len(to_run)} module...\n")

    n_success = 0
    n_failed  = 0

    for m in to_run:
        print(f"{'=' * 40}")
        print(f"Module: {m['name']} ({len(m['files'])} files)")
        print(f"{'=' * 40}")

        import_status = "success"
        now = datetime.datetime.now().isoformat(timespec="seconds")

        try:
            run_batch(
                input_dir=str(m["path"]),
                module=m["name"],
                output_dir=str(output_root  / m["name"]),
                schemas_dir=str(schemas_root / m["name"]),
            )
            n_success += 1

        except Exception as e:
            print(f"[ERROR] Module {m['name']} thất bại: {e}")
            import_status = "failed"
            n_failed += 1

        # Update registry stats
        if active_only and m["name"] in registry_modules:
            info = registry_modules[m["name"]]
            info["last_import_at"]     = now
            info["last_import_status"] = import_status

            out_dir = output_root / m["name"]
            if out_dir.exists():
                info["endpoint_count"] = len([
                    f for f in out_dir.iterdir()
                    if f.is_file() and f.suffix.lower() in (".yaml", ".yml")
                ])

        print()

    # Ghi lại registry
    if active_only and registry_modules:
        raw_full = registry_path.read_text(encoding="utf-8").strip()
        reg_full = yaml.safe_load(raw_full) if raw_full else {}
        reg_full["modules"] = registry_modules
        registry_path.write_text(
            yaml.safe_dump(reg_full, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    print(f"Import hoàn thành.  success={n_success}  failed={n_failed}")
    if active_only:
        print(f"Registry updated: {registry_path}")
        print(f"Xem stats: {RUNNER} list-modules")


# ─────────────────────────────────────────
# Main
# ─────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="API Import Orchestration — scan/suggest/convert/import API Contract folders"
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # scan
    subparsers.add_parser(
        "scan",
        help="Scan source_root, liệt kê folder module và file unassigned",
    )

    # suggest-root
    subparsers.add_parser(
        "suggest-root",
        help="Parse file unassigned ở source_root, gợi ý module theo endpoint — chưa convert",
    )

    p_apply =subparsers.add_parser(
        "apply-suggestions",
        help="Apply import_suggestions.json: copy/move file vào folder module và update module_registry",
    )

    p_apply.add_argument(
        "--suggestions",
        default=str(REPORT_DIR / "import_suggestions.json"),
        help="Path tới import_suggestions.json",
    )

    p_apply.add_argument(
        "--move-files",
        action="store_true",
        help="Move file vào folder module thay vì copy"
    )

    p_apply.add_argument(
        "--convert",
        action="store_true",
        help="Convert luôn sau khi apply suggestions",
    )

    # review-suggestions
    p_review = subparsers.add_parser(
        "review-suggestions",
        help="In bảng review suggestions, hiển thị approval_status từng item",
    )
    p_review.add_argument(
        "--suggestions",
        default=str(REPORT_DIR / "import_suggestions.json"),
        help="Path tới import_suggestions.json",
    )

    # approve-suggestions
    p_approve = subparsers.add_parser(
        "approve-suggestions",
        help="Approve items trong import_suggestions.json",
    )
    p_approve.add_argument(
        "--suggestions",
        default=str(REPORT_DIR / "import_suggestions.json"),
        help="Path tới import_suggestions.json",
    )
    p_approve.add_argument(
        "--all",
        dest="approve_all",
        action="store_true",
        help="Approve tất cả item pending",
    )
    p_approve.add_argument(
        "--module",
        dest="module_filter",
        default=None,
        help="Approve item có module = giá trị này",
    )
    p_approve.add_argument(
        "--file",
        dest="file_name",
        default=None,
        help="Approve 1 file cụ thể theo tên",
    )
    p_approve.add_argument(
        "--override-module",
        dest="override_module",
        default=None,
        help="Override module khi approve (dùng với --file hoặc --module)",
    )

    # convert-folder
    p_folder = subparsers.add_parser(
        "convert-folder",
        help="Convert tất cả file trong 1 folder với module chỉ định",
    )
    p_folder.add_argument("--folder", required=True, help="Path đến folder chứa file")
    p_folder.add_argument("--module", required=True, help="Tên module, ví dụ: ticket")

    # convert-root
    p_root = subparsers.add_parser(
        "convert-root",
        help="Convert file unassigned ở source_root với module chỉ định",
    )

    p_root.add_argument("--module", required=True, help="Tên module, ví dụ: ticket")

    # activate-module
    p_activate = subparsers.add_parser(
        "activate-module",
        help="Chuyển module từ draft → active sau khi verify paths",
    )

    # deactivate-module
    p_deactivate = subparsers.add_parser(
        "deactivate-module",
        help="Chuyển module từ active → deprecated",
    )
    p_deactivate.add_argument("--module", required=True, help="Tên module cần deactivate")

    # reactivate-module
    p_reactivate = subparsers.add_parser(
        "reactivate-module",
        help="Chuyển module từ deprecated → active",
    )
    p_reactivate.add_argument("--module", required=True, help="Tên module cần reactivate")

    p_activate.add_argument(
        "--module",
        required=True,
        help="Tên module cần activate, ví dụ: ticket",
    )

    # list-modules
    subparsers.add_parser(
        "list-modules",
        help="In bảng tất cả module trong registry với status và stats",
    )

    # import
    p_import = subparsers.add_parser(
        "import",
        help="Auto convert tất cả folder con trong source_root",
    )

    p_import.add_argument(
        "--all",
        dest="import_all",
        action="store_true",
        help="Convert tất cả module, bỏ qua check registry status",
    )

    p_import.add_argument(
        "--module",
        dest="import_module",
        default=None,
        help="Chỉ import 1 module cụ thể, ví dụ: --module ticket",
    )

    args = parser.parse_args()

    if args.command == "scan":
        cmd_scan()

    elif args.command == "suggest-root":
        cmd_suggest_root()

    elif args.command == "apply-suggestions":
        cmd_apply_suggestions(
            suggestions_path=args.suggestions,
            move_files=args.move_files,
            convert=args.convert,
        )
    
    elif args.command == "review-suggestions":
        cmd_review_suggestions(suggestions_path=args.suggestions)

    elif args.command == "approve-suggestions":
        if not args.approve_all and not args.module_filter and not args.file_name:
            print("[ERROR] Cần chỉ định --all, --module, hoặc --file")
            sys.exit(1)
        cmd_approve_suggestions(
            suggestions_path=args.suggestions,
            approve_all=args.approve_all,
            module_filter=args.module_filter,
            file_name=args.file_name,
            override_module=args.override_module,
        )

    elif args.command == "convert-folder":
        cmd_convert_folder(folder=args.folder, module=args.module)

    elif args.command == "convert-root":
        cmd_convert_root(module=args.module)

    elif args.command == "activate-module":
        cmd_activate_module(module=args.module)

    elif args.command == "deactivate-module":
        cmd_deactivate_module(module=args.module)

    elif args.command == "reactivate-module":
        cmd_reactivate_module(module=args.module)

    elif args.command == "list-modules":
        cmd_list_modules()

    elif args.command == "import":
        cmd_import(
            active_only=not args.import_all,
            module_filter=args.import_module,
        )


if __name__ == "__main__":
    main()