# enrich_errors.py
# Gắn x-error-responses vào OpenAPI YAML theo Hướng D:
#   - x-error-responses nằm ở cấp operation (cùng cấp responses)
#   - responses giữ $ref thuần, không wrap allOf
#   - message lấy từ incoming.message trong parsed_error_tables.json (message gốc DOCX)
#   - category lấy từ incoming.category trong parsed_error_tables.json

import json
import os
import yaml
import ruamel.yaml


BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "..")
INTERMEDIATE_DIR = os.path.join(BASE_DIR, "3.build", "intermediate", "errors")
RESPONSE_REFS_PATH = os.path.join(BASE_DIR, "4.config", "global", "response_refs.yaml")


def _load_response_refs() -> dict:
    if not os.path.exists(RESPONSE_REFS_PATH):
        return {}
    with open (RESPONSE_REFS_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return {str(k): v for k, v in data.get("response_refs", {}).items()}


def _load_json(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _build_code_lookup(parsed_tables: dict) -> dict[str, dict]:
    """
    Từ parsed_error_tables.json, build dict:
      code -> { category, message, http_status }
    Dùng incoming.message và incoming.category — message gốc từ DOCX.
    """
    lookup = {}
    for entry in parsed_tables.get("entries", []):
        code = str(entry.get("code", ""))
        incoming = entry.get("incoming", {})
        if code and incoming:
            lookup[code] = {
                "category": incoming.get("category"),
                "message": incoming.get("message", ""),
                "http_status": incoming.get("http_status", ""),
            }
    return lookup


def _build_x_error_responses(errors: dict, code_lookup: dict) -> dict:
    """
    Build x-error-responses theo Hướng D.

    Hỗ trợ cả format cũ:
      { "401": ["4102", "4108"] }

    Và format mới từ operation_error_map:
      { "401": [{code, category, message, http_status_source}, ...] }
    """
    x_error = {}

    for http_status, codes in errors.items():
        entries = []

        for item in codes:
            if isinstance(item, dict):
                code = str(item.get("code", ""))
                info = item
            else:
                code = str(item)
                info = code_lookup.get(code, {})

            if not code:
                continue

            entries.append({
                "code": code,
                "category": info.get("category"),
                "message": info.get("message", ""),
            })

        if entries:
            x_error[str(http_status)] = entries

    return x_error


def _fix_responses(responses: dict) -> dict:
    """
    Với mỗi response trong responses:
    - Nếu đang dùng allOf wrap $ref: tháo ra, giữ $ref thuần
    - Xoá x-error-codes nếu có
    Trả về dict responses đã fix.
    """
    yaml = ruamel.yaml.YAML()
    fixed = ruamel.yaml.comments.CommentedMap()

    for status, resp in responses.items():
        if resp is None:
            fixed[status] = resp
            continue

        # Trường hợp allOf wrap $ref (lỗi cũ ở 401)
        if "allOf" in resp:
            allof_items = resp["allOf"]
            ref_item = next((i for i in allof_items if "$ref" in i), None)
            if ref_item:
                # Giữ $ref thuần, bỏ allOf và x-error-codes
                new_resp = ruamel.yaml.comments.CommentedMap()
                new_resp["$ref"] = ref_item["$ref"]
                fixed[status] = new_resp
                continue

        # Trường hợp 422 có content inline: map về $ref thuần
        if str(status) == "422" and "content" in resp and "$ref" not in resp:
            new_resp = ruamel.yaml.comments.CommentedMap()
            new_resp["$ref"] = "../../components/responses/StandardError422.yaml"
            fixed[status] = new_resp
            continue

        # Trường hợp có x-error-codes inline: xoá đi, xoá luôn description nếu reference tới x-error-codes
        # Xoá x-error-codes inline và description rác nếu có
        has_error_codes = "x-error-codes" in resp
        has_stale_desc = (
            "description" in resp
            and isinstance(resp.get("description"), str)
            and "x-error-codes" in resp.get("description", "")
        )
        if has_error_codes or has_stale_desc:
            new_resp = ruamel.yaml.comments.CommentedMap()
            for k, v in resp.items():
                if k == "x-error-codes":
                    continue
                if k == "description" and isinstance(v, str) and "x-error-codes" in v:
                    continue
                new_resp[k] = v
            fixed[status] = new_resp
            continue

        fixed[status] = resp

    return fixed


def enrich_yaml_file(yaml_path: str, operation_data: dict, code_lookup: dict, dry_run: bool = False, response_refs: dict = None) -> bool:
    """
    Đọc 1 file YAML operation, gắn x-error-responses, fix responses.
    Trả về True nếu có thay đổi.
    """
    yaml = ruamel.yaml.YAML()
    yaml.preserve_quotes = True
    yaml.width = 120

    with open(yaml_path, encoding="utf-8") as f:
        doc = yaml.load(f)

    if doc is None:
        print(f"   File rỗng hoặc không parse được: {yaml_path}")
        return False

    # File YAML operation có cấu trúc: { get: { responses: ..., ... } }
    # Tìm method key (get/post/put/delete/patch)
    method_key = None
    for key in doc:
        if key in ("get", "post", "put", "delete", "patch"):
            method_key = key
            break

    if not method_key:
        print(f"   Không tìm thấy method key trong: {yaml_path}")
        return False

    operation = doc[method_key]

    # Fix responses: tháo allOf, xoá x-error-codes inline
    if "responses" in operation:
        operation["responses"] = _fix_responses(operation["responses"])

    # Build và gắn x-error-responses
    errors = operation_data.get("errors", {})
    x_error = _build_x_error_responses(errors, code_lookup)

    if x_error:
        operation["x-error-responses"] = x_error
    
    # Xoá x-error-responses cũ nếu có (tránh duplicate)
    # Đã được ghi đè ở trên nếu x_error có data

    responses_to_add = {}
    if x_error and response_refs and "responses" in operation:
        for http_status in x_error:
            if str(http_status) not in operation["responses"]:
                ref_path = response_refs.get(str(http_status))
                if ref_path:
                    responses_to_add[str(http_status)] = ref_path
                else:
                    print(f"    [WARN] Không có $ref config cho status {http_status}")

    if dry_run:
        print(f"    [dry-run] Sẽ gắn x-error-responses vào: {yaml_path}")
        for status, entries in x_error.items():
            print(f"    {status}: {[e['code'] for e in entries]}")
        if responses_to_add:
            print(f"    [dry-run] Sẽ gắn bổ sung responses: {list(responses_to_add.keys())}")
        return True

    for http_status, ref_path in responses_to_add.items():
        new_resp = ruamel.yaml.comments.CommentedMap()
        new_resp["$ref"] = ref_path
        operation["responses"][str(http_status)] = new_resp

    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(doc, f)

    print(f" Đã ghi: {yaml_path}")
    return True


def cmd_enrich_errors(module: str, file: str = None, folder: str = None,
                       output: str = None, dry_run: bool = False) -> None:
    """
    Entry point từ run_api_import.py.
    Đọc operation_error_map.json + parsed_error_tables.json,
    gắn x-error-responses vào từng file YAML operation.
    """
    module_intermediate = os.path.join(INTERMEDIATE_DIR, module)
    operation_map_path = os.path.join(module_intermediate, "operation_error_map.json")
    parsed_tables_path = os.path.join(module_intermediate, "parsed_error_tables.json")

    if not os.path.exists(operation_map_path):
        print(f" Chưa có operation_error_map.json cho module '{module}'.")
        print(f"  Chạy trước: python3 2.pipeline/run_api_import.py build-operation-map --module {module}")
        return

    if not os.path.exists(parsed_tables_path):
        print(f" Chưa có parsed_error_tables.json cho module '{module}'.")
        print(f"  Chạy trước: python3 2.pipeline/run_api_import.py parse-errors --module {module}")
        return

    operation_map = _load_json(operation_map_path)
    parsed_tables = _load_json(parsed_tables_path)
    code_lookup = _build_code_lookup(parsed_tables)
    response_refs = _load_response_refs()

    operations = operation_map.get("operations", {})
    if not operations:
        print(f" Không có operation nào trong map của module '{module}'.")
        return

    print(f"[enrich-errors] module={module}, {len(operations)} operation, dry_run={dry_run}")

    success = 0
    skip = 0
    error = 0

    for op_id, op_data in operations.items():
        yaml_path = op_data.get("output_yaml", "")
        if not yaml_path or not os.path.exists(yaml_path):
            print(f" [{op_id}] Không tìm thấy file: {yaml_path}")
            error += 1
            continue

        print(f"  [{op_id}] {op_data.get('method','').upper()} {op_data.get('path','')}")
        try:
            changed = enrich_yaml_file(yaml_path, op_data, code_lookup, dry_run=dry_run, response_refs=response_refs)
            if changed:
                success += 1
            else:
                skip += 1
        except Exception as e:
            print(f"     Lỗi: {e}")
            error += 1

    print(f"\n=== SUMMARY ===")
    print(f"  success : {success}")
    print(f"  skip    : {skip}")
    print(f"  error   : {error}")