from dataclasses import dataclass, field
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from converters.request_body.schema_models import SchemaParseResult


@dataclass
class ParsedOperation:
    summary: str = ""
    operation_id: str = ""
    description: str = ""
    method: str = ""
    path: str = ""
    service: str = ""
    content_type: str = "application/json"
    permission: str = ""
    parameters: list = field(default_factory=list)
    has_request_body: bool = False
    request_body_required: bool = True
    request_body_fields: list = field(default_factory=list)
    error_codes: list = field(default_factory=list)
    response_schemas: dict = field(default_factory=dict)
    success_status: str = ""
    request_schema_result: "SchemaParseResult | None" = None
    review_flags: list = field(default_factory=list)
    version: str = ""
    query_parameters: list = field(default_factory=list)
    change_history: list = field(default_factory=list)
    request_schema_result: "SchemaParseResult | None" = None