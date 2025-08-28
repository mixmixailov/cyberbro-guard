# Makefile for CyberBro Guard

.PHONY: help test test-unit test-regression test-all lint format install clean

help: ## Show this help message
	@echo "Available commands:"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Install dependencies
	pip install -r requirements.txt
	pip install -r requirements-dev.txt

test: test-unit ## Run unit tests (default)

test-unit: ## Run unit tests
	python -m pytest tests/unit/ -v

test-regression: ## Run regression tests
	python -m pytest tests/regression/ -m regression -v

test-regression-smoke: ## Run fast regression smoke tests
	python -m pytest tests/regression/ -m regression -k smoke -v

test-payments: ## Run payment-related tests
	python -m pytest tests/ -m payments -v

test-all: ## Run all tests
	python -m pytest tests/ -v

test-coverage: ## Run tests with coverage report
	python -m pytest tests/ --cov=app --cov-report=html --cov-report=term

lint: ## Run linting
	ruff check app/ tests/
	mypy app/

format: ## Format code
	ruff format app/ tests/

clean: ## Clean temporary files
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .coverage htmlcov/ .pytest_cache/

check: lint test-regression-smoke ## Quick check (lint + regression smoke tests)

ci: lint test-all ## CI pipeline (lint + all tests)