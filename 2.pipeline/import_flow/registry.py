import sys
import datetime
import yaml
from pathlib import Path

from import_flow.config import (
    CONFIG_DIR,
    RUNNER,
    MODULE_STATUS_ICONS,
    MODULE_STATUS_ICON_DEFAULT,
    load_import_config,
    load_yaml,
    relative_to_project,
    supported_extensions,
)


def register_module(
    registry: dict,
    module: str,
    source_dir: Path,
    output_dir: Path,
    schemas_dir: Path,
    actor: str = "cli",
) -> None:
    if module not in registry["modules"]:
        cfg        = load_import_config()
        extensions = supported_extensions(cfg)
        file_count = len([
            f for f in source_dir.iterdir()
            if f.is_file() and f.suffix.lower() in extensions
        ]) if source_dir.exists() else 0

        registry["modules"][module] = {
            "status":                   "draft",
            "source_dir":               relative_to_project(source_dir),
            "output_dir":               relative_to_project(output_dir),
            "schemas_dir":              relative_to_project(schemas_dir),
            "created_at":               datetime.datetime.now().isoformat(timespec="seconds"),
            "created_by":               actor,
            "activated_at":             None,
            "activated_by":             None,
            "deprecated_at":            None,
            "deprecated_by":            None,
            "file_count":               file_count,
            "source_files_count":       file_count,
            "selected_files_count":     0,
            "skipped_duplicate_count":  0,
            "endpoint_count":           0,
            "last_import_at":           None,
            "last_import_status":       None,
            "notes":                    None,
        }


def cmd_activate_module(module: str, actor: str = "cli") -> None:
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
        sys.exit(1)

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
    registry_path = CONFIG_DIR / "module_registry.yaml"
    if not registry_path.exists():
        print(f"[ERROR] Không tìm thấy registry: {registry_path}")
        sys.exit(1)

    registry = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
    modules  = registry.get("modules", {})

    if module not in modules:
        print(f"[ERROR] Module '{module}' không có trong registry.")
        sys.exit(1)

    info   = modules[module]
    status = info.get("status", "draft")

    if status == "deprecated":
        print(f"[INFO] Module '{module}' đã ở trạng thái deprecated.")
        return

    if status == "draft":
        print(f"[WARN] Module '{module}' đang draft. Chưa cần deactivate.")
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
    print(f"Module '{module}' sẽ không được import khi dùng --active-only.")
    print(f"Để kích hoạt lại, chạy: {RUNNER} reactivate-module --module {module}")


def cmd_reactivate_module(module: str, actor: str = "cli") -> None:
    registry_path = CONFIG_DIR / "module_registry.yaml"
    if not registry_path.exists():
        print(f"[ERROR] Không tìm thấy registry: {registry_path}")
        sys.exit(1)

    registry = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
    modules  = registry.get("modules", {})

    if module not in modules:
        print(f"[ERROR] Module '{module}' không có trong registry.")
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

    print(
        f"{'MODULE':<20} "
        f"{'STATUS':<12} "
        f"{'SOURCE':>8} "
        f"{'SELECTED':>10} "
        f"{'SKIPPED':>8} "
        f"{'ENDPOINTS':>10} "
        f"{'LAST IMPORT':<24} "
        f"{'CREATED'}"
    )
    print("-" * 115)

    for name, info in modules.items():
        status         = info.get("status", "draft")

        source_files_count = info.get("source_files_count", info.get("file_count", 0))
        selected_files_count = info.get("selected_files_count", source_files_count)
        skipped_duplicate_count = info.get("skipped_duplicate_count", 0)
        endpoint_count = info.get("endpoint_count", 0)

        last_import_at = _fmt_dt(info.get("last_import_at"), fmt="%Y-%m-%d %H:%M")
        last_status    = info.get("last_import_status") or ""
        created_at     = _fmt_dt(info.get("created_at"))

        last_import_col = f"{last_import_at} ({last_status})" if last_status else last_import_at
        icon            = MODULE_STATUS_ICONS.get(status, MODULE_STATUS_ICON_DEFAULT)

        print(
        f"{icon} {name:<19} "
        f"{status:<12} "
        f"{source_files_count:>8} "
        f"{selected_files_count:>10} "
        f"{skipped_duplicate_count:>8} "
        f"{endpoint_count:>10} "
        f"{last_import_col:<24} "
        f"{created_at}"
    )

    print()
    total  = len(modules)
    counts = {}
    for m in modules.values():
        s = m.get("status", "draft")
        counts[s] = counts.get(s, 0) + 1

    summary = ", ".join(f"{s}={c}" for s, c in sorted(counts.items()))
    print(f"Total: {total}  ({summary})")
    print(f"\nĐể activate module, chạy:")
    print(f"  {RUNNER} activate-module --module <tên_module>")