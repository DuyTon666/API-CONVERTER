# global_usage_auditor.py
# Audit toàn hệ thống: quét global_usage.yaml của tất cả module,
# so message với global map, phát hiện mismatch/orphan.
# Không ghi gì vào config — chỉ xuất report.

import os
import yaml
import json
from datetime import datetime
import anthropic


def _normalize_message(msg: str) -> str:
    return msg.strip().lower()


def _is_same_meaning_by_rule(msg_a: str, msg_b: str) -> bool:
    """Lớp 1 — rule substring, nhanh, không tốn token."""
    a = _normalize_message(msg_a)
    b = _normalize_message(msg_b)
    return a == b or a in b or b in a


def _is_same_meaning_by_ai(msg_a: str, msg_b: str) -> str:
    """
    Lớp 2 — gọi Anthropic API khi rule substring không khớp.
    Trả về: 'same_meaning' / 'different_meaning' / 'uncertain'
    """
    client = anthropic.Anthropic()
    prompt = (
        f"So sánh 2 message lỗi API sau, chúng có cùng nghĩa/tình huống không?\n"
        f"Message A: \"{msg_a}\"\n"
        f"Message B: \"{msg_b}\"\n"
        f"Trả lời CHỈ 1 trong 3 từ sau, không giải thích thêm: "
        f"same_meaning / different_meaning / uncertain"
    )
    response = client.messages.create(
        model="cc/claude-sonnet-4-6",
        max_tokens=10,
        messages=[{"role": "user", "content": prompt}]
    )
    verdict = response.content[0].text.strip().lower()
    if verdict not in ("same_meaning", "different_meaning", "uncertain"):
        return "uncertain"
    return verdict


def audit_global_usage(errors_dir: str, report_path: str) -> None:
    """
    Quét tất cả modules/<tên>/global_usage.yaml,
    so message với global map, ghi mismatch/orphan vào report.
    """
    global_map_path = os.path.join(errors_dir, "error_code_map.yaml")
    if not os.path.exists(global_map_path):
        print(f"Không tìm thấy global map: {global_map_path}")
        return

    with open(global_map_path, encoding="utf-8") as f:
        global_data = yaml.safe_load(f) or {}
    global_map = global_data.get("error_codes", {})

    modules_dir = os.path.join(errors_dir, "modules")
    if not os.path.isdir(modules_dir):
        print(f"⚠ Không tìm thấy thư mục modules: {modules_dir}")
        return

    issues = []
    modules_scanned = []

    for module_name in sorted(os.listdir(modules_dir)):
        usage_path = os.path.join(modules_dir, module_name, "global_usage.yaml")
        if not os.path.exists(usage_path):
            continue

        modules_scanned.append(module_name)

        with open(usage_path, encoding="utf-8") as f:
            usage_data = yaml.safe_load(f) or {}

        runs = usage_data.get("runs", [])
        if not runs:
            continue

        # Chỉ xét run gần nhất
        latest_run = runs[-1]
        used_by = latest_run.get("used_by", [])

        for entry in used_by:
            code = str(entry.get("code", ""))
            module_msg = entry.get("message_in_document", "")
            source_file = entry.get("source_file", "")

            if code not in global_map:
                issues.append({
                    "module": module_name,
                    "code": code,
                    "source_file": source_file,
                    "global_message": None,
                    "module_message": module_msg,
                    "verdict": "orphan",
                    "method": "rule",
                })
                print(f"  [{module_name}] {code} → orphan (không còn trong global map)")
                continue

            global_msg = global_map[code].get("message", "")

            # Lớp 1 — rule substring
            if _is_same_meaning_by_rule(global_msg, module_msg):
                print(f"  [{module_name}] {code} → ok (rule)")
                continue

            # Lớp 2 — AI
            print(f"  [{module_name}] {code} → rule miss, gọi AI...")
            ai_verdict = _is_same_meaning_by_ai(global_msg, module_msg)
            print(f"             AI verdict: {ai_verdict}")

            if ai_verdict == "same_meaning":
                continue

            issues.append({
                "module": module_name,
                "code": code,
                "source_file": source_file,
                "global_message": global_msg,
                "module_message": module_msg,
                "verdict": "mismatch" if ai_verdict == "different_meaning" else "uncertain",
                "method": "ai",
            })

    report = {
        "generated_at": datetime.now().isoformat(),
        "modules_scanned": modules_scanned,
        "total_issues": len(issues),
        "issues": issues,
    }

    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n AUDIT SUMMARY ")
    print(f"  modules scanned : {len(modules_scanned)}")
    print(f"  total issues    : {len(issues)}")
    for issue in issues:
        print(f"  [{issue['verdict']}] {issue['module']}.{issue['code']}: "
              f"\"{issue['module_message']}\" vs global \"{issue['global_message']}\"")
    print(f"\n Report ghi: {report_path}")