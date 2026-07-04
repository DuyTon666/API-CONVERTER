"""
Đọc file_versions.json, sinh đoạn paths: chuẩn OpenAPI để merge vào openapi.yaml.
Output: 6.path_stub/path_stubs.yaml

Chạy:
    python3 6.path_stub/generate_path_stubs.py
    python3 6.path_stub/generate_path_stubs.py --module ticket
    python3 6.path_stub/generate_path_stubs.py --dry-run
"""
from __future__ import annotations

import re
import argparse
import json
from pathlib import Path

import yaml

_HERE = Path(__file__).resolve().parent
PROJECT_ROOT = _HERE.parent
VERSIONS_PATH = PROJECT_ROOT / "3.build/reports/file_versions.json"
OPENAPI_ROOT = PROJECT_ROOT / "5.openapi"
OUTPUT_PATH = _HERE / "path_stubs.yaml"
OPENAPI_YAML_PATH = OPENAPI_ROOT / "openapi.yaml"
OBSERVATIONS_PATH = PROJECT_ROOT / "3.build/reports/module_observations.json"


def _to_ref(output_path: str) -> str | None:
    """Chuyển absolute output path → $ref tương đối từ 5.openapi/."""
    candidate = Path(output_path)
    if not candidate.is_absolute():
        candidate = PROJECT_ROOT / candidate
    if not candidate.exists():
        return None
    try:
        rel = candidate.relative_to(OPENAPI_ROOT)
        return f"./{rel}"
    except ValueError:
        return None


def _normalize_http_path(http_path: str) -> str:
    """Chuẩn hóa {} placeholder — giữ nguyên, openapi.yaml dùng {param_name}."""
    # file_versions dùng {} — giữ nguyên để người review đặt tên param
    return http_path


def generate_stubs(module_filter: str | None = None) -> dict:
    """Đọc file_versions.json, trả về dict paths: chuẩn OpenAPI."""
    if not VERSIONS_PATH.exists():
        raise FileNotFoundError(f"Không tìm thấy: {VERSIONS_PATH}")

    versions = json.loads(VERSIONS_PATH.read_text(encoding="utf-8"))
    path_lookup = _build_path_lookup()
    paths: dict = {}

    def _entry_endpoint_key(entry: dict) -> tuple[str, str] | None:
        raw_path = entry.get("http_path", "").strip()
        http_path = path_lookup.get(raw_path, raw_path)
        method = entry.get("method", "").strip().lower()

        if not http_path or not method:
            return None

        return (http_path, method)

    valid_endpoint_keys = set()
    for entry in versions.values():
        if entry.get("status") != "success":
            continue

        if module_filter and entry.get("module") != module_filter:
            continue

        output = entry.get("output", "")
        endpoint_key = _entry_endpoint_key(entry)

        if endpoint_key and output and _to_ref(output):
            valid_endpoint_keys.add(endpoint_key)

    skipped = []
    for key, entry in versions.items():
        if entry.get("status") != "success":
            skipped.append((entry.get("file"), "status != success"))
            continue

        if module_filter and entry.get("module") != module_filter:
            continue

        raw_path = entry.get("http_path", "").strip()
        http_path = path_lookup.get(raw_path, raw_path)
        method = entry.get("method", "").strip().lower()
        output = entry.get("output", "")

        if not http_path or not method or not output:
            skipped.append((entry.get("file"), "thiếu http_path/method/output"))
            continue

        ref = _to_ref(output)
        if not ref:
            if (http_path, method) in valid_endpoint_keys:
                continue

            skipped.append((entry.get("file"), f"output không tồn tại: {output}"))
            continue

        if http_path not in paths:
            paths[http_path] = {}

        paths[http_path][method] = ref

    output_paths = {}
    for http_path, methods in paths.items():
        if len(methods) == 1:
            method, ref = next(iter(methods.items()))
            output_paths[http_path] = {"$ref": ref}
        else:
            output_paths[http_path] = {
                m: {"$ref": f"{r}#/{m}"}
                for m, r in methods.items()
            }

    return {"paths": output_paths, "_skipped": skipped}
    

def _build_path_lookup() -> dict[str, str]:
    """
    Trả về dict: normalized_path (dùng {}) → full_path (có param name).
    Ví dụ: "/v1/users/{}/tickets/{}" → "/v1/users/{user_id}/tickets/{id}"
    """
    if not OBSERVATIONS_PATH.exists():
        return {}
    obs = json.loads(OBSERVATIONS_PATH.read_text(encoding="utf-8"))
    lookup = {}
    for module_data in obs.values():
        for endpoint in module_data.get("endpoints", []):
            normalized = re.sub(r"\{[^}]+\}", "{}", endpoint)
            lookup[normalized] = endpoint
    return lookup


def merge_into_openapi(dry_run: bool = False) -> None:
    """Thay toàn bộ section paths: trong openapi.yaml bằng nội dung từ path_stubs.yaml."""
    if not OUTPUT_PATH.exists():
        raise FileNotFoundError(f"Chưa có path_stubs.yaml - chạy generate trước: {OUTPUT_PATH}")
    if not OPENAPI_YAML_PATH.exists():
        raise FileNotFoundError(f"Không tìm thấy openapi.yaml: {OPENAPI_YAML_PATH}")

    stubs = yaml.safe_load(OUTPUT_PATH.read_text(encoding="utf-8")) or {}
    new_paths = stubs.get("paths", {})

    openapi = yaml.safe_load(OPENAPI_YAML_PATH.read_text(encoding="utf-8")) or {}
    old_count = len(openapi.get("paths", {}))
    openapi["paths"] = new_paths

    out_yaml = yaml.dump(openapi, allow_unicode=True, sort_keys=False, indent=2)

    if dry_run:
        print(out_yaml)
    else:
        OPENAPI_YAML_PATH.write_text(out_yaml, encoding="utf-8")
        print(f"[path_stub] Đã merge vào: {OPENAPI_YAML_PATH}")

    print(f"[path_sub] Paths cũ: {old_count} -> mới: {len(new_paths)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Sinh path stubs cho openapi.yaml")
    parser.add_argument("--module", help="Chỉ sinh stub cho module này")
    parser.add_argument("--dry-run", action="store_true", help="in ra stdout, không ghi file")
    parser.add_argument("--merge", action="store_true", help="Merge path_stubs.yaml vào openapi.yaml")
    args = parser.parse_args()

    if args.merge:
        merge_into_openapi(dry_run=args.dry_run)
        return

    result = generate_stubs(module_filter=args.module)
    skipped = result.pop("_skipped", [])
    out_yaml = yaml.dump(result, allow_unicode=True, sort_keys=False, indent=2)

    if args.dry_run:
        print(out_yaml)
    else:
        OUTPUT_PATH.write_text(out_yaml, encoding="utf-8")
        print(f"[path_stub] Đã ghi: {OUTPUT_PATH}")

    print(f"[path_stub] Tổng paths: {len(result.get('paths', {}))}")
    if skipped:
        print(f"[path_stub] Skipped: {len(skipped)}")
        for file,reason in skipped:
            print(f"    - {file}: {reason}")

if __name__ == "__main__":
    main()