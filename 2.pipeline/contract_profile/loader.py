from pathlib import Path
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = PROJECT_ROOT / "4.config"
GLOBAL_DIR = CONFIG_DIR / "global"


def load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    raw = path.read_text(encoding="utf-8").strip()
    return yaml.safe_load(raw) if raw else {}


def load_contract_profile() -> dict:
    return {
        "api_contract_profile": load_yaml(CONFIG_DIR / "api_contract_profile.yaml"),
        "section_aliases": load_yaml(GLOBAL_DIR / "section_aliases.yaml"),
        "table_type_rules": load_yaml(GLOBAL_DIR / "table_type_rules.yaml"),
        "field_type_rules": load_yaml(GLOBAL_DIR / "field_type_rules.yaml"),
        "response_contract_rules": load_yaml(GLOBAL_DIR / "response_contract_rules.yaml"),
        "enum_inference_rules": load_yaml(GLOBAL_DIR / "enum_inference_rules.yaml"),
        "extraction_policy": load_yaml(GLOBAL_DIR / "extraction_policy.yaml"),
        "header_refs": load_yaml(GLOBAL_DIR / "header_refs.yaml"),
        "status_response_refs": load_yaml(GLOBAL_DIR / "status_response_refs.yaml"),
        "error_code_map": load_yaml(CONFIG_DIR / "error_code_map.yaml"),
    }
