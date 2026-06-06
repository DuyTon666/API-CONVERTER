import json
import re
import yaml
from datetime import datetime
from pathlib import Path

from .module_suggester import SuggestionResult

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = PROJECT_ROOT / "4.config" / "module_resolution.yaml"
REPORT_DIR = PROJECT_ROOT / "3.build" / "reports"

def _load_config() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}

def _resolve_project_path(value: str, default: Path) -> Path:
    if not value:
        return default

    path = Path(value)

    if path.is_absolute():
        return path
        
    return PROJECT_ROOT / path

def _get_observation_paths() -> tuple[Path, Path]:
    cfg = _load_config()
    observation_cfg = cfg.get("observation", {})

    observation_path = _resolve_project_path(
        observation_cfg.get("output_file", ""),
        REPORT_DIR / "module_observations.json",
    )

    approval_queue_path = _resolve_project_path(
        observation_cfg.get("module_approval_queue_file", ""),
        REPORT_DIR / "module_approval_queue.json",
    )

    return observation_path, approval_queue_path

def _load_json(path: Path) -> dict | list:
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def _load_json_list(path: Path) -> list:
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else []

def _save_json(path: Path, data: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def _extract_resource(endpoint: str) -> str | None:
    """
    Tách resource từ endpoint để gợi ý pattern.
    Bỏ {param}, tìm segment kết thúc "s" từ cuối lên.

    Ví dụ:
        /v1/users/{id}/tickets/{id}/close → "tickets"
        /v1/services/types               → "services"
    """
    segments = endpoint.strip("/").split("/")
    segments = [s for s in segments if not re.fullmatch(r"\{.*?\}", s)]
    for segment in reversed(segments):
        if segment.endswith("s"):
            return segment
    return segments[-1] if segments else None

def load_observations() -> dict:
    observations_path, _ = _get_observation_paths()
    data = _load_json(observations_path)
    return data if isinstance(data, dict) else {}

def append_observation(
    module: str,
    endpoint: str,
    resource: str | None = None,
) -> None:
    """
    Ghi lại endpoint đã thấy theo module.
    resource optional — nếu None thì tự extract từ endpoint.
    Chỉ lưu resource/pattern nếu có resource hợp lệ.
    """
    data = load_observations()

    if module not in data:
        data[module] = {
            "endpoints": [],
            "resources": [],
            "suggested_patterns": [],
        }

    if endpoint not in data[module]["endpoints"]:
        data[module]["endpoints"].append(endpoint)

    resolved_resource = resource or _extract_resource(endpoint)

    if resolved_resource and resolved_resource not in data[module]["resources"]:
        data[module]["resources"].append(resolved_resource)
        pattern = f"/{resolved_resource}"
        if pattern not in data[module]["suggested_patterns"]:
            data[module]["suggested_patterns"].append(pattern)

    observations_path, _ = _get_observation_paths()
    _save_json(observations_path, data)

def append_module_approval(result: SuggestionResult) -> None:
    """
    Append entry vào module_approval_queue.json.
    Ghi khi review_type là "pending_approval" hoặc "logged_conflict".

    pending_approval  → cần user approve module
    logged_conflict   → đã auto approve theo user_selected, chỉ cảnh báo
    """
    if result.review_type not in ("pending_approval", "logged_conflict"):
        return

    _, approval_queue_path = _get_observation_paths()
    data = _load_json_list(approval_queue_path)
    entry = {
        "endpoint": result.endpoint,
        "suggested_module": result.suggested_module,
        "final_module": result.final_module,
        "service_in_doc": result.service_in_doc,
        "confidence_score": result.confidence_score,
        "confidence_label": result.confidence_label,
        "review_type": result.review_type,
        "conflict_reason": result.conflict_reason,
        "source": result.source,
        "timestamp": datetime.now().isoformat(),
    }

    exists = any(
        item.get("endpoint") == entry["endpoint"]
        and item.get("final_module") == entry["final_module"]
        and item.get("review_type") == entry["review_type"]
        and item.get("conflict_reason") == entry["conflict_reason"]
        for item in data
    )

    if not exists:
        data.append(entry)
        save_module_approval_queue(data)

def load_module_approval_queue() -> list:
    _, approval_queue_path = _get_observation_paths()
    return _load_json_list(approval_queue_path)

def save_module_approval_queue(items: list) -> None:
    _, approval_queue_path = _get_observation_paths()
    _save_json(approval_queue_path, items)