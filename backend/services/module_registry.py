from core.config import CONFIG_DIR
from core.errors import ErrorCode, http_error


# Logic rút từ route GET /modules/scan — quét 1.docs/source/ xem có module/file
# nào, gom theo phần mở rộng file, phục vụ ScanCard ở frontend.
def scan_modules() -> dict:
    from import_flow.config import (
        load_import_config,
        get_source_root,
        supported_extensions,
        ignore_dirs,
    )
    from import_flow.scanner import scan_source_root

    cfg = load_import_config()
    source_root = get_source_root(cfg)
    result = scan_source_root(source_root, supported_extensions(cfg), ignore_dirs(cfg))
    modules = []
    for m in result["modules"]:
        by_extension: dict[str, int] = {}
        for f in m["files"]:
            ext = f.suffix.lower().lstrip(".")
            by_extension[ext] = by_extension.get(ext, 0) + 1
        modules.append(
            {"name": m["name"], "total": len(m["files"]), "by_extension": by_extension}
        )

    return {
        "source_root": str(source_root),
        "modules": modules,
        "unassigned": [{"name": f.name} for f in result["unassigned"]],
    }


# Logic rút từ route GET /modules — đọc 4.config/module_registry.yaml, đếm số
# module theo status, phục vụ ModuleRegistryCard ở frontend. Cũng được gọi lại
# bởi activate_module/deactivate_module để trả state mới nhất sau khi đổi.
def list_modules() -> dict:
    import yaml as _yaml

    registry_path = CONFIG_DIR / "module_registry.yaml"
    raw = {}
    if registry_path.exists():
        raw = _yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
    raw_modules = raw.get("modules", {})
    modules = []
    by_status: dict[str, int] = {}
    for name, info in raw_modules.items():
        status = info.get("status", "draft")
        by_status[status] = by_status.get(status, 0) + 1
        modules.append(
            {
                "name": name,
                "status": status,
                "file_count": info.get("file_count", 0),
                "endpoint_count": info.get("endpoint_count", 0),
                "last_import_at": info.get("last_import_at"),
                "last_import_status": info.get("last_import_status"),
                "created_at": info.get("created_at"),
            }
        )
    return {
        "modules": modules,
        "summary": {"total": len(modules), "by_status": by_status},
    }


# Logic rút từ route POST /modules/{module}/activate — chuyển module sang
# status "active" (hoặc "reactivate" nếu đang deprecated) để được phép import.
def activate_module(module: str) -> dict:
    import yaml as _yaml
    from run_api_import import cmd_activate_module, cmd_reactivate_module

    registry_path = CONFIG_DIR / "module_registry.yaml"
    if not registry_path.exists():
        raise http_error(404, ErrorCode.REGISTRY_NOT_FOUND, "Không tìm thấy registry")
    registry = _yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
    if module not in registry.get("modules", {}):
        raise http_error(
            404,
            ErrorCode.MODULE_NOT_FOUND,
            f"Module '{module}' không có trong registry",
        )

    status = registry["modules"][module].get("status")
    try:
        if status == "deprecated":
            cmd_reactivate_module(module=module, actor="ui")
        else:
            cmd_activate_module(module=module, actor="ui")
    except SystemExit:
        raise http_error(
            400,
            ErrorCode.MODULE_ACTIVATE_FAILED,
            f"Không thể activate module '{module}' — kiểm tra trạng thái và đường dẫn (xem log backend)",
        )

    return list_modules()


# Logic rút từ route POST /modules/{module}/deactivate — chuyển module sang
# status "deprecated", không import được nữa tới khi activate lại.
def deactivate_module(module: str) -> dict:
    import yaml as _yaml
    from run_api_import import cmd_deactivate_module

    registry_path = CONFIG_DIR / "module_registry.yaml"
    if not registry_path.exists():
        raise http_error(404, ErrorCode.REGISTRY_NOT_FOUND, "Không tìm thấy registry")
    registry = _yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
    if module not in registry.get("modules", {}):
        raise http_error(
            404,
            ErrorCode.MODULE_NOT_FOUND,
            f"Module '{module}' không có trong registry",
        )

    try:
        cmd_deactivate_module(module=module, actor="ui")
    except SystemExit:
        raise http_error(
            400,
            ErrorCode.MODULE_DEACTIVATE_FAILED,
            f"Không thể deactivate module '{module}' — kiểm tra log backend",
        )

    return list_modules()
