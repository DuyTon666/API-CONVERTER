from __future__ import annotations

import json
from pathlib import Path

from contract_profile.loader import load_contract_profile
from contract_profile.hints_builder import build_contract_hints
from contract_profile.openapi_hint_patcher import (
    _find_target_yaml,
    patch_yaml_with_hints,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _supported_file(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in {".docx", ".pdf", ".txt", ".md"}


def _collect_files(module: str, file: str | None = None, folder: str | None = None) -> list[Path]:
    if file:
        return [Path(file)]

    if folder:
        root = Path(folder)
    else:
        root = PROJECT_ROOT / "1.docs/source/api_contract" / module

    if not root.exists():
        raise FileNotFoundError(f"Source folder not found: {root}")

    return sorted(p for p in root.rglob("*") if _supported_file(p))


def _default_hints_output(module: str) -> Path:
    return PROJECT_ROOT / "3.build/reports" / f"contract_profile_hints_{module}.json"


def cmd_enrich_openapi(
    module: str,
    file: str | None = None,
    folder: str | None = None,
    output: str | None = None,
    dry_run: bool = False,
) -> None:
    module = module.strip().lower()
    files = _collect_files(module=module, file=file, folder=folder)

    output_path = Path(output) if output else _default_hints_output(module)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    config = load_contract_profile()

    hints_results = []
    patch_results = []

    for source_file in files:
        try:
            hints = build_contract_hints(source_file)
            hints["status"] = "success"
            hints_results.append(hints)
        except Exception as e:
            hints_results.append({
                "source_file": str(source_file),
                "status": "failed",
                "error": str(e),
            })

    output_path.write_text(
        json.dumps(
            {
                "count": len(hints_results),
                "results": hints_results,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    for hints in hints_results:
        if hints.get("status") != "success":
            patch_results.append({
                "source_file": hints.get("source_file"),
                "changed": False,
                "error": hints.get("error", "hint build failed"),
            })
            continue

        target_yaml = _find_target_yaml(hints["source_file"], module)

        if not target_yaml:
            patch_results.append({
                "source_file": hints["source_file"],
                "changed": False,
                "error": "target yaml not found",
                "actions": hints.get("actions", []),
            })
            continue

        if dry_run:
            patch_results.append({
                "source_file": hints["source_file"],
                "yaml_path": str(target_yaml),
                "changed": False,
                "dry_run": True,
                "actions": hints.get("actions", []),
            })
            continue

        patched = patch_yaml_with_hints(target_yaml, hints, config)
        patched["source_file"] = hints["source_file"]
        patched["actions"] = hints.get("actions", [])
        patch_results.append(patched)

    print(json.dumps(
        {
            "module": module,
            "files": len(files),
            "hints_output": str(output_path),
            "dry_run": dry_run,
            "patch_results": patch_results,
        },
        ensure_ascii=False,
        indent=2,
    ))
