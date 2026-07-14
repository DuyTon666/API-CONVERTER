from pathlib import Path
import yaml

try:
    _LOADER = yaml.CSafeLoader
except AttributeError:
    _LOADER = yaml.SafeLoader


try: 
    _DUMPER = yaml.CSafeDumper
except AttributeError:
    _DUMPER = yaml.SafeDumper

_cache: dict[Path, tuple[float, dict]] = {}


# Đọc + parse YAML, cache theo (path, mtime) — file không đổi (mtime giống lần
# trước) thì trả thẳng bản đã parse trong RAM, không đọc/parse lại. Đúng với
# MỌI nơi ghi đè file (write_text hay subprocess ghi mới) vì mtime luôn đổi
# khi nội dung đổi — không cần gọi invalidate thủ công ở nơi ghi.
def load_yaml_cached(path: Path) -> dict:
    mtime = path.stat().st_mtime
    cached = _cache.get(path)
    if cached is not None and cached[0] == mtime:
        return cached[1]
    data = yaml.load(path.read_text(encoding="utf-8"), Loader=_LOADER) or {}
    _cache[path] = (mtime, data)
    return data


# Dump nhanh bằng CSafeDumper — dùng khi ghi file (không cache, vì nội dung
# ghi luôn là bản mới nhất, không có gì để cache).
def dump_yaml_fast(data: dict) -> str:
    return yaml.dump(
        data, Dumper=_DUMPER, allow_unicode=True, sort_keys=False, default_flow_style=False
    )