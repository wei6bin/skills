# Build the jidoka harness variants from the single source tree in src/.
#
# Targets:
#   build     render jidoka/, jidoka-copilot/, jidoka-cursor/ and the agents and
#             skills arrays in .claude-plugin/marketplace.json from src/
#   bump      increment the patch number in src/VERSION, then build (CI runs
#             it on every merge to main that touches the jidoka family)
#   check     fail when the committed outputs differ from a fresh render (CI)
#   test      unit tests for the renderer and model routing (CI)
#   lint      markdownlint every Markdown file per .markdownlint-cli2.jsonc (CI)
#   smoke-claude  dispatch one agent per role through Claude Code and report
#             the model each ran on (costs a few API calls; not in CI)
#   eval-claude   end-to-end verifier: run the jidoka/evals suite through
#             `claude plugin eval` in the eval-image container, one full
#             /jidoka:line run per case (costs a whole workflow per case; not
#             in CI). Needs a token in EVAL_ENV; HOST=1 runs it on the host
#   eval-image    build the eval runner image from jidoka/evals/Dockerfile
#   validate  claude plugin validate .
#   help      list targets and vars
#
# Vars:
#   PYTHON=python3   interpreter for scripts/render.py (needs PyYAML)
#   MARKDOWNLINT=... markdownlint command; pinned so a new rule cannot fail CI
#                    unannounced (needs Node)
#   ARGS="..."       passthrough to smoke-claude (--override) and eval-claude
#                    (e.g. --case <glob>, --model <m>, --no-publish, --keep-temp)
#   HOST=1           eval-claude on the host instead of the container
#   EVAL_ENV=...     env file holding CLAUDE_CODE_OAUTH_TOKEN (from
#                    `claude setup-token`) or ANTHROPIC_API_KEY; default
#                    ~/.config/jidoka/eval.env. Without it, those two variables
#                    are forwarded from the calling shell
#   EVAL_IMAGE=...   runner image tag (default jidoka-eval)
#   CLAUDE_CODE_VERSION=...  Claude Code in the image; default the host's
#   EXTRA_CA=...     PEM of a TLS-inspecting proxy, for the image build and the
#                    run; default $NODE_EXTRA_CA_CERTS

PYTHON ?= python3
MARKDOWNLINT ?= npx --yes markdownlint-cli2@0.23.3
EVAL_IMAGE ?= jidoka-eval
EVAL_ENV ?= $(HOME)/.config/jidoka/eval.env
CLAUDE_CODE_VERSION ?= $(or $(shell claude --version 2>/dev/null | cut -d' ' -f1),latest)
EXTRA_CA ?= $(NODE_EXTRA_CA_CERTS)
# A literal comma, for an argument inside $(if ...).
, := ,

.DEFAULT_GOAL := help
.PHONY: help build bump check test lint smoke-claude eval-claude eval-image validate

help: ## List targets and vars
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-13s %s\n", $$1, $$2}'
	@echo "  vars: PYTHON=$(PYTHON) MARKDOWNLINT=$(MARKDOWNLINT) ARGS=$(ARGS)"
	@echo "        HOST=$(HOST) EVAL_ENV=$(EVAL_ENV) EVAL_IMAGE=$(EVAL_IMAGE) EXTRA_CA=$(EXTRA_CA)"
	@echo "        CLAUDE_CODE_VERSION (default: the host's claude --version)"

build: ## Render every harness variant from src/
	$(PYTHON) scripts/render.py

bump: ## Increment the patch version in src/VERSION, then render
	$(PYTHON) scripts/render.py --bump

check: ## Verify the committed outputs match src/ (what CI runs)
	$(PYTHON) scripts/render.py --check

test: ## Run the renderer and model-routing unit tests (what CI runs)
	$(PYTHON) -m unittest discover -s scripts -p 'test_*.py'

lint: ## Lint every Markdown file, rendered ones included (what CI runs)
	$(MARKDOWNLINT) '**/*.md'

smoke-claude: ## Dispatch one agent per role via Claude Code; report the model each ran on
	bash scripts/routing-smoke.sh $(ARGS)

# --ablation none: a no-plugin arm cannot run /jidoka:line, it would only double
# the cost. --scaffold and --trust-plugin: the fixtures and the plugin are this
# repo's own. --allow-tools: the workflow edits files and runs git, npm and
# dotnet; a run's Bash has no network beyond the domains granted here, and
# line-greenfield-scaffold installs from the npm and NuGet registries.
EVAL_DOMAINS := registry.npmjs.org api.nuget.org globalcdn.nuget.org
EVAL_FLAGS := --ablation none --scaffold --trust-plugin --allow-tools Bash Write Edit \
	$(foreach d,$(EVAL_DOMAINS),'WebFetch(domain:$(d))')

# The repo mounts read-only; only the results directory is writable. The eval's
# own Bash sandbox is bubblewrap, which needs user namespaces (blocked by
# Docker's default seccomp profile) and a fresh /proc (blocked by Docker's
# masked paths), hence the two security options. The report stays local
# (--no-publish): publishing from inside the container is untested.
EVAL_RUN = docker run --rm \
	--security-opt seccomp=unconfined --security-opt systempaths=unconfined \
	-v $(CURDIR):/repo:ro -v $(CURDIR)/jidoka/evals/results:/repo/jidoka/evals/results \
	$(if $(wildcard $(EVAL_ENV)),--env-file $(EVAL_ENV),-e CLAUDE_CODE_OAUTH_TOKEN -e ANTHROPIC_API_KEY) \
	$(if $(EXTRA_CA),-v $(EXTRA_CA):/etc/ssl/extra-ca.pem:ro -e NODE_EXTRA_CA_CERTS=/etc/ssl/extra-ca.pem) \
	$(EVAL_IMAGE)

eval-claude: $(if $(HOST),,eval-image) ## Run the jidoka eval suite end to end (a full /jidoka:line run per case)
	mkdir -p jidoka/evals/results
	$(if $(HOST),,$(EVAL_RUN)) claude plugin eval ./jidoka $(EVAL_FLAGS) $(if $(HOST),,--no-publish) $(ARGS)

eval-image: ## Build the eval runner image (Claude Code, bubblewrap, git, curl, Node 22, .NET SDK)
	docker build -t $(EVAL_IMAGE) --build-arg CLAUDE_CODE_VERSION=$(CLAUDE_CODE_VERSION) \
		$(if $(EXTRA_CA),--secret id=ca$(,)src=$(EXTRA_CA)) - < jidoka/evals/Dockerfile

validate: ## Check the marketplace and its plugins load
	claude plugin validate .
