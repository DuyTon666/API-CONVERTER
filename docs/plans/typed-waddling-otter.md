# Rebuild homepage UI around the `run_api_import` module workflow (MVP: scan + list-modules)

## Context

The npm scripts in `package.json` (`scan`, `suggest:module`, `review:suggest`, `approve`, `update:registry`, `list:module`, `activate:module`, `convert:api`, `verify:stats`) are thin wrappers around `2.pipeline/run_api_import.py` subcommands — the intended primary workflow for importing mixed PDF/DOCX folders into modules (scan → suggest → approve → apply → activate → import).

The current frontend homepage (`frontend/app/page.tsx`) has nothing to do with this workflow — it's a single-shot "drag & drop .docx → `POST /jobs` → redirect to `/jobs/[job_id]`" upload screen, built for a different (older) one-shot convert+review+export flow. The user wants the UI to mirror the CLI/npm workflow so the two stay "khít" (in sync), and has chosen to **replace** the current homepage entirely with a dashboard centered on the module-import workflow.

This plan covers the agreed MVP slice: **`scan`** (detect module folders / unassigned files) and **`list-modules`** (registry status table) — the first two steps of the workflow, surfaced as a new homepage. Later phases (suggest/approve/apply/activate/import) would extend this same dashboard; this plan does not build them, but the structure should make adding them natural.

The existing `/jobs` upload+convert+review+export backend endpoints and the `/jobs/[job_id]` page are **left untouched** — they still represent the "convert/import" capability and will likely be wired into a later "import" step of this same dashboard, just not from the homepage anymore.

## Backend changes (`backend/main.py`)

Add two new read-only GET endpoints that expose data `run_api_import.py` already computes/stores, mirroring `cmd_scan()` ([2.pipeline/run_api_import.py:165](2.pipeline/run_api_import.py#L165)) and `cmd_list_modules()` ([2.pipeline/run_api_import.py:880](2.pipeline/run_api_import.py#L880)) but returning JSON instead of printing tables.

1. **`GET /modules/scan`**
   - Reuse the existing helpers from `run_api_import` (already importable since `PIPELINE_DIR` is on `sys.path` — same pattern as `from pipeline_DOCX import run`): `_load_import_config`, `_get_source_root`, `_supported_extensions`, `_ignore_dirs`, `_scan_source_root`.
   - Call `_scan_source_root(source_root, extensions, ignore)` and serialize the result (it returns `Path` objects — convert to relative path strings):
     ```json
     {
       "source_root": "1.docs/source/api_contract",
       "modules": [
         { "name": "ticket", "path": "1.docs/source/api_contract/ticket", "file_count": 5, "by_extension": {"docx": 3, "pdf": 2} }
       ],
       "unassigned": [ { "name": "abc.pdf" } ]
     }
     ```
   - The `by_extension` breakdown mirrors the `ext_summary` computation already in `cmd_scan` (group `m["files"]` by `f.suffix.lower()`).

2. **`GET /modules`**
   - Read `4.config/module_registry.yaml` directly (same `_yaml.safe_load` pattern already used inside `process_file`, via the existing `CONFIG_DIR` constant) — no need to shell out or reimplement registry logic.
   - Return the `modules` dict as a JSON array, passing through the fields `cmd_list_modules` displays: `name`, `status`, `file_count`, `endpoint_count`, `last_import_at`, `last_import_status`, `created_at` (raw values — let the frontend format dates for display, avoiding duplicating `_fmt_dt`).
   - If the registry file doesn't exist or `modules` is empty, return `[]` (frontend shows the "chưa có module nào" empty state).

Both endpoints are simple synchronous `def` handlers (no job/threadpool involved — these are quick reads), placed near `GET /health` at the top of the route definitions.

## Frontend changes

### Replace `frontend/app/page.tsx`

Remove the drag-drop upload UI entirely. New homepage is a two-section dashboard styled consistently with the existing app (Tailwind, `bg-gray-50` page background, white rounded-lg bordered cards/rows, gray/blue/green palette — following patterns already in `frontend/app/jobs/[job_id]/page.tsx`):

**Section 1 — "Scan kết quả"** (mirrors `npm run scan`)
- On mount, `fetch('http://localhost:8000/modules/scan')`.
- Show `source_root` path.
- List detected module folders: name, file count, extension breakdown badge (e.g. "docx: 3 · pdf: 2").
- List unassigned files with a count and a short hint pointing at the next CLI/npm step (`suggest:module` → `review:suggest` → `approve`), matching the guidance text `cmd_scan` prints.
- Loading / error / empty states (e.g. "Không tìm thấy folder module nào").
- A "Quét lại" button to refetch.

**Section 2 — "Modules đã đăng ký"** (mirrors `npm run list:module` / `verify:stats`)
- On mount, `fetch('http://localhost:8000/modules')`.
- Table: status badge (●active / ○draft / ✕deprecated — reuse the `MODULE_STATUS_ICONS` mapping from `run_api_import.py:34`, recreated as a small frontend lookup + Tailwind color classes, similar to the existing `statusColor`/`statusLabel` maps in `frontend/app/jobs/[job_id]/page.tsx:65-79`), name, file_count, endpoint_count, last import (date + status), created date.
- Empty state matching CLI: "Chưa có module nào trong registry. Chạy apply-suggestions trước."
- Summary line: total + counts per status (e.g. "Total: 3 (active=1, draft=2)"), mirroring `cmd_list_modules`'s summary.

Use the same `"use client"` + `useState`/`useEffect` + hardcoded `http://localhost:8000` fetch pattern already used throughout the frontend (no new conventions introduced).

### `frontend/app/jobs/[job_id]/page.tsx`

No changes — kept as-is for when a future "import" step links into it.

## Verification

1. Start backend: `cd backend && uvicorn main:app --reload --port 8000`.
2. Manually check the new endpoints: `curl localhost:8000/modules/scan` and `curl localhost:8000/modules` — compare the JSON against the output of `python3 2.pipeline/run_api_import.py scan` and `python3 2.pipeline/run_api_import.py list-modules` run from the project root, to confirm the data matches (source root, module folders/counts, unassigned files, registry rows — registry is currently empty so `/modules` should return `[]` and the CLI prints "Chưa có module nào trong registry").
3. Start frontend: `cd frontend && npm run dev`, open `http://localhost:3000`, confirm:
   - Scan section shows the same module folders / unassigned files as `make scan` / `npm run scan`.
   - Module registry section renders the empty state (registry is currently empty) and the layout/styling looks consistent with the rest of the app.
   - "Quét lại" refetches and updates the view.
4. Run `npm run lint` in `frontend/` to catch type/lint issues in the new component.
