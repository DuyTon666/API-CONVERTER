import sys
import json
import yaml
import unicodedata
import re
from pathlib import Path

sys.path.insert(0, "2.pipeline")

from converters.pdf.reader import read_pdf
from converters.pdf.parser import parse_text

CONFIG = "4.config/sources/pdf_sections.yaml"
REGISTRY = "4.config/module_registry.yaml"

def _load_yaml(path: str) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}

def _normalize_filename(pdf_name: str) -> str:
     """
    'API Contract - API đóng ticket của khách hàng.docx.pdf'
    → 'api_dong_ticket_cua_khach_hang'
    """
    name = Path(pdf_name).stem
    