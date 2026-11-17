.DEFAULT_GOAL := help
VENV ?= venv
BOOTSTRAP_PYTHON ?= python3
PYTHON ?= $(VENV)/bin/python
PIP ?= "$(PYTHON)" -m pip

.PHONY: help setup test check
help: ## Show available tasks
	@awk 'BEGIN {FS = ":.*## "} /^[a-zA-Z_-]+:.*## / {printf "%-12s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

setup: ## Create the local venv and install pinned test dependencies
	"$(BOOTSTRAP_PYTHON)" -m venv "$(VENV)"
	$(PIP) install -r requirements-dev.txt

test: ## Check signer boundaries and unsafe artifact rejection cases
	"$(PYTHON)" -m pytest -q

check: test ## Run signer behavior and workflow policy tests
