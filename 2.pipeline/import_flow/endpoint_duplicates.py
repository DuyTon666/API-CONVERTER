# endpoint_duplicates.py
# Print các file có cùng endpont
# Kiểm tra endpoint ấy có cùng chức năng hay không

import argparse
import re
import sys

from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PIPELINE_DIR = ROOT / "2.pipeline"
SOURCE_ROOT = ROOT / "1.docs/source/api_contract"

sys.path.insert(0, str(PIPELINE_DIR))

try:
    from converters.docx.reader import read_docx, read_text
    from converters.pdf.reader import read_pdf
    from converters.docx.parser import parse_text
except Exception as exc:
    print(f"[ERROR] Không import được parser/reader: {exc}", file=sys.stderr)
    sys.exit(2)

try:
    from import_flow.scanner import normalize_http_path
except Exception:
    normalize_http_path = None


SUPPORTED_EXTS = {".docx", ".pdf", ".txt", ".md"}
HTTP_METHOD = {"GET", "POST", "PUT", "PATCH", "DELETE"}


def _read_source(path: Path) -> str:
    ext = path.suffix.lower()

    if ext == ".docx":
        return str(read_docx(str(path)) or "")

    if ext == ".pdf":
        return str(read_pdf(str(path)) or "")

    if ext in (".txt", ".md"):
        try:
            return str(read_text(str(path)) or "")
        except Exception:
            return path.read_text(encoding="utf-8", errors="ignore")

    return ""


def _get_attr(obj, name, default=None):
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _parse_operation(text: str, source_file: str):
    try:
        try:
            op = parse_text(text, source_file=source_file)
        except TypeError:
            op = parse_text(text)

        method = _get_attr(op, "method")
        path = _get_attr(op, "path")
        operation_id = _get_attr(op, "operation_id") or _get_attr(op, "operation_id")
        summary = _get_attr(op, "summary")  
        version = _get_attr(op, "version")

        if method and path:
            return {
                "method" : str(method).upper().strip(),
                "path"   : str(path).strip(),
                "operation_id": str(operation_id or "").strip(),
                "summary": str(summary or "").strip(),
                "version": str(version or "").strip(),
            }

    except Exception:
        pass

    return _fallback_extract_operation(text)


def _fallback_extract_operation(text: str):
    # Fallback nhẹ nếu parse_text không lấy được method/path.
    # Bắt các pattern kiểu: GET /v1/..., POST https://domain/v1/...
    pattern = re.compile(
        r"\b(GET|POST|PUT|PATCH|DELETE)\b\s+((?:https?://[^/\s]+)?/[^\s|,;]+)",
        re.IGNORECASE,
    )

    m = pattern.search(text or "")
    if not m:
        return None

    method = m.group(1).upper()
    path = m.group(2).strip()

    path = re.sub(r"^https?://[^/]+", "", path)
    path = path.split("?")[0].strip()

    return {
        "method": method,
        "path": path,
        "operation_id": "",
        "summary": "",
        "version": "",
    }


def _local_normalize_path(path: str) -> str:
    path = str(path or "").strip()
    path = re.sub(r"^https?://[^/]+", "", path)
    path = path.split("?")[0].strip()
    path = re.sub(r"/+", "/", path)

    # Normalize numeric sample IDs: /23/456 -> /{}/{}
    parts = []
    for part in path.split("/"):
        if re.fullmatch(r"\d+", part or ""):
            parts.append("{}")
        else:
            parts.append(part)

    normalized = "/".join(parts)
    if not normalized.startswith("/"):
        normalized = "/" + normalized
    return normalized


def _normalize_path(path: str) -> str:
    if normalize_http_path:
        try:
            return str(normalize_http_path(path)).strip()
        except Exception:
            pass
    return _local_normalize_path(path)


def _module_from_path(path: Path) -> str:
    try:
        rel = path.relative_to(SOURCE_ROOT)
    except ValueError:
        return "_unknow"

    if len(rel.parts) >= 2:
        return rel.parts[0]
    return "_root"


def _iter_files(module: str | None):
    if module: 
        base = SOURCE_ROOT / module
        if not base.exists():
            return []
        return sorted(
            p for p in base.rglob("*")
            if p.is_file()
            and p.suffix.lower() in SUPPORTED_EXTS
            and not o.name.startswith("~$")
        )

    return sorted(
        p for p in SOURCE_ROOT.rglob("*")
        if p.is_file()
        and p.suffix.lower() in SUPPORTED_EXTS
        and not p.name.startswith("~$")
    )


def collect(module: str | None,  cross_module: bool, verbose_errors: bool):
    groups = defaultdict(list)
    errors = []
    scanned = 0
    parsed = 0

    for path in _iter_files(module):
        scanned += 1
        current_module = _module_from_path(path)

        try:
            text = _read_source(path)
            op = _parse_operation(text, path.name)

            if not op:
                errors.append((path, "Không parse được method/path"))
                continue

            method = str(op["method"]).upper().strip()
            raw_path = str(op["path"]).strip()

            if method not in HTTP_METHOD or not raw_path:
                errors.append((path, f"Method/path không hợp lệ: {method} {raw_path}"))
                continue

            normalized_path = _normalize_path(raw_path)

            if cross_module:
                key = (method, normalized_path)
            else:
                key = (current_module, method, normalized_path)

            groups[key].append({
                "module": current_module,
                "file": path.name,
                "path": str(path.relative_to(ROOT)),
                "method": method,
                "raw_path": raw_path,
                "normalized-path": normalized_path,
                "operation_id": op.get("operation_id") or "",
                "summary": op.get("summary") or "",
                "version": op.get("version") or "",
                "ext": path.suffix.lower(),
            })
            parsed += 1

        except Exception as exc:
            errors.append((path, str(exc)))

    duplicate_groups = {
        key: items
        for key, items in groups.items()
        if len(items) > 1
    }

    return {
        "scanned": scanned,
        "parsed": parsed,
        "groups": duplicate_groups,
        "errors": errors,
        "verbose_errors": verbose_errors,
    }


def print_report(result, cross_module: bool):
    groups = result["groups"]

    print (f"Scanned files             : {result['scanned']}")
    print (f"Parsed endpoint files     : {result['parsed']}")
    print (f"Duplicate endpoint groups : {len(groups)}")

    if not groups:
        print("OK: không có file nào cùng endpoint.")
    else:
        for key in sorted(groups.keys(), key=lambda x: str(x)):
            items = groups[key]

            if cross_module:
                method, normalized_path = key
                title = f"{method} {normalized_path}"
            else:
                module, method, normalized_path = key
                title = f"[{module}] {method} {normalized_path}"

            print("")
            print(f"- {title} | files={len(items)}-")

            for idx, item in enumerate(sorted(items, key=lambda x: x["path"]), 1):
                version = f" | version={item['version']}" if item ["version"] else ""
                opid = f"    | operationId={item['operationa_id']}" if item["operation_id"] else ""
                summary = f" | summary={item['summary']}" if item["summary"] else ""

                print(f"[{idx:02d}] {item['path']}")
                print(f"     raw      : {item['method']} {item['raw_path']}{version}{opid}")
                if summary:
                    print(f"     {summary}")

    if result["verbose_errors"] and result["errors"]:
        print("")
        print(f"- Parse errors: {len(result['errors'])}")
        for path, reason in result["errors"]:
            print(f"- {path.relative_to(ROOT)}: (reason)")


def main():
    parser = argparse.ArgumentParser(
        description="In ra các source files có cùng HTTP method + normalized endpoint."
    )
    parser.add_argument("--module", default=None, help="Chỉ scan 1 module, ví dụ ticket/order/admin")
    parser.add_argument(
        "--cross-module",
        action="store_true",
        help="Group endpoint trùng giữa tất cả module, không tách theo module.",
    )
    parser.add_argument(
        "--verbose-errors",
        action="store_true",
        help="In các file không parse được method/path.",
    )

    args = parser.parse_args()

    result = collect(
        module=args.module,
        cross_module=args.cross_module,
        verbose_errors=args.verbose_errors,
    )
    print_report(result, cross_module=args.cross_module)


if __name__ == "__main__":
    main()