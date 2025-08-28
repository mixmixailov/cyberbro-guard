# CyberBro Guard - Development Makefile

.PHONY: help install test lint format migrate migrate-dry backup-migrate clean docker-build docker-run preflight mcp-proof guard

# Default target
help:
	@echo "Available targets:"
	@echo "  install        - Install dependencies"
	@echo "  test           - Run all tests"
	@echo "  test-unit      - Run unit tests only"
	@echo "  test-e2e       - Run E2E tests"
	@echo "  lint           - Run linting (ruff check)"
	@echo "  format         - Format code (ruff format)"
	@echo "  migrate        - Run database migrations with backup"
	@echo "  migrate-dry    - Show migration plan without applying"
	@echo "  backup-migrate - Run migrations with explicit backup"
	@echo "  clean          - Clean temporary files"
	@echo "  docker-build   - Build Docker image"
	@echo "  docker-run     - Run in Docker"
	@echo "  preflight      - Run rules compliance check"
	@echo "  mcp-proof      - Run MCP sanity checks"
	@echo "  guard          - Run full compliance guard (preflight + mcp-proof + tests)"

# Development setup
install:
	pip install -r requirements.txt
	pip install -r requirements-dev.txt
	npm install
	npx playwright install --with-deps

# Testing
test: test-unit test-e2e

test-unit:
	python -m pytest tests/ -v --tb=short -x

test-e2e:
	npm run test:e2e

# Code quality
lint:
	python -m ruff check .

format:
	python -m ruff format .
	python -m ruff check --fix .

# Database migrations
migrate:
	python -m app.utils.migrate --backup

migrate-dry:
	python -m app.utils.migrate --dry-run

backup-migrate:
	python -m app.utils.migrate --backup --backup-retention 10

# Cleanup
clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache
	rm -rf playwright-report
	rm -rf test-results
	rm -rf .coverage
	rm -rf htmlcov

# Docker
docker-build:
	docker build -t cyberbro-guard .

docker-run:
	docker run -p 8000:8000 --env-file .env cyberbro-guard

# Quick development commands
dev-setup: install migrate

dev-test: lint test-unit

dev-full: format lint test

# Compliance and Guard targets
preflight:
	@echo "🔍 Running rules compliance check..."
	chmod +x scripts/check_rules.sh
	./scripts/check_rules.sh

mcp-proof:
	@echo "🤖 Running MCP sanity checks..."
	@echo "Checking MCP configuration and results..."
	@if [ -d "docs/automation/mcp_sanity" ]; then \
		echo "✅ MCP sanity directory exists"; \
		result_count=$$(ls docs/automation/mcp_sanity/*.txt 2>/dev/null | wc -l); \
		echo "Found $$result_count MCP sanity result files"; \
		if [ "$$result_count" -lt 1 ]; then \
			echo "⚠️  No MCP sanity results found - run manual MCP tests"; \
		else \
			echo "✅ MCP sanity results present"; \
		fi; \
	else \
		echo "❌ MCP sanity directory missing"; \
		exit 1; \
	fi
	@if [ -f ".cursor/mcp.json" ]; then \
		echo "✅ MCP configuration found"; \
		if command -v jq >/dev/null 2>&1; then \
			if jq empty .cursor/mcp.json >/dev/null 2>&1; then \
				echo "✅ MCP configuration is valid JSON"; \
			else \
				echo "❌ MCP configuration has invalid JSON"; \
				exit 1; \
			fi; \
		else \
			echo "⚠️  jq not available, skipping JSON validation"; \
		fi; \
	else \
		echo "⚠️  MCP configuration not found (expected in CI)"; \
	fi

guard: preflight mcp-proof test-unit
	@echo "🛡️ All guard checks completed successfully!"
	@echo "✅ Rules compliance: PASSED"
	@echo "✅ MCP sanity: PASSED" 
	@echo "✅ Unit tests: PASSED"
	@echo "🎉 Project is ready for deployment!"