# Bổ sung test cho `backend/services/ai_fix.py`

## Context

`backend/tests/test_ai_fix.py` hiện chỉ test 5 hàm thuần nhỏ
(`_merge_overlapping_ranges`, `_parse_ai_json`, `_get_breadcrumb`,
`_get_parent_block`, `_build_batch_prompt`) — mỗi hàm 1-2 case. Hàm **chính**
của cả module, `run()` (orchestrator gọi Claude để tự sửa lỗi lint), và
`fix_bundle()` (wrapper validate payload rồi gọi `run()`), **chưa có test
nào**. `_parse_checkstyle_output()` cũng chưa có test. Đây là phần rủi ro cao
nhất trong file vì chứa nhiều nhánh rẽ (lọc severity, phân loại
resolved/unresolved, validate kết quả AI, phân biệt 2 lý do fail khác nhau)
mà chưa được khoá lại bằng test — sửa nhầm 1 dòng có thể âm thầm phá vỡ logic
mà không ai biết.

Mục tiêu: lấp các lỗ hổng này trong đúng 1 file `backend/tests/test_ai_fix.py`
(không đổi code sản phẩm `ai_fix.py`), theo đúng quy ước mock đã dùng nhất
quán trong toàn bộ `backend/tests/` (xác nhận qua khảo sát toàn bộ file test
hiện có): dùng `monkeypatch` của pytest + fake object viết tay, **không**
dùng `unittest.mock`/`pytest-mock`. Không có `conftest.py` trong repo — fixture
khai báo cục bộ trong file.

## Điểm kỹ thuật cần lưu ý (đã verify trên code thật)

- `run()` làm `import anthropic` **bên trong thân hàm**
  (`backend/services/ai_fix.py:129`), không phải ở đầu file — nên phải patch
  thẳng module `anthropic` gốc (`monkeypatch.setattr(anthropic, "Anthropic", ...)`),
  không patch qua `services.ai_fix.anthropic` (tên đó không tồn tại ở cấp
  module trong `ai_fix.py`).
- `http_error()` (`backend/core/errors.py:49`) **trả về** `HTTPException`,
  không tự raise — `fix_bundle()` gọi `raise http_error(...)`. Test theo đúng
  quy ước đã dùng ở `test_import_jobs.py`:
  ```python
  with pytest.raises(HTTPException) as exc_info:
      fix_bundle(payload)
  assert exc_info.value.status_code == 400
  assert exc_info.value.detail["code"] == "EMPTY_BUNDLE"
  ```
- Các chuỗi lý do (Vietnamese) phải khớp **verbatim** với `ai_fix.py`:
  - Spectral thiếu range: `"Không có range, không xác định được vị trí sửa"`
  - Redocly thiếu line: `"Không xác định được vị trí (thiếu line/column) — cần sửa tay"`
  - AI call lỗi: `"Lỗi gọi AI cho nhóm này (xem log server)"`
  - AI trả sai: `"AI không trả về kết quả hợp lệ cho vị trí này"`

## Sửa import ở đầu `test_ai_fix.py`

```python
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
```

## Fixture/fake dùng chung (thêm 1 lần, sau phần import)

```python
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
```

## Test case cần thêm

### Ưu tiên 1 — `run()`

| Test | Arrange chính | Assert chính |
|---|---|---|
| `test_run_filters_out_issues_with_non_matching_severity` | spectral severity=1, redocly severity="warning" | `result == {"patches": [], "unresolved": [], "failed": []}` — **không** gọi `fake_anthropic` (không cần fixture) |
| `test_run_marks_spectral_issue_without_range_as_unresolved` | spectral severity=0, không có `"range"` | `unresolved` có 1 entry với `reason` đúng chuỗi trên |
| `test_run_marks_redocly_issue_without_line_as_unresolved` | redocly severity="error", không có `"line"` | tương tự, reason của redocly |
| `test_run_returns_early_and_never_calls_ai_when_nothing_resolved` | gộp 2 case trên, có cài `fake_anthropic("{}")` | `len(unresolved) == 2`, và **`fake_messages.calls == []`** (chứng minh không gọi AI) |
| `test_run_validates_and_returns_successful_patch` | 1 spectral có `range` hợp lệ, `fake_anthropic('{"patches": [{"id": "loc-0", "fixed_text": "  title: New Title"}]}')` | `len(patches) == 1`, đúng `id`/`start_line`/`end_line`/`original_text`/`fixed_text`/`issues` |
| `test_run_moves_invalid_ai_fix_to_failed` | AI trả `fixed_text` phá YAML (vd `"  title: 'unterminated"`) | `len(failed) == 1`, reason = "AI không trả về kết quả hợp lệ..." |
| `test_run_moves_patches_to_failed_when_ai_call_raises` | `fake_anthropic(RuntimeError("network down"))` | `len(failed) == 1`, reason = "Lỗi gọi AI..." — **khác** reason ở test trên |

Case bonus (không bắt buộc, đánh dấu optional): `test_run_splits_into_multiple_batches_of_25` — cần 26 issue + patch `ai_fix_module.time.sleep`. Bỏ qua trong lần này, có thể làm sau nếu muốn full coverage `BATCH_SIZE`.

### Ưu tiên 2 — `fix_bundle()`

| Test | Arrange | Assert |
|---|---|---|
| `test_fix_bundle_raises_400_when_content_empty` | `payload = {"content": "", "spectral": [{"severity": 0}], "redocly": []}` | `pytest.raises(HTTPException)`, status 400, code `"EMPTY_BUNDLE"` |
| `test_fix_bundle_raises_400_when_content_missing` | `payload = {"spectral": [], "redocly": []}` (không có key `"content"`) | tương tự — khoá nhánh `payload.get("content") or ""` |
| `test_fix_bundle_short_circuits_when_no_spectral_or_redocly` | `payload = {"content": "openapi: 3.1.0\n", "spectral": [], "redocly": []}`, patch `ai_fix_module.run` thành hàm raise `AssertionError` nếu bị gọi | `result == {"patches": [], "unresolved": [], "failed": []}`, không có `AssertionError` nào nổi lên |

### Ưu tiên 3 — `_parse_checkstyle_output()`

| Test | Arrange | Assert |
|---|---|---|
| `test_parse_checkstyle_output_parses_multiple_errors` | XML checkstyle có 2 `<error>` | list 2 dict đúng `ruleId`/`message`/`line`/`column` (đọc từ `source`, không đọc `severity`) |
| `test_parse_checkstyle_output_returns_empty_list_on_malformed_xml` | chuỗi XML không đóng tag | `result == []` (nhánh `except ET.ParseError`) |

### Ưu tiên 4 — lỗ hổng trong hàm đã có test

| Test | Ghi chú |
|---|---|
| `test_merge_overlapping_ranges_returns_empty_list_for_empty_input` | `_merge_overlapping_ranges([])` → khoá nhánh `if not ranges: return []` |
| `test_get_parent_block_returns_empty_string_for_top_level_field` | dùng lại fixture `NESTED_YAML_LINES` có sẵn, `target_line=0` ("paths:") → `""` |
| `test_get_parent_block_returns_empty_string_when_only_one_level_of_nesting` | `target_line=1` ("  /tickets/{id}:") → nhánh early-return **khác** (`parent_start_line is None`), 2 nhánh return "" độc lập trong cùng hàm |
| `test_build_batch_prompt_omits_parent_section_when_parent_text_empty` | patch có `"parent_text": ""` → assert `"Object cha" not in prompt` |
| `test_build_batch_prompt_includes_multiple_patches` | 2 patch → assert `prompt.count("LOCATION_ID") == 2`, cả 2 `id`/breadcrumb đều xuất hiện |

## Verify

```bash
cd backend && .venv/bin/python -m pytest tests/test_ai_fix.py -q
```
Toàn bộ test cũ (8 test) + test mới (~17 test) phải pass. Không cần
`ANTHROPIC_API_KEY` thật vì `anthropic.Anthropic` luôn bị patch trước khi
gọi trong mọi test có đụng tới `run()`.
