import sys
import argparse
import json
import unicodedata
from datetime import datetime
from pathlib import Path

from schema_converter.reader import read_docx, read_text
from schema_converter.parser import parse_text
from schema_converter.llm_client import fill_metadata
from schema_converter.emitter import emit_yaml, emit_request_schema, emit_response_schemas

VERSION_FILE = "file_version.json"

def _load_versions(output_dir: str) -> dict:
    path = Path(output_dir) / VERSION_FILE
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}

def _save_versions(versions: dict, output_dir: str) -> None:
    path = Path(output_dir) / VERSION_FILE
    with open(path, "w", encoding="utf-8") as f:
        json.dump(versions, f, ensure_ascii=False, indent=2)

def run(input_path: str, output_path: str, schemas_dir: str = None, domain: str = "") -> None:
    #1 Đọc File
    print(f"[1/4] Đọc file: {input_path}")
    ext = Path(input_path).suffix.lower()
    if ext == ".docx":
        text = read_docx(input_path)
    elif ext in (".txt", ".md"):
        text = read_text(input_path)
    else:
        raise ValueError(f"Định dạng hỗ trợ: {ext}")

    #2 parser text -> parserOperation
    print("[2/4] parser thông tin")
    op = parse_text(text)
    if not op.service and domain:
        op.service = domain
    print(f" method={op.method}, path={op.path}, content_type={op.content_type}")

    if not op.method or not op.path:
        raise ValueError("Không tìm thấy method hoặc path trong tài liệu, Kiểm tra lại file")

    #3 Gọi LLM để điền summary và operationId
    print("[3/4] Goij LLM để generate summary và operationId")
    title = Path(input_path).stem # Lấy tên file làm title gợi ý cho LLM
    metadata = fill_metadata(title=title, method=op.method, path=op.path)
    print(f"    summary='{metadata.get('summary', '')}', operationId='{metadata.get('operationId', '')}'")

    # Gắn metadata vào parserOperation
    op.summary = metadata.get("summary", "")
    op.operation_id = metadata.get("operationId", "")
    op.description = metadata.get("description", "")

    #4 emit YAML
    print(f"[4/4] Ghi file YAML: {output_path}")
    emit_yaml(op, output_path)
    print(f"\nHoàn thành: {output_path}")

    schemas = schemas_dir if schemas_dir else "."

    if op.has_request_body and op.request_body_fields:
        schema_name = emit_request_schema(op, schemas)
        print(f"      Request schema: {schema_name}.yaml")

    if op.response_schemas:
        emit_response_schemas(op, schemas)
    return op

def main():
    parser = argparse.ArgumentParser(description="Schema Converter - docx -> OpenAPI YAML")
    parser.add_argument("input", nargs="?", help="File tài liệu đầu vào (.docx)")
    parser.add_argument("output", nargs="?", help="File YAML đầu ra")
    parser.add_argument("--batch", nargs=2, metavar=("INPUT_DIR", "OUTPUT_DIR"),
                        help="Chạy batch: --batch <input_dir> <output_dir>")
    args = parser.parse_args()

    if args.batch:
        input_dir, output_dir = args.batch
        domain = Path(input_dir).name
        schemas_dir = str(Path(output_dir).parent.parent / "components" / "schemas" / domain)
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        files = list(Path(input_dir).glob("*.docx"))
        print(f"Tìm thấy {len(files)} file\n")

        versions = _load_versions(output_dir)
        needs_review = []
        errors = []
        skipped = []

        for f in files:
            _text = unicodedata.normalize('NFC', read_docx(str(f)))
            _op = parse_text(_text)
            new_version = _op.version
            # Lấy segment cuối URL: /v1/users/{id}/tickets → tickets, /close → close
            _segments = [s for s in _op.path.split('/') if s and s != 'v1']
            _last = _segments[-1] if _segments else ""

            if not _last.startswith('{'):
                # Kết thúc bằng action cụ thể: close, reopen, tickets...
                # Nếu là resource (tickets) → phân biệt theo method
                _non_resource_actions = {'close', 'reopen', 'ratings', 'feedback', 'conversations', 'support-staffs', 'change-assignee'}
                if _last in _non_resource_actions:
                    _action = _last
                else:
                    if _op.method == 'GET':
                        _action = 'list'
                    elif _op.method == 'POST':
                        _action = 'create'
                    else:
                        _action = _last
            else:
                _prev = _segments[-2] if len(_segments) >= 2 else ""
                _prev_clean = _prev if not _prev.startswith('{') else ""

                # Kết thúc bằng {id} → detail/update/delete theo method
                if _op.method == 'GET':
                    _action = 'detail'
                elif _op.method in ('PUT', 'PATCH'):
                    _action = 'update'
                elif _op.method == 'DELETE':
                    _action = 'delete'
                elif _op.method == 'POST':
                    # POST /{sub-resource}/{id} → update (chỉnh sửa item đã có)
                    # POST /{id} không có sub-resource → create (tạo mới dưới resource cha)
                    _action = f"{_prev_clean}-update" if _prev_clean else 'create'
                else:
                    _action = 'action'
            out = Path(output_dir) / f"{_action}.yaml"
            print(f"==={f.name}===")
            old_entry = versions.get(f.name, "")
            if isinstance(old_entry, dict):
                old_version = old_entry.get("version", "")
            else:
                old_version = old_entry
            if new_version and new_version == old_version and out.exists():
                print(f"    [SKIP] version {new_version} không đổi")
                skipped.append(f.name)
                print()
                continue
            try:
                op = run(str(f), str(out), schemas_dir, domain)
                if op and op.version:
                    versions[f.name] = {
                        "version": op.version,
                        "change_history": op.change_history
                    }
                    _save_versions(versions, output_dir)
                if op and op.review_flags:
                    needs_review.append({
                        "file": f.name,
                        "flags":  op.review_flags
                    })
                    print(f"    [REVIEW] {op.review_flags}")
            except Exception as e:
                print(f"[SKIP] {f.name}: {e}")
                errors.append({"file": f.name, "error": str(e)})
            print()

        print(f"\nHoàn thành: {len(files) - len(errors)}/{len(files)} file")

        # Ghi log ra file
        log = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total": len(files),
            "success": len(files) - len(errors),
            "failed": len(errors),
            "needs_review": needs_review,
            "error_groups": {
                "method_missing": [r["file"] for r in needs_review if "method_missing" in r["flags"]],
                "path_missing": [r["file"] for r in needs_review if "path_missing" in r["flags"]],
                "permission_missing": [r["file"] for r in needs_review if "permission_missing" in r["flags"]],
                "error_codes_not_parsed": [r["file"] for r in needs_review if "error_codes_not_parsed" in r["flags"]],
                "request_body_fields_empty": [r["file"] for r in needs_review if "request_body_fields_empty" in r["flags"]],
            },
            "errors": errors
        }
        log_path = Path(output_dir) / "batch_log.json"
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(log, f, ensure_ascii=False, indent=2)
        print(f"Log ghi tại: {log_path}")

        if errors:
            print("Lỗi:", ", ".join([e["file"] for e in errors]))
    elif args.input and args.output:
        # nhánh single file — giữ nguyên như cũ
        try:                              
            run(args.input, args.output)
        except ValueError as e:
            print(f"\n[ERROR] {e}", file=sys.stderr)
            sys.exit(1)
        except FileNotFoundError as e:
            print(f"\n[ERROR] Không tìm thất file: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()