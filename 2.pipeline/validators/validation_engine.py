# validators/validation_engine.py
# Orchestrate tất cả validator theo thứ tự.
# converter.py chỉ gọi run_validation() — không gọi trực tiếp từng validator.

from validators.review_engine import ReviewEngine
from validators.content_type_validator import validate_content_types
from validators.side_effects_validator import validate_side_effects
from validators.restfulness_validator import validate_restfulness

#Danh sách validator theo thứ tự chạy 
# Mỗi entry là tuple (tên, callable nhận module: str | None).
# Thêm validator mới: append vào list này, không sửa run_validation().
_VALIDATORS: list[tuple[str, callable]] = [
    ("content_type", validate_content_types),
    ("side_effects", validate_side_effects),
    ("restfulness", validate_restfulness),
]


def run_validation(module: str | None = None) -> dict:
    """
    Chạy tất cả validator theo thứ tự.

    Args:
        module: tên module cụ thể, hoặc None để chạy toàn bộ.

    Returns:
        summary dict — số lượng validator đã chạy, để converter.py log.
    """
    print(f"\n[validation_engine] Bắt đầu validation — module={module or 'ALL'}")
    print(f"[validation_engine] {len(_VALIDATORS)} validator đã đăng ký.")

    ran     = 0
    failed  = 0

    for name, validator_fn in _VALIDATORS:
        print(f"[validation_engine] → Chạy {name}_validator...")
        try:
            validator_fn(module=module)
            ran += 1
        except Exception as e:
            print(f"[ERROR] {name}_validator gặp lỗi: {e}")
            failed += 1

    print(
        f"[validation_engine] Hoàn tất — "
        f"ran={ran} failed={failed}"
    )

    return {"ran": ran, "failed": failed}
