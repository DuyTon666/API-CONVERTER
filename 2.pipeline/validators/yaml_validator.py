from pathlib import Path
import yaml


def validate_yaml_file(path):
    path = Path(path)

    if not path.exists():
        raise RuntimeError(f"[WRITE ERROR] {path} does not exist")

    raw = path.read_bytes()

    if not raw:
        raise RuntimeError(f"[WRITE ERROR] {path} is empty")

    if b"\x00" in raw:
        raise RuntimeError(f"[WRITE ERROR] {path} contains NULL bytes")

    try:
        yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as e:
        raise RuntimeError(f"[WRITE ERROR] {path} invalid YAML: {e}")


def write_text_checked(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)

    validate_yaml_file(path)