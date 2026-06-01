import unicodedata 
import pandas as pd
import yaml
from pathlib import Path

def _load_config(config_path: str) -> dict:
    return yaml.safe_load(Path(config_path).read_text(encoding="utf-8")) or {}

def _normalize(text: str) -> str:
    text = str(text).strip().lower()
    text = unicodedata.normalize("NFD", text)
    return text.encode("ascii", "ignore").decode()

def _find_header_row(file_path: str, header_signals: set, max_scan_rows: int) -> int:
    probe = pd.read_excel(file_path, header=None, nrows=max_scan_rows, dtype=str)
    for i, row in probe.iterrows():
        normalize = {_normalize(v) for v in row.dropna()}
        if header_signals & normalize:
            return i
    return 0

def read_excel(file_path: str, config_path: str) -> pd.DataFrame:
    cfg = _load_config(config_path).get("reader", {})
    
    max_scan_rows = cfg.get("max_scan_rows", 5)
    header_signals = {_normalize(s) for s in cfg.get("header_signals", [])}
    column_map = {_normalize(k): v for k, v in cfg.get("column_map", {}).items()}

    header_row =  _find_header_row(file_path, header_signals, max_scan_rows)
    df = pd.read_excel(file_path, header=header_row, dtype=str)

    rename = {}
    for col in df.columns:
        key = _normalize(col)
        if key in column_map:
            rename[col] = column_map[key]

    df.rename(columns=rename, inplace=True)
    df = df.apply(lambda col: col.str.strip() if col.dtype == object else col)
    df.dropna(how="all", inplace=True)
    df.reset_index(drop=True, inplace=True)

    return df