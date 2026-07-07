import json
import subprocess
from pathlib import Path

from core.config import DIST_DIR
from core.errors import ErrorCode, http_error
from services import ai_fix


# Parse stdout của lệnh "redocly lint --format json" thành list issue —
# tự xử lý 2 format khác nhau tuỳ phiên bản Redocly CLI (v2 mới và bản cũ).
# Nhận output của lệnh redocly lint rồi chuyển thành một list các lỗi
def _parse_redocly_output(result: subprocess.CompletedProcess) -> list:
    raw = result.stdout.strip() or result.stderr.strip()
    if not raw:
        return []
    try:
        data = json.loads(raw)
        # Redocly v2: single object {totals, version, problems: [...]}
        if isinstance(data, dict) and "problems" in data:
            return data["problems"]
        # Older format: [{filePath, problems: [...]}, ...]
        if isinstance(data, list):
            issues = []
            for entry in data:
                if isinstance(entry, dict) and "problems" in entry:
                    issues.extend(entry["problems"])
                elif isinstance(entry, dict) and "ruleId" in entry:
                    issues.append(entry)
            return issues
    except Exception:
        pass
    return []


# Gắn line/column thật vào từng redocly issue, dựa vào kết quả lint dạng checkstyle
# (chạy song song, vì bản JSON của Redocly không có line/column, chỉ có JSON Pointer).
def _enrich_redocly_with_line_col(
    redocly_issues: list[dict], checkstyle_xml: str
) -> list[dict]:
    checkstyle_issues = ai_fix._parse_checkstyle_output(checkstyle_xml)

    # Khớp theo cặp (ruleId, message) — dùng danh sách "còn lại" để khớp đúng
    # theo thứ tự xuất hiện khi có nhiều issue trùng cả ruleId và message.
    remaining = list(checkstyle_issues)
    for issue in redocly_issues:
        rule_id = issue.get("ruleId")
        message = issue.get("message")
        for i, cs in enumerate(remaining):
            if cs["ruleId"] == rule_id and cs["message"] == message:
                issue["line"] = (
                    cs["line"] - 1
                )  # đổi về 0-indexed, đồng nhất với Spectral
                issue["column"] = cs["column"] - 1
                remaining.pop(i)
                break

    return redocly_issues


def build_and_lint(project_root: Path, do_bundle: bool = True) -> dict:
    """Chạy bundle (tuỳ chọn) → lint Spectral/Redocly → build Swagger UI HTML."""
    if do_bundle:
        path_stub_result = subprocess.run(
            ["npm", "run", "gen:path-stubs"],
            cwd=str(project_root),
            capture_output=True,
            text=True,
        )
        if path_stub_result.returncode != 0:
            raise http_error(500, ErrorCode.PATH_STUB_FAILED, path_stub_result.stderr)

        merge_result = subprocess.run(
            ["npm", "run", "merge:openapi"],
            cwd=str(project_root),
            capture_output=True,
            text=True,
        )
        if merge_result.returncode != 0:
            raise http_error(500, ErrorCode.PATH_STUB_FAILED, merge_result.stderr)

        DIST_DIR.mkdir(parents=True, exist_ok=True)
        bundle_result = subprocess.run(
            ["npm", "run", "bundle:api"],
            cwd=str(project_root),
            capture_output=True,
            text=True,
        )
        if bundle_result.returncode != 0:
            raise http_error(500, ErrorCode.PIPELINE_FAILED, bundle_result.stderr)
    spectral_result = subprocess.run(
        ["npm", "run", "--silent", "lint:spectral"],
        cwd=str(project_root),
        capture_output=True,
        text=True,
    )
    try:
        spectral_issues = (
            json.loads(spectral_result.stdout) if spectral_result.stdout.strip() else []
        )
        if not isinstance(spectral_issues, list):
            spectral_issues = []
    except Exception:
        spectral_issues = []

    redocly_result = subprocess.run(
        ["npm", "run", "--silent", "validate:api"],
        cwd=str(project_root),
        capture_output=True,
        text=True,
    )
    redocly_issues = _parse_redocly_output(redocly_result)

    # Chạy thêm bản --format checkstyle (gọi npx trực tiếp vì package.json không có
    # script riêng cho format này) chỉ để lấy line/column thật, gắn vào redocly_issues.
    checkstyle_result = subprocess.run(
        [
            "npx",
            "@redocly/cli",
            "lint",
            "dist/openapi-bundled.yaml",
            "--config",
            "redocly.yaml",
            "--format",
            "checkstyle",
        ],
        cwd=str(project_root),
        capture_output=True,
        text=True,
    )
    redocly_issues = _enrich_redocly_with_line_col(
        redocly_issues, checkstyle_result.stdout
    )

    html_path = project_root / "public" / "api-docs.html"
    (project_root / "public").mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["npm", "run", "build:docs"],
        cwd=str(project_root),
        capture_output=True,
        text=True,
    )

    return {
        "bundle_ready": True,
        "html_ready": html_path.exists(),
        "spectral": spectral_issues,
        "redocly": redocly_issues,
    }


# Logic rút từ route POST /docs/build.
def build_docs() -> dict:
    project_root = Path(__file__).parent.parent.parent
    return build_and_lint(project_root, do_bundle=True)


# Logic rút từ route GET /docs/status.
def get_status() -> dict:
    project_root = Path(__file__).parent.parent.parent
    bundle_path = DIST_DIR / "openapi-bundled.yaml"
    html_path = project_root / "public" / "api-docs.html"
    return {"bundle_ready": bundle_path.exists(), "html_ready": html_path.exists()}


# Logic rút từ route GET /docs/download-html.
def get_html_path_or_404() -> Path:
    project_root = Path(__file__).parent.parent.parent
    html_path = project_root / "public" / "api-docs.html"
    if not html_path.exists():
        raise http_error(
            404,
            ErrorCode.HTML_NOT_FOUND,
            "HTML chưa được build, hãy build tài liệu trước",
        )
    return html_path


# Logic rút từ route POST /docs/relint.
def relint_docs() -> dict:
    bundle_path = DIST_DIR / "openapi-bundled.yaml"
    if not bundle_path.exists():
        raise http_error(
            404,
            ErrorCode.BUNDLE_NOT_FOUND,
            "Bundle chưa được tạo, hãy build tài liệu trước",
        )

    project_root = Path(__file__).parent.parent.parent
    return build_and_lint(project_root, do_bundle=False)
