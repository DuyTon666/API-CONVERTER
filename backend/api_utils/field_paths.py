from dataclasses import dataclass

@dataclass(frozen=True)
class PathSegment:
    key: str
    selector: str | None = None
    match_field: str | None = None

def parse_path(path_str: str) -> list[PathSegment]:
    segments = []
    for part in path_str.split("."):
        if "[" not in part:
            segments.append(PathSegment(key=part))
            continue
        key, rest = part.split("[", 1)
        inner = rest.rstrip("]")
        if inner.startswith("name="):
            segments.append(PathSegment(key=key, selector=inner[len("name="):], match_field="name"))
        else:
            segments.append(PathSegment(key=key, selector=inner))
    return segments

def format_path(segments: list[PathSegment]) -> str:
    parts = []
    for seg in segments:
        if seg.match_field:
            parts.append(f"{seg.key}[{seg.match_field}={seg.selector}]")
        elif seg.selector is not None:
            parts.append(f"{seg.key}[{seg.selector}]")
        else:
            parts.append(seg.key)
    return ".".join(parts)

def get_value_at_path(node: dict, path_str: str) -> tuple[bool, object]:
    current = node
    for seg in parse_path(path_str):
        if seg.match_field:
            if not isinstance(current, dict):
                return False, None
            items = current.get(seg.key)
            if not isinstance(items, list):
                return False, None
            found_item = None
            for item in items:
                if isinstance(item, dict) and item.get(seg.match_field) == seg.selector:
                    found_item = item
                    break
            if found_item is None:
                return False, None
            current = found_item
        elif seg.selector is not None:
            if not isinstance(current, dict):
                return False, None
            container = current.get(seg.key)
            if not isinstance(container, dict) or seg.selector not in container:
                return False, None
            current = container[seg.selector]
        else:
            if not isinstance(current, dict) or seg.key not in current:
                return False, None
            current = current[seg.key]
    return True, current

def set_value_at_path(node: dict, path_str: str, value: object) -> bool:
    segments = parse_path(path_str)
    if not segments:
        return False

    current = node
    for seg in segments[:-1]:
        if seg.match_field:
            if not isinstance(current, dict):
                return False
            items = current.get(seg.key)
            if not isinstance(items, list):
                return False
            found_item = None
            for item in items:
                if isinstance(item, dict) and item.get(seg.match_field) == seg.selector:
                    found_item = item
                    break
            if found_item is None:
                return False
            current = found_item
        elif seg.selector is not None:
            if not isinstance(current, dict):
                return False
            container = current.get(seg.key)
            if not isinstance(container, dict) or seg.selector not in container:
                return False
            current = container[seg.selector]
        else:
            if not isinstance(current, dict) or seg.key not in current:
                return False
            current = current[seg.key]

    last = segments[-1]
    if not isinstance(current, dict):
        return False
    if last.match_field:
        items = current.get(last.key)
        if not isinstance(items, list):
            return False
        for i, item in enumerate(items):
            if isinstance(item, dict) and item.get(last.match_field) == last.selector:
                items[i] = value
                return True
        return False
    elif last.selector is not None:
        container = current.get(last.key)
        if not isinstance(container, dict):
            return False
        container[last.selector] = value
        return True
    else:
        current[last.key] = value
        return True
