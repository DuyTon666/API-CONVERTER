def indent_of(line: str) -> int | None:
    stripped = line.strip()
    if stripped == "" or stripped.startswith("#"):
        return None  # dòng trống/comment không dùng để so sánh
    return len(line) - len(line.lstrip(" "))


def extract_key(line: str) -> str:
    text = line.strip()
    if text.startswith("- "):
        text = text[2:].strip()
    return text.split(":", 1)[0].strip()


def find_block_end(lines: list[str], start_line: int) -> int:
    base_indent = indent_of(lines[start_line]) or 0

    end_line = start_line
    for i in range(start_line + 1, len(lines)):
        indent = indent_of(lines[i])
        if indent is None:
            continue  # dòng trống/comment: bỏ qua, không dừng, không tính vào block
        if indent > base_indent:
            end_line = i  # vẫn lồng trong block hiện tại
            continue
        if indent == base_indent and lines[i].lstrip().startswith("- "):
            break  # sibling item khác trong cùng sequence -> không thuộc block này
        break  # dedent về <= base_indent -> hết block

    return end_line
