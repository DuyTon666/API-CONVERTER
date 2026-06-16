from __future__ import annotations
import argparse
import json
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True)
    args = parser.parse_args()

    path = Path(args.file)
    config = load_contract_profile()
    text = read_document(path)

    section_texts = extract_section_texts(text, config)

    response_headers_text = section_texts.get("response_headers", "")

    result = {
        "file": str(path),
        "text_length": len(text),
        "sections": detect_sections(text, config),
        "section_text_lengths": {
            key: len(value)
            for key, value in sorted(section_texts.items())
        },
        "content_types": find_content_types(text),
        "response_headers": detect_response_headers(response_headers_text, config),
        "response_modes": detect_response_modes(text, config),
        "enum_candidates": infer_enums(text, config),
    }

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
