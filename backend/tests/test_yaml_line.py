from api_utils.yaml_line import indent_of, find_block_end


def test_indent_of_counts_leading_spaces():
    assert indent_of("  foo: bar") == 2


def test_indent_of_returns_zero_for_no_indent():
    assert indent_of("foo: bar") == 0


def test_indent_of_returns_none_for_empty_line():
    assert indent_of("") is None
    assert indent_of("   ") is None


def test_indent_of_returns_none_for_comment_line():
    assert indent_of("  # ghi chú") is None


def test_find_block_end_stops_at_dedent():
    lines = [
        "parent:",
        "  child_a: 1",
        "  child_b: 2",
        "sibling:",  # dedent về cấp 0 -> hết block của "parent"
        "  other: 3",
    ]
    assert find_block_end(lines, 0) == 2


def test_find_block_end_stops_at_sibling_list_item():
    lines = [
        "items:",
        "  - name: a",  # start_line = 1, block của item này
        "    value: 1",
        "  - name: b",  # sibling khác trong cùng list -> không thuộc block trên
        "    value: 2",
    ]
    assert find_block_end(lines, 1) == 2


def test_find_block_end_skips_blank_and_comment_lines():
    lines = [
        "parent:",
        "  child_a: 1",
        "",  # dòng trống, indent_of trả None -> phải bỏ qua, không dừng ở đây
        "  # ghi chú giữa block",  # comment, cũng phải bỏ qua
        "  child_b: 2",
        "sibling:",
    ]
    assert find_block_end(lines, 0) == 4


def test_find_block_end_single_line_block_has_no_deeper_lines():
    lines = [
        "a: 1",
        "b: 2",
    ]
    assert find_block_end(lines, 0) == 0
