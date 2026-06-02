import re
import yaml
import pandas as pd
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

@dataclass
class EndpointRecord:
    method:         str
    path:           str
    summary:        str
    tags:           list = field(default_factory=list)
    service:        str = ""
    author:         str = ""
    source_file:    Optional[str] = None

def _load_config(config_path: str) -> dict:
    return yaml.safe_load(Path(config_path).read_text(encoding="utf-8")) or {}

def _parse_endpoint(endpoint: str, method_col: str, valid_methods: set) -> tuple[str, str]:
    """
    Trả về (method, path).
    Case 1 — mixed:  "POST /v1/tickets"  → ("POST", "/v1/tickets")
    Case 2 — thuần:  "/v1/tickets"       → method lấy từ cột Method
    """
    endpoint = endpoint.strip()
    pattern = r'^(' + '|'.join(valid_methods) + r')\s+(/\S+)$'
    match = re.match(pattern, endpoint, re.IGNORECASE)
    if match:
        return match.group(1).upper(), match.group(2)
    if endpoint.startswith("/"):
        m = method_col.strip().upper() if pd.notna(method_col) else ""
        return m, endpoint
    return "", ""

def parse_df(df: pd.DataFrame, config_path: str) -> list[EndpointRecord]:
    cfg = _load_config(config_path).get("parser", {})
    valid_methods = set(cfg.get("valid_methods", []))

    records = []
    for _, row in df.iterrows():
        raw_endpoint =row.get("endpoint", "")
        if pd.isna(raw_endpoint) or not str(raw_endpoint).strip():
            continue

        method, path = _parse_endpoint(
            str(raw_endpoint),
            str(row.get("method", "")) if pd.notna(row.get("method")) else "",
            valid_methods
        )

        if not path or method not in valid_methods:
            continue

        def _str(col):
            v = row.get(col, "")
            return str(v).strip() if pd.notna(v) else ""

        source_file = _str("source_file") or None

        records.append(EndpointRecord(
            method         = method,
            path           = path,
            summary        = _str("summary"),
            tags           = [_str("group")] if _str("group") else [],
            service        = _str("service"),
            author         = _str("author"),
            source_file    = source_file,
        ))

    return records