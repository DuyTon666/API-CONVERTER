import sys
import datetime
from pathlib import Path

import yaml

from pipeline_API import run_batch
from import_flow.source_selector import select_canonical_sources
from merger.conflict_detector import detect
from merger.source_merger import merge
from import_flow.config import (
    CONFIG_DIR,
    REPORT_DIR,
    RUNNER,
    load_import_config,
    get_source_root,
    get_output_root,
    get_schemas_root,
    supported_extensions,
    ignore_dirs,
)
from import_flow.scanner import scan_source_root, scan_for_collisions
from validators.validation_engine import run_validation

def cmd_scan() -> None:
    cfg         = load_import_config()
    source_root = get_source_root(cfg)
    extensions  = supported_extensions(cfg)
    ignore      = ignore_dirs(cfg)

    result = scan_source_root(source_root, extensions, ignore)

    print(f"Source root: {source_root}\n")

    if result["modules"]:
        print("Module folders:")
        for m in result["modules"]:
            count_by_ext = {}
            for f in m["files"]:
                ext = f.suffix.lower()
                count_by_ext[ext] = count_by_ext.get(ext, 0) + 1
            ext_summary = ", ".join(
                f"{ext.strip(chr(46))}: {count}"
                for ext, count in sorted(count_by_ext.items())
            )
            total = len(m["files"])
            print(f"  {m[chr(110)+chr(97)+chr(109)+chr(101)]:<20s} {total} file  ({ext_summary})")
    else:
        print("Không tìm thấy folder module nào.")

    print()

    if result["unassigned"]:
        print(f"Unassigned files ({len(result[chr(117)+chr(110)+chr(97)+chr(115)+chr(115)+chr(105)+chr(103)+chr(110)+chr(101)+chr(100)])} file ở root):")
        for f in result["unassigned"]:
            print(f"  {f.name}")
        print()
        print(f"  {RUNNER} suggest-root")
        print(f"  {RUNNER} convert-root --module <tên_module>")
    else:
        print("Không có file unassigned ở root.")

    print()
    if result["modules"]:
        print("Để convert từng module:")
        for m in result["modules"]:
            print(f"  {RUNNER} convert-folder --folder {m[chr(112)+chr(97)+chr(116)+chr(104)]} --module {m[chr(110)+chr(97)+chr(109)+chr(101)]}")
        print()
        print(f"  {RUNNER} import")


def cmd_convert_folder(folder: str, module: str) -> None:
    cfg          = load_import_config()
    output_root  = get_output_root(cfg)
    schemas_root = get_schemas_root(cfg)

    output_dir  = str(output_root  / module)
    schemas_dir = str(schemas_root / module)

    print(f"Convert folder : {folder}")
    print(f"Module         : {module}")
    print(f"Output dir     : {output_dir}")
    print(f"Schemas dir    : {schemas_dir}")
    print()

    run_batch(
        input_dir=folder,
        module=module,
        output_dir=output_dir,
        schemas_dir=schemas_dir,
    )


def cmd_convert_root(module: str) -> None:
    cfg          = load_import_config()
    source_root  = get_source_root(cfg)
    output_root  = get_output_root(cfg)
    schemas_root = get_schemas_root(cfg)

    output_dir  = str(output_root  / module)
    schemas_dir = str(schemas_root / module)

    print(f"Convert root   : {source_root}")
    print(f"Module         : {module}")
    print(f"Output dir     : {output_dir}")
    print(f"Schemas dir    : {schemas_dir}")
    print()

    run_batch(
        input_dir=str(source_root),
        module=module,
        output_dir=output_dir,
        schemas_dir=schemas_dir,
    )


def cmd_import(active_only: bool = True, module_filter: str | None = None) -> None:
    cfg          = load_import_config()
    source_root  = get_source_root(cfg)
    output_root  = get_output_root(cfg)
    schemas_root = get_schemas_root(cfg)
    extensions   = supported_extensions(cfg)
    ignore       = ignore_dirs(cfg)

    result = scan_source_root(source_root, extensions, ignore)

    if not result["modules"]:
        print("Không tìm thấy folder module nào để convert.")
        if result["unassigned"]:
            print(f"\n{len(result[chr(117)+chr(110)+chr(97)+chr(115)+chr(115)+chr(105)+chr(103)+chr(110)+chr(101)+chr(100)])} file unassigned ở root.")
            print(f"Chạy: {RUNNER} suggest-root")
            print(f"Sau đó: {RUNNER} apply-suggestions")
        return

    if result["unassigned"]:
        print(
            f"[WARN] {len(result[chr(117)+chr(110)+chr(97)+chr(115)+chr(115)+chr(105)+chr(103)+chr(110)+chr(101)+chr(100)])} file unassigned ở root sẽ không được convert.\n"
            f"       Chạy '{RUNNER} suggest-root' rồi '{RUNNER} apply-suggestions' nếu cần.\n"
        )

    registry_path    = CONFIG_DIR / "module_registry.yaml"
    registry_modules: dict = {}

    if active_only:
        if registry_path.exists():
            raw = registry_path.read_text(encoding="utf-8").strip()
            registry_data    = yaml.safe_load(raw) if raw else {}
            registry_modules = registry_data.get("modules", {})
        else:
            print("[WARN] Không tìm thấy module_registry.yaml — chạy tất cả module.")
            active_only = False

    to_run = []
    for m in result["modules"]:
        if not m["files"]:
            print(f"[SKIP] {m[chr(110)+chr(97)+chr(109)+chr(101)]} — không có file hợp lệ")
            continue
        if module_filter and m["name"] != module_filter:
            continue
        if active_only:
            reg_info = registry_modules.get(m["name"])
            if reg_info is None:
                print(f"[SKIP] {m[chr(110)+chr(97)+chr(109)+chr(101)]} — không có trong registry")
                continue
            status = reg_info.get("status", "draft")
            if status != "active":
                print(f"[SKIP] {m[chr(110)+chr(97)+chr(109)+chr(101)]} — status={status}")
                continue
        to_run.append(m)

    if module_filter and not to_run:
        print(f"[ERROR] Không tìm thấy module '{module_filter}' trong source_root.")
        return

    if not to_run:
        print("\nKhông có module nào để convert.")
        if active_only:
            print(f"Kiểm tra: {RUNNER} list-modules")
        return

    # --- pre-import collision check ---
    total_collisions = 0
    for m in to_run:
        cols = scan_for_collisions(m["path"], extensions)
        if cols:
            total_collisions += len(cols)
            mname = m["name"]
            print(f"[WARN] Module '{mname}' có {len(cols)} endpoint collision giữa các file nguồn:")
            for c in cols:
                ckey = c["key"]
                print(f"  {ckey}")
                for f, raw in zip(c["files"], c["raw_paths"]):
                    fname = Path(f).name
                    print(f"    [{raw}] trong {fname}")
            print()
    if total_collisions == 0:
        print("  [OK] Không phát hiện endpoint collision giữa các file nguồn.")
    print()
    # --- end collision check ---

    print(f"\nBắt đầu import {len(to_run)} module...\n")

    n_success = 0
    n_failed  = 0
    total_converted = 0

    for m in to_run:
        print(f"{'=' * 40}")
        print(f"Module: {m['name']} ({len(m['files'])} files)")
        print(f"{'=' * 40}")

        import_status = "success"
        now = datetime.datetime.now().isoformat(timespec="seconds")

        candidate_files = sorted([
            p for p in Path(m["path"]).iterdir()
            if p.is_file() and p.suffix.lower() in (".pdf", ".docx", ".txt", ".md")
        ])

        source_files_count = len(candidate_files)
        selected_files_count = 0
        skipped_duplicate_count = 0

        try:
            selection = select_canonical_sources(
                files=candidate_files,
                module=m["name"],
            )

            selected_files_count = len(selection["selected_files"])
            skipped_duplicate_count = len(selection["skipped_duplicates"])

            print(
                f"[source_selector] module={m['name']} "
                f"input={source_files_count} "
                f"selected={selected_files_count} "
                f"skipped_duplicate={skipped_duplicate_count}"
            )

            n_converted = run_batch(
                input_dir=str(m["path"]),
                module=m["name"],
                output_dir=str(output_root / m["name"]),
                schemas_dir=str(schemas_root / m["name"]),
                files_override=selection["selected_files"],
            )

            n_success += 1
            total_converted += n_converted

        except Exception as e:
            print(f"[ERROR] Module {m['name']} thất bại: {e}")
            import_status = "failed"
            n_failed += 1

        if active_only and m["name"] in registry_modules:
            info = registry_modules[m["name"]]

            info["last_import_at"] = now
            info["last_import_status"] = import_status

            info["source_files_count"] = source_files_count
            info["selected_files_count"] = selected_files_count
            info["skipped_duplicate_count"] = skipped_duplicate_count

            out_dir = output_root / m["name"]
            if out_dir.exists():
                info["endpoint_count"] = len([
                    f for f in out_dir.iterdir()
                    if f.is_file() and f.suffix.lower() in (".yaml", ".yml")
                ])

        print()

    if active_only and registry_modules:
        raw_full = registry_path.read_text(encoding="utf-8").strip()
        reg_full = yaml.safe_load(raw_full) if raw_full else {}
        reg_full["modules"] = registry_modules
        registry_path.write_text(
            yaml.safe_dump(reg_full, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    print(f"Import hoàn thành.  success={n_success}  failed={n_failed}")
    if active_only:
        print(f"Registry updated: {registry_path}")
        print(f"Xem stats: {RUNNER} list-modules")

    if total_converted > 0:
        print("\n" + "=" * 40)
        print("Post-process: conflict detection...")
        print("=" * 40)
        detect(module=module_filter)

        print("\n" + "=" * 40)
        print("Post-process: source merger...")
        print("=" * 40)
        merge(module=module_filter, dry_run=False)

    print("\n" + "=" *40)
    print("Post-process: content-type validation...")
    print("=" * 40)
    run_validation(module=module_filter)