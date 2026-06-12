import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path

ROOT             = Path(__file__).resolve().parent.parent.parent
CONFLICT_PATH    = ROOT / "3.build/reports/conflict_report.json"
VERSIONS_PATH    = ROOT / "3.build/reports/file_versions.json"
MERGE_RULES_PATH = ROOT / "4.config/merge_rules.yaml"
BACKUP_PATH      = ROOT / "3.build/reports/file_versions.before_merge.json"
APPLIED_PATH     = ROOT / "3.build/reports/merge_applied.json"
REVIEW_PATH      = ROOT / "3.build/reports/merge_review_queue.json"

def _load_json(path: Path) -> dict:
    if not path.exists():
        print(f"[ERROR] Không tìm thấy {path}")
        raise FileNotFoundError(str(path))
    return json.loads(path.read_text(encoding="utf-8"))

def _normalize_basename(file_name: str) -> str:
    name = Path(file_name).name.lower()
    for suffix in (".docx.pdf", ".pdf", ".docx", ".md", ".yaml", ".yml", ".txt"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
            break
    return name.strip()

def _find_winner_key(versions: dict, suggested_winner: str, source: list) -> str | None:
    candidates = []
    for key, entry in versions.items():
        if not isinstance(entry, dict):
            continue
        if entry.get("file")  == suggested_winner:
            candidates.append((key, entry))

    if not candidates:
        return None

    for key, entry in candidates:
        p = entry.get("path", "")
        parts = Path(p).parts

        if len(parts) >= 2:
            parent = Path(p).parent.name
            if parent not in ("api_contract", "source", "1.docs"):
                return key

    return candidates[0][0]

def _find_duplicate_keys(versions: dict, winner_key: str, sources: list) -> list[str]:
    winner_entry = versions.get(winner_key, {})
    winner_file  = winner_entry.get("file", "")
    winner_base  = _normalize_basename(winner_file)

    source_files = {s.get("file", "") for s in sources}

    duplicates = []
    for key, entry in versions.items():
        if key == winner_key:
            continue
        if not isinstance(entry, dict):
            continue
        if entry.get("file", "") not in source_files:
            continue
        if _normalize_basename(entry.get("file", "")) == winner_base:
            duplicates.append(key)

    return duplicates

def _find_loser_keys(versions: dict, output_path: str, suggested_winner: str) -> list[str]:
    """
    Tìm tất cả key trong file_versions.json có cùng output
    nhưng file != suggested_winner → đây là loser cần xóa.
    """
    losers = []
    for key, entry in versions.items():
        if not isinstance(entry, dict):
            continue
        entry_output = entry.get("output", "")
        if Path(entry_output).name != Path(output_path).name:
            continue
        if entry.get("file", "") == suggested_winner:
            continue
        losers.append(key)
    return losers

def _find_endpoint_loser_keys(
    versions: dict,
    method: str,
    http_path: str,
    suggested_winner: str,
    module: str,
) -> list[str]:
    """
    Tìm loser keys cho endpoint_collision:
    cùng module + method + http_path nhưng file != suggested_winner.
    """
    losers = []

    for key, entry in versions.items():
        if not isinstance(entry, dict):
            continue

        if entry.get("module") != module:
            continue

        if (entry.get("method") or "").lower() != (method or "").lower():
            continue

        if entry.get("http_path", "") != http_path:
            continue

        if entry.get("file", "") == suggested_winner:
            continue

        losers.append(key)

    return losers

def merge(module: str | None = None, dry_run: bool = True) -> dict:
    """
    Đọc conflict_report.json và apply safe resolution.

    duplicate_import + requires_review=False → auto apply, remove duplicate từ file_versions
    output_collision / endpoint_collision    → đưa vào merge_review_queue.json

    dry_run=True (default): không ghi file, chỉ in kết quả.
    """
    conflict_data = _load_json(CONFLICT_PATH)
    versions      = _load_json(VERSIONS_PATH)
    conflicts     = conflict_data.get("conflicts", [])

    if module:
        conflicts = [c for c in conflicts if c.get("module") == module]

    applied         = []
    review_queue    = []
    removed_keys     = []

    for conflict in conflicts:
        ct              = conflict.get("conflict_type", "")
        requires_review = conflict.get("requires_review", True)
        suggested       = conflict.get("suggested_winner", "")
        sources         = conflict.get("sources", [])
        conflict_id     = conflict.get("conflict_id", "")
        severity        = conflict.get("severity", "")

        if ct == "duplicate_import" and not requires_review:
            winner_key = _find_winner_key(versions, suggested, sources)

            if not winner_key:
                review_queue.append({
                    "conflict_id":      conflict_id,
                    "conflict_type":    ct,
                    "reason":           "winner_key_not_found_in_versions",
                    "suggested_winner": suggested,
                    "sources":          sources
                })
                continue

            dup_keys = _find_duplicate_keys(versions, winner_key, sources)

            applied.append({
                "conflict_id":      conflict_id,
                "conflict_type":    ct,
                "action":           "removed_duplicates",
                "winner_key":       winner_key,
                "winner_file":      suggested,
                "removed_keys":     dup_keys,
                "dry_run":          dry_run,
            })

            if not dry_run:
                for k in dup_keys:
                    versions.pop(k, None)
                removed_keys.extend(dup_keys)

            action_label = "DRY-RUN" if dry_run else "APPLIED"
            print(f"[{action_label}] duplicate_import: keep '{suggested}', remove {len(dup_keys)} duplicate(s)")
            for k in dup_keys:
                print(f"    - {k}")

        elif ct in ("output_collision", "endpoint_collision"):
            review_queue.append({
                "conflict_id":      conflict_id,
                "conflict_type":    ct,
                "severity":         severity,
                "module":           conflict.get("module", ""),
                "method": conflict.get("method", ""),
                "path": conflict.get("path", ""),
                "output":           conflict.get("output", ""),
                "sources":          sources,
                "suggested_winner": suggested,
                "reason":           conflict.get("reason", []),
                "confidence_score": conflict.get("confidence_score", 0),
                "recommended_action": conflict.get("recommended_action", ""),
                "note": "Cần human review. source_merger không tự xử lý output_collision.",
            })
            print(f"[REVIEW] {ct}: {conflict_id} -> suggested_winner='{suggested}'")

        else:
            review_queue.append({
                "conflict_id": conflict_id,
                "conflict_type": ct,
                "severity":     severity,
                "reason":       "requires_review=True hoặc unknown conflict_type",
                "sources":      sources,
                "suggested_winner": suggested,
            })

    now = datetime.now().isoformat(timespec="seconds")

    result = {
        "timestamp":        now,
        "module_filter":    module,
        "dry_run":          dry_run,
        "summary":          {
            "total_conflicts": len(conflicts),
            "auto_applied":    len(applied),
            "review_required": len(review_queue),
            "keys_removed":    len(removed_keys), 
        },
        "applied":          applied,
        "review_queue":     review_queue,
    }

    if not dry_run:
        shutil.copy2(VERSIONS_PATH, BACKUP_PATH)
        print(f"[BACKUP] {BACKUP_PATH}")

        VERSIONS_PATH.write_text(
            json.dumps(versions, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"[UPDATED] {VERSIONS_PATH} (removed {len(removed_keys)} duplicate keys)")

    APPLIED_PATH.parent.mkdir(parents=True, exist_ok=True)

    APPLIED_PATH.write_text(
        json.dumps({"applied": applied}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    existing_queue = []
    if REVIEW_PATH.exists():
        try:
            existing_queue = _load_json(REVIEW_PATH).get("review_queue", [])
        except Exception:
            existing_queue = []

    existing_ids = {q.get("conflict_id") for q in existing_queue}
    new_items = [
        q for q in review_queue
        if q.get("conflict_id") not in existing_ids
    ]

    REVIEW_PATH.write_text(
        json.dumps(
            {"review_queue": existing_queue + new_items},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return result

def accept_suggestions(
    module: str | None = None,
    dry_run: bool = True,
    delete_losers: bool = False,
) -> dict:
    if not REVIEW_PATH.exists():
        print(f"[ERROR] Không tìm thấy: {REVIEW_PATH}")
        print(f"Chạy trước: python3 source_merger.py --apply-safe")
        return {}

    queue_data = _load_json(REVIEW_PATH)
    versions   = _load_json(VERSIONS_PATH)
    queue      = queue_data.get("review_queue", [])

    if module:
        queue = [q for q in queue if q.get("module") == module]

    accepted      = []
    remaining     = []
    removed_keys  = []
    deleted_files = []

    for item in queue:
        ct          = item.get("conflict_type", "")
        conflict_id = item.get("conflict_id", "")
        suggested   = item.get("suggested_winner", "")
        output      = item.get("output", "")
        mod         = item.get("module", "")

        if ct not in ("output_collision", "endpoint_collision"):
            remaining.append(item)
            continue

        if ct == "endpoint_collision":
            loser_keys = _find_endpoint_loser_keys(
                versions=versions,
                method=item.get("method", ""),
                http_path=item.get("path", ""),
                suggested_winner=suggested,
                module=mod,
            )
        else:
            loser_keys = _find_loser_keys(
                versions=versions,
                output_path=output,
                suggested_winner=suggested,
            )

        loser_files = []
        if delete_losers:
            for k in loser_keys:
                entry = versions.get(k, {})
                loser_output = entry.get("output", "")
                if loser_output:
                    loser_path = ROOT / loser_output if not Path(loser_output).is_absolute() else Path(loser_output)
                    # Chỉ xóa nếu loser output KHÁC winner output
                    # output_collision: cùng output path → không xóa YAML
                    if Path(loser_output).name != Path(output).name and loser_path.exists():
                        loser_files.append(loser_path)

        accepted.append({
            "conflict_id":   conflict_id,
            "conflict_type": ct,
            "action":        "accepted_winner",
            "module":        mod,
            "output":        output,
            "winner_file":   suggested,
            "removed_keys":  loser_keys,
            "deleted_files": [str(f) for f in loser_files],
            "dry_run":       dry_run,
        })

        if not dry_run:
            for k in loser_keys:
                versions.pop(k, None)
            removed_keys.extend(loser_keys)

            if delete_losers:
                for f in loser_files:
                    f.unlink()
                    deleted_files.append(str(f))
                    print(f"    [DELETED] {f.name}")

        action_label = "DRY-RUN" if dry_run else "ACCEPTED"
        print(f"[{action_label}] {conflict_id}: keep '{suggested}', remove {len(loser_keys)} loser(s)")
        for k in loser_keys:
            print(f"    - {k}")

    # Ghi file SAU KHI xử lý xong tất cả item
    if not dry_run:
        shutil.copy2(VERSIONS_PATH, BACKUP_PATH)
        print(f"\n[BACKUP] {BACKUP_PATH}")
        VERSIONS_PATH.write_text(
            json.dumps(versions, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"[UPDATED] {VERSIONS_PATH}  (removed {len(removed_keys)} loser keys)")

        REVIEW_PATH.write_text(
            json.dumps({"review_queue": remaining}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        existing_applied = []
        if APPLIED_PATH.exists():
            existing_applied = _load_json(APPLIED_PATH).get("applied", [])
        APPLIED_PATH.write_text(
            json.dumps({"applied": existing_applied + accepted}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    now = datetime.now().isoformat(timespec="seconds")

    result = {
        "timestamp":     now,
        "module_filter": module,
        "dry_run":       dry_run,
        "summary": {
            "total_reviewed":  len(queue),
            "accepted":        len(accepted),
            "remaining_queue": len(remaining),
            "keys_removed":    len(removed_keys),
            "files_deleted":   len(deleted_files),
        },
        "accepted":  accepted,
        "remaining": remaining,
    }
    return result

def main():
    parser = argparse.ArgumentParser(
        description="Apply safe conflict resolution từ conflict_report.json"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Chỉ xem kết quả, không sửa file_versions.json",
    )

    parser.add_argument(
        "--apply-safe",
        action="store_true",
        default=False,
        help="Apply duplicate_import resolution và populate review queue",
    )

    parser.add_argument(
        "--accept-suggestions",
        action="store_true",
        default=False,
        help="Accept suggested_winner cho output_collision / endpoint_collision trong review queue",
    )

    parser.add_argument(
        "--delete-losers",
        action="store_true",
        default=False,
        help="Xóa YAML loser trên disk khi accept suggestions",
    )

    parser.add_argument(
        "--module",
        default=None,
        help="Chỉ xử lý conflict thuộc module này",
    )

    args = parser.parse_args()

    if not args.dry_run and not args.apply_safe and not args.accept_suggestions:
        print("[ERROR] Cần chỉ định một trong các flag:")
        print("  --dry-run             : xem conflict, không sửa file")
        print("  --apply-safe          : xử lý duplicate_import và ghi review queue")
        print("  --accept-suggestions  : accept winner trong review queue")
        import sys
        sys.exit(1)

    if args.accept_suggestions:
        print(f"[source_merger] mode=accept-suggestions  module={args.module or 'all'}")
        print()

        result = accept_suggestions(
            module=args.module,
            dry_run=args.dry_run,
            delete_losers=args.delete_losers,
        )

        s = result.get("summary", {})
        print()
        print("Accept summary:")
        print(f"  total_reviewed  : {s.get('total_reviewed', 0)}")
        print(f"  accepted        : {s.get('accepted', 0)}")
        print(f"  remaining_queue : {s.get('remaining_queue', 0)}")
        print(f"  keys_removed    : {s.get('keys_removed', 0)}")
        print(f"  files_deleted   : {s.get('files_deleted', 0)}")
        print()
        print(f"Applied log  : {APPLIED_PATH}")
        print(f"Review queue : {REVIEW_PATH}")

        if not args.dry_run:
            print(f"Backup       : {BACKUP_PATH}")

        return

    dry_run = not args.apply_safe

    print(f"[source_merger] mode={'dry-run' if dry_run else 'apply-safe'}  module={args.module or 'all'}")
    print()

    result = merge(
        module=args.module,
        dry_run=dry_run,
    )

    s = result.get("summary", {})

    print()
    print("Merger summary:")
    print(f"  total_conflicts : {s.get('total_conflicts', 0)}")
    print(f"  auto_applied    : {s.get('auto_applied', 0)}")
    print(f"  review_required : {s.get('review_required', 0)}")
    print(f"  keys_removed    : {s.get('keys_removed', 0)}")
    print()
    print(f"Applied log  : {APPLIED_PATH}")
    print(f"Review queue : {REVIEW_PATH}")

    if not dry_run:
        print(f"Backup       : {BACKUP_PATH}")

if __name__ == "__main__":
    main()