.DEFAULT_GOAL := help
VENV ?= venv
BOOTSTRAP_PYTHON ?= python3
PYTHON ?= $(VENV)/bin/python
PIP ?= "$(PYTHON)" -m pip
ACTIONLINT ?= actionlint

.PHONY: help setup test lint check
help: ## Show available tasks
	@awk 'BEGIN {FS = ":.*## "} /^[a-zA-Z_-]+:.*## / {printf "%-12s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

setup: ## Create the local venv and install pinned test dependencies
	"$(BOOTSTRAP_PYTHON)" -m venv "$(VENV)"
	$(PIP) install -r requirements-dev.txt

test: ## Check trusted workflow boundaries and candidate rejection cases
	"$(PYTHON)" -m pytest -q

lint: ## Lint GitHub Actions workflows (requires actionlint on PATH)
	"$(ACTIONLINT)" .github/workflows/*.yml

check: test lint ## Run tests and workflow lint
