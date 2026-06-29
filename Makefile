.PHONY: help bootstrap lock install-dev test quality preflight dashboard dashboard-install research-db research-db-eur research-db-gbpusd research-db-xauusd test-research-db

PYTHON ?= python3

help:
	@echo "Targets:"
	@echo "  make bootstrap           Create .venv and install the lock compiler"
	@echo "  make lock                Regenerate hashed runtime and development locks"
	@echo "  make install-dev         Install the hashed development environment"
	@echo "  make test                Run the complete locked test suite"
	@echo "  make quality             Run initial Ruff and mypy quality gates"
	@echo "  make preflight           Verify dependencies, quality, tests, and diff hygiene"
	@echo "  make dashboard           Start the SVOS/EVF/Trade dashboard (default port 8080)"
	@echo "  make dashboard-install   Install dashboard Python dependencies"
	@echo "  make research-db         Build the research feature database for EURUSD, GBPUSD, and XAUUSD"
	@echo "  make research-db-eur     Build the research feature database for EURUSD only"
	@echo "  make research-db-gbpusd  Build the research feature database for GBPUSD only"
	@echo "  make research-db-xauusd   Build the research feature database for XAUUSD only"
	@echo "  make test-research-db    Run the focused feature-database tests"

bootstrap:
	$(PYTHON) -m venv .venv
	.venv/bin/python -m pip install --upgrade pip pip-tools

lock: bootstrap
	.venv/bin/pip-compile --generate-hashes --strip-extras --resolver=backtracking --output-file=requirements.lock requirements.in
	.venv/bin/pip-compile --generate-hashes --strip-extras --resolver=backtracking --output-file=requirements-dev.lock requirements-dev.in

install-dev: lock
	.venv/bin/python -m pip install --require-hashes -r requirements-dev.lock

test:
	.venv/bin/python -m pytest -q

quality:
	.venv/bin/ruff check svos strategy_validation
	.venv/bin/mypy svos/lifecycle svos/shared

preflight:
	.venv/bin/python -m pip check
	$(MAKE) quality
	$(MAKE) test
	git diff --check

dashboard:
	$(PYTHON) dashboard/app.py

dashboard-install:
	pip install flask flask-cors pyyaml

research-db:
	$(PYTHON) run_pipeline.py --symbols EURUSD GBPUSD XAUUSD

research-db-eur:
	$(PYTHON) run_pipeline.py --symbols EURUSD

research-db-gbpusd:
	$(PYTHON) run_pipeline.py --symbols GBPUSD

research-db-xauusd:
	$(PYTHON) run_pipeline.py --symbols XAUUSD

test-research-db:
	$(PYTHON) -m pytest tests/research_engine/test_features.py tests/research_engine/test_feature_database.py -q
