import sys
import argparse
import json
import unicodedata
import re
from datetime import datetime
from pathlib import Path

import yaml

sys.path.insert(0, "2.pipeline")

from converters.pdf.reader import read_pdf
from converters.docx.parser import parse_text
from enrichers.llm_enricher import enrich
from generator.emitter import emit_yaml, emit_request_schema, emit_response_schemas, init_config

from utils.module_registry import ModuleRegistry
from utils.pluralizer import pluralize
from utils.report_store import load_versions, save_versions, append_version_history, save_review_queue, write_batch_log

CONFIG_DIR = Path(__file__).resolve().parent.parent / "4.config"
REPORT_DIR = Path(__file__).resolve().parent.parent / "3.build" / "reports"

PDF_CONFIG = CONFIG_DIR / "sources" / "pdf_sections.yaml"


def _to_snake_case(name: str) -> str:
    name = re.sub(r"([A-Z])", r"_\1", name)
    name = re.sub(r"[^a-zA-Z0-9]+", "_", name)
    return name.strip("_").lower()


def _normalize_filename(file_name: str) -> str:
    """
    Ví dụ:
      API Contract - API đóng ticket của khách hàng.docx.pdf
    Thành:
      api_dong_ticket_cua_khach_hang
    """
    name = Path(file_name).stem

    # Trường hợp file tên kiểu xxx.docx.pdf
    name = re.sub(r"\.docx$", "", name, flags=re.IGNORECASE)

    name = re.sub(r"^API Contract\s*-\s*", "", name, flags=re.IGNORECASE)
    name = re.sub(r"^API\s+", "", name, flags=re.IGNORECASE)

    name = unicodedata.normalize("NFD", name)
    name = name.encode("ascii", "ignore").decode()

    name = re.sub(r"[^a-zA-Z0-9]+", "_", name)
    return name.strip("_").lower()


def _read_pdf_contract(input_path: str) -> str:
    """
    PDF API Contract chỉ khác DOCX ở reader layer.

    Sau khi read_pdf() trả text,
    vẫn dùng chung parser DOCX hiện tại.
    """
    return read_pdf(input_path, str(PDF_CONFIG))


def _guess_action_name(op, fallback_file_name: str) -> str:
    """
    Sinh tên file output.

    Ưu tiên:
      1. operation_id từ LLM
      2. fallback từ tên file PDF

    Ví dụ:
      closeTicket -> close_ticket.yaml
      API Contract - đóng ticket.pdf -> dong_ticket.yaml
    """
    if getattr(op, "operation_id", ""):
        return _to_snake_case(op.operation_id)

    return _normalize_filename(fallback_file_name)


def run(input_path: str, output_path: str, schemas_dir: str = None, domain: str = "", post_enrich_checks: dict = None):
    print(f"[1/4] Đọc PDF: {input_path}")
    text = _read_pdf_contract(input_path)

    print("[2/4] Parse thông tin")
    op = parse_text(text)

    if not op.service and domain:
        op.service = domain

    print(f"    method={op.method}, path={op.path}, content_type={op.content_type}")

    if not op.method or not op.path:
        raise ValueError("Không tìm thấy method hoặc path trong PDF. Kiểm tra lại tài liệu.")

    print("[3/4] Gọi LLM để generate summary và operationId")
    title = Path(input_path).stem
    op = enrich(op, title=title)

    print(f"    summary='{op.summary}', operationId='{op.operation_id}'")

    for field_name, flag in (post_enrich_checks or {}).items():
        if not getattr(op, field_name, None):
            op.review_flags.append(flag)

    print(f"[4/4] Ghi YAML: {output_path}")
    emit_yaml(op, output_path)

    schemas = schemas_dir if schemas_dir else "."

    if op.has_request_body and op.request_body_fields:
        schema_name = emit_request_schema(op, schemas)
        print(f"    Request schema: {schema_name}.yaml")

    if op.response_schemas:
        emit_response_schemas(op, schemas)

    print(f"Hoàn thành: {output_path}")
    return op


def resolve_module_paths(module: str, mode: str) -> dict:
    registry = ModuleRegistry(str(CONFIG_DIR))

    if not registry.exists(module):
        raise ValueError(
            f"Module '{module}' chưa có trong module_registry.yaml. "
            f"Hãy bootstrap/register trước."
        )

    status = registry.get_status(module)

    if mode == "strict" and status != "active":
        raise ValueError(
            f"Module '{module}' đang status='{status}', không được chạy strict. "
            f"Hãy approve module trước."
        )

    if mode == "bootstrap" and status == "draft":
        print(f"[WARN] Module '{module}' đang draft — output cần review.")

    info = registry.get_info(module)
    project_root = CONFIG_DIR.parent

    return {
        "domain": module,
        "input_dir": str(project_root / info["source_dir"]),
        "output_dir": str(project_root / info["output_dir"]),
        "schemas_dir": str(project_root / info["schemas_dir"]),
        "status": status,
    }


def _run_batch(input_dir: str, output_dir: str, schemas_dir: str, domain: str, review_actions: dict, post_enrich_checks: dict) -> None:
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    files = sorted(Path(input_dir).glob("*.pdf"))

    print(f"Tìm thấy {len(files)} file PDF API Contract\n")

    versions = load_versions()
    needs_review = []
    errors = []
    skipped = []
    success_files = []
    source_format = "pdf"

    for f in files:
        print(f"==={f.name}===")

        try:
            text = unicodedata.normalize("NFC", _read_pdf_contract(str(f)))
            op_preview = parse_text(text)

            new_version = getattr(op_preview, "version", "")

            version_key = f"{domain}:{f.name}"
            old_entry = versions.get(version_key, "")
            if isinstance(old_entry, dict):
                old_version = old_entry.get("version", "")
            else:
                old_version = old_entry

            preview_title = _guess_action_name(op_preview, f.name)
            out = Path(output_dir) / f"{preview_title}.yaml"

            if new_version and new_version == old_version and out.exists():
                print(f"    [SKIP] version {new_version} không đổi")
                skipped.append(f.name)
                print()
                continue

            op = run(
                str(f),
                str(out),
                schemas_dir=schemas_dir,
                domain=domain,
                post_enrich_checks=post_enrich_checks,
            )

            # Sau enrich có thể có operation_id tốt hơn,
            # nên rename output nếu cần.
            final_title = _guess_action_name(op, f.name)
            final_out = Path(output_dir) / f"{final_title}.yaml"

            if final_out != out:
                if out.exists():
                    final_out.parent.mkdir(parents=True, exist_ok=True)
                    out.rename(final_out)

                out = final_out

            success_files.append({
                "file": f.name,
                "output": str(out),
                "version": getattr(op, "version", ""),
                "operation_id": getattr(op, "operation_id", ""),
                "method": getattr(op, "method", ""),
                "path": getattr(op, "path", "")
            })

            if op and getattr(op, "version", ""):
                versions[version_key] = {
                    "module": domain,
                    "source_type": "api_contract",
                    "source_format": source_format,
                    "file": f.name,
                    "path": str(f),
                    "output": str(out),
                    "version": getattr(op, "version", ""),
                    "change_history": getattr(op, "change_history", []),
                    "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "status": "success",
                }

                save_versions(versions)

                append_version_history({
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "file": f.name,
                    "module": domain,
                    "source_format": source_format,
                    "old_version": old_version,
                    "new_version": op.version,
                })

            if op and op.review_flags:
                needs_review.append({
                    "file": f.name,
                    "flags": op.review_flags,
                    "actions": [review_actions.get(flag, flag) for flag in op.review_flags],
                    "output": str(out),
                })
                print(f"    [REVIEW] {op.review_flags}")

        except Exception as e:
            print(f"[SKIP] {f.name}: {e}")
            errors.append({"file": f.name, "error": str(e)})

        print()

    print(f"Hoàn thành: {len(files) - len(errors)}/{len(files)} file")

    log_path = write_batch_log(
        module=domain,
        source_format=source_format,
        stats={
            "total": len(files),
            "success": len(success_files),
            "failed": len(errors),
            "skipped": len(skipped),
            "success_files": success_files,
            "skipped_files": skipped,
            "errors": errors,
            "needs_review": needs_review,
            "review_actions": review_actions
        },
    )

    print(f"Log theo module ghi lại: {log_path}")

    if needs_review:
        save_review_queue(needs_review)
        print(f"Review queue: {REPORT_DIR / 'human_review_queue.json'} ({len(needs_review)} items)")

def _scan_new_modules() -> None:
    """
    Scan 1.docs/source/api_contract/,
    phát hiện folder module chưa có trong registry.

    Cấu trúc khuyến nghị:
      1.docs/source/api_contract/ticket/*.pdf
      1.docs/source/api_contract/payment/*.pdf
    """
    project_root = CONFIG_DIR.parent
    source_root = project_root / "1.docs" / "source" / "api_contract"

    registry = ModuleRegistry(str(CONFIG_DIR))

    if not source_root.exists():
        print(f"[ERROR] Không tìm thấy: {source_root}")
        return

    folders = [d for d in source_root.iterdir() if d.is_dir()]
    new_modules = [f for f in folders if not registry.exists(f.name)]

    if not new_modules:
        print("Không có module mới. Đã được đăng ký.")
        return

    print(f"Phát hiện {len(new_modules)} module mới")

    for folder in new_modules:
        module = folder.name
        plural = pluralize(module, str(CONFIG_DIR))

        suggested = {
            "source_dir": f"1.docs/source/api_contract/{module}",
            "output_dir": f"5.openapi/paths/{plural}",
            "schemas_dir": f"5.openapi/components/schemas/{module}",
        }

        print(f"\nModule: {module}")
        print(f"    source_dir : {suggested['source_dir']}")
        print(f"    output_dir : {suggested['output_dir']}")
        print(f"    schemas_dir : {suggested['schemas_dir']}")

        ans = input("\n    output_dir đúng chưa? [Enter = giữ nguyên, hoặc nhập lại]: ").strip()
        if ans:
            suggested["output_dir"] = ans

        registry.register(
            module=module,
            source_dir=suggested["source_dir"],
            output_dir=suggested["output_dir"],
            schemas_dir=suggested["schemas_dir"],
        )

        print(f"  ✓ Đã đăng ký '{module}' với status: draft")

    print("\nScan PDF modules hoàn thành.")


def main():
    parser = argparse.ArgumentParser(description="Schema Converter - PDF API Contract -> OpenAPI YAML")

    parser.add_argument("input", nargs="?", help="File PDF đầu vào")
    parser.add_argument("output", nargs="?", help="File YAML đầu ra")

    parser.add_argument(
        "--batch",
        nargs=2,
        metavar=("INPUT_DIR", "OUTPUT_DIR"),
        help="Chạy batch PDF: --batch <input_dir> <output_dir>",
    )

    parser.add_argument("--module", help="Tên module cần convert PDF")
    parser.add_argument(
        "--mode",
        choices=["strict", "bootstrap"],
        default="strict",
        help="strict: chỉ chạy module active; bootstrap: cho phép draft",
    )

    parser.add_argument("--scan", action="store_true", help="Scan 1.docs/source/api_contract để phát hiện module PDF")
    parser.add_argument("--approve", metavar="MODULE", help="Xác nhận module từ draft thành active")
    parser.add_argument("--approved-by", default="", help="Tên người approve")

    args = parser.parse_args()

    init_config(str(CONFIG_DIR))

    from generator.emitter import _CONFIG

    review_actions = _CONFIG.get("review_actions", {})
    post_enrich_checks = _CONFIG.get("post_enrich_checks", {})

    if args.scan:
        _scan_new_modules()
        return

    if args.approve:
        registry = ModuleRegistry(str(CONFIG_DIR))
        registry.approve(args.approve, approved_by=args.approved_by)
        print(f"✓ Module '{args.approve}' đã được approve → status: active")
        return

    if args.module:
        if args.module == "all":
            raise NotImplementedError("--module all sẽ làm sau")

        paths = resolve_module_paths(args.module, args.mode)

        _run_batch(
            input_dir=paths["input_dir"],
            output_dir=paths["output_dir"],
            schemas_dir=paths["schemas_dir"],
            domain=paths["domain"],
            review_actions=review_actions,
            post_enrich_checks=post_enrich_checks,
        )

    elif args.batch:
        input_dir, output_dir = args.batch
        domain = Path(input_dir).name
        schemas_dir = str(Path(output_dir).parent.parent / "components" / "schemas" / domain)

        _run_batch(
            input_dir=input_dir,
            output_dir=output_dir,
            schemas_dir=schemas_dir,
            domain=domain,
            review_actions=review_actions,
            post_enrich_checks=post_enrich_checks,
        )

    elif args.input and args.output:
        try:
            domain = Path(args.input).parent.name
            run(
                args.input,
                args.output,
                domain=domain,
                post_enrich_checks=post_enrich_checks,
            )
        except ValueError as e:
            print(f"\n[ERROR] {e}", file=sys.stderr)
            sys.exit(1)
        except FileNotFoundError as e:
            print(f"\n[ERROR] Không tìm thấy file: {e}", file=sys.stderr)
            sys.exit(1)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()