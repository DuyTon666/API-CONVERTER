import sys
import argparse
import re
import unicodedata
from datetime import datetime
from pathlib import Path

import yaml

sys.path.insert(0, "2.pipeline")

from converters.docx.reader import read_docx, read_text
from converters.pdf.reader import read_pdf
from converters.docx.parser import parse_text
from import_flow.scanner import normalize_http_path

from enrichers.llm_enricher import enrich
from generator.emitter import (
    emit_yaml,
    emit_request_schema,
    emit_response_schemas,
    init_config,
)

from utils.report_store import (
    load_versions,
    save_versions,
    append_version_history,
    load_review_queue,
    save_review_queue,
    write_batch_log,
)

from module_resolution import (
    parse_endpoint,
    suggest_module,
    append_observation,
    append_module_approval,
)


CONFIG_DIR = Path(__file__).resolve().parent.parent / "4.config"
PDF_CONFIG = CONFIG_DIR / "sources" / "pdf_sections.yaml"
MODULE_RESOLUTION_CONFIG = CONFIG_DIR / "module_resolution.yaml"


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _to_snake_case(name: str) -> str:
    name = re.sub(r"([A-Z])", r"_\1", name)
    name = re.sub(r"[^a-zA-Z0-9]+", "_", name)
    return name.strip("_").lower()


def _normalize_filename(file_name: str) -> str:
    name = Path(file_name).stem
    name = re.sub(r"\.docx$", "", name, flags=re.IGNORECASE)

    name = re.sub(r"^API Contract\s*-\s*", "", name, flags=re.IGNORECASE)
    name = re.sub(r"^API Service\s*-\s*", "", name, flags=re.IGNORECASE)
    name = re.sub(r"^API statistic\s*-\s*", "", name, flags=re.IGNORECASE)
    name = re.sub(r"^API\s+", "", name, flags=re.IGNORECASE)

    name = unicodedata.normalize("NFD", name)
    name = name.encode("ascii", "ignore").decode()
    name = re.sub(r"[^a-zA-Z0-9]+", "_", name)

    return name.strip("_").lower()


def _guess_action_name(op, fallback_file_name: str) -> str:
    if getattr(op, "operation_id", ""):
        return _to_snake_case(op.operation_id)

    return _normalize_filename(fallback_file_name)


def _read_contract(input_path: str) -> tuple[str, str]:
    ext = Path(input_path).suffix.lower()

    if ext == ".pdf":
        return read_pdf(input_path, str(PDF_CONFIG)), "pdf"

    if ext == ".docx":
        return read_docx(input_path), "docx"

    if ext in (".txt", ".md"):
        return read_text(input_path), ext.strip(".")

    raise ValueError(f"Định dạng chưa hỗ trợ: {ext}")


def _supported_files(input_dir: Path) -> list[Path]:
    files = []
    for ext in ("*.pdf", "*.docx", "*.txt", "*.md"):
        files.extend(input_dir.glob(ext))
    return sorted(files)


def _parse_segments(endpoint: str) -> list[str]:
    try:
        parsed = parse_endpoint(endpoint)

        if isinstance(parsed, dict):
            segments = parsed.get("segments", [])
            return segments if isinstance(segments, list) else []

        if isinstance(parsed, list):
            return parsed

    except Exception:
        pass

    return [
        s.strip("{}")
        for s in str(endpoint or "").strip("/").split("/")
        if s
    ]


def _resolve_module(op, user_selected_module: str, endpoint_rules: dict):
    endpoint = getattr(op, "path", "") or ""
    service_in_doc = getattr(op, "service", "") or ""
    segments = _parse_segments(endpoint)

    return suggest_module(
        segments=segments,
        endpoint=endpoint,
        endpoint_rules=endpoint_rules,
        service_in_doc=service_in_doc,
        user_selected=user_selected_module,
    )


def _convert_one_file(
    file_path: Path,
    output_dir: Path,
    schemas_dir: Path,
    user_selected_module: str,
    endpoint_rules: dict,
    post_enrich_checks: dict | None = None,
):
    print(f"[1/4] Đọc file: {file_path}")
    text, source_format = _read_contract(str(file_path))

    print("[2/4] Parse thông tin")
    op = parse_text(text)

    print(
        f"    method={getattr(op, 'method', '')}, "
        f"path={getattr(op, 'path', '')}, "
        f"service={getattr(op, 'service', '')}"
    )

    if not op.method or not op.path:
        raise ValueError("Không tìm thấy method hoặc path trong tài liệu.")

    resolution = _resolve_module(
        op=op,
        user_selected_module=user_selected_module,
        endpoint_rules=endpoint_rules,
    )

    final_module = resolution.final_module or user_selected_module

    # Module user chọn là context chính cho output/tag/schema.
    # Service gốc vẫn còn trong resolution.service_in_doc.
    op.service = final_module

    append_observation(
        module=final_module,
        endpoint=op.path,
    )

    append_module_approval(resolution)

    print(
        f"    module={final_module}, "
        f"conflict={resolution.conflict}, "
        f"review_type={resolution.review_type}"
    )

    print("[3/4] Gọi LLM để generate summary và operationId")
    title = file_path.stem
    op = enrich(op, title=title)

    print(f"    summary='{op.summary}', operationId='{op.operation_id}'")

    for field_name, flag in (post_enrich_checks or {}).items():
        if not getattr(op, field_name, None):
            op.review_flags.append(flag)

    output_dir.mkdir(parents=True, exist_ok=True)

    temp_name = _normalize_filename(file_path.name)
    out = output_dir / f"{temp_name}.yaml"

    print(f"[4/4] Ghi YAML: {out}")
    emit_yaml(op, str(out))

    schemas_dir.mkdir(parents=True, exist_ok=True)

    if op.has_request_body and op.request_body_fields:
        schema_name = emit_request_schema(op, str(schemas_dir))
        print(f"    Request schema: {schema_name}.yaml")

    if op.response_schemas:
        emit_response_schemas(op, str(schemas_dir))

    final_title = _guess_action_name(op, file_path.name)
    final_out = output_dir / f"{final_title}.yaml"

    if final_out != out:
        if out.exists():
            final_out.parent.mkdir(parents=True, exist_ok=True)

            if final_out.exists():
                final_out.unlink()

            out.rename(final_out)

        out = final_out

    print(f"Hoàn thành: {out}")

    return op, resolution, source_format, out


def run_batch(
    input_dir: str,
    module: str,
    output_dir: str | None = None,
    schemas_dir: str | None = None,
    files_override: list[Path] | None = None,
) -> int:

    input_path = Path(input_dir)

    output_path = Path(output_dir) if output_dir else Path("5.openapi/paths") / module
    schemas_path = Path(schemas_dir) if schemas_dir else Path("5.openapi/components/schemas") / module

    if files_override is not None:
        files = [Path(p) for p in files_override]
    else:
        files = _supported_files(input_path)

    print(f"Tìm thấy {len(files)} file API Contract (.pdf/.docx/.txt/.md)")
    print(f"Module user chọn: {module}")
    print(f"Output dir: {output_path}")
    print(f"Schemas dir: {schemas_path}")
    print()

    module_cfg = _load_yaml(MODULE_RESOLUTION_CONFIG)
    endpoint_rules = module_cfg.get("endpoint_rules", {})

    init_config(str(CONFIG_DIR))

    from generator.emitter import _CONFIG

    review_actions = _CONFIG.get("review_actions", {})
    post_enrich_checks = _CONFIG.get("post_enrich_checks", {})

    versions = load_versions()

    source_type = "api_contract"
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S") + f"_{module}_api"

    success_files = []
    skipped = []
    errors = []
    needs_review = []
    seen_endpoints: dict[str, str] = {}
    output_collisions = []

    for file_path in files:
        print(f"==={file_path.name}===")

        try:
            preview_text, source_format = _read_contract(str(file_path))
            preview_op = parse_text(preview_text)

            new_version = getattr(preview_op, "version", "")
            version_key = f"{source_type}:{source_format}:{module}:{file_path.as_posix()}"

            old_entry = versions.get(version_key, "")
            old_version = old_entry.get("version", "") if isinstance(old_entry, dict) else old_entry
            old_output = old_entry.get("output", "") if isinstance(old_entry, dict) else ""

            if new_version and new_version == old_version and old_output and Path(old_output).exists():
                print(f"    [SKIP] version {new_version} không đổi")

                skipped.append({
                    "file": file_path.name,
                    "reason": "version_unchanged",
                    "version": new_version,
                    "output": old_output,
                    "source_format": source_format,
                })

                append_version_history({
                    "run_id": run_id,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "module": module,
                    "source_type": source_type,
                    "source_format": source_format,
                    "file": file_path.name,
                    "path": str(file_path),
                    "output": old_output,
                    "status": "skipped",
                    "old_version": old_version,
                    "new_version": new_version,
                    "reason": "version_unchanged",
                })

                print()
                continue

            op, resolution, source_format, out = _convert_one_file(
                file_path=file_path,
                output_dir=output_path,
                schemas_dir=schemas_path,
                user_selected_module=module,
                endpoint_rules=endpoint_rules,
                post_enrich_checks=post_enrich_checks,
            )

            version_key = f"{source_type}:{source_format}:{module}:{file_path.as_posix()}"

            versions[version_key] = {
                "module": module,
                "source_type": source_type,
                "source_format": source_format,
                "file": file_path.name,
                "path": str(file_path),
                "output": str(out),
                "method": (getattr(op, "method", "") or "").lower(),
                "http_path": normalize_http_path(getattr(op, "path", "") or ""),
                "version": getattr(op, "version", ""),
                "change_history": getattr(op, "change_history", []),
                "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "status": "success",
                "module_resolution": {
                    "suggested_module": resolution.suggested_module,
                    "final_module": resolution.final_module,
                    "service_in_doc": resolution.service_in_doc,
                    "conflict": resolution.conflict,
                    "review_type": resolution.review_type,
                    "source": resolution.source,
                },
            }

            save_versions(versions)

            _ep_method = (getattr(op, "method", "") or "").lower()
            _ep_path   = normalize_http_path(getattr(op, "path", "") or "")
            _ep_key    = f"{_ep_method}:{_ep_path}"

            if _ep_key in seen_endpoints:
                print(
                    f"  [WARN] output collision: '{_ep_key}' "
                    f"đã có từ '{seen_endpoints[_ep_key]}'"
                )
                output_collisions.append({
                    "endpoint_key": _ep_key,
                    "first_file": seen_endpoints[_ep_key],
                    "second_file": file_path.name,
                    "output": str(out),
                })
            else:
                seen_endpoints[_ep_key] = file_path.name

            success_files.append({
                "file":                 file_path.name,
                "output":               str(out),
                "version":              getattr(op, "version", ""),
                "operation_id":         getattr(op, "operation_id", ""),
                "method":               getattr(op, "method", ""),
                "path":                 getattr(op, "path", ""),
                "source_format":        source_format,
                "module_conflict":      resolution.conflict,
                "module_review_type":   resolution.review_type,
            })

            append_version_history({
                "run_id":           run_id,
                "timestamp":        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "module":           module,
                "source_type":      source_type,
                "source_format":    source_format,
                "file":             file_path.name,
                "path":             str(file_path),
                "output":           str(out),
                "method": (getattr(op, "method", "") or "").lower(),
                "http_path": normalize_http_path(getattr(op, "path", "") or ""),
                "status":           "success",
                "old_version":      old_version,
                "new_version":      getattr(op, "version", ""),
                "change_history":   getattr(op, "change_history", []),
            })

            if op.review_flags:
                review_item = {
                    "type": "convert_review",
                    "file": file_path.name,
                    "flags": op.review_flags,
                    "actions": [review_actions.get(flag, flag) for flag in op.review_flags],
                    "output": str(out),
                    "source_format": source_format,
                    "module": module,
                }
                needs_review.append(review_item)

            print()

        except Exception as e:
            print(f"[ERROR] {file_path.name}: {e}")

            errors.append({
                "file": file_path.name,
                "error": str(e),
            })

            append_version_history({
                "run_id": run_id,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "module": module,
                "source_type": source_type,
                "source_format": file_path.suffix.lower().strip("."),
                "file": file_path.name,
                "path": str(file_path),
                "output": "",
                "status": "failed",
                "error": str(e),
            })

            print()

    if needs_review:
        queue = load_review_queue()
        queue.extend(needs_review)
        save_review_queue(queue)

    if success_files:
        print("\n[post_process] Tagging readOnly + replacing $ref...")
        from post_process.run import run as post_process_run
        post_process_run(str(schemas_path))

    log_path = write_batch_log(
        module=module,
        source_format="mixed",
        stats={
            "source_type": source_type,
            "module_resolution": "user_selected",
            "total": len(files),
            "success": len(success_files),
            "failed": len(errors),
            "skipped": len(skipped),
            "success_files": success_files,
            "skipped_files": skipped,
            "errors": errors,
            "needs_review": needs_review,
            "review_actions": review_actions,
            "output_collisions": output_collisions,
        },
    )

    print(
        f"Hoàn thành batch: total={len(files)}, "
        f"success={len(success_files)}, "
        f"failed={len(errors)}, "
        f"skipped={len(skipped)}"
    )
    print(f"Batch log: {log_path}")
    return len(success_files)

def main():
    parser = argparse.ArgumentParser(
        description="Schema Converter - API Contract PDF/DOCX -> OpenAPI 3.1"
    )

    parser.add_argument(
        "--scan",
        action="store_true",
        help="Scan 1.docs/source/api_contract, phát hiện folder module mới",
    )

    parser.add_argument(
        "--import-folder",
        required=True,
        help="Folder chứa API Contract .pdf/.docx/.txt/.md",
    )

    parser.add_argument(
        "--module",
        required=True,
        help="Module user chọn khi import, ví dụ: ticket, service, account",
    )

    parser.add_argument(
        "--output-dir",
        default=None,
        help="Output folder cho paths. Nếu bỏ trống: 5.openapi/paths/<module>",
    )

    parser.add_argument(
        "--schemas-dir",
        default=None,
        help="Output folder cho schemas. Nếu bỏ trống: 5.openapi/components/schemas/<module>",
    )

    args = parser.parse_args()

    run_batch(
        input_dir=args.import_folder,
        module=args.module,
        output_dir=args.output_dir,
        schemas_dir=args.schemas_dir,
    )

if __name__ == "__main__":
    main()