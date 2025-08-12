SHELL := /bin/sh
PYTHON ?= python

.PHONY: dev set-webhook get-webhook del-webhook ping lint type

dev:
	uvicorn app.main:app --reload --port 8000

set-webhook:
	@if [ -z "$$BOT_TOKEN" ] || [ -z "$$PUBLIC_BASE" ]; then \
		echo "ERROR: set BOT_TOKEN and PUBLIC_BASE env vars. Example:"; \
		echo "PUBLIC_BASE=https://<domain> BOT_TOKEN=123:abc make set-webhook"; \
		exit 1; \
	fi
	$(PYTHON) scripts/manage_webhook.py set

get-webhook:
	@if [ -z "$$BOT_TOKEN" ]; then \
		echo "ERROR: set BOT_TOKEN env var. Example:"; \
		echo "BOT_TOKEN=123:abc make get-webhook"; \
		exit 1; \
	fi
	$(PYTHON) scripts/manage_webhook.py get

del-webhook:
	@if [ -z "$$BOT_TOKEN" ]; then \
		echo "ERROR: set BOT_TOKEN env var. Example:"; \
		echo "BOT_TOKEN=123:abc make del-webhook"; \
		exit 1; \
	fi
	$(PYTHON) scripts/manage_webhook.py delete


ping:
	$(PYTHON) scripts/ping_webhook.py


lint:
	ruff check .

type:
	mypy app || true


