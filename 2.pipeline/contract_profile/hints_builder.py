from __future__ import annotations
from pathlib import Path

from contract_profile.loader import load_contract_profile
from contract_profile.document_reader import read_document
from contract_profile.section_matcher import detect_sections, extract_section_texts
from contract_profile.enum_inferer import infer_enums
from contract_profile.response_mode_detector import (
    find_content_types,
    detect_response_headers,
    detect_response_modes,
)
from validators.validation_model import (
    ValidationResult,
    SEVERITY_LOW,
    SOURCE_RULE_BASED,
    FIX_MANUAL,
)
from validators.review_engine import ReviewEngine
from contract_profile.header_detector import detect_request_headers
from contract_profile.status_detector import detect_status_codes

def _has_mode(modes: list[dict], mode_name: str) -> bool:
    return any(m.get("mode") == mode_name for m in modes)


def _build_actions(
    content_types: list[str],
    response_headers: list[str],
    response_modes: list[dict],
    enum_candidates: list[dict],
    request_headers: list[dict],
    status_codes: list[dict],
) -> list[str]:
    actions: list[str] = []

    if _has_mode(response_modes, "binary_file"):
        actions.append("add_binary_response")

    if _has_mode(response_modes, "multi_format"):
        actions.append("handle_multi_format_response")

    if response_headers:
        actions.append("add_response_headers")

    if enum_candidates:
        actions.append("fix_query_enum")

    if "application/zip" in content_types and "application/json" in content_types:
        actions.append("ensure_zip_and_json_200_response")

    if any(h.get("emit") and h.get("ref") for h in request_headers):
        actions.append("add_request_headers")

    if any(item.get("status") == "409" for item in status_codes):
        actions.append("add_conflict_response")

    return sorted(set(actions))


def build_contract_hints(path: str | Path, module: str = "unknown", emit_to_queue: bool = True) -> dict:
    path = Path(path)
    config = load_contract_profile()
    text = read_document(path)
    section_texts = extract_section_texts(text, config)

    response_headers_text = section_texts.get("response_headers", "")
    request_headers_text = section_texts.get("request_headers", "")
    error_response_text = section_texts.get("error_response", "")

    sections = detect_sections(text, config)
    content_types = find_content_types(text)
    response_headers = detect_response_headers(response_headers_text, config)
    response_modes = detect_response_modes(text, config)
    enum_candidates = infer_enums(text, config)
    request_headers = detect_request_headers(request_headers_text, config)
    status_codes = detect_status_codes(error_response_text, config)

    actions = _build_actions(
        content_types=content_types,
        response_headers=response_headers,
        response_modes=response_modes,
        enum_candidates=enum_candidates,
        request_headers=request_headers,
        status_codes=status_codes,
    )

    result = {
        "source_file": str(path),
        "source_format": path.suffix.lower().lstrip("."),
        "text_length": len(text),
        "sections": sections,
        "section_text_lengths": {
            key: len(value)
            for key, value in sorted(section_texts.items())
        },
        "response_contract": {
            "content_types": content_types,
            "response_headers": response_headers,
            "response_modes": response_modes,
        },
        "request_contract": {
            "request_headers": request_headers,
        },
        "error_contract": {
            "status_codes": status_codes,
        },
        "query_enum_candidates": enum_candidates,
        "actions": actions,
    }

    if emit_to_queue:
        sections_cfg = config.get("section_aliases", {}).get("sections", {})
        missed = [
            name for name, info in sections.items()
            if not info.get("found", False)
            and sections_cfg.get(name, {}).get("required", False)
        ]
        if missed:
            reviewer = ReviewEngine()
            reviewer.load()
            for section_name in missed:
                result = ValidationResult(
                    type            = "section_not_detected",
                    severity        = SEVERITY_LOW,
                    confidence      = 1.0,
                    source          = SOURCE_RULE_BASED,
                    fix_strategy    = FIX_MANUAL,                    
                    review_required = True,
                    module          = module,
                    file            = Path(path).name,
                    output          = str(path),
                    detail          = {
                        "section":    section_name,
                        "reason":      "Không tìm thấy allias khớp trong tài liệu",
                        "suggestion": f"Thêm alias Việt/Anh cho section '{section_name}'"
                    },
                )
                reviewer.add(result)
            reviewer.save()
            print(f"[hints_builder] {len(missed)} section không detect được → ghi queue.")
    return result