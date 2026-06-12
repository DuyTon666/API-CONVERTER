# 2.pipeline/import_flow/scanner.py
import sys
import re
import unicodedata
from pathlib import Path

from converters.pdf.reader import read_pdf
from converters.docx.reader import read_docx, read_text
from converters.docx.parser import parse_text
from module_resolution import parse_endpoint

from import_flow.config import (
    PDF_CONFIG,
    load_import_config,
    get_source_root,
    supported_extensions,
    ignore_dirs,
)

def normalize_http_path(path: str) -> str:
    """
    Normalize param name trong http_path về {} để so sánh nhất quán.
    /v1/users/{user_id}/tickets/{id} → /v1/users/{}/tickets/{}
    """
    return re.sub(r"\{[^}]+\}", "{}", path)

def read_contract(file_path: Path) -> tuple[str, str]:
    ext = file_path.suffix.lower()
    if ext == ".pdf":
        return read_pdf(str(file_path), str(PDF_CONFIG)), "pdf"
    if ext == ".docx":
        return read_docx(str(file_path)), "docx"
    if ext in (".txt", ".md"):
        return read_text(str(file_path)), ext.strip(".")
    raise ValueError(f"Unsupported file type: {ext}")


def parse_segments(endpoint: str, ignored_segments: list[str]) -> list[str]:
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


def scan_source_root(
    source_root: Path,
    extensions: list[str],
    ignore: set[str],
) -> dict:
    if not source_root.exists():
        print(f"[ERROR] Không tìm thấy source_root: {source_root}")
        sys.exit(1)

    modules    = []
    unassigned = []

    for item in sorted(source_root.iterdir()):
        if item.is_dir():
            if item.name in ignore:
                continue
            files = [
                f for f in sorted(item.iterdir())
                if f.is_file() and f.suffix.lower() in extensions
            ]
            modules.append({"name": item.name, "path": item, "files": files})

        elif item.is_file():
            if item.suffix.lower() in extensions:
                unassigned.append(item)

    return {"modules": modules, "unassigned": unassigned}

_HTTP_METHODS = {"GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"}

_RE_INLINE = re.compile(
    r"\b(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)\s+(/[^\s\"'<>]+)",
    re.IGNORECASE,
)

_RE_TAB_CELL = re.compile(
    r"^(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)\t(/[^\t\n\"'<>]+)",
    re.IGNORECASE | re.MULTILINE,
)

def light_parse(file_path: Path) -> list[tuple[str,str]]:
    try:
        ext = file_path.suffix.lower()
        if ext == ".pdf":
            text = read_pdf(str(file_path), str(PDF_CONFIG))
        elif ext == ".docx":
            text = read_docx(str(file_path))
        elif ext in (".txt", ".md"):
            text = read_text(str(file_path))
        else:
            return[]
    except Exception as e:
        print(f"    [WARN] light_parse: Không đọc được {file_path.name}: {e}")
        return []

    result: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def _add(method: str, path: str) -> None:
        key = (method.upper(), path.strip())
        if key not in seen:
            seen.add(key)
            result.append(key)

    for m in _RE_INLINE.finditer(text):
        _add(m.group(1), m.group(2))

    for m in _RE_TAB_CELL.finditer(text):
        _add(m.group(1), m.group(2))

    return result

def scan_for_collisions(
    module_path: Path, extensions: list[str],
) -> list[dict]:

    if not module_path.is_dir():
        return []

    index: dict[str, list[tuple[Path, str]]] = {}

    for file_path in sorted(module_path.iterdir()):
        if not file_path.is_file():
            continue
        if file_path.suffix.lower() not in extensions:
            continue

        endpoints = light_parse(file_path)
        for method, raw_path in endpoints:
            norm_key = f"{method}:{normalize_http_path(raw_path)}"
            index.setdefault(norm_key, []).append((file_path, f"{method} {raw_path}"))

    collisions = []
    for key, entries in index.items():
        files_seen: dict[Path, str] = {}
        for fp, raw in entries:
            if fp not in files_seen:
                files_seen[fp] = raw

        if len(files_seen) >= 2:
            collisions.append({
                "key": key,
                "files": [str(fp) for fp in files_seen],
                "raw_paths": list(files_seen.values())
            })

    return collisions