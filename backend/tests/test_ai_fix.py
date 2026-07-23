import types
import pytest
from fastapi import HTTPException
import anthropic
import services.ai_fix as ai_fix_module
from services.ai_fix import (
    _merge_overlapping_ranges,
    _parse_ai_json,
    _parse_checkstyle_output,
    _get_breadcrumb,
    _get_parent_block,
    _build_batch_prompt,
    run,
    fix_bundle,
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


class _FakeAnthropicResponse:
    def __init__(self, text):
        self.content = [types.SimpleNamespace(text=text)]


class _FakeMessages:
    """responses: list các item tiêu thụ theo thứ tự gọi, 1 item/lần gọi batch.
    Item là chuỗi JSON (-> bọc thành response) hoặc 1 Exception (-> raise)."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return _FakeAnthropicResponse(item)


class _FakeAnthropicClient:
    def __init__(self, messages):
        self.messages = messages


@pytest.fixture
def fake_anthropic(monkeypatch):
    def _install(*responses):
        fake_messages = _FakeMessages(list(responses))
        monkeypatch.setattr(
            anthropic, "Anthropic", lambda *a, **k: _FakeAnthropicClient(fake_messages)
        )
        return fake_messages

    return _install


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


def test_merge_overlapping_ranges_returns_empty_list_for_empty_input():
    assert _merge_overlapping_ranges([]) == []


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


def test_run_filters_out_issues_with_non_matching_severity():
    spectral = [{"severity": 1, "code": "x", "message": "m", "range": {"start": {"line": 0}, "end": {"line": 0}}}]
    redocly = [{"severity": "warning", "ruleId": "y", "message": "n", "line": 0}]

    result = run("openapi: 3.1.0\n", spectral, redocly)

    assert result == {"patches": [], "unresolved": [], "failed": []}


def test_run_marks_spectral_issue_without_range_as_unresolved():
    spectral = [{"severity": 0, "code": "no-empty-description", "message": "thiếu mô tả"}]

    result = run("openapi: 3.1.0\n", spectral, [])

    assert result["patches"] == []
    assert len(result["unresolved"]) == 1
    assert result["unresolved"][0]["reason"] == "Không có range, không xác định được vị trí sửa"


def test_run_marks_redocly_issue_without_line_as_unresolved():
    redocly = [{"severity": "error", "ruleId": "no-empty-description", "message": "thiếu mô tả"}]

    result = run("openapi: 3.1.0\n", [], redocly)

    assert result["patches"] == []
    assert len(result["unresolved"]) == 1
    assert result["unresolved"][0]["reason"] == (
        "Không xác định được vị trí (thiếu line/column) - cần sửa tay"
    )


def test_run_returns_early_and_never_calls_ai_when_nothing_resolved(fake_anthropic):
    fake_messages = fake_anthropic("{}")
    spectral = [{"severity": 0, "code": "a", "message": "ma"}]
    redocly = [{"severity": "error", "ruleId": "b", "message": "mb"}]

    result = run("openapi: 3.1.0\n", spectral, redocly)

    assert len(result["unresolved"]) == 2
    assert fake_messages.calls == []


def test_run_validates_and_returns_successful_patch(fake_anthropic):
    content = "openapi: 3.1.0\ninfo:\n  title: ''\n"
    spectral = [
        {
            "severity": 0,
            "code": "no-empty-title",
            "message": "thiếu title",
            "range": {"start": {"line": 2}, "end": {"line": 2}},
        }
    ]
    fake_anthropic('{"patches": [{"id": "loc-0", "fixed_text": "  title: New Title"}]}')

    result = run(content, spectral, [])

    assert len(result["patches"]) == 1
    patch = result["patches"][0]
    assert patch["id"] == "loc-0"
    assert patch["start_line"] == 2
    assert patch["end_line"] == 2
    assert patch["original_text"] == "  title: ''"
    assert patch["fixed_text"] == "  title: New Title"
    assert patch["issues"] == [{"source": "spectral", "code": "no-empty-title", "message": "thiếu title"}]


def test_run_moves_invalid_ai_fix_to_failed(fake_anthropic):
    content = "openapi: 3.1.0\ninfo:\n  title: ''\n"
    spectral = [
        {
            "severity": 0,
            "code": "no-empty-title",
            "message": "thiếu title",
            "range": {"start": {"line": 2}, "end": {"line": 2}},
        }
    ]
    fake_anthropic('{"patches": [{"id": "loc-0", "fixed_text": "  title: \'unterminated"}]}')

    result = run(content, spectral, [])

    assert result["patches"] == []
    assert len(result["failed"]) == 1
    assert result["failed"][0]["reason"] == "AI không trả về kết quả hợp lệ cho vị trí này"


def test_run_moves_patches_to_failed_when_ai_call_raises(fake_anthropic):
    content = "openapi: 3.1.0\ninfo:\n  title: ''\n"
    spectral = [
        {
            "severity": 0,
            "code": "no-empty-title",
            "message": "thiếu title",
            "range": {"start": {"line": 2}, "end": {"line": 2}},
        }
    ]
    fake_anthropic(RuntimeError("network down"))

    result = run(content, spectral, [])

    assert result["patches"] == []
    assert len(result["failed"]) == 1
    assert result["failed"][0]["reason"] == "Lỗi gọi AI cho nhóm này (xem log server)"


def test_fix_bundle_raises_400_when_content_empty():
    payload = {"content": "", "spectral": [{"severity": 0}], "redocly": []}

    with pytest.raises(HTTPException) as exc_info:
        fix_bundle(payload)

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["code"] == "EMPTY_BUNDLE"


def test_fix_bundle_raises_400_when_content_missing():
    payload = {"spectral": [], "redocly": []}

    with pytest.raises(HTTPException) as exc_info:
        fix_bundle(payload)

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["code"] == "EMPTY_BUNDLE"


def test_fix_bundle_short_circuits_when_no_spectral_or_redocly(monkeypatch):
    def _fail_if_called(*args, **kwargs):
        raise AssertionError("run() không nên bị gọi khi không có spectral/redocly")

    monkeypatch.setattr(ai_fix_module, "run", _fail_if_called)

    payload = {"content": "openapi: 3.1.0\n", "spectral": [], "redocly": []}
    result = fix_bundle(payload)

    assert result == {"patches": [], "unresolved": [], "failed": []}


def test_parse_checkstyle_output_parses_multiple_errors():
    xml_text = (
        '<checkstyle version="1.0">'
        '<file name="bundle.yaml">'
        '<error line="5" column="3" severity="error" message="thiếu mô tả" source="no-empty-description"/>'
        '<error line="10" column="1" severity="warning" message="operationId sai" source="operation-id-valid"/>'
        "</file>"
        "</checkstyle>"
    )

    issues = _parse_checkstyle_output(xml_text)

    assert issues == [
        {"ruleId": "no-empty-description", "message": "thiếu mô tả", "line": 5, "column": 3},
        {"ruleId": "operation-id-valid", "message": "operationId sai", "line": 10, "column": 1},
    ]


def test_parse_checkstyle_output_returns_empty_list_on_malformed_xml():
    assert _parse_checkstyle_output("<checkstyle><file>") == []


def test_get_parent_block_returns_empty_string_for_top_level_field():
    assert _get_parent_block(NESTED_YAML_LINES, 0) == ""


def test_get_parent_block_returns_empty_string_when_only_one_level_of_nesting():
    assert _get_parent_block(NESTED_YAML_LINES, 1) == ""


def test_build_batch_prompt_omits_parent_section_when_parent_text_empty():
    patch = {
        "id": "loc-0",
        "breadcrumb": "paths./tickets.get.summary",
        "parent_text": "",
        "issues": [{"source": "spectral", "code": "x", "message": "m"}],
        "original_text": "  summary: ''",
    }

    prompt = _build_batch_prompt([patch])

    assert "Object cha" not in prompt


def test_build_batch_prompt_includes_multiple_patches():
    patch1 = {
        "id": "loc-0",
        "breadcrumb": "paths./tickets.get.summary",
        "parent_text": "",
        "issues": [{"source": "spectral", "code": "x", "message": "m1"}],
        "original_text": "  summary: ''",
    }
    patch2 = {
        "id": "loc-1",
        "breadcrumb": "paths./tickets.post.summary",
        "parent_text": "",
        "issues": [{"source": "spectral", "code": "y", "message": "m2"}],
        "original_text": "  summary: ''",
    }

    prompt = _build_batch_prompt([patch1, patch2])

    assert prompt.count("### LOCATION_ID:") == 2
    assert patch1["id"] in prompt and patch2["id"] in prompt
    assert patch1["breadcrumb"] in prompt and patch2["breadcrumb"] in prompt