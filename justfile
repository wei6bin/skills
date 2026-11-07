# justfile - render the jidoka plugin from src/, check and test it, and run the
# end-to-end evals.
#
#   just                        list recipes and knobs
#   just build                  render jidoka/ and the marketplace arrays from
#                               src/
#   just test check lint test-hooks   what CI runs
#   just test-hooks --bash32    the post-edit hooks against fixture projects,
#                               and the secrets scan under bash 3.2 in Docker
#   just smoke-claude --override  one dispatch per role on Claude Code, with the
#                               Task model override too
#   just eval-claude            every eval case, in the runner container
#   just eval-claude --case line-greenfield-scaffold   one case
#   just HOST=1 eval-claude     on the host instead
#
# Knobs are the upper-case variables below, and go between `just` and the
# recipe: `just HOST=1 eval-claude`. `HOST=1 just eval-claude` is ignored: knobs
# are just variables, not environment reads (EXTRA_CA's default excepted).
# Arguments after test-hooks, smoke-claude and eval-claude pass straight
# through, as ARGS does.

# Arguments arrive as $1, $2, ... so "$@" keeps quoted ones intact.
set positional-arguments
set shell := ["bash", "-euo", "pipefail", "-c"]

# ---- knobs ---------------------------------------------------------------------

# interpreter for scripts/render.py (needs PyYAML)
PYTHON := "python3"
# markdownlint command; pinned so a new rule cannot fail CI unannounced (needs
# Node)
MARKDOWNLINT := "npx --yes markdownlint-cli2@0.23.3"
# extra words for test-hooks (--bash32, --keep, --hooks <dir>), smoke-claude
# (--override) and eval-claude (--case <glob>, --model <m>, --no-publish,
# --keep-temp)
ARGS := ""
# 1: eval-claude runs on the host instead of the container
HOST := ""
# env file holding CLAUDE_CODE_OAUTH_TOKEN (from `claude setup-token`) or
# ANTHROPIC_API_KEY. Without it, the container gets those two from the shell
EVAL_ENV := home_directory() / ".config/jidoka/eval.env"
# the eval runner image's tag
EVAL_IMAGE := "jidoka-eval"
# Claude Code in the image; empty: the host's `claude --version`, else latest
CLAUDE_CODE_VERSION := ""
# PEM of a TLS-inspecting proxy, for the image build and the run. It defaults to
# NODE_EXTRA_CA_CERTS from the environment, which Node reads anyway
EXTRA_CA := env("NODE_EXTRA_CA_CERTS", "")

# ---- internals -----------------------------------------------------------------

# A run's Bash has no network beyond the domains granted to its WebFetch, and
# line-greenfield-scaffold installs from the npm and NuGet registries.
eval_domains := "registry.npmjs.org api.nuget.org globalcdn.nuget.org"

[private]
default:
    @{{ quote(just_executable()) }} --justfile {{ quote(justfile()) }} --list --unsorted
    @echo; echo 'Knobs and their defaults, between `just` and the recipe (just HOST=1 eval-claude):'
    @for v in $({{ quote(just_executable()) }} --justfile {{ quote(justfile()) }} --variables | tr ' ' '\n' | grep '^[A-Z]'); do \
      val=$({{ quote(just_executable()) }} --justfile {{ quote(justfile()) }} --evaluate "$v"); \
      printf '    %-20s %s\n' "$v" "${val:-\"\"}"; done

# ---- render --------------------------------------------------------------------

# render jidoka/ and the marketplace arrays from src/: PYTHON
[group('render')]
build:
    {{ PYTHON }} scripts/render.py

# fail when the committed renders differ from a fresh one (CI): PYTHON
[group('render')]
check:
    {{ PYTHON }} scripts/render.py --check

# ---- test ----------------------------------------------------------------------

# the renderer and model-routing unit tests (CI): PYTHON
[group('test')]
test:
    {{ PYTHON }} -m unittest discover -s scripts -p 'test_*.py'

# markdownlint every Markdown file, rendered ones included (CI): MARKDOWNLINT
[group('test')]
lint:
    {{ MARKDOWNLINT }} '**/*.md'

# check that the marketplace and its plugins load
[group('test')]
validate:
    claude plugin validate .

# feed the post-edit hooks Claude payloads in fixture projects (CI, needs npm): ARGS
[group('test')]
test-hooks *args:
    bash scripts/test-hooks.sh {{ ARGS }} "$@"

# dispatch one agent per role via Claude Code, report each one's model: ARGS
[group('test')]
smoke-claude *args:
    bash scripts/routing-smoke.sh {{ ARGS }} "$@"

# ---- eval ----------------------------------------------------------------------

# every eval case end to end, a /jidoka:line or /jidoka:refine run each: HOST, ARGS, EVAL_ENV, EXTRA_CA
[group('eval')]
eval-claude *args: (_eval-image HOST)
    #!/usr/bin/env bash
    set -euo pipefail
    mkdir -p jidoka/evals/results
    # --ablation none: a no-plugin arm cannot run a jidoka skill, it would only
    # double the cost. --scaffold and --trust-plugin: the fixtures and the plugin
    # are this repo's own. --allow-tools: the workflow edits files and runs git,
    # npm and dotnet, and fetches only from eval_domains.
    flags=(--ablation none --scaffold --trust-plugin --allow-tools Bash Write Edit)
    for d in {{ eval_domains }}; do flags+=("WebFetch(domain:$d)"); done
    # The eval makes each run's workspace under TMPDIR, and its Bash sandbox
    # denies writes to /tmp, which beats its own grant to the workspace: with
    # the workspace under /tmp, every write in the run fails. So the workspace
    # goes elsewhere: a cache directory here, /eval-tmp in the image.
    if [ -n {{ quote(HOST) }} ]; then
      export TMPDIR="${XDG_CACHE_HOME:-$HOME/.cache}/jidoka/eval-tmp"
      mkdir -p "$TMPDIR"
      exec claude plugin eval ./jidoka "${flags[@]}" {{ ARGS }} "$@"
    fi
    # The repo mounts read-only; only the results directory is writable. The
    # eval's own Bash sandbox is bubblewrap, which needs user namespaces (blocked
    # by Docker's default seccomp profile) and a fresh /proc (blocked by Docker's
    # masked paths), hence the two security options. The report stays local
    # (--no-publish): publishing from inside the container is untested.
    repo={{ quote(justfile_directory()) }}
    run=(docker run --rm --security-opt seccomp=unconfined --security-opt systempaths=unconfined
      -v "$repo:/repo:ro" -v "$repo/jidoka/evals/results:/repo/jidoka/evals/results")
    if [ -e {{ quote(EVAL_ENV) }} ]; then
      run+=(--env-file {{ quote(EVAL_ENV) }})
    else
      run+=(-e CLAUDE_CODE_OAUTH_TOKEN -e ANTHROPIC_API_KEY)
    fi
    if [ -n {{ quote(EXTRA_CA) }} ]; then
      run+=(-v {{ quote(EXTRA_CA) }}:/etc/ssl/extra-ca.pem:ro -e NODE_EXTRA_CA_CERTS=/etc/ssl/extra-ca.pem)
    fi
    # On WSL the container shares the WSL kernel, so the eval takes it for WSL
    # and refuses a Bash grant unless /proc/mounts shows a Windows drive to put
    # out of the sandbox's reach. The container has none; an empty tmpfs whose
    # source reads C: stands in for one, and the sandbox denies it like a drive.
    if grep -qi microsoft /proc/version 2>/dev/null; then
      run+=(--mount 'type=volume,dst=/mnt/c,volume-driver=local,volume-opt=type=tmpfs,volume-opt=device=C:,volume-opt=o=size=1m')
    fi
    exec "${run[@]}" {{ quote(EVAL_IMAGE) }} claude plugin eval ./jidoka "${flags[@]}" --no-publish {{ ARGS }} "$@"

# build the eval runner image: EVAL_IMAGE, CLAUDE_CODE_VERSION, EXTRA_CA
[group('eval')]
eval-image: (_eval-image "")

# The image build, which eval-claude skips with HOST=1: Claude Code,
# bubblewrap, git, curl, Node 22 and the .NET SDK. The build has no context:
# the Dockerfile comes on stdin.
[private]
_eval-image host:
    #!/usr/bin/env bash
    set -euo pipefail
    [ -z {{ quote(host) }} ] || exit 0
    version={{ quote(CLAUDE_CODE_VERSION) }}
    [ -n "$version" ] || version=$(claude --version 2>/dev/null | cut -d' ' -f1 || true)
    secret=()
    [ -z {{ quote(EXTRA_CA) }} ] || secret=(--secret id=ca,src={{ quote(EXTRA_CA) }})
    docker build -t {{ quote(EVAL_IMAGE) }} --build-arg CLAUDE_CODE_VERSION="${version:-latest}" \
      ${secret[@]+"${secret[@]}"} - < jidoka/evals/Dockerfile
