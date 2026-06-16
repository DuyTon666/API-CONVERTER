# ============================================================
#  API-CONVERTER_V2 — Makefile
#  Yêu cầu: Python 3.10+, pip, ANTHROPIC_API_KEY đã set
# ============================================================

PYTHON      := python3
VENV        := .venv
PIP         := $(VENV)/bin/pip
PY          := $(VENV)/bin/python
PIPELINE    := 2.pipeline/pipeline_DOCX.py

.PHONY: help setup install env check \
        scan approve run-single run-batch run-module \
        test clean

# ── Mặc định ──────────────────────────────────────────────
help:
	@echo ""
	@echo "  API-CONVERTER_V2"
	@echo ""
	@echo "  make setup          Tạo venv + cài thư viện"
	@echo "  make check          Kiểm tra môi trường (Python, API key)"
	@echo ""
	@echo "  make scan           Scan module mới trong 1.docs/source/"
	@echo "  make approve m=<tên> Approve module draft → active"
	@echo ""
	@echo "  make run-module m=<tên>          Chạy module (strict)"
	@echo "  make run-module m=<tên> mode=bootstrap  Chạy module draft"
	@echo "  make run-batch in=<dir> out=<dir>  Chạy batch thủ công"
	@echo "  make run-single in=<file> out=<file>  Chạy 1 file"
	@echo ""
	@echo "  make test           Chạy pytest"
	@echo "  make clean          Xoá venv + __pycache__"
	@echo ""

# ── Setup môi trường ──────────────────────────────────────
setup: $(VENV)/bin/activate install
	@echo "✓ Môi trường sẵn sàng. Nhớ set ANTHROPIC_API_KEY."

$(VENV)/bin/activate:
	$(PYTHON) -m venv $(VENV)

install: $(VENV)/bin/activate
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

# ── Kiểm tra ──────────────────────────────────────────────
check:
	@echo "── Python version ──"
	@$(PY) --version
	@echo "── Packages ──"
	@$(PIP) show anthropic python-docx ruamel.yaml chardet | grep -E "^(Name|Version):"
	@echo "── ANTHROPIC_API_KEY ──"
	@test -n "$$ANTHROPIC_API_KEY" \
		&& echo "  ✓ Đã set ($${#ANTHROPIC_API_KEY} ký tự)" \
		|| echo "  ✗ CHƯA SET — export ANTHROPIC_API_KEY=sk-ant-..."

# ── Chạy pipeline ─────────────────────────────────────────
scan:
	cd 2.pipeline && $(PY) pipeline_DOCX.py --scan

approve:
	@test -n "$(m)" || (echo "Dùng: make approve m=<module>" && exit 1)
	cd 2.pipeline && $(PY) pipeline_DOCX.py --approve $(m) --approved-by "$(by)"

# make run-module m=ticket
# make run-module m=ticket mode=bootstrap
mode ?= strict
run-module:
	@test -n "$(m)" || (echo "Dùng: make run-module m=<module>" && exit 1)
	cd 2.pipeline && $(PY) pipeline_DOCX.py --module $(m) --mode $(mode)

# make run-batch in=1.docs/source/ticket out=5.openapi/paths/tickets
run-batch:
	@test -n "$(in)" || (echo "Dùng: make run-batch in=<dir> out=<dir>" && exit 1)
	@test -n "$(out)" || (echo "Dùng: make run-batch in=<dir> out=<dir>" && exit 1)
	cd 2.pipeline && $(PY) pipeline_DOCX.py --batch ../$(in) ../$(out)

# make run-single in=1.docs/source/ticket/create.docx out=5.openapi/paths/tickets/create.yaml
run-single:
	@test -n "$(in)" || (echo "Dùng: make run-single in=<file> out=<file>" && exit 1)
	@test -n "$(out)" || (echo "Dùng: make run-single in=<file> out=<file>" && exit 1)
	cd 2.pipeline && $(PY) pipeline_DOCX.py ../$(in) ../$(out)

# ── Test ──────────────────────────────────────────────────
test:
	cd 2.pipeline && $(PY) -m pytest -v

# ── Dọn dẹp ──────────────────────────────────────────────
clean:
	rm -rf $(VENV)
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete
	@echo "✓ Đã dọn sạch"