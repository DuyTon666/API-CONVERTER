import sys
import argparse
import json
import unicodedata
from datetime import datetime
from pathlib import Path

from converters.docx.reader import read_docx, read_text
from converters.docx.parser import parse_text
from enrichers.llm_enricher import enrich
from generator.emitter import emit_yaml, emit_request_schema, emit_response_schemas, init_config
from utils.module_registry import ModuleRegistry
from utils.pluralizer import pluralize

CONFIG_DIR = Path(__file__).resolve().parent.parent / "4.config"
REPORT_DIR = Path(__file__).resolve().parent.parent / "3.build" / "reports"

def _load_versions() -> dict:
    path = REPORT_DIR / "file_version.json"
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}

def _save_versions(versions: dict) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / "file_version.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(versions, f, ensure_ascii=False, indent=2)


def run(input_path: str, output_path: str, schemas_dir: str = None, domain: str = "", post_enrich_checks: dict = None) -> None:
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
    op = enrich(op, title=title)
    print(f"    summary='{op.summary}', operationId='{op.operation_id}'")

    for field_name, flag in (post_enrich_checks or {}).items():
        if not getattr(op, field_name, None):
            op.review_flags.append(flag)

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

def _run_batch(input_dir: str, output_dir: str, schemas_dir: str, domain: str,
               _review_actions: dict, _post_enrich_checks: dict) -> None:
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    files = list(Path(input_dir).glob("*.docx"))
    print(f"Tìm thấy {len(files)} file\n")

    versions = _load_versions()
    needs_review = []
    errors = []
    skipped = []

    module_config_path = CONFIG_DIR / "modules" / f"{domain}.yaml"
    _non_resource_actions = set()
    if module_config_path.exists():
        import yaml as _yaml
        _mod_cfg = _yaml.safe_load(module_config_path.read_text(encoding="utf-8")) or {}
        _non_resource_actions = set(_mod_cfg.get("action_names", []))
    else:
        print(f"    [WARN] Không tìm thấy module config: {module_config_path}")

    for f in files:
        _text = unicodedata.normalize('NFC', read_docx(str(f)))
        _op = parse_text(_text)
        new_version = _op.version
        # Lấy segment cuối URL: /v1/users/{id}/tickets → tickets, /close → close
        _segments = [s for s in _op.path.split('/') if s and s != 'v1']
        _last = _segments[-1] if _segments else ""

        if not _last.startswith('{'):
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
            op = run(str(f), str(out), schemas_dir, domain, post_enrich_checks=_post_enrich_checks)
            if op and op.version:
                versions[f.name] = {
                    "version": op.version,
                    "change_history": op.change_history
                }
                _save_versions(versions)
            if op and op.review_flags:
                needs_review.append({
                    "file": f.name,
                    "flags":  op.review_flags,
                    "actions": [_review_actions.get(flag, flag) for flag in op.review_flags],
                    "output": str(out),
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
        "skipped": len(skipped),
        "needs_review": needs_review,
        "error_groups": {
            flag: [r["file"] for r in needs_review if flag in r["flags"]]
            for flag in _review_actions
        },
        "errors": errors
    }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    log_path = REPORT_DIR / "batch_log.json"
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)
    print(f"Log ghi tại: {log_path}")

    if needs_review:
        review_path = REPORT_DIR / "human_review_queue.json"
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        with open(review_path, "w", encoding="utf-8") as f:
            json.dump(needs_review, f, ensure_ascii=False, indent=2)
        print(f"Review queue: {review_path} ({len(needs_review)} items)")

    # Bước 4: post_process — tag readOnly + replace $ref
    print(f"\n[4/4] Post-processing schemas...")
    try:
        from post_process.run import run as run_post_process
        run_post_process(schemas_dir)
        print("  ✓ Post-process hoàn thành")
    except Exception as e:
        print(f"  [WARN] Post-process lỗi: {e}")

def _scan_new_modules() -> None:
    """
     Scan 1.docs/source/, phát hiện folder chưa có trong registry.
    Với mỗi folder mới: đề xuất đường dẫn, hỏi confirm, đăng ký draft.
    """
    project_root = CONFIG_DIR.parent
    source_root  = project_root / "1.docs" / "source"
    registry     = ModuleRegistry(str(CONFIG_DIR))

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
            "source_dir": f"1.docs/source/{module}",
            "output_dir": f"5.openapi/paths/{plural}",
            "schemas_dir": f"5.openapi/components/schemas/{module}",
        }

        print(f"Module: {module}")
        print(f"    source_dir : {suggested['source_dir']}")
        print(f"    output_dir : {suggested['output_dir']}")
        print(f"    schemas_dir : {suggested['schemas_dir']}")

        ans = input(f"\n    output_dir đúng chưa? [Enter = giữ nguyên, hoặc nhập lại]:").strip()
        if ans:
            suggested["output_dir"] = ans
        
        registry.register(
            module=module,
            source_dir=suggested["source_dir"],
            output_dir=suggested["output_dir"],
            schemas_dir=suggested["schemas_dir"],
        )
        print(f"  ✓ Đã đăng ký '{module}' với status: draft\n")

    print("Scan hoàn thành. Chạy '--module <tên> --mode bootstrap' để convert.")

def main():
    parser = argparse.ArgumentParser(description="Schema Converter - docx -> OpenAPI YAML")
    parser.add_argument("input", nargs="?", help="File tài liệu đầu vào (.docx)")
    parser.add_argument("output", nargs="?", help="File YAML đầu ra")
    parser.add_argument("--batch", nargs=2, metavar=("INPUT_DIR", "OUTPUT_DIR"),
                        help="Chạy batch: --batch <input_dir> <output_dir>")
    parser.add_argument("--module", 
                        help="Tên module cần convert")
    parser.add_argument("--mode", choices=["strict", "bootstrap"], default="strict",
                        help="chỉ chạy module active; boootstrap: cho phép draft")
    parser.add_argument("--scan", action="store_true",
                        help="Scan thư mục source, phát hiện module")
    args = parser.parse_args()

    init_config(str(CONFIG_DIR))
    from generator.emitter import _CONFIG

    _review_actions = _CONFIG.get("review_actions", {})
    _post_enrich_checks = _CONFIG.get("post_enrich_checks", {})

    if args.scan:
        _scan_new_modules()
        return

    if args.module:
        if args.module == "all":
            raise NotImplementedError("--module all sẽ làm sau")

        paths = resolve_module_paths(args.module, args.mode)

        input_dir = paths["input_dir"]
        output_dir = paths["output_dir"]
        schemas_dir = paths["schemas_dir"]
        domain = paths["domain"]
        _run_batch(input_dir, output_dir, schemas_dir, domain,
               _review_actions, _post_enrich_checks)

    elif args.batch:
        input_dir, output_dir = args.batch
        domain = Path(input_dir).name
        schemas_dir = str(Path(output_dir).parent.parent / "components" / "schemas" / domain)
        _run_batch(input_dir, output_dir, schemas_dir, domain,
                   _review_actions, _post_enrich_checks)

    elif args.input and args.output:
        # nhánh single file — giữ nguyên như cũ
        try:             
            domain = Path(args.input).parent.name                 
            run(args.input, args.output, domain=domain, post_enrich_checks=_post_enrich_checks)
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