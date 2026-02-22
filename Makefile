PYTHON ?= python
PIP ?= $(PYTHON) -m pip
APP ?= main.py

.PHONY: help install run check clean

help:
	@echo "Targets:"
	@echo "  make install    Install Python dependencies"
	@echo "  make run        Run application"
	@echo "  make check      Basic syntax check"
	@echo "  make clean      Remove Python cache files"

install:
	$(PIP) install -r requirements.txt

run:
	$(PYTHON) $(APP)

check:
	$(PYTHON) -m py_compile $(APP)

clean:
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
