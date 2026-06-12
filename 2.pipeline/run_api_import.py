import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from contract_profile.enrich_openapi import cmd_enrich_openapi
from import_flow.module_rule_approver import cmd_approve_module_rule
from import_flow.config import REPORT_DIR, RUNNER
from import_flow.scanner import scan_source_root
from import_flow.registry import (
    cmd_activate_module,
    cmd_deactivate_module,
    cmd_reactivate_module,
    cmd_list_modules,
)
from import_flow.resolver import (
    cmd_suggest_root,
    cmd_review_suggestions,
    cmd_approve_suggestions,
    cmd_apply_suggestions,
)
from import_flow.converter import (
    cmd_scan,
    cmd_convert_folder,
    cmd_convert_root,
    cmd_import,
)

def main():
    parser = argparse.ArgumentParser(
        description="API Import Orchestration — scan/suggest/convert/import API Contract folders"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # scan
    subparsers.add_parser("scan", help="Scan source_root, liệt kê folder module và file unassigned")

    # suggest-root
    subparsers.add_parser("suggest-root", help="Parse file unassigned ở source_root, gợi ý module theo endpoint")

    # review-suggestions
    p_review = subparsers.add_parser("review-suggestions", help="In bảng review suggestions")
    p_review.add_argument("--suggestions", default=str(REPORT_DIR / "import_suggestions.json"))

    #approve-module
    p_approve_rule = subparsers.add_parser("approve-module-rule", help="Approve endpoint prefix vào module rule và register module nếu chưa có")
    p_approve_rule.add_argument("--module", required=True)
    p_approve_rule.add_argument("--path-prefix", required=True)
    p_approve_rule.add_argument("--actor", default="cli")
    p_approve_rule.add_argument("--dry-run", action="store_true")

    # approve-suggestions
    p_approve = subparsers.add_parser("approve-suggestions", help="Approve items trong import_suggestions.json")
    p_approve.add_argument("--suggestions", default=str(REPORT_DIR / "import_suggestions.json"))
    p_approve.add_argument("--all", dest="approve_all", action="store_true")
    p_approve.add_argument("--module", dest="module_filter", default=None)
    p_approve.add_argument("--file", dest="file_name", default=None)
    p_approve.add_argument("--override-module", dest="override_module", default=None)

    # apply-suggestions
    p_apply = subparsers.add_parser("apply-suggestions", help="Apply suggestions: copy/move file vào folder module")
    p_apply.add_argument("--suggestions", default=str(REPORT_DIR / "import_suggestions.json"))
    p_apply.add_argument("--move-files", action="store_true")
    p_apply.add_argument("--convert", action="store_true")

    # convert-folder
    p_folder = subparsers.add_parser("convert-folder", help="Convert tất cả file trong 1 folder")
    p_folder.add_argument("--folder", required=True)
    p_folder.add_argument("--module", required=True)

    p_enrich = subparsers.add_parser("enrich-openapi", help="Build contract profile hints và patch OpenAPI YAML output")
    p_enrich.add_argument("--module", required=True)
    p_enrich.add_argument("--file")
    p_enrich.add_argument("--folder")
    p_enrich.add_argument("--output")
    p_enrich.add_argument("--dry-run", action="store_true")

    # convert-root
    p_root = subparsers.add_parser("convert-root", help="Convert file unassigned ở source_root")
    p_root.add_argument("--module", required=True)

    # activate-module
    p_activate = subparsers.add_parser("activate-module", help="Chuyển module draft → active")
    p_activate.add_argument("--module", required=True)

    # deactivate-module
    p_deactivate = subparsers.add_parser("deactivate-module", help="Chuyển module active → deprecated")
    p_deactivate.add_argument("--module", required=True)

    # reactivate-module
    p_reactivate = subparsers.add_parser("reactivate-module", help="Chuyển module deprecated → active")
    p_reactivate.add_argument("--module", required=True)

    # list-modules
    subparsers.add_parser("list-modules", help="In bảng tất cả module trong registry")

    # import
    p_import = subparsers.add_parser("import", help="Auto convert tất cả folder con trong source_root")
    p_import.add_argument("--all", dest="import_all", action="store_true")
    p_import.add_argument("--module", dest="import_module", default=None)

    args = parser.parse_args()

    if args.command == "scan":
        cmd_scan()

    elif args.command == "suggest-root":
        cmd_suggest_root()

    elif args.command == "review-suggestions":
        cmd_review_suggestions(suggestions_path=args.suggestions)

    elif args.command == "approve-module-rule":
        cmd_approve_module_rule(
            module=args.module,
            path_prefix=args.path_prefix,
            actor=args.actor,
            dry_run=args.dry_run,
        )

    elif args.command == "approve-suggestions":
        if not args.approve_all and not args.module_filter and not args.file_name:
            print("[ERROR] Cần chỉ định --all, --module, hoặc --file")
            sys.exit(1)
        cmd_approve_suggestions(
            suggestions_path=args.suggestions,
            approve_all=args.approve_all,
            module_filter=args.module_filter,
            file_name=args.file_name,
            override_module=args.override_module,
        )

    elif args.command == "apply-suggestions":
        cmd_apply_suggestions(
            suggestions_path=args.suggestions,
            move_files=args.move_files,
            convert=args.convert,
        )

    elif args.command == "convert-folder":
        cmd_convert_folder(folder=args.folder, module=args.module)

    elif args.command == "enrich-openapi":
        cmd_enrich_openapi(
            module=args.module,
            file=args.file,
            folder=args.folder,
            output=args.output,
            dry_run=args.dry_run,
        )

    elif args.command == "convert-root":
        cmd_convert_root(module=args.module)

    elif args.command == "activate-module":
        cmd_activate_module(module=args.module)

    elif args.command == "deactivate-module":
        cmd_deactivate_module(module=args.module)

    elif args.command == "reactivate-module":
        cmd_reactivate_module(module=args.module)

    elif args.command == "list-modules":
        cmd_list_modules()

    elif args.command == "import":
        cmd_import(
            active_only=not args.import_all,
            module_filter=args.import_module,
        )


if __name__ == "__main__":
    main()
