import sys
import argparse
import yaml
from pathlib import Path

sys.path.insert(0, "2.pipeline")

from converters.excel.reader import read_excel
from converters.excel.parser import parse_df
from converters.excel.emitter import emit

CONFIG = "4.config/sources/excel_template.yaml"


def _load_config() -> dict:
    return yaml.safe_load(Path(CONFIG).read_text(encoding="utf-8")) or {}


def _get_services(records) -> set:
    return {r.service.lower().replace(" ", "_") for r in records if r.service}


def run_setup(records, cfg: dict) -> None:
    api_contract_dir = Path(cfg["pipeline"]["source_api_contract_dir"])
    doc_process_dir  = Path(cfg["pipeline"]["source_doc_process_dir"])
    registry_path    = Path("4.config/module_registry.yaml")

    registry = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
    modules  = registry.setdefault("modules", {})

    services = _get_services(records)
    for service in services:
        # Tạo folders
        (api_contract_dir / service).mkdir(parents=True, exist_ok=True)
        (doc_process_dir  / service).mkdir(parents=True, exist_ok=True)
        print(f"  [setup] folders created: {service}/")

        # Register nếu chưa có
        if service not in modules:
            modules[service] = {
                "status":       "draft",
                "source_dir":   str(api_contract_dir / service),
                "output_dir":   f"5.openapi/paths/{service}",
                "schemas_dir":  f"5.openapi/components/schemas/{service}",
            }
            print(f"  [setup] registered module: {service}")
        else:
            print(f"  [setup] module already exists, skipped: {service}")

    registry_path.write_text(
        yaml.dump(registry, allow_unicode=True, sort_keys=False, default_flow_style=False),
        encoding="utf-8"
    )


def run_convert(records, cfg: dict) -> None:
    emit(records, CONFIG)


def main():
    parser = argparse.ArgumentParser(description="Excel Inventory Pipeline")
    parser.add_argument("--setup",   action="store_true", help="Tạo folder structure + register modules")
    parser.add_argument("--convert", action="store_true", help="Convert inventory → partial OpenAPI")
    args = parser.parse_args()

    if not args.setup and not args.convert:
        parser.print_help()
        return

    cfg      = _load_config()
    excel    = cfg["pipeline"]["excel_file"]
    df       = read_excel(excel, CONFIG)
    records  = parse_df(df, CONFIG)
    print(f"  [pipeline] loaded {len(records)} records from {excel}")

    if args.setup:
        run_setup(records, cfg)

    if args.convert:
        run_convert(records, cfg)

    print("  [pipeline] done.")


if __name__ == "__main__":
    main()