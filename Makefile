PYTHON ?= python
SRC_DIRS = src tests

.PHONY: test test-cov lint format type ci build clean engine-info

test:
	$(PYTHON) -m pytest tests/ -v

test-cov:
	$(PYTHON) -m pytest tests/ -v --cov=src

lint:
	$(PYTHON) -m ruff check $(SRC_DIRS)

format:
	$(PYTHON) -m ruff format $(SRC_DIRS)

type:
	$(PYTHON) -m mypy src/ --ignore-missing-imports

ci: lint type test

build:
	$(PYTHON) -m PyInstaller build.spec

clean:
	@for path in build dist __pycache__; do \
		if [ -e "$$path" ]; then rm -rf "$$path"; fi; \
	done

engine-info:
	$(PYTHON) -c "from src.core.compressor import get_engine_name; print(get_engine_name())"
