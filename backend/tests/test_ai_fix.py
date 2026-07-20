from services.ai_fix import (
    _merge_overlapping_ranges,
    _parse_ai_json,
    _get_breadcrumb,
    _get_parent_block,
    _build_batch_prompt,
)

# YAML mẫu mô phỏng đúng cấu trúc thật của 1 operation OpenAPI, nhiều cấp lồng
# nhau (path -> method -> response -> content -> schema -> properties -> field)
# -- tương ứng TC-AIFIX-04/05 trong docs/guidelines/manual-test-checklist.md,
# trước đây chỉ verify bằng script Python đứng riêng, giờ khoá lại thành pytest.
NESTED_YAML_LINES = [
    "paths:",  # 0
    "  /tickets/{id}:",  # 1
    "    get:",  # 2
    "      responses:",  # 3
    "        '200':",  # 4
    "          content:",  # 5
    "            application/json:",  # 6
    "              schema:",  # 7
    "                properties:",  # 8
    "                  status:",  # 9
    "                    type: string",  # 10
    "                    description: ''",  # 11 <- field lỗi (target_line)
    "                  priority:",  # 12  <- sibling của "status"
    "                    type: string",  # 13
]


def test_merge_overlapping_ranges_joins_touching_ranges():
    ranges = [
        {"start_line": 5, "end_line": 8, "issues": ["a"]},
        {"start_line": 7, "end_line": 10, "issues": ["b"]},
    ]
    merged = _merge_overlapping_ranges(ranges)
    assert len(merged) == 1
    assert merged[0]["start_line"] == 5
    assert merged[0]["end_line"] == 10
    assert merged[0]["issues"] == ["a", "b"]


def test_merge_overlapping_ranges_keeps_separate_when_not_touching():
    ranges = [
        {"start_line": 0, "end_line": 2, "issues": ["a"]},
        {"start_line": 5, "end_line": 8, "issues": ["b"]},
    ]
    merged = _merge_overlapping_ranges(ranges)
    assert len(merged) == 2


def test_parse_ai_json_parses_clean_json():
    assert _parse_ai_json('{"patches": []}') == {"patches": []}


def test_parse_ai_json_handles_text_wrapped_around_json():
    raw = "Đây là kết quả:\n{\"patches\": [{\"id\": \"loc-0\"}]}\nHết rồi."
    assert _parse_ai_json(raw) == {"patches": [{"id": "loc-0"}]}


def test_parse_ai_json_returns_empty_dict_when_unparseable():
    assert _parse_ai_json("không phải JSON gì cả") == {}


# TC-AIFIX-04: breadcrumb phải nối đúng đường dẫn khoá từ root tới field lỗi
def test_get_breadcrumb_builds_full_path_to_nested_field():
    breadcrumb = _get_breadcrumb(NESTED_YAML_LINES, 11)
    assert breadcrumb == (
        "paths./tickets/{id}.get.responses.'200'.content."
        "application/json.schema.properties.status.description"
    )


# TC-AIFIX-05: parent_text phải lấy đúng block cha (2 cấp dedent) chứa cả
# field lỗi ("status") lẫn sibling cùng cấp ("priority"), không chỉ riêng field
def test_get_parent_block_includes_sibling_field():
    parent_text = _get_parent_block(NESTED_YAML_LINES, 11)
    assert "status:" in parent_text
    assert "priority:" in parent_text
    assert parent_text.startswith("                properties:")


# DEF-04 (chất lượng AI-fix): prompt phải chứa chỉ dẫn rõ ràng chống mô tả
# chung chung/sai nghiệp vụ khi fix nhiều operation khác nhau trong 1 batch —
# khoá lại bằng test để lần sau lỡ tay xoá/rút gọn đoạn hướng dẫn này thì test
# báo fail ngay, thay vì phải chờ AI sinh sai rồi mới phát hiện lại.
def test_build_batch_prompt_warns_against_generic_description():
    patch = {
        "id": "loc-0",
        "breadcrumb": "paths./tickets/{id}/reopen.post.description",
        "parent_text": "post:\n  operationId: createReopen\n  summary: Mở lại ticket",
        "issues": [{"source": "spectral", "code": "no-empty-description", "message": "thiếu mô tả"}],
        "original_text": "      description: ''",
    }
    prompt = _build_batch_prompt([patch])

    assert "Lấy danh sách tài nguyên" in prompt  # ví dụ mô tả generic bị cấm
    assert "operationId" in prompt and "HTTP method" in prompt and "path" in prompt
    assert "loc-0" in prompt
    assert patch["breadcrumb"] in prompt
