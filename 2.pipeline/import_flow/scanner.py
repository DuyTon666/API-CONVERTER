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
    Normalize http_path để so sánh endpoint:
    - bỏ domain nếu có
    - bỏ query string
    - {id}, {user_id}, {certId} -> {}
    - sample numeric id như /23/456 -> /{}/{}
    """
    path = str(path or "").strip()
    path = re.sub(r"^https?://[^/]+", "", path)
    path = path.split("?")[0].strip()
    path = path.rstrip(".,;:)]\"'")
    path = re.sub(r"/+", "/", path)

    parts = []
    for part in path.split("/"):
        if re.fullmatch(r"\{[^/{}]+\}", part or ""):
            parts.append("{}")
        elif re.fullmatch(r"\d+", part or ""):
            parts.append("{}")
        else:
            parts.append(part)

    normalized = "/".join(parts)
    if not normalized.startswith("/"):
        normalized = "/" + normalized
    return normalized


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


def primary_endpoint(file_path: Path) -> tuple[str, str] | None:
    """
    Lấy endpoint chính của API contract.
    Chỉ dùng parser chính, không scan toàn bộ nội dung file.
    """
    try:
        text, _ = read_contract(file_path)

        try:
            parsed = parse_text(text, source_file=file_path.name)
        except TypeError:
            parsed = parse_text(text)

        if isinstance(parsed, dict):
            method = parsed.get("method")
            path = parsed.get("path")
        else:
            method = getattr(parsed, "method", None)
            path = getattr(parsed, "path", None)

        if not method or not path:
            return None

        method = str(method).upper().strip()
        path = str(path).strip()

        if method not in _HTTP_METHODS:
            return None

        return method, path

    except Exception as e:
        print(f"    [WARN] primary_endpoint: Không parse được {file_path.name}: {e}")
        return None


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

        endpoint = primary_endpoint(file_path)
        if not endpoint:
            continue

        method, raw_path = endpoint
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