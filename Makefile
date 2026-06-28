.PHONY: help install test lint backtest health dashboard dashboard-install \
        research-db research-db-eur research-db-gbpusd research-db-xauusd test-research-db \
        test-governance test-risk

PYTHON ?= python3

help:
	@echo ""
	@echo "Session SMC Trading Bot — Makefile targets"
	@echo ""
	@echo "  make install             Install all Python dependencies"
	@echo "  make test                Run all tests"
	@echo "  make test-governance     Run governance smoke tests only"
	@echo "  make test-risk           Run risk guard smoke tests only"
	@echo "  make lint                Lint with ruff"
	@echo "  make backtest            Run Phase-0 gate backtest (ST-A2 cached result)"
	@echo "  make health              Operator health check"
	@echo "  make dashboard           Start the SVOS/EVF/Trade dashboard (default port 8080)"
	@echo "  make dashboard-install   Install dashboard Python dependencies"
	@echo "  make research-db         Build the research feature database for EURUSD, GBPUSD, and XAUUSD"
	@echo "  make research-db-eur     Build the research feature database for EURUSD only"
	@echo "  make research-db-gbpusd  Build the research feature database for GBPUSD only"
	@echo "  make research-db-xauusd  Build the research feature database for XAUUSD only"
	@echo "  make test-research-db    Run the focused feature-database tests"
	@echo ""

install:
	pip install -r requirements.txt

test:
	$(PYTHON) -m pytest tests/ -q --tb=short

test-governance:
	$(PYTHON) -m pytest tests/test_governance.py -v --tb=short

test-risk:
	$(PYTHON) -m pytest tests/test_risk_guards.py -v --tb=short

lint:
	ruff check session_smc/ tests/test_governance.py tests/test_risk_guards.py --ignore E501,E402

backtest:
	$(PYTHON) scripts/run_backtest.py --strategy-id ST-A2

health:
	$(PYTHON) scripts/operator_health_check.py

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
