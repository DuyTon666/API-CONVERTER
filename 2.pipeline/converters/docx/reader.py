from docx import Document
from docx.oxml.ns import qn

def _paragraph_text(paragraph) -> str:
    """
    Nối text run (<w:t>) trong 1 đoạn văn, đồng thời giữ lại
    line break thủ công (<w:br/>, Shift+Enter) thành '\n'.
    Nếu không xử lý, các đoạn JSON mẫu nhiều dòng viết bằng
    Shift+Enter (thay vì nhiều <w:p> riêng) sẽ bị dồn thành 1 dòng
    duy nhất, làm hỏng comment-stripping và pseudo-JSON parser.
    """
    parts = []
    for node in paragraph.iter():
        tag = node.tag.split('}')[-1]
        if tag == 't':
            parts.append(node.text or '')
        elif tag == 'br':
            parts.append('\n')
    return ''.join(parts)

def _read_tbl_element(tbl_element) -> list:
    lines = []
    for row in tbl_element.findall(qn('w:tr')):
        cells = []
        for cell in row.findall(qn('w:tc')):
            text = ''.join(node.text or '' for node in cell.iter(qn('w:t'))).strip()
            cells.append(text)
        lines.append('\t'.join(cells))
    lines.append('')
    return lines

def _process_block(block, lines):
    tag = block.tag.split('}')[-1]
    if tag == 'p':
        lines.append(_paragraph_text(block))
    elif tag == 'tbl':
        lines.extend(_read_tbl_element(block))
    elif tag == 'sdt':
        content = block.find(qn('w:sdtContent'))
        if content is not None:
            for child in content:
                _process_block(child, lines)

def read_docx(file_path: str) -> str:
    doc = Document(file_path)
    lines = []

    # Kiểm tra có sdt chứa table không
    has_sdt_tables = any(
        sdt.find('.//' + qn('w:tbl')) is not None
        for sdt in doc.element.body.iter(qn('w:sdt'))
    )

    if has_sdt_tables:
        # Đọc kể cả sdt (file detail với nested tables)
        for block in doc.element.body:
            _process_block(block, lines)
    else:
        # Đọc bình thường — không xử lý sdt
        for block in doc.element.body:
            tag = block.tag.split('}')[-1]
            if tag == 'p':
                lines.append(_paragraph_text(block))
            elif tag == 'tbl':
                lines.extend(_read_tbl_element(block))

    return '\n'.join(lines)

def read_text(file_path: str) -> str:
    with open(file_path, encoding='utf-8') as f:
        return f.read()