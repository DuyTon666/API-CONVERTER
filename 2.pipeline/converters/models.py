from dataclasses import dataclass, field


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
    request_body_children: dict = field(default_factory=dict)
    review_flags: list = field(default_factory=list)
    version: str = ""
    query_parameters: list = field(default_factory=list)
    change_history: list = field(default_factory=list)