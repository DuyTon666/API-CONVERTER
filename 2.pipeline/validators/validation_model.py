# validators/validation_model.py
# Schema chuẩn cho mọi kết quả validation trong pipeline.
# Tất cả validator phải trả về ValidationResult thay vì dict thô.

import datetime
from dataclasses import dataclass, field, asdict
from typing import Any


#Hằng số severity 
SEVERITY_HIGH   = "high"
SEVERITY_MEDIUM = "medium"
SEVERITY_LOW    = "low"

#Hằng số source 
SOURCE_RULE_BASED = "rule_based"
SOURCE_CLAUDE     = "claude"
SOURCE_HEURISTIC  = "heuristic"

#Hằng số fix_strategy 
FIX_MANUAL         = "manual"
FIX_AUTO_FIXABLE   = "auto_fixable"
FIX_NO_FIX_NEEDED  = "no_fix_needed"


@dataclass
class ValidationResult:
    #Thông tin phân loại issue 
    type:            str    # vd: content_type_mismatch, action_style_endpoint
    severity:        str    # high / medium / low
    confidence:      float  # 0.0 → 1.0
    source:          str    # rule_based / claude / heuristic
    fix_strategy:    str    # manual / auto_fixable / no_fix_needed
    review_required: bool

    #Định vị file
    module:  str
    file:    str   # tên file, vd: create_user_ticket.yaml
    output:  str   # đường dẫn tuyệt đối

    #Chi tiết đặc thù của từng loại issue 
    detail: dict = field(default_factory=dict)

    #Timestamp
    detected_at: str = field(
        default_factory=lambda: datetime.datetime.now().isoformat(timespec="seconds")
    )

    #Serialization

    def to_dict(self) -> dict[str, Any]:
        """Chuyển sang dict để ghi JSON (human_review_queue.json)."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ValidationResult":
        """Tạo lại ValidationResult từ dict đọc ra từ JSON."""
        return cls(
            type            = data["type"],
            severity        = data["severity"],
            confidence      = data.get("confidence", 1.0),
            source          = data.get("source", SOURCE_RULE_BASED),
            fix_strategy    = data.get("fix_strategy", FIX_MANUAL),
            review_required = data.get("review_required", True),
            module          = data["module"],
            file            = data["file"],
            output          = data.get("output", ""),
            detail          = data.get("detail", {}),
            detected_at     = data.get("detected_at", ""),
        )

    #Dedup key — dùng trong review_engine 

    def dedup_key(self) -> tuple[str, str, str]:
        """Key để kiểm tra duplicate: (type, module, file)."""
        extra = self.detail.get("section", "") if self.type == "section_not_detected" else ""
        return (self.type, self.module, self.file, extra)