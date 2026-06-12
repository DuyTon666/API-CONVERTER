from __future__ import annotations
import argparse
import json
from pathlib import Path

from contract_profile.hints_builder import build_contract_hints


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = PROJECT_ROOT / "3.build/reports/contract_profile_hints.json"


def _supported_file(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in {".docx", ".pdf", ".txt", ".md"}


def collect_files(file: str | None, folder: str | None) -> list[Path]:
    if file:
        return [Path(file)]

    if folder:
        root = Path(folder)
        return sorted(p for p in root.rglob("*") if _supported_file(p))

    raise ValueError("Require --file or --folder")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file")
    parser.add_argument("--folder")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    files = collect_files(args.file, args.folder)
    results = []

    for file_path in files:
        try:
            hints = build_contract_hints(file_path)
            hints["status"] = "success"
            results.append(hints)
            print(f"[OK] {file_path}")
        except Exception as e:
            results.append({
                "source_file": str(file_path),
                "status": "failed",
                "error": str(e),
            })
            print(f"[ERR] {file_path}: {e}")

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "count": len(results),
                "results": results,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print()
    print(f"[DONE] wrote: {output}")


if __name__ == "__main__":
    main()
