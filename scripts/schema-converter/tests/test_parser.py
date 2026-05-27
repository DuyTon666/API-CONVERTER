import sys
import os
sys.path.insert(0, "src")

from schema_converter.parser import parse_text
from schema_converter.emitter import emit_yaml

SAMPLE = """
PUT /v1/users/{user_id}/tickets/{id}/close HTTP/1.1
account apigateway.example.vn PUT
Content-Type: application/json
Middleware: permission:CHECK_NEWUPDATE

4.2 Request Parameters
a. Path Parameters
user_id ✔️ Integer UID của khách hàng
id ✔️ Integer Id ticket

b. Query Parameters
Không có

4.3 Request Body
Không có

4.4 Quy tắc validate input

5.2.3 Danh sách mã lỗi
4102 Auth Token không hợp lệ
4108 Auth IP không được phép
4200 Input validation
4004 Not Found
4463 Tạo phản hồi thất bại
4464 Câu hỏi đã đóng
"""

def test_parse_method():
    result = parse_text(SAMPLE)
    assert result.method == "PUT"

def test_parse_path():
    result = parse_text(SAMPLE)
    assert result.path == "/v1/users/{user_id}/tickets/{id}/close"

def test_no_request_body():
    result = parse_text(SAMPLE)
    assert result.has_request_body == False

def test_error_codes():
    result = parse_text(SAMPLE)
    assert "4102" in result.error_codes
    assert "4200" in result.error_codes

def test_permission():
    result = parse_text(SAMPLE)
    print(f"\nPermission parsed: '{result.permission}'")
    assert result.permission == "CHECK_NEWUPDATE"

def test_path_parameters():
    result = parse_text(SAMPLE)
    names = [p["name"] for p in result.parameters]
    assert "user_id" in names
    assert "id" in names

def test_emit_yaml():
    result = parse_text(SAMPLE)
    emit_yaml(result, "tests/output/close-ticket.yaml")
    assert os.path.exists("tests/output/close-ticket.yaml")

def test_error_codes_no_false_positive():
    """4000 trong 'Tối đa 4000 ký tự' không được bắt nhầm thành error code"""
    text = "5.2.3 Danh sách mã lỗi\n4200\tInput\tDữ liệu không hợp lệ\n4466\t\tQuá thời hạn\n\nTối đa 4000 ký tự"
    op = parse_text(text)
    assert '4000' not in op.error_codes
    assert '4200' in op.error_codes

def test_request_body_required():
    """File có ✔ trong request body → required: true"""
    text = "PUT /v1/test\n4.3 Request Body\nTên\tBắt buộc\tKiểu\nfield1\t✔\tString\n4.4 Validate"
    op = parse_text(text)
    assert op.has_request_body is True
    assert op.request_body_required is True

def test_request_body_optional():
    """File không có ✔ → required: false"""
    text = "POST /v1/test\n4.3 Request Body\nTên\tBắt buộc\tKiểu\nfield1\t✖\tString\n4.4 Validate"
    op = parse_text(text)
    assert op.request_body_required is False

def test_request_body_fields_maxlength():
    """Extract maxLength từ description"""
    text = "POST /v1/test\n4.3 Request Body\nTên\tBắt buộc\tKiểu\tMô tả\ndescriptions\t✖\tString\tNội dung - Tối đa 4000 ký tự\n4.4 Validate"
    op = parse_text(text)
    field = next((f for f in op.request_body_fields if f['name'] == 'descriptions'), None)
    assert field is not None
    assert field['max_length'] == 4000