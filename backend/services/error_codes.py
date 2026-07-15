"""Review & xác nhận mã lỗi nghiệp vụ (x-error-responses) trước khi ghi chính
thức vào 4.config/errors/. Đọc report do CLI `errors:parse` (2.pipeline, chạy
tay bởi người phụ trách 2.pipeline/) sinh sẵn — không tự chạy lại parse ở đây.
resolve/apply gọi thẳng 2 hàm cmd_* có sẵn trong contract_profile — không sửa
gì trong 2.pipeline/, chỉ import dùng lại, giống cách core/config.py đã làm
với generator.emitter.
"""

import io
import json
import re
from contextlib import redirect_stdout

from core.config import REPORTS_DIR
from core.errors import ErrorCode, http_error


def _report_path(module: str):
    return REPORTS_DIR / "errors" / module / "error_codes_review.json"


def list_error_entries(module: str) -> dict:
    """Đọc report review đã có sẵn (entries + summary) — không sinh mới gì."""
    path = _report_path(module)
    if not path.exists():
        raise http_error(
            404,
            ErrorCode.ERROR_REPORT_NOT_FOUND,
            f"Chưa có report mã lỗi cho module '{module}' — cần chạy "
            "errors:parse trước (người phụ trách 2.pipeline).",
        )
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_error_entry(
    module: str,
    code: str,
    decision: str,
    approved_by: str,
    new_code: str | None = None,
    source_file: str | None = None,
) -> dict:
    """Ghi resolution cho 1 entry trong report — CHƯA ghi vào catalog chính
    thức (đó là việc của apply_error_entries). Trả về report đã đọc lại."""
    from contract_profile.run_error_parser import cmd_resolve_error

    if not approved_by or not approved_by.strip():
        raise http_error(
            400, ErrorCode.INVALID_ERROR_RESOLVE, "Thiếu tên người duyệt (approved_by)"
        )

    buf = io.StringIO()
    with redirect_stdout(buf):
        cmd_resolve_error(
            module=module,
            code=str(code),
            decision=decision,
            approved_by=approved_by.strip(),
            new_code=new_code,
            source_file=source_file,
        )
    output = buf.getvalue().strip()

    report = list_error_entries(module)
    entry = next(
        (
            e
            for e in report.get("entries", [])
            if str(e["code"]) == str(code)
            and (source_file is None or e.get("source_file") == source_file)
        ),
        None,
    )

    # cmd_resolve_error không raise khi gặp lỗi nghiệp vụ (code không tồn tại,
    # trùng nhiều source_file chưa chọn, resolution không hợp lệ...) — nó chỉ
    # print rồi return None, không có gì để phân biệt qua giá trị trả về. Cách
    # đáng tin cậy hơn là soi thẳng field "resolution" trong report vừa đọc
    # lại: nếu hàm chạy đúng, field này chắc chắn đã khớp decision vừa gửi;
    # nếu không, coi là thất bại và trả lại đúng dòng nó đã in ra (đã là câu
    # giải thích tiếng Việt sẵn có, không cần tự soạn lại).
    if (
        entry is None
        or not entry.get("resolution")
        or entry["resolution"].get("decision") != decision
    ):
        raise http_error(
            400,
            ErrorCode.INVALID_ERROR_RESOLVE,
            output or "Resolve thất bại, không rõ lý do.",
        )

    return report


def apply_error_entries(module: str) -> dict:
    """Đẩy toàn bộ entry đã resolve trong report lên 4.config/errors/ (global
    map hoặc module catalog). Entry chưa resolve tự bị bỏ qua (skipped)."""
    from contract_profile.run_error_parser import cmd_apply_errors

    buf = io.StringIO()
    with redirect_stdout(buf):
        cmd_apply_errors(module=module)
    output = buf.getvalue()

    # apply_decisions() không return gì và cũng không ghi ngược lại report —
    # chỉ ghi 4.config/errors/**, nên không có file nào để đọc lại đối chiếu
    # (khác hẳn resolve_error_entry ở trên). Cách duy nhất lấy được số liệu có
    # cấu trúc là soi đúng khối tóm tắt cố định nó luôn in ra cuối cùng.
    def _count(label: str) -> int:
        match = re.search(rf"{label}\s*:\s*(\d+)", output)
        return int(match.group(1)) if match else 0

    return {
        "applied": _count("Applied"),
        "skipped": _count("Skipped"),
        "rejected": _count("Rejected"),
        "raw_output": output,
    }
