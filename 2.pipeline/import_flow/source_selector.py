import json
import re
import inspect
from pathlib import Path
from datetime import datetime

import yaml

from converters.docx.reader import read_docx, read_text
from converters.pdf.reader import read_pdf
from converters.docx.parser import parse_text
from import_flow.scanner import normalize_http_path


ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "4.config/merge_rules.yaml"
_PDF_CONFIG = str(ROOT / "4.config" / "sources" / "pdf_sections.yaml")

def _load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}

    raw = path.read_text(encoding="utf-8").strip()
    return yaml.safe_load(raw) if raw else {}


def _source_selection_config() -> dict:
    cfg = _load_yaml(CONFIG_PATH)
    return cfg.get("source_selection", {})


def _report_path(cfg: dict) -> Path:
    path = cfg.get("report", {}).get(
        "path",
        "3.build/reports/source_selection_report.json",
    )
    return ROOT / path


def _allowed_extensions(cfg: dict) -> set[str]:
    return set(cfg.get("allowed_extensions", [".pdf", ".docx", ".txt", ".md"]))


def _source_format(path: Path, cfg: dict) -> str:
    name = path.name.lower()

    strip_exts = (
        cfg.get("filename_normalization", {})
        .get("strip_extensions", [])
    )

    for ext in sorted(strip_exts, key=len, reverse=True):
        ext = ext.lower()
        if name.endswith(ext):
            if ext == ".docx.pdf":
                return "pdf"
            return ext.lstrip(".")

    return path.suffix.lower().strip(".")


def _read_source(path: Path) -> str:
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        return read_pdf(str(path), _PDF_CONFIG)

    if suffix == ".docx":
        return read_docx(str(path))

    return read_text(str(path))


def _parse_operation(text: str, module: str):
    sig = inspect.signature(parse_text)

    if "module" in sig.parameters:
        return parse_text(text, module=module)

    return parse_text(text)


def _normalize_name(path: Path, cfg: dict) -> str:
    norm_cfg = cfg.get("filename_normalization", {})
    name = path.name.lower()

    strip_exts = norm_cfg.get("strip_extensions", [])

    for ext in sorted(strip_exts, key=len, reverse=True):
        ext = ext.lower()
        if name.endswith(ext):
            name = name[: -len(ext)]
            break

    for pattern in norm_cfg.get("strip_prefix_patterns", []):
        name = re.sub(pattern, "", name, flags=re.IGNORECASE)

    for item in norm_cfg.get("replace_patterns", []):
        pattern = item.get("pattern", "")
        repl = item.get("repl", "")
        if pattern:
            name = re.sub(pattern, repl, name)

    return name.strip()


def _identity_for_file(path: Path, module: str, cfg: dict) -> tuple[str, dict]:
    meta = {
        "file": path.name,
        "path": str(path),
        "source_format": _source_format(path, cfg),
        "method": "",
        "http_path": "",
        "identity_type": "",
        "identity": "",
        "parse_error": "",
    }

    strategies = cfg.get("identity_strategy_order", ["endpoint", "normalized_name"])

    if "endpoint" in strategies:
        try:
            text = _read_source(path)
            op = _parse_operation(text, module)

            method = (getattr(op, "method", "") or "").lower()
            http_path = normalize_http_path(getattr(op, "path", "") or "")

            if method and http_path:
                identity = f"{module}:{method}:{http_path}"
                meta.update({
                    "method": method,
                    "http_path": http_path,
                    "identity_type": "endpoint",
                    "identity": identity,
                })
                return identity, meta

        except Exception as e:
            meta["parse_error"] = str(e)

    if "normalized_name" in strategies:
        normalized = _normalize_name(path, cfg)
        identity = f"{module}:name:{normalized}"
        meta.update({
            "identity_type": "normalized_name",
            "identity": identity,
        })
        return identity, meta

    identity = f"{module}:path:{path.name}"
    meta.update({
        "identity_type": "path",
        "identity": identity,
    })
    return identity, meta


def _format_priority(source_format: str, full_cfg: dict) -> int:
    priority = (
        full_cfg.get("merge_rules", {})
        .get("source_format_priority", {})
    )
    return int(priority.get(source_format, 0))


def _choose_winner(items: list[dict], full_cfg: dict) -> dict:
    return sorted(
        items,
        key=lambda x: (
            -_format_priority(x["source_format"], full_cfg),
            len(x["file"]),
            x["file"],
        ),
    )[0]


def _should_auto_dedup(items: list[dict], cfg: dict) -> bool:
    auto = cfg.get("auto_dedup", {})

    if not auto.get("enabled", True):
        return False

    if len(items) <= 1:
        return False

    if auto.get("only_when_different_formats", True):
        formats = {x.get("source_format") for x in items}
        if len(formats) <= 1:
            return False

    if auto.get("require_same_endpoint_if_available", True):
        endpoint_items = [
            x for x in items
            if x.get("identity_type") == "endpoint"
        ]

        if endpoint_items:
            endpoints = {
                (x.get("method"), x.get("http_path"))
                for x in endpoint_items
            }

            if len(endpoints) > 1:
                return False

    return True


def select_canonical_sources(files: list[Path], module: str) -> dict:
    cfg = _source_selection_config()

    if not cfg.get("enabled", True):
        return {
            "selected_files": [Path(p) for p in files],
            "skipped_duplicates": [],
            "duplicate_groups": [],
            "unresolved_groups": [],
            "report_path": "",
        }

    full_cfg = _load_yaml(CONFIG_PATH)
    allowed = _allowed_extensions(cfg)

    files = [
        Path(p) for p in files
        if Path(p).suffix.lower() in allowed
    ]

    groups: dict[str, list[dict]] = {}

    for file_path in files:
        identity, meta = _identity_for_file(file_path, module, cfg)
        groups.setdefault(identity, []).append(meta)

    selected_files: list[str] = []
    skipped_duplicates: list[dict] = []
    duplicate_groups: list[dict] = []
    unresolved_groups: list[dict] = []

    for identity, items in groups.items():
        if len(items) == 1:
            selected_files.append(items[0]["path"])
            continue

        if not _should_auto_dedup(items, cfg):
            selected_files.extend([x["path"] for x in items])
            unresolved_groups.append({
                "identity": identity,
                "reason": "not_safe_to_auto_dedup_by_config",
                "files": items,
            })
            continue

        winner = _choose_winner(items, full_cfg)
        selected_files.append(winner["path"])

        losers = [
            x for x in items
            if x["path"] != winner["path"]
        ]

        duplicate_groups.append({
            "identity": identity,
            "winner": winner,
            "losers": losers,
        })

        for loser in losers:
            skipped_duplicates.append({
                "file": loser["file"],
                "path": loser["path"],
                "source_format": loser["source_format"],
                "identity": identity,
                "winner_file": winner["file"],
                "reason": "duplicate_source_pre_import",
            })

    report = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "module": module,
        "total_input_files": len(files),
        "selected_count": len(selected_files),
        "skipped_duplicate_count": len(skipped_duplicates),
        "duplicate_groups": duplicate_groups,
        "unresolved_groups": unresolved_groups,
        "skipped_duplicates": skipped_duplicates,
    }

    report_path = _report_path(cfg)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    existing = []
    if report_path.exists():
        try:
            old = json.loads(report_path.read_text(encoding="utf-8"))
            existing = old.get("runs", [])
        except Exception:
            existing = []

    existing.append(report)

    report_path.write_text(
        json.dumps({"runs": existing}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return {
        "selected_files": [Path(p) for p in selected_files],
        "skipped_duplicates": skipped_duplicates,
        "duplicate_groups": duplicate_groups,
        "unresolved_groups": unresolved_groups,
        "report_path": str(report_path),
    }