import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path


def _text(value):
    if value is None:
        return "None"
    return str(value)


def _short(value, limit=180):
    text = _text(value).replace("\n", " ").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _review_files(root: Path, module: str | None):
    base = root / "3.build" / "reports" / "errors"

    if module:
        path = base / module / "error_codes_review.json"
        return [path] if path.exists() else []

    return sorted(base.glob("*/error_codes_review.json"))


def _load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def collect_conflicts(root: Path, module: str | None, only_unresolved: bool):
    rows = []
    files = _review_files(root, module)

    for path in files:
        try:
            data = _load_json(path)
        except Exception as exc:
            print(f"[WARN] Không đọc được {path}: {exc}", file=sys.stderr)
            continue

        current_module = path.parent.name
        entries = data.get("entries") or []

        for entry in entries:
            if entry.get("status") != "conflict":
                continue

            resolution = entry.get("resolution")
            if only_unresolved and resolution:
                continue

            incoming = entry.get("incoming") or {}
            existing = entry.get("existing_in_map") or {}

            rows.append(
                {
                    "module": current_module,
                    "code": _text(entry.get("code")),
                    "source_file": _text(entry.get("source_file")),
                    "matched_namespace": _text(entry.get("matched_namespace")),
                    "missing_http_status": bool(entry.get("missing_http_status")),
                    "intra_batch_conflict": bool(entry.get("intra_batch_conflict")),
                    "incoming_http_status": incoming.get("http_status"),
                    "incoming_category": incoming.get("category"),
                    "incoming_message": incoming.get("message"),
                    "existing_http_status": existing.get("http_status"),
                    "existing_message": existing.get("message"),
                    "resolution": resolution,
                    "report_file": str(path),
                }
            )

    return files, rows


def print_text(files, rows):
    print(f"Review files scanned : {len(files)}")
    print(f"Conflict entries     : {len(rows)}")

    if not rows:
        print("OK: không có conflict nào.")
        return

    unique_codes = sorted({row["code"] for row in rows})
    print(f"Unique conflict codes: {len(unique_codes)} -> {', '.join(unique_codes)}")

    grouped = defaultdict(list)
    for row in rows:
        grouped[row["module"]].append(row)

    for module in sorted(grouped):
        items = grouped[module]
        codes = sorted({row["code"] for row in items})

        print("")
        print(f"=== module={module} | conflicts={len(items)} | codes={', '.join(codes)} ===")

        for idx, row in enumerate(items, 1):
            print(
                f"[{idx:02d}] code={row['code']} "
                f"namespace={row['matched_namespace']} "
                f"source={row['source_file']}"
            )
            print(
                f"     incoming : http={_text(row['incoming_http_status'])} "
                f"| category={_text(row['incoming_category'])} "
                f"| {_short(row['incoming_message'])}"
            )
            print(
                f"     existing : http={_text(row['existing_http_status'])} "
                f"| {_short(row['existing_message'])}"
            )
            print(
                f"     flags    : missing_http_status={row['missing_http_status']} "
                f"| intra_batch_conflict={row['intra_batch_conflict']}"
            )
            print(f"     resolution: {_text(row['resolution'])}")


def main():
    parser = argparse.ArgumentParser(
        description="Đọc tất cả error_codes_review.json và in ra các conflict."
    )
    parser.add_argument(
        "--root",
        default=".",
        help="Project root. Mặc định là current directory.",
    )
    parser.add_argument(
        "--module",
        default=None,
        help="Chỉ đọc conflict của 1 module, ví dụ: ticket/service/order.",
    )
    parser.add_argument(
        "--only-unresolved",
        action="store_true",
        help="Chỉ in conflict chưa có resolution.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="In raw JSON để pipe sang tool khác.",
    )

    args = parser.parse_args()

    root = Path(args.root).resolve()
    files, rows = collect_conflicts(
        root=root,
        module=args.module,
        only_unresolved=args.only_unresolved,
    )

    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return

    print_text(files, rows)


if __name__ == "__main__":
    main()