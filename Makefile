.PHONY: help research-db research-db-eur research-db-gbpusd research-db-xauusd test-research-db

PYTHON ?= python3

help:
	@echo "Targets:"
	@echo "  make research-db         Build the research feature database for EURUSD, GBPUSD, and XAUUSD"
	@echo "  make research-db-eur     Build the research feature database for EURUSD only"
	@echo "  make research-db-gbpusd  Build the research feature database for GBPUSD only"
	@echo "  make research-db-xauusd   Build the research feature database for XAUUSD only"
	@echo "  make test-research-db    Run the focused feature-database tests"

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
