from pathlib import Path
import sys
import datetime
import yaml

from import_flow.config import CONFIG_DIR, RUNNER
from import_flow.registry import register_module


PROJECT_ROOT = CONFIG_DIR.parent
MODULE_RESOLUTION_PATH = CONFIG_DIR / "module_resolution.yaml"
MODULE_REGISTRY_PATH = CONFIG_DIR / "module_registry.yaml"


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    raw = path.read_text(encoding="utf-8").strip()
    return yaml.safe_load(raw) if raw else {}


def _write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _normalize_module_name(name: str) -> str:
    return name.strip().lower().replace(" ", "-")


def _normalize_path_prefix(prefix: str) -> str:
    prefix = prefix.strip()

    if not prefix.startswith("/"):
        prefix = "/" + prefix

    # /v1/orders -> /orders, vì ignored_segments đã có v1/v2/v3
    if prefix.startswith("/v1/"):
        prefix = prefix[3:]
    elif prefix.startswith("/v2/"):
        prefix = prefix[3:]
    elif prefix.startswith("/v3/"):
        prefix = prefix[3:]

    return prefix.rstrip("/")


def _add_endpoint_rule(module: str, path_prefix: str) -> tuple[dict, bool]:
    """
    Update module_resolution.yaml data.
    Format hiện tại:
      endpoint_rules:
        order:
          patterns:
            - "/orders"

    Return: (data, added_rule)
    """
    data = _load_yaml(MODULE_RESOLUTION_PATH)
    endpoint_rules = data.setdefault("endpoint_rules", {})

    module_rule = endpoint_rules.setdefault(module, {})
    patterns = module_rule.setdefault("patterns", [])

    normalized_prefix = _normalize_path_prefix(path_prefix)

    if normalized_prefix in patterns:
        return data, False

    patterns.append(normalized_prefix)
    return data, True


def _ensure_module_registry(module: str, actor: str = "cli") -> bool:
    """
    Tạo folder + register module nếu chưa có.
    Return True nếu tạo mới registry entry.
    """
    registry = _load_yaml(MODULE_REGISTRY_PATH)
    registry.setdefault("modules", {})

    modules = registry["modules"]

    source_dir = PROJECT_ROOT / "1.docs/source/api_contract" / module
    output_dir = PROJECT_ROOT / "5.openapi/paths" / module
    schemas_dir = PROJECT_ROOT / "5.openapi/components/schemas" / module

    source_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    schemas_dir.mkdir(parents=True, exist_ok=True)

    if module in modules:
        _write_yaml(MODULE_REGISTRY_PATH, registry)
        return False

    register_module(
        registry=registry,
        module=module,
        source_dir=source_dir,
        output_dir=output_dir,
        schemas_dir=schemas_dir,
        actor=actor,
    )

    modules[module]["notes"] = (
        "Auto-created by approve-module-rule at "
        f"{datetime.datetime.now().isoformat(timespec='seconds')}"
    )

    _write_yaml(MODULE_REGISTRY_PATH, registry)
    return True


def cmd_approve_module_rule(
    module: str,
    path_prefix: str,
    actor: str = "cli",
    dry_run: bool = False,
) -> None:
    module = _normalize_module_name(module)
    normalized_prefix = _normalize_path_prefix(path_prefix)

    if not module:
        print("[ERROR] module không được rỗng.")
        sys.exit(1)

    if not normalized_prefix or normalized_prefix == "/":
        print("[ERROR] path-prefix không hợp lệ.")
        sys.exit(1)

    print("Approve module rule")
    print(f"  module      : {module}")
    print(f"  path_prefix : {normalized_prefix}")
    print()

    if dry_run:
        print("[DRY-RUN] Sẽ thực hiện:")
        print(f"  - Add endpoint rule: {normalized_prefix} → {module}")
        print(f"  - Ensure source dir : 1.docs/source/api_contract/{module}")
        print(f"  - Ensure output dir : 5.openapi/paths/{module}")
        print(f"  - Ensure schemas dir: 5.openapi/components/schemas/{module}")
        print("  - Register module nếu chưa có trong module_registry.yaml")
        return

    resolution_data, added_rule = _add_endpoint_rule(module, normalized_prefix)
    _write_yaml(MODULE_RESOLUTION_PATH, resolution_data)

    created_module = _ensure_module_registry(module, actor=actor)

    print("[OK] Module rule approved")
    print(f"  rule_added     : {added_rule}")
    print(f"  module_created : {created_module}")
    print()
    print("Chạy lại suggest để verify:")
    print(f"  {RUNNER} suggest-root")
