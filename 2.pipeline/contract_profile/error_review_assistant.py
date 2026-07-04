# 2.pipeline/contract_profile/error_review_assistant.py
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from error_review_policy import (
    ReviewEntry,
    flatten_review_entries,
    get_group_order,
    get_group_title,
    group_entries,
    message_similarity,
    policy_get,
    suggest_decision,
    suggest_http_status,
    to_review_entry,
)


ROOT = Path(__file__).resolve().parents[2]
REPORT_ROOT = ROOT / "3.build" / "reports" / "errors"


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def review_path(module: str) -> Path:
    return REPORT_ROOT / module / "error_codes_review.json"


def load_entries(module: str) -> list[ReviewEntry]:
    path = review_path(module)

    if not path.exists():
        raise FileNotFoundError(f"Không tìm thấy review file: {path}")

    data = load_json(path)
    raw_entries = flatten_review_entries(data)
    return [to_review_entry(raw) for raw in raw_entries]


def _norm_msg(text: str) -> str:
    return " ".join(str(text or "").strip().lower().split())


def summarize_by_code(entries: list[ReviewEntry]) -> dict[str, list[ReviewEntry]]:
    grouped: dict[str, list[ReviewEntry]] = {}

    for entry in entries:
        grouped.setdefault(str(entry.code), []).append(entry)

    return grouped


def unique_messages(entries: list[ReviewEntry]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []

    for entry in entries:
        msg = str(entry.incoming_message or "").strip()
        key = _norm_msg(msg)

        if not key:
            continue

        if key not in seen:
            seen.add(key)
            result.append(msg)
        
    return result


def unique_sources(entries: list[ReviewEntry]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []

    for entry in entries:
        source = str(entry.source or "").strip()
        if not source:
            continue

        if source not in seen:
            seen.add(source)
            result.append(source)

    return result


def min_message_similarity(messages: list[str]) -> float:
    clean = [msg for msg in messages if str(msg or "").strip()]

    if len(clean) <= 1:
        return 1.0

    scores: list[float] = []

    for i in range(len(clean)):
        for j in range(i + 1, len(clean)):
            scores.append(message_similarity(clean[i], clean[j]))

    return min(scores) if scores else 1.0


def policy_float(path: list[str], default: float) -> float:
    value = policy_get(path, default)

    try:
        return float(value)
    except Exception:
        return default


def policy_int(path: list[str], default: int) -> int:
    value = policy_get(path, default)

    try:
        return int(value)
    except Exception:
        return default


def is_likely_same_meaning(messages: list[str]) -> bool:
    threshold = policy_float(
        ["module_code_conflict", "same_meaning_threshold"],
        0.72,
    )
    return min_message_similarity(messages) >= threshold


def missing_http_default_status() -> str:
    return str(policy_get(["status_suggestion", "default"], "review"))


def is_missing_http_needs_review(entry: ReviewEntry) -> bool:
    suggested = suggest_http_status(entry)
    return suggested == missing_http_default_status()


def print_missing_http_summary(items: list[ReviewEntry], show_safe_http: bool = False) -> int:
    review_items: list[ReviewEntry] = []
    auto_items: list[ReviewEntry] = []

    for entry in items:
        if is_missing_http_needs_review(entry):
            review_items.append(entry)
        else:
            auto_items.append(entry)

    print()
    print(
        f"--- MISSING HTTP STATUS SUMMARY |"
        f" auto_suggested={len(auto_items)} |"
        f"needs_review={len(review_items)} |"
        f"total={len(items)} ---"
    )

    visible_items = items if show_safe_http else review_items

    if auto_items and not show_safe_http:
        print("Ẩn các mã đã suggest rõ. Dùng --show-safe-http để xem toàn bộ.")

    if not visible_items:
        print("OK: toàn bộ missing HTTP status đã có suggestion rõ.")
        return 0

    for idx, entry in enumerate(visible_items, 1):
        suggested = suggest_http_status(entry)

        print()
        print(f"[{idx:02d}] code={entry.code} source={entry.source or '-'}")
        print(f"    incoming : {entry.incoming_message or '-'}")
        print(f"    suggest  : http_status={suggested}")

        if entry.namespace:
            print(f"    namespace: {entry.namespace}")

        if entry.existing_http or entry.existing_message:
            print(
                f"     existing : "
                f"http={entry.existing_http or '-'} | "
                f"message={entry.existing_message or '-'}"
            )

    return len(visible_items)


def preview_text(text: str, max_chars: int) -> str:
    value = " ".join(str(text or "-").strip().split())

    if len(value) <= max_chars:
        return value

    return value[: max_chars - 3] + "..."

def print_parse_suspect_summary(items: list[ReviewEntry]) -> int:
    max_items_preview = policy_int(
        ["parse_suspect", "max_items_preview"],
        12,
    )
    max_text_preview_chars = policy_int(
        ["parse_suspect", "max_text_preview_chars"],
        120,
    )

    by_source: dict[str, list[ReviewEntry]] = {}

    for entry in items:
        source = entry.source or "-"
        by_source.setdefault(source, []).append(entry)

    print()
    print(
        f"--- PARSE SUSPECT MESSAGE SUMMARY | "
        f"count={len(items)} | "
        f"sources={len(by_source)} ---"
    )
    print("Các dòng này có message null/rỗng/JSON, cần kiểm tra parser hoặc source table.")

    shown = 0

    for source in sorted(by_source.keys()):
        entries = by_source[source]

        print ()
        print(f"- source={source} | count={len(entries)}")

        for entry in entries:
            if shown >= max_items_preview:
                break

            incoming = preview_text(
                entry.incoming_message,
                max_text_preview_chars,
            )
            category = preview_text(
                entry.category,
                max_text_preview_chars,
            )
            flag = " | intra_batch_conflict=True" if entry.intra_batch_conflict else ""

            print(
                f"  - code={entry.code} | "
                f"http={entry.incoming_http or '-'} | "
                f"incoming={incoming} | "
                f"category={category}"
                f"{flag}"
            )

            shown += 1

        if shown >= max_items_preview:
            break

    remaining = len(items) - shown

    if remaining > 0:
        print(f"... +{remaining} suspect entry khác. Dùng --detail để xem toàn bộ.")
    
    return len(items)


def list_modules() -> list[str]:
    if not REPORT_ROOT.exists():
        return []

    modules = []
    for child in sorted(REPORT_ROOT.iterdir()):
        if child.is_dir() and (child / "error_codes_review.json").exists():
            modules.append(child.name)

    return modules


def print_entry(index: int, entry: ReviewEntry, group: str) -> None:
    sim = message_similarity(entry.incoming_message, entry.existing_message)
    decision = suggest_decision(entry, group)

    print(f"[{index:02d}] code={entry.code} namespace={entry.namespace or '-'} source={entry.source or '-'}")
    print(
        f"     http     : incoming={entry.incoming_http or '-'} | "
        f"existing={entry.existing_http or '-'}"
    )

    if entry.category:
        print(f"     category : {entry.category}")

    print(f"     incoming : {entry.incoming_message or '-'}")

    if entry.existing_message:
        print(f"     existing : {entry.existing_message}")

    print(f"     similarity={sim:.2f} | suggest={decision}")

    if entry.intra_batch_conflict:
        print("     flag     : intra_batch_conflict=True")

    print()


def print_module_report(
    module: str,
    show_resolved: bool = False,
    show_new: bool = False,
    detail: bool = False,
    show_safe_http: bool = False,
) -> int:

    entries = load_entries(module)
    grouped = group_entries(entries, show_resolved=show_resolved, show_new=show_new)

    total_visible = sum(len(items) for items in grouped.values())
    report_items = 0

    print(f"\n==============================")
    print(f"Module: {module}")
    print(f"Review file: {review_path(module)}")
    print(f"Total entries loaded : {len(entries)}")
    print(f"Visible raw entries  : {total_visible}")

    if total_visible == 0:
        print("OK: không còn entry cần review.")
        return 0

    for group in get_group_order():
        items = grouped.get(group, [])
        if not items:
            continue

        if group == "PARSE_SUSPECT_MESSAGE" and not detail:
            report_items += print_parse_suspect_summary(items)
            continue

        if group == "INTRA_MODULE_CODE_REVIEW" and not detail:
            report_items += print_intra_module_summary(items)
            continue

        if group == "MISSING_HTTP_STATUS" and not detail:
            report_items += print_missing_http_summary(
                items,
                show_safe_http=show_safe_http,
            )
            continue

        print()
        print(f"=== {get_group_title(group)} | count={len(items)} ===")

        report_items += len(items)
        for idx, entry in enumerate(items, 1):
            print_entry(idx, entry, group)

    print()
    print(f"Visible report items : {report_items}")
    return report_items


def print_intra_module_summary(items: list[ReviewEntry]) -> int:
    by_code = summarize_by_code(items)
    max_messages_preview = policy_int(
        ["module_code_conflict", "max_messages_preview"],
        8,
    )
    max_sources_preview = policy_int(
        ["module_code_conflict", "max_sources_preview"],
        6,
    )
    conflict_codes: list[str] = []

    for code in sorted(by_code.keys()):
        entries = by_code[code]
        messages = unique_messages(entries)

        if not is_likely_same_meaning(messages):
            conflict_codes.append(code)

    print()
    print(
        f"=== MODULE CODE CONFLICT SUMMARY | "
        f"conflict_codes={len(conflict_codes)} | "
        f"total_reused_codes={len(by_code)} | "
        f"entries={len(items)} ==="
    )

    if not conflict_codes:
        print("OK: không thấy code nào trong module bị dùng cho message khác nghĩa rõ.")
        return 0

    for code in conflict_codes:
        entries = by_code[code]
        messages = unique_messages(entries)
        min_sim = min_message_similarity(messages)
        sources = unique_sources(entries)

        print()
        print(
            f"- code={code} | variants={len(messages)} | "
            f"sources={len(sources)} | entries={len(entries)} | "
            f"min_similarity={min_sim:.2f}"
        )

        for idx, msg in enumerate(messages[:max_messages_preview], 1):
            print(f"  [{idx}] {msg}")

        if len(messages) > max_messages_preview:
            print(f"  ... +{len(messages) - max_messages_preview} message khác")

        print("  sources:")
        for source in sources[:max_sources_preview]:
            print(f"    - {source}")

        if len(sources) > max_sources_preview:
            print(f"    ... +{len(sources) - max_sources_preview} file khác")
    return len(conflict_codes)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="In report gọn cho error_codes_review.json theo policy conflict."
    )
    parser.add_argument("--module", help="Module cần review, ví dụ: order/admin/topup")
    parser.add_argument("--all", action="store_true", help="Review tất cả module có report")
    parser.add_argument("--show-resolved", action="store_true", help="Hiện cả entry đã có resolution")
    parser.add_argument("--show-new", action="store_true", help="Hiện cả mã mới bình thường. Mặc định ẩn để report gọn.")
    parser.add_argument("--detail", action="store_true",help="In chi tiết từng entry. Mặc định chỉ in summary gọn.")
    parser.add_argument("--show-safe-http", action="store_true", help="Hiện cả missing HTTP status đã có suggestion rõ. Mặc định chỉ hiện mã cần review.")
    parser.add_argument(
        "--ai",
        action="store_true",
        help="Reserved cho bước sau: AI semantic review. Patch hiện tại chưa gọi AI.",
    )

    args = parser.parse_args()

    if args.ai:
        print("[INFO] --ai được nhận, nhưng patch 1 chưa gọi AI. Đang chạy rule-based report trước.\n")

    if not args.module and not args.all:
        print("[ERROR] Cần truyền --module <name> hoặc --all", file=sys.stderr)
        return 2

    modules = [args.module] if args.module else list_modules()

    if not modules:
        print("[ERROR] Không tìm thấy module review nào.", file=sys.stderr)
        return 2

    total = 0

    for module in modules:
        try:
            total += print_module_report(module, show_resolved=args.show_resolved, show_new=args.show_new, detail=args.detail, show_safe_http=args.show_safe_http)
        except Exception as exc:
            print(f"[ERROR] module={module}: {exc}", file=sys.stderr)
            return 1

    print()
    print("==============================")
    print(f"Total visible report items: {total}")

    if total == 0:
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())