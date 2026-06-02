import json
import yaml
from pathlib import Path
from converters.excel.parser import EndpointRecord

def _load_config(config_path: str) -> dict:
    return yaml.safe_load(Path(config_path).read_text(encoding="utf-8")) or {}

def _group_by_service(records: list[EndpointRecord]) -> dict:
    """Gom records theo service → dict[service, list[EndpointRecord]]"""
    groups = {}
    for r in records:
        key = r.service.lower().replace(" ", "_") or "unknown"
        groups.setdefault(key, []).append(r)
    return groups

def _build_paths(records: list[EndpointRecord]) -> dict:
    """
    Gom các record cùng path vào 1 key.
    GET + POST /v1/tickets → 1 path key, 2 method key bên trong.
    """
    paths = {}
    for r in records:
        paths.setdefault(r.path, {})
        paths[r.path][r.method.lower()] = {
            "summary": r.summary,
            "tags": r.tags,
            "x-source": {
                "file": r.source_file,
                "author": r.author,
                "service": r.service,
            }
        }
    return paths

def emit(records: list[EndpointRecord], config_path: str) -> None:
    cfg = _load_config(config_path).get("emitter", {})
    output_dir = Path(cfg.get("output_dir", "5.openapi/paths"))
    map_path = Path(cfg.get("inventory_map_path", "3.build/reports/inventory_map.json"))

    groups = _group_by_service(records)
    for service, recs in groups.items():
        service_dir = output_dir / service
        service_dir.mkdir(parents=True, exist_ok=True)

        out = {"paths": _build_paths(recs)}
        out_file = service_dir / "_inventory.yaml"
        out_file.write_text(
            yaml.dump(out, allow_unicode=True, sort_keys=False, default_flow_style=False),
            encoding="utf-8"
        )
        print(f"    [emitter] {out_file} ({len(recs)} endpoints)")

    map_path.parent.mkdir(parents=True, exist_ok=True)
    inventory_map = {
        f"{r.method} {r.path}": {
            "source_file": r.source_file,
            "service": r.service,
            "author":  r.author,
        }
        for r in records
    }
    map_path.write_text(json.dumps(inventory_map, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  [emitter] {map_path} ({len(inventory_map)} entries)")