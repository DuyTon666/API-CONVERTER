# 2.pipeline/enrichers/side_effects/yaml_injector.py
"""
Inject x-side-effects vào file YAML OpenAPI path.

Vị trí chèn: ngay sau "operationId" trong operation block (get/post/put/...).
Nếu không có operationId, chèn ngay sau "summary".
Nếu cả 2 đều không có, chèn ở đầu operation block.

Dùng PyYAML (file không có comment, đã verify trước đó).
"""

from pathlib import Path
import yaml


def _insert_after_key(d: dict, target_key: str, new_key: str, new_value, fallback_keys=()) -> dict:
    """
    Trả về dict mới với new_key/new_value chèn ngay sau target_key.
    Nếu target_key không có, thử các fallback_keys theo thứ tự.
    Nếu không key nào có, chèn ở đầu dict.

    Nếu new_key đã tồn tại trong d -> sẽ bị ghi đè ở đúng vị trí cũ
    (giữ vị trí gốc, không di chuyển xuống cuối).
    """
    keys_to_try = (target_key,) + tuple(fallback_keys)

    insert_after = None
    for k in keys_to_try:
        if k in d:
            insert_after = k
            break

    result = {}
    inserted = False
    already_existed = new_key in d

    for k, v in d.items():
        if k == new_key:
            # Bỏ qua -- sẽ chèn lại ở vị trí mới
            continue
        result[k] = v
        if insert_after is not None and k == insert_after:
            result[new_key] = new_value
            inserted = True

    if not inserted:
        # Không tìm được vị trí target -> chèn ở đầu
        result = {new_key: new_value, **result}

    return result


def inject_x_side_effects(
    filepath: str,
    method: str,
    x_side_effects: dict,
    dry_run: bool = False,
) -> str | None:
    """
    Đọc file YAML, inject x-side-effects vào operation block tương ứng với
    method, ghi lại file.

    Args:
        filepath: đường dẫn tới file YAML (absolute path từ entry["output"])
        method: HTTP method viết thường (vd "put", "post")
        x_side_effects: dict đã validate qua schema_validator
        dry_run: nếu True, không ghi file, trả về YAML string để preview

    Returns:
        None nếu ghi file thành công.
        YAML string nếu dry_run=True.

    Raises:
        FileNotFoundError: file không tồn tại
        KeyError: method không tồn tại trong file YAML
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Không tìm thấy file YAML: {filepath}")

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    method = method.lower()
    if method not in data:
        raise KeyError(
            f"Method '{method}' không tồn tại trong {filepath}. "
            f"Methods có sẵn: {list(data.keys())}"
        )

    operation_block = data[method]

    new_block = _insert_after_key(
        operation_block,
        target_key="operationId",
        new_key="x-side-effects",
        new_value=x_side_effects,
        fallback_keys=("summary",),
    )

    data[method] = new_block

    output = yaml.safe_dump(
        data,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
        width=1000,  # tránh PyYAML tự wrap dòng dài
    )

    if dry_run:
        return output

    with open(path, "w", encoding="utf-8") as f:
        f.write(output)

    return None