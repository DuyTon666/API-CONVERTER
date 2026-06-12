import json
import yaml
from pathlib import Path
from datetime import datetime
from collections import defaultdict
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from import_flow.scanner import normalize_http_path

ROOT             = Path(__file__).resolve().parent.parent.parent
VERSIONS_PATH    = ROOT / "3.build/reports/file_versions.json"
OPENAPI_PATH     = ROOT / "5.openapi/openapi.yaml"
MERGE_RULES_PATH = ROOT / "4.config/merge_rules.yaml"
IMPORT_FLOW_PATH = ROOT / "4.config/import_flow.yaml"
REPORT_PATH      = ROOT / "3.build/reports/conflict_report.json"


def _load_json(path: Path) -> dict:
    if not path.exists():
        print(f"[WARN] Không tìm thấy: {path}")
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        print(f"[WARN] Không tìm thấy: {path}")
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _normalize_project_path(value: str) -> str:
    """
    Normalize output path về relative từ ROOT.
    Xử lý trường hợp file_versions.json lưu absolute path hoặc relative path.
    """
    if not value:
        return ""
    path = Path(value)
    if path.is_absolute():
        try:
            return str(path.resolve().relative_to(ROOT))
        except ValueError:
            return str(path)
    return str(path)


def _normalize_basename(file_name: str) -> str:
    """
    Normalize basename để detect duplicate_import dù file là .docx hay .docx.pdf.
    Ví dụ:
      API Ticket - Tạo ticket.docx     → api ticket - tạo ticket
      API Ticket - Tạo ticket.docx.pdf → api ticket - tạo ticket
    """
    name = Path(file_name).name.lower()
    for suffix in (".docx.pdf", ".pdf", ".docx", ".txt", ".md", ".yaml", ".yml"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
            break
    return name.strip()


def _normalize_ref(ref: str) -> str:
    """Normalize $ref về relative path từ root."""
    ref = ref.lstrip("./")
    if not ref.startswith("5.openapi"):
        ref = "5.openapi/" + ref
    return ref


def _build_ref_to_path_map(openapi_path: Path) -> dict:
    """
    Đọc openapi.yaml, build map:
    "5.openapi/paths/ticket/close_user_ticket.yaml" → "/v1/users/{user_id}/tickets/{ticket_id}/close"
    """
    ref_map = {}
    try:
        data = _load_yaml(openapi_path)
        for http_path, path_item in (data.get("paths", {}) or {}).items():
            if not isinstance(path_item, dict):
                continue
            if "$ref" in path_item:
                ref_map[_normalize_ref(path_item["$ref"])] = http_path
            else:
                for method_item in path_item.values():
                    if isinstance(method_item, dict) and "$ref" in method_item:
                        ref_map[_normalize_ref(method_item["$ref"])] = http_path
    except Exception as e:
        print(f"[WARN] Không đọc được openapi.yaml: {e}")
    return ref_map


def _read_method_from_yaml(yaml_path: Path) -> str:
    """Đọc method từ YAML output. Format: { method: { ... } }"""
    http_methods = {"get", "post", "put", "patch", "delete", "head", "options"}
    try:
        data = _load_yaml(yaml_path)
        for key in data:
            if key.lower() in http_methods:
                return key.lower()
    except Exception:
        pass
    return ""


def _path_priority_score(file_path: str, rules: dict, source_root: str) -> int:
    """
    Tính điểm theo vị trí file source.
    source_root đọc từ import_flow.yaml, không hardcode.
    """
    p        = file_path or ""
    priority = rules.get("path_priority", {})
    if source_root and source_root in p:
        rel = p[p.index(source_root) + len(source_root):].lstrip("/")
        if "/" in rel:
            return priority.get("canonical_module_folder", 100)
        return priority.get("source_root", 50)
    if Path(p).is_absolute():
        return priority.get("external_absolute_path", 20)
    return priority.get("source_root", 50)


def _format_priority_score(source_format: str, rules: dict) -> int:
    fmt = (source_format or "").lower()
    return rules.get("source_format_priority", {}).get(fmt, 30)


def _confidence_score(entry: dict, rules: dict, source_root: str) -> float:
    """Normalize về 0.0–1.0. Max = (max_format + max_path) / max_total"""
    fmt_score  = _format_priority_score(entry.get("source_format", ""), rules)
    path_score = _path_priority_score(entry.get("path", ""), rules, source_root)
    max_total  = (
        max(rules.get("source_format_priority", {1: 1}).values(), default=100) +
        max(rules.get("path_priority", {1: 1}).values(), default=100)
    )
    return round((fmt_score + path_score) / max_total, 4)


def _suggest_winner(sources: list, rules: dict, source_root: str) -> tuple:
    scored = sorted(
        [(s, _confidence_score(s, rules, source_root)) for s in sources],
        key=lambda x: x[1],
        reverse=True,
    )
    winner, winner_score = scored[0]
    loser,  loser_score  = scored[1] if len(scored) > 1 else (scored[0][0], scored[0][1])

    reasons = []
    if winner.get("source_format") != loser.get("source_format"):
        reasons.append(f"{winner.get('source_format')} preferred over {loser.get('source_format')}")
    if winner.get("version") == loser.get("version"):
        reasons.append("same version")
    if winner_score > loser_score:
        reasons.append(f"higher confidence ({winner_score} vs {loser_score})")

    return winner.get("file", ""), reasons, winner_score


def detect(module=None) -> dict:
    rules_cfg   = _load_yaml(MERGE_RULES_PATH).get("merge_rules", {})
    flow_cfg    = _load_yaml(IMPORT_FLOW_PATH)
    versions    = _load_json(VERSIONS_PATH)
    ref_to_path = _build_ref_to_path_map(OPENAPI_PATH)
    thresholds  = rules_cfg.get("thresholds", {"auto_resolve": 0.90, "review": 0.50})
    source_root = flow_cfg.get("source_root", "")

    by_output   = defaultdict(list)
    by_endpoint = defaultdict(list)
    by_basename = defaultdict(list)

    for key, entry in versions.items():
        if not isinstance(entry, dict):
            continue
        if entry.get("status") != "success":
            continue
        if module and entry.get("module") != module:
            continue

        output = _normalize_project_path(entry.get("output", ""))
        if not output:
            continue

        source_entry = {
            "file":          entry.get("file", ""),
            "path":          entry.get("path", ""),
            "source_format": entry.get("source_format", ""),
            "version":       entry.get("version", ""),
            "output":        output,
            "module":        entry.get("module", ""),
            "method":        (entry.get("method") or "").lower(),
            "http_path":     entry.get("http_path", ""),
        }

        by_output[output].append(source_entry)

        basename = _normalize_basename(entry.get("file", ""))
        by_basename[basename].append(source_entry)

        method = source_entry.get("method", "")
        http_path = source_entry.get("http_path", "")

        # Fallback cũ nếu file_versions.json chưa có method/http_path
        if not method or not http_path:
            http_path = ref_to_path.get(_normalize_ref(output), "")
            method = _read_method_from_yaml(ROOT / output)

        if method and http_path:
            endpoint_key = (
                source_entry.get("module", ""),
                method.lower(),
                http_path,
            )
            by_endpoint[endpoint_key].append({
                **source_entry,
                "method": method.lower(),
                "http_path": http_path,
            })

    conflicts = []
    counts    = defaultdict(int)

    # --- output_collision ---
    for output_path, sources in by_output.items():
        if len(sources) < 2:
            continue
        
        Normalized_basenames = {
            _normalize_basename(s.get("file", ""))
            for s in sources
        }
        if len(Normalized_basenames) == 1:
            continue

        ct = "output_collision"
        counts[ct] += 1
        winner_file, reasons, score = _suggest_winner(sources, rules_cfg, source_root)
        conflicts.append({
            "conflict_id":        Path(output_path).stem,
            "conflict_type":      ct,
            "severity":           rules_cfg.get("conflict_types", {}).get(ct, {}).get("severity", "high"),
            "module":             sources[0].get("module", ""),
            "output":             output_path,
            "sources":            sources,
            "confidence_score":   score,
            "suggested_winner":   winner_file,
            "reason":             reasons,
            "requires_review":    True,
            "recommended_action": "review_suggested_winner",
        })

    # --- endpoint_collision ---
    for endpoint_key, sources in by_endpoint.items():
        if len(sources) < 2:
            continue

        module_name, method, hpath = endpoint_key

        outputs = [s.get("output") for s in sources]
        if len(set(outputs)) == 1:
            continue  # cùng output → đã detect ở output_collision

        ct = "endpoint_collision"
        counts[ct] += 1

        winner_file, reasons, score = _suggest_winner(sources, rules_cfg, source_root)

        cid = (
            f"{module_name}_{method}_"
            f"{hpath.strip('/').replace('/', '_').replace('{','').replace('}','')}"
        )
        
        conflicts.append({
            "conflict_id":        cid,
            "conflict_type":      ct,
            "severity":           rules_cfg.get("conflict_types", {}).get(ct, {}).get("severity", "medium"),
            "module":             module_name,
            "method":             method,
            "path":               hpath,
            "outputs":            list(set(outputs)),
            "sources":            sources,
            "confidence_score":   score,
            "suggested_winner":   winner_file,
            "reason":             reasons,
            "requires_review":    True,
            "recommended_action": "review_suggested_winner",
        })

    # --- duplicate_import ---
    for basename, sources in by_basename.items():
        if len(sources) < 2:
            continue
        ct = "duplicate_import"
        counts[ct] += 1
        winner_file, reasons, score = _suggest_winner(sources, rules_cfg, source_root)
        auto_ok    = rules_cfg.get("conflict_types", {}).get(ct, {}).get("auto_resolve", False)
        req_review = not (auto_ok and score >= thresholds.get("auto_resolve", 0.90))
        conflicts.append({
            "conflict_id":        f"dup_{basename[:40]}",
            "conflict_type":      ct,
            "severity":           rules_cfg.get("conflict_types", {}).get(ct, {}).get("severity", "low"),
            "module":             sources[0].get("module", ""),
            "sources":            sources,
            "confidence_score":   score,
            "suggested_winner":   winner_file,
            "reason":             reasons,
            "requires_review":    req_review,
            "recommended_action": "keep_canonical_path" if not req_review else "review_suggested_winner",
        })

    auto_resolvable = sum(1 for c in conflicts if not c["requires_review"])
    needs_review    = sum(1 for c in conflicts if c["requires_review"])
    report = {
        "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "summary": {
            "total_conflicts":    len(conflicts),
            "duplicate_import":   counts["duplicate_import"],
            "endpoint_collision": counts["endpoint_collision"],
            "output_collision":   counts["output_collision"],
            "auto_resolvable":    auto_resolvable,
            "requires_review":    needs_review,
        },
        "conflicts": conflicts,
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[conflict_detector] Ghi report: {REPORT_PATH}")
    return report

def main():
    print("[conflict_detector] Bắt đầu detect conflicts...")
    report = detect()

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    s = report["summary"]
    print(f"  total_conflicts:    {s['total_conflicts']}")
    print(f"  duplicate_import:   {s['duplicate_import']}")
    print(f"  endpoint_collision: {s['endpoint_collision']}")
    print(f"  output_collision:   {s['output_collision']}")
    print(f"  auto_resolvable:    {s['auto_resolvable']}")
    print(f"  requires_review:    {s['requires_review']}")
    print(f"[conflict_detector] Ghi report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
