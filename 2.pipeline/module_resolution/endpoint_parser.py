import re

def parse_endpoint(endpoint: str, ignored_segments: list[str]) -> list[str]:
    """
    Tách endpoint thành list resource đã lọc.

    Bước 1: tách theo "/"
    Bước 2: bỏ path parameter dạng {user_id}, {id}, ...
    Bước 3: bỏ segment nằm trong ignored_segments (đọc từ YAML)
    Bước 4: trả về list resource còn lại

    Ví dụ:
        endpoint         = "/v1/users/{user_id}/tickets/{id}/close"
        ignored_segments = ["v1", "users"]
        → ["tickets", "close"]
    """
    segments = endpoint.strip("/").split("/")

    segments = [s for s in segments if not re.fullmatch(r"\{.*?\}", s)]

    ignored_lower = [s.lower() for s in ignored_segments]
    segments = [s for s in segments if s.lower() not in ignored_lower]

    return segments

def extract_primary_resource(segments: list[str]) -> str | None:
    """
    Lấy resource nghiệp vụ chính từ list segment đã lọc.
    Thường là segment đầu tiên.

    Ví dụ:
        ["tickets", "close"] → "tickets"
        []                   → None
    """
    return segments[0] if segments else None