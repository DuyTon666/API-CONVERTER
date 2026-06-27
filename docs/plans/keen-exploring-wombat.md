# Rebuild homepage UI around the `run_api_import.py` module workflow

## Context

The npm scripts in `package.json` (`scan`, `suggest:module`, `review:suggest`, `approve`, `update:registry`, `list:module`, `activate:module`, `convert:api`) all wrap `2.pipeline/run_api_import.py` subcommands — the project's intended primary workflow for importing mixed PDF/DOCX folders (scan → suggest → approve → apply → activate → import).

The current frontend homepage (`frontend/app/page.tsx`) is built around a completely different, older flow: drag-drop upload → `POST /jobs` → convert on the spot → review/export at `/jobs/[job_id]`. It has no connection to the module-registry workflow at all — the backend doesn't even expose it.

User decision (confirmed via question): **replace** the homepage entirely so it's centered on the `run_api_import` workflow, and start with an MVP covering the first two read-only steps — **scan** (`make scan` / `npm run scan`) and **list-modules** (`npm run list:module`) — before building out suggest/approve/apply/activate/import in later passes. The existing `/jobs/[job_id]` review+export flow stays as-is; it's the natural reuse target for the future "convert/import" step.

## Backend: two new read-only JSON endpoints in `backend/main.py`

`run_api_import.py` already has the data-producing logic factored out from its print statements — reuse it instead of re-implementing or shelling out to the CLI:

- `_load_import_config()`, `_get_source_root(cfg)`, `_supported_extensions(cfg)`, `_ignore_dirs(cfg)`, and `_scan_source_root(source_root, extensions, ignore)` ([2.pipeline/run_api_import.py:47-161](2.pipeline/run_api_import.py#L47), returns `{"modules": [{"name", "path", "files": [Path,...]}], "unassigned": [Path,...]}`) — exactly what `cmd_scan()` ([run_api_import.py:165](2.pipeline/run_api_import.py#L165)) prints from.
- For modules, `cmd_list_modules()` ([run_api_import.py:880](2.pipeline/run_api_import.py#L880)) just loads `4.config/module_registry.yaml` with `yaml.safe_load` and reads `registry["modules"]` — no need to import that function, replicate the same direct YAML read in the endpoint (mirrors how `process_file` already loads `modules/<domain>.yaml` via `yaml.safe_load` in main.py).

Add near the existing `@app.get("/health")` block (around [backend/main.py:105](backend/main.py#L105)), following the same plain-`def` + direct-return-dict style as `/health` and `/jobs/{job_id}/flags`:

```python
@app.get("/modules/scan")
def scan_modules():
    sys.path imports run_api_import helpers (PIPELINE_DIR already on sys.path)
    cfg = _load_import_config()
    source_root = _get_source_root(cfg)
    result = _scan_source_root(source_root, _supported_extensions(cfg), _ignore_dirs(cfg))
    # serialize Path objects to plain names/strings; compute per-module file count + extension breakdown
    return {
        "source_root": str(source_root),
        "modules": [{"name", "total", "by_extension": {...}} ...],
        "unassigned": [{"name": f.name} ...],
    }

@app.get("/modules")
def list_modules():
    registry = yaml.safe_load((CONFIG_DIR / "module_registry.yaml").read_text(encoding="utf-8")) or {}
    modules = registry.get("modules", {})
    # shape each entry: name, status, file_count, endpoint_count, last_import_at, last_import_status, created_at
    # plus a summary: {"total": N, "by_status": {"active": x, "draft": y, ...}}
    return {"modules": [...], "summary": {...}}
```

Import `from run_api_import import _load_import_config, _get_source_root, _supported_extensions, _ignore_dirs, _scan_source_root` near the existing `from generator.emitter import init_config as _init_emitter` (line ~26) — it resolves through the same `sys.path.insert(0, str(PIPELINE_DIR))` already in place. `yaml` needs a top-level import (currently only imported lazily inside `process_file`); add `import yaml` to the module imports.

No changes to CORS config needed — `allow_origins=["http://localhost:3000"]` already covers the frontend.

## Frontend: rewrite `frontend/app/page.tsx`

Replace the upload-dropzone homepage with a two-section dashboard, following the existing patterns in the codebase (Tailwind utility classes matching the gray/blue palette used in `page.tsx` and `jobs/[job_id]/page.tsx`, `"use client"`, `useState`/`useEffect`, direct `fetch("http://localhost:8000/...")` — there's no shared API client to extend, every component calls the backend directly).

**Section 1 — Scan** (`GET /modules/scan`):
- Show `source_root` path
- Module folders: name + total file count + extension breakdown (e.g. "ticket — 12 file (docx: 10, pdf: 2)"), mirroring the table in `cmd_scan()`
- Unassigned files: list of filenames at the root (the test data in `1.docs/source/api_contract/` currently has ~16 unassigned PDFs and zero module folders — exercise the empty-modules / populated-unassigned state)

**Section 2 — Modules** (`GET /modules`):
- Table mirroring `cmd_list_modules()`'s columns: status icon (●/○/✕ for active/draft/deprecated, reuse `MODULE_STATUS_ICONS` semantics), name, file_count, endpoint_count, last import (date + status), created_at
- Summary line ("Total: N (active=x, draft=y)")
- Empty state ("Chưa có module nào trong registry") since `module_registry.yaml` currently has `modules: {}`

Both sections fetch on mount (`useEffect`), with loading/error states consistent with the existing `loading`/`error` state pattern in the current `page.tsx`.

This is read-only (no actions/buttons that trigger suggest/approve/apply/activate/import yet — those are later phases per the agreed MVP scope), so no new backend mutation endpoints or job-creation wiring is needed for this pass.

## Verification

1. Start backend (`cd backend && uvicorn main:app --reload --port 8000`) and frontend (`cd frontend && npm run dev`).
2. Open `http://localhost:3000` — confirm the new dashboard loads, the Scan section lists the unassigned PDFs currently sitting in `1.docs/source/api_contract/` with zero module folders, and the Modules section shows the empty-registry state (since `4.config/module_registry.yaml` is `modules: {}`).
3. Cross-check `GET http://localhost:8000/modules/scan` and `GET http://localhost:8000/modules` directly (e.g. via curl) against the output of `python3 2.pipeline/run_api_import.py scan` and `... list-modules` to confirm the JSON matches the CLI's data.
4. Confirm `/jobs` upload flow and `/jobs/[job_id]` review/export page are untouched and still reachable/working.
