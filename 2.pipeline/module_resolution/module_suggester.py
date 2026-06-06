from dataclasses import dataclass
import re
import unicodedata

@dataclass
class SuggestionResult:
    endpoint: str
    suggested_module: str | None
    final_module: str | None
    user_selected: str | None
    confidence_score: float
    confidence_label: str
    reason: str
    service_in_doc: str
    conflict: bool
    conflict_reason: str
    action: str
    review_type: str
    status: str
    matched_pattern: str | None
    source: str

def _normalize_name(value: str | None) -> str:
    value = str(value or "").strip().lower()
    value = unicodedata.normalize("NFD", value)
    value = value.encode("ascii", "ignore").decode()
    value = re.sub(r"[^a-zA-Z0-9]+", "_", value)
    return value.strip("_")

def _normalize_endpoint(endpoint: str) -> str:
    endpoint = str(endpoint or "").strip().lower()
    endpoint = endpoint.split("?")[0]
    endpoint = re.sub(r"/+", "/", endpoint)
    return endpoint

def _match_endpoint_rule(endpoint: str, segments: list[str], endpoint_rules: dict) -> tuple[str | None, str | None]:
    normalized_endpoint = _normalize_endpoint(endpoint)
    normalized_segments = {_normalize_name(s) for s in segments}

    for module, rule in endpoint_rules.items():
        module_norm = _normalize_name(module)

        for pattern in rule.get("patterns", []):
            pattern_text = str(pattern or "").strip().lower()
            pattern_segment = _normalize_name(pattern_text.strip("/"))

            if pattern_text and pattern_text in normalized_endpoint:
                return module_norm, pattern

            if pattern_segment and pattern_segment in normalized_segments:
                return module_norm, pattern
    return None, None

def suggest_module(
    segments: list[str],
    endpoint: str,
    endpoint_rules: dict,
    service_in_doc: str,
    user_selected: str | None = None,
) -> SuggestionResult:

    suggested_module, matched_pattern = _match_endpoint_rule(
        endpoint=endpoint,
        segments=segments,
        endpoint_rules=endpoint_rules
    )

    user_norm = _normalize_name(user_selected)
    service_norm = _normalize_name(service_in_doc)

    if user_norm:
        final_module = user_norm
        source = "user_selected"
    elif suggested_module:
        final_module = suggested_module
        source = "endpoint_rule"
    else:
        final_module = None
        source = "unresolved"
    
    if not final_module:
        conflict = False
        conflict_reason = ""
        score = 0.20
        label = "low"
        reason = "no module resolved"
        status = "needs_review"
        action = "pending_review"
        review_type = "pending_approval"

        return SuggestionResult(
            endpoint=endpoint,
            suggested_module=suggested_module,
            final_module=final_module,
            user_selected=user_norm or None,
            service_in_doc=service_norm,
            confidence_score=score,
            confidence_label=label,
            reason=reason,
            conflict=conflict,
            conflict_reason=conflict_reason,
            action=action,
            review_type=review_type,
            status=status,
            matched_pattern=matched_pattern,
            source=source,
        )

    if not service_norm:
        conflict = False
        conflict_reason = ""
    elif service_norm == final_module:
        conflict = False
        conflict_reason = ""
    else:
        conflict = True
        conflict_reason = (
            f"service_in_doc='{service_norm}' differs from final_module='{final_module}'"
        )

    if suggested_module is None:
        score = 0.20
        reason = "no endpoint pattern matched"
    elif not service_norm:
        score = 0.80
        reason = "endpoint matched, service field empty"
    elif conflict:
        score = 0.60
        reason = f"endpoint matched but service_in_doc='{service_norm}' differs"
    else:
        score = 0.95
        reason = "endpoint matched and service field agrees"

    label = "high" if score >= 0.9 else "medium" if score >= 0.5 else "low"

    if not conflict:
        status = "auto_approved"
        action = "none"
        review_type = "none"
    elif conflict and user_norm:
        status = "auto_approved"
        action = "logged"
        review_type = "logged_conflict"
    else: 
        status = "needs_review"
        action = "pending_review"
        review_type = "pending_approval"

    return SuggestionResult(
        endpoint=endpoint,
        suggested_module=suggested_module,
        final_module=final_module,
        user_selected=user_norm or None,
        service_in_doc=service_norm,
        confidence_score=score,
        confidence_label=label,
        reason=reason,
        conflict=conflict,
        conflict_reason=conflict_reason,
        action=action,
        review_type=review_type,
        status=status,
        matched_pattern=matched_pattern,
        source=source,
    )