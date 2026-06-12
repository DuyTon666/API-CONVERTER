# 2.pipeline/import_flow/config.py
import sys
import yaml
from pathlib import Path

CONFIG_DIR               = Path(__file__).resolve().parent.parent.parent / "4.config"
IMPORT_FLOW_CONFIG       = CONFIG_DIR / "import_flow.yaml"
MODULE_RESOLUTION_CONFIG = CONFIG_DIR / "module_resolution.yaml"
PDF_CONFIG               = CONFIG_DIR / "sources" / "pdf_sections.yaml"
REPORT_DIR               = CONFIG_DIR.parent / "3.build" / "reports"
OPENAPI_DIR = CONFIG_DIR.parent / "5.openapi"

RUNNER = "python3 2.pipeline/run_api_import.py"
MODULE_STATUS_ICONS        = {"active": "●", "draft": "○", "deprecated": "✕"}
MODULE_STATUS_ICON_DEFAULT = "?"


def load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load_import_config() -> dict:
    if not IMPORT_FLOW_CONFIG.exists():
        print(f"[ERROR] Không tìm thấy: {IMPORT_FLOW_CONFIG}")
        sys.exit(1)
    return yaml.safe_load(IMPORT_FLOW_CONFIG.read_text(encoding="utf-8")) or {}


def get_source_root(cfg: dict) -> Path:
    return CONFIG_DIR.parent / cfg["source_root"]


def get_output_root(cfg: dict) -> Path:
    return CONFIG_DIR.parent / cfg["output_root"]


def get_schemas_root(cfg: dict) -> Path:
    return CONFIG_DIR.parent / cfg["schemas_root"]


def relative_to_project(path: Path) -> str:
    project_root = CONFIG_DIR.parent
    try:
        return str(path.resolve().relative_to(project_root.resolve()))
    except ValueError:
        return str(path)


def supported_extensions(cfg: dict) -> list[str]:
    return cfg.get("supported_extensions", [".pdf", ".docx", ".txt", ".md"])


def ignore_dirs(cfg: dict) -> set[str]:
    return set(cfg.get("ignore_dirs", []))