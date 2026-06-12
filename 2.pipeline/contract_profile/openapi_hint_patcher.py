from __future__ import annotations

import argparse
import json
from pathlib import Path
import yaml

from contract_profile.loader import load_contract_profile


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _load_yaml(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8").strip()
    return yaml.safe_load(raw) if raw else {}


def _write_yaml(path: Path, data: dict) -> None:
    path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _load_hints(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("results", [])


def _source_stem(source_file: str) -> str:
    return Path(source_file).stem


def _get_response_header_refs(config: dict) -> dict:
    response_cfg = config.get("response_contract_rules", {})
    headers_cfg = response_cfg.get("response_headers", {})
    emit_headers = headers_cfg.get("emit_headers", {})

    refs = {}
    for header_name, info in emit_headers.items():
        ref = info.get("ref")
        if ref:
            refs[header_name] = ref

    return refs


def _get_schema_refs(config: dict) -> dict:
    response_cfg = config.get("response_contract_rules", {})
    modes = response_cfg.get("response_modes", {})
    fallback = response_cfg.get("fallback", {})

    refs = {
        "json": fallback.get(
            "default_json_ref",
            "../../components/schemas/common/StandardSuccess.yaml",
        ),
        "error": fallback.get(
            "default_error_ref",
            "../../components/schemas/common/StandardError.yaml",
        ),
    }

    binary_mode = modes.get("binary_file", {})
    refs["binary"] = binary_mode.get(
        "schema_ref",
        "../../components/schemas/common/BinaryFile.yaml",
    )

    return refs

def _get_request_header_refs(config: dict) -> dict:
    header_cfg = config.get("header_refs", {})
    request_headers = header_cfg.get("request_headers", {})

    refs = {}
    for header_name, info in request_headers.items():
        if info.get("emit") and info.get("ref"):
            refs[header_name] = info["ref"]

    return refs

def _get_status_response_refs(config: dict) -> dict:
    status_cfg = config.get("status_response_refs", {})
    responses = status_cfg.get("responses", {})

    refs = {}
    for status, info in responses.items():
        if info.get("ref"):
            refs[str(status)] = info["ref"]

    return refs

def _parameter_exists(params: list, header_name: str, ref: str) -> bool:
    for param in params:
        if not isinstance(param, dict):
            continue

        if param.get("$ref") == ref:
            return True

        if param.get("name") == header_name and param.get("in") == "header":
            return True

    return False


def _patch_request_headers(op: dict, request_headers: list[dict], header_refs: dict) -> bool:
    changed = False
    params = op.setdefault("parameters", [])

    if not isinstance(params, list):
        return False

    for header in request_headers:
        if not header.get("emit"):
            continue

        header_name = header.get("name")
        ref = header.get("ref") or header_refs.get(header_name)

        if not header_name or not ref:
            continue

        if _parameter_exists(params, header_name, ref):
            continue

        params.append({"$ref": ref})
        changed = True

    return changed

def _patch_status_responses(responses: dict, status_codes: list[dict], status_refs: dict) -> bool:
    changed = False

    for item in status_codes:
        status = str(item.get("status"))
        ref = item.get("ref") or status_refs.get(status)

        if not status or not ref:
            continue

        if status in responses:
            continue

        responses[status] = {"$ref": ref}
        changed = True

    return changed

def _find_target_yaml(source_file: str, module: str) -> Path | None:
    """
    MVP matching:
    - Tìm trong 5.openapi/paths/<module>
    - Match theo summary == source filename stem
    """
    stem = _source_stem(source_file)
    root = PROJECT_ROOT / "5.openapi/paths" / module

    if not root.exists():
        return None

    for path in sorted(root.glob("*.yaml")):
        try:
            data = _load_yaml(path)
        except Exception:
            continue

        for method in ["get", "post", "put", "patch", "delete"]:
            op = data.get(method)
            if isinstance(op, dict) and op.get("summary") == stem:
                return path

    return None


def _patch_format_enum(op: dict, enum_candidates: list[dict]) -> bool:
    changed = False

    params = op.get("parameters", [])
    if not isinstance(params, list):
        return False

    by_name = {
        item.get("param"): item
        for item in enum_candidates
        if isinstance(item, dict)
    }

    for param in params:
        if not isinstance(param, dict):
            continue

        name = param.get("name")
        candidate = by_name.get(name)
        if not candidate:
            continue

        schema = param.setdefault("schema", {})
        values = candidate.get("values", [])
        default = candidate.get("default")

        if values:
            if schema.get("type") != "string":
                schema["type"] = "string"
                changed = True

            if schema.get("enum") != values:
                schema["enum"] = values
                changed = True

        if default:
            if schema.get("default") != default:
                schema["default"] = default
                changed = True
            
    return changed

def _patch_response_headers(resp_200: dict, headers: list[str], header_refs: dict) -> bool:
    changed = False
    target = resp_200.setdefault("headers", {})

    for header in headers:
        if header == "Content-Type":
            # Content-Type được biểu diễn bằng responses.200.content
            continue

        ref = header_refs.get(header)
        if not ref:
            continue

        expected = {"$ref": ref}
        if target.get(header) != expected:
            target[header] = expected
            changed = True

    return changed


def _patch_binary_and_json_response(
    resp_200: dict,
    content_types: list[str],
    schema_refs: dict,
) -> bool:
    changed = False
    content = resp_200.setdefault("content", {})

    if "application/zip" in content_types:
        expected = {
            "schema": {
                "$ref": schema_refs["binary"]
            }
        }
        if content.get("application/zip") != expected:
            content["application/zip"] = expected
            changed = True

    if "application/json" in content_types and "application/json" not in content:
        content["application/json"] = {
            "schema": {
                "$ref": schema_refs["json"]
            }
        }
        changed = True

    return changed


def patch_yaml_with_hints(yaml_path: Path, hints: dict, config: dict) -> dict:
    data = _load_yaml(yaml_path)
    changed = False

    header_refs = _get_response_header_refs(config)
    schema_refs = _get_schema_refs(config)
    request_header_refs = _get_request_header_refs(config)
    status_response_refs = _get_status_response_refs(config)

    response_contract = hints.get("response_contract", {})
    content_types = response_contract.get("content_types", [])
    response_headers = response_contract.get("response_headers", [])
    enum_candidates = hints.get("query_enum_candidates", [])
    actions = set(hints.get("actions", []))
    request_headers = hints.get("request_contract", {}).get("request_headers", [])
    status_codes = hints.get("error_contract", {}).get("status_codes", [])

    for method in ["get", "post", "put", "patch", "delete"]:
        op = data.get(method)
        if not isinstance(op, dict):
            continue

        if "fix_query_enum" in actions:
            changed |= _patch_format_enum(op, enum_candidates)

        if "add_request_headers" in actions:
            changed |= _patch_request_headers(op, request_headers, request_header_refs)

        responses = op.setdefault("responses", {})
        if "add_conflict_response" in actions:
            changed |= _patch_status_responses(responses, status_codes, status_response_refs)
        resp_200 = responses.setdefault("200", {"description": "Thành công"})

        if "add_response_headers" in actions:
            changed |= _patch_response_headers(resp_200, response_headers, header_refs)

        if (
            "add_binary_response" in actions
            or "ensure_zip_and_json_200_response" in actions
        ):
            changed |= _patch_binary_and_json_response(resp_200, content_types, schema_refs)

    if changed:
        _write_yaml(yaml_path, data)

    return {
        "yaml_path": str(yaml_path),
        "changed": changed,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hints", required=True)
    parser.add_argument("--module")
    parser.add_argument("--yaml")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    config = load_contract_profile()
    hints_list = _load_hints(Path(args.hints))
    results = []

    for hints in hints_list:
        if hints.get("status") != "success":
            continue

        if args.yaml:
            target = Path(args.yaml)
        else:
            if not args.module:
                raise SystemExit("[ERROR] Require --module when --yaml is not provided.")
            target = _find_target_yaml(hints["source_file"], args.module)

        if not target or not target.exists():
            results.append({
                "source_file": hints["source_file"],
                "changed": False,
                "error": "target yaml not found",
            })
            continue

        if args.dry_run:
            results.append({
                "source_file": hints["source_file"],
                "yaml_path": str(target),
                "changed": False,
                "dry_run": True,
                "actions": hints.get("actions", []),
            })
            continue

        patched = patch_yaml_with_hints(target, hints, config)
        patched["source_file"] = hints["source_file"]
        patched["actions"] = hints.get("actions", [])
        results.append(patched)

    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
