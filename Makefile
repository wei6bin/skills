# Build the jidoka harness variants from the single source tree in src/.
#
# Targets:
#   build     render jidoka/, jidoka-copilot/, jidoka-cursor/ and the agents and
#             skills arrays in .claude-plugin/marketplace.json from src/
#   check     fail when the committed outputs differ from a fresh render (CI)
#   test      unit tests for the renderer and model routing (CI)
#   lint      markdownlint every Markdown file per .markdownlint-cli2.jsonc (CI)
#   smoke-claude  dispatch one agent per role through Claude Code and report
#             the model each ran on (costs a few API calls; not in CI)
#   validate  claude plugin validate .
#   help      list targets and vars
#
# Vars:
#   PYTHON=python3   interpreter for scripts/render.py (needs PyYAML)
#   MARKDOWNLINT=... markdownlint command; pinned so a new rule cannot fail CI
#                    unannounced (needs Node)

PYTHON ?= python3
MARKDOWNLINT ?= npx --yes markdownlint-cli2@0.23.3

.DEFAULT_GOAL := help
.PHONY: help build check test lint smoke-claude validate

help: ## List targets and vars
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-10s %s\n", $$1, $$2}'
	@echo "  vars: PYTHON=$(PYTHON) MARKDOWNLINT=$(MARKDOWNLINT)"

build: ## Render every harness variant from src/
	$(PYTHON) scripts/render.py

check: ## Verify the committed outputs match src/ (what CI runs)
	$(PYTHON) scripts/render.py --check

test: ## Run the renderer and model-routing unit tests (what CI runs)
	$(PYTHON) -m unittest discover -s scripts -p 'test_*.py'

lint: ## Lint every Markdown file, rendered ones included (what CI runs)
	$(MARKDOWNLINT) '**/*.md'

smoke-claude: ## Dispatch one agent per role via Claude Code; report the model each ran on
	bash scripts/routing-smoke.sh $(ARGS)

validate: ## Check the marketplace and its plugins load
	claude plugin validate .
