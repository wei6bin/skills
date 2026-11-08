# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## What this repo is

A Claude Code **plugin marketplace** (defined in
`.claude-plugin/marketplace.json`) hosting:

- `jidoka/` - the **jidoka** dev-workflow plugin for Claude Code (agents,
  skills, hooks), authored under `src/` and rendered (see "One source, two
  renders" below). `jidoka/evals/` is hand-written.
- `utility-skills/` - standalone user-invocable skills with no agents or hooks.
  Each skill is a `skills/<name>/SKILL.md` file, optionally with bundled
  `scripts/` and `references/` beside it (as `my-work` has). Skills may declare
  required `args:` in frontmatter (YAML list with `name`, `description`,
  `required`). Current skills: `teach-me`, `learn-it`, `spec-me`, `html-it`,
  `my-work`.
- `code-to-prd/` and `clinical-lecture-brief/` - single-skill plugins
  (`skills/<name>/SKILL.md` with bundled resources such as `scripts/` and
  `references/`), no agents or hooks.

`claude plugin validate .` checks the marketplace and its plugins load. The
"test" is installing the plugin and exercising it:
`/plugin marketplace add wei6bin/skills`, `/plugin install jidoka@skills`. The
marketplace is added from GitHub, so a local edit is not live until it is merged
to `main` and the plugin updated (`claude plugin update jidoka@skills`, or the
marketplace's background auto-update on the next session start), then
`/reload-plugins`. Installed contents land at
`~/.claude/plugins/cache/skills/<plugin-name>/<commit-sha>/`.

## One source, two renders

`src/` is the only place the jidoka plugin is edited. `just build` runs
`scripts/render.py` (Python 3 with PyYAML) and rewrites every rendered path
listed below; `just check` fails when the committed outputs are stale and is
what CI runs (`.github/workflows/render-check.yml`).

- `src/agents/<name>.md` - one agent: a body plus frontmatter with `name`,
  `description`, `tools` (Claude tool names) and a `role`, which
  `src/models.yaml` resolves to a model (see "Model routing"). An optional
  `model:` map pins the Claude alias or the Copilot worker model when an agent
  must deviate from its role; say why in a comment. An optional `claude:` block
  adds Claude-only frontmatter keys (`effort`, which beats the role's,
  `omitClaudeMd`, `is_background`); it cannot set `name`, `description`,
  `tools` or `model`. Each agent is rendered twice: as the plugin's agent
  (`jidoka/agents/<name>.md`) and as the worker render (below). Text only one
  of them gets goes in a render section of the body: a line
  `<!-- harness: claude -->` (or `worker`) opens it, the next marker or
  `<!-- harness: end -->` closes it, and the renderer drops the sections that
  do not name the render (format in `scripts/render.py`). Today only
  `impl-simplify` has them, because the plugin's agent wraps Claude Code's
  built-in `simplify` skill while a worker on another harness, which has no
  such skill, gets the simplification rules. One file per agent; the renderer
  rejects a `<name>.<suffix>.md`.
- `src/skills/<skill>/` - copied into `jidoka/skills/`. A skill has one render,
  read by the lead and by every herdr worker alike, so the renderer rejects a
  render section in one. A bundled script (a non-Markdown file starting `#!`)
  gets the hooks' one-line GENERATED comment; other files are copied byte for
  byte, except Python bytecode (`__pycache__/`, `*.pyc`), which `just test`
  leaves beside a script it imports and the renderer skips.
- The worker render: every agent is also written to
  `jidoka/skills/herdr-crew/agents/<name>.md` for herdr mode (see
  "Architecture"): the body plus the `worker` sections, under a flat
  frontmatter (`role`, `tools`, `claude-model`, `claude-effort`,
  `copilot-model`) that `crew.sh` reads. A worker without the jidoka plugin
  (Codex, Copilot CLI, Claude Code without the plugin) reads it as its
  instructions. `src/skills/herdr-crew/agents/` must not exist; the renderer
  refuses it.
- `src/hooks/hooks.json` - the canonical `afterFileEdit` script list, rendered
  to Claude's `PostToolUse` (matcher `Edit|Write|MultiEdit`,
  `${CLAUDE_PLUGIN_ROOT}`). `src/hooks/*.sh` are copied beside it.
- The `agents` and `skills` arrays of the `jidoka` entry in `marketplace.json`
  are rendered too: adding a file under `src/agents/` or `src/skills/`
  registers it on the next build.

Rendered paths are generated and never hand-edited:
`jidoka/{agents,skills,hooks}/` and the two marketplace arrays. To change one,
edit its source under `src/`, run `just build` and commit both. The rendered
Markdown carries no inline marker on purpose: every skill, skill reference and
agent file loads into the model's context when it runs, so the header comment
it used to carry cost tokens on every load. This rule is the marker instead,
backed by `.gitattributes`, which marks the same directories
`linguist-generated` (GitHub collapses them in a diff) and which `just test`
checks against the renderer. Hook and skill scripts are executed, never loaded
into context, so each keeps a one-line comment under its shebang naming its
source.

## Model routing

Models are not written into agent files. Each agent names a `role`, and
`src/models.yaml` holds two tables: `roles` (role to tier, plus Claude's
`effort`) and `tiers` (tier to a Claude alias, plus the model a herdr worker on
Copilot CLI runs on). Today reasoning is `frontier` (code-architect),
verification is `strong` (plan-reviewer, code-reviewer, security-reviewer,
project-scaffolder), and implementation and exploration are `standard`. Three
layers, in order of how often they change:

1. **Source** - edit `src/models.yaml` to move a role between tiers or change a
   tier's model, then `just build`. Pin a single agent with its `model:` map
   only when it must deviate (impl-simplify's Copilot worker runs on the
   economy model, since it does the cleanup from its own rules).
2. **Run time** - `line` passes `model` on a Task call for three exceptions:
   refactor-tier stories review on `sonnet`, an implementer re-dispatched
   after `FIXES_NEEDED` or a failed evidence check goes up to `opus`, and the
   architect amending a plan after plan review runs on `opus`. The Task
   `model` beats frontmatter. In herdr mode it becomes `crew.sh dispatch
   --model`, for Claude workers only.
3. **Environment, no plugin edit** - the agents carry aliases (`fable`, `opus`,
   `sonnet`, `haiku`), so `ANTHROPIC_DEFAULT_<TIER>_MODEL` in a settings file's
   `env` remaps a whole tier, `CLAUDE_CODE_SUBAGENT_MODEL` sets a default that
   frontmatter still beats, and a same-named agent in `.claude/agents/` beats
   the plugin's.

## Testing

The task runner is [just](https://just.systems): `just` alone lists the recipes
and the knobs they take, and a knob goes between `just` and the recipe
(`just HOST=1 eval-claude`).

- `just test` - unit tests for the renderer (`scripts/test_render.py`): role
  resolution, pins and `claude.effort` precedence, the worker render, render
  sections, error cases, no inline marker in rendered Markdown,
  `.gitattributes` covering exactly the rendered paths, and determinism on the
  real tree. Also the refine skill's `agreement.py`
  (`scripts/test_agreement.py`): the round trip through the work item fields,
  the hash, every format and ready rule, the `Base:` line, the line's claim,
  compare, record and comment, and the Azure DevOps reads and writes against
  a fake `az` on `PATH`. Also the line's scheduled pick-up
  (`scripts/test_pickup.py`): the oldest story chosen, the container started
  and killed past its time, the `flock` lock, the wait after a failed run,
  the hold on a broken base until it moves, and the stale-claim report,
  against a fake `az`, `docker` and `git`. And, on the real tree, that only
  `refine` and `check` mention `AskUserQuestion`: nothing the line runs may
  ask. CI runs it together with `just check`, `just lint` and
  `just test-hooks`.
- `just check` - the committed renders match `src/`. `claude plugin validate .`
  checks the marketplace loads.
- `just lint` - markdownlint-cli2 (version pinned in the `justfile`, needs Node)
  over every Markdown file, rendered ones included, per
  `.markdownlint-cli2.jsonc`.
- `just test-hooks` - the post-edit hooks (`scripts/test-hooks.sh`): feeds
  each rendered hook Claude Code's `PostToolUse` payload against throwaway
  fixture projects (an npm workspace with a root `.prettierignore`, a Biome
  project, and single, workspace, create-vite and composite-reference
  TypeScript projects) and asserts on its reply and on the file it leaves on
  disk, plus a grep for bash 4 syntax. Installs pinned Prettier, Biome and
  TypeScript from npm, so it needs Node and the registry; CI runs it on the
  runner's own Node. `--bash32` also runs the secrets scan under bash 3.2
  (macOS's `/bin/bash`) in Docker, which CI skips so a Docker Hub or Alpine
  mirror outage cannot turn it red; `--hooks <dir>` tests another copy, such
  as the committed one, to check that a new case fails before a fix.
- `just smoke-claude` - end to end on Claude Code: loads `jidoka/` through
  `--plugin-dir` (from a temp copy carrying a throwaway manifest), dispatches
  one agent per role with a trivial prompt, then reads the session's subagent
  transcripts under `~/.claude/projects/` to report the model each actually
  ran on against the alias in its frontmatter. Costs a few short API calls, so
  it is not in CI. `just smoke-claude --override` also exercises the Task
  `model` parameter.
- `just eval-claude` - the end-to-end verifier: `claude plugin eval` runs each
  case under `jidoka/evals/` in a sandboxed headless session, inside a
  container built from `jidoka/evals/Dockerfile` (`just eval-image`;
  `just HOST=1 eval-claude` runs on the host instead). Seven cases. No line
  case has anyone standing in for a developer: each story is a signed
  agreement file the scaffold builds and signs with `agreement.py`, so a
  question in the run is a failure.
  `line-minimal-story` scaffolds a zero-dependency Node API as a git repo,
  types `/jidoka:line` on a two-AC backend story, and grades the claim, the
  dispatch order and the end state (story.md, the four plan docs `02`-`05`
  with no overview or business plan copying the agreement and no change-site
  snippet over 12 lines, ledger, line decisions, the summary's AC table,
  merged code with tests citing the AC IDs, story `jidoka-done`, backlog
  closed, worktree gone).
  `line-greenfield-scaffold` starts from a repo with no code and a setup
  agreement whose `Stack:` line holds the Dev Lead's answers, and grades the
  new-project branch: `project-setup` invoked, the `project-scaffolder` agent
  dispatched, a .NET + React skeleton and project context merged into `main`,
  and no story phase run.
  `line-not-ready` (a draft story) and `line-changed-after-signoff` (an AC
  edited after the sign-offs) must be refused at the claim, before any agent,
  worktree or branch; they take minutes. `line-base-broken` signs the story,
  then breaks `main` (its 404 test fails), and grades the base check: the
  base tested through `git-worktrees`, then no claim, agent, branch,
  worktree or `andon.md`, and the story still `jidoka-ready`.
  `line-andon-stop` signs a stop condition the story must hit (any change to
  the note store) and grades the stop: no implementer, `andon.md` and an open
  Andon row on the branch, the story `jidoka-blocked` there, the worktree
  kept.
  `refine-three-roles` types `/jidoka:refine` on a vague story file in that
  same Node repo, with the case's system prompt playing the BA, Dev Lead and
  QE, and grades the questions' role tags, the agreement on disk (format,
  three live sign-offs at one hash, `jidoka-ready`) and, judged, that it
  settles every planted gap. A full line run is a whole workflow, up to an
  hour and several dollars, so none of this is in CI; run the line cases
  before merging a change to the `line` flow and the refine case before one to
  `refine` or the agreement format (`just eval-claude --case <name>` runs one).
  A resumed run (after an andon answer) has no case: an eval run is one
  session, and `scripts/test_agreement.py` covers `compare`, which it rests
  on.
  The container needs a credential in `~/.config/jidoka/eval.env`
  (`CLAUDE_CODE_OAUTH_TOKEN` from `claude setup-token`, or
  `ANTHROPIC_API_KEY`). Harness facts it relies on: the case's
  `plugins: ["../.."]` is what loads `jidoka/` without a manifest;
  `AskUserQuestion` is not offered headless, so `refine-three-roles`'s
  `append_system_prompt` stands in for the three people in the room; a
  Bash-granting eval
  refuses to start while the host's Docker credential store holds a symlink
  (Docker Desktop's "User" CLI install mode links its tools there), which is
  why the container is the default; the eval's bubblewrap sandbox only
  starts in a container run with `seccomp=unconfined` and
  `systempaths=unconfined`; and that sandbox denies writes to `/tmp` over its
  grant to the run's workspace, which the eval makes under `TMPDIR`, so the
  image and `HOST=1` both point `TMPDIR` outside `/tmp` (on the host the
  sandbox also needs `bwrap` and `socat`, and Ubuntu's npm 9.2 fails its
  proxy, so the greenfield case needs the container). On a WSL host the
  container shares WSL's kernel, and the eval refuses a Bash grant there
  unless `/proc/mounts` shows a Windows drive to exclude, so the recipe mounts
  an empty tmpfs whose source reads `C:` at `/mnt/c`. A run's Bash also has no
  network beyond the domains the operator grants
  (`--allow-tools "WebFetch(domain:...)"`; a case
  cannot grant any), so the justfile's `eval_domains` grants the npm and NuGet
  registries the greenfield case installs from, and the image's entrypoint adds
  a mounted `EXTRA_CA` to the system store because .NET, unlike Node, ignores
  `NODE_EXTRA_CA_CERTS`.
- Herdr mode has no scripted test. Inside herdr, run `/jidoka:check`, then
  drive `crew.sh` (`up`, `dispatch`, `wait`, `report`, `send`, `release`,
  `down`) against a scratch config and state (`JIDOKA_HERDR_CONF`,
  `JIDOKA_HERDR_STATE`). For native Claude workers without the plugin
  installed, run it from a copy of `jidoka/` with a throwaway manifest, as
  `just smoke-claude` does.

## Architecture

The jidoka plugin implements one 10-phase orchestrator-driven flow that runs
unattended (readiness and claim → exploration → settle against the agreement →
architecture → plan docs → review → summary → slice-by-slice implementation →
test-plan walkthrough with screenshots → PR), from a story the BA, Dev Lead and
QE signed in `refine`.
The full phase → subagent/skill → artifact map, drawn as an inline SVG flow, is
in `docs/orchestrator-workflow.html` - open it in a browser.

Three component types:

- **Skills** (`src/skills/<name>/SKILL.md`, one file per skill) - `refine` and
  `line` are the two halves of a story: `refine` is where the BA, Dev Lead and
  QE settle every decision and sign **the agreement** (format in
  `src/skills/refine/references/agreement-format.md`, moved between an Azure
  DevOps work item and Markdown only by its bundled `scripts/agreement.py`),
  and `line` builds the story with nobody to ask. The split and the decisions
  behind it are in `docs/refine-and-autonomous-line.md`. `line` claims a
  `jidoka-ready` story through the same script, which snapshots it as
  `story.md` on the story's branch. Before the claim it tests the story's
  base (section 10's signed `Base:` branch, else the default branch) in a
  detached worktree; a broken base stops the run without touching the story.
  A gap the agreement leaves that it may
  close, it decides and records in `09-decisions.md` (`AD-n`, later confirmed
  by the owning role through `refine`). Anything else stops the line: andon,
  with `andon.md`, a draft PR, a question on the story and the story marked
  `jidoka-blocked`. Every gate gets three attempts. A timer can start it:
  `src/skills/line/scripts/pickup.py` picks the oldest `jidoka-ready` story
  and runs the line in a fresh container from `src/skills/line/runner/`, the
  only place it skips permission prompts, and holds the stories of a base a
  run found broken until that branch moves. The rest are companions `line`
  invokes (`vertical-slicing`,
  `git-worktrees`, `raise-pr`, `backend-implementer`, `frontend-implementer`,
  `sweep-implementer`, `reuse-ladder`, `codebase-context-builder`,
  `context-updater`, `react-best-practices`, `frontend-styling-standard`,
  `restful-api-design`, `test-plan-walkthrough`, `project-setup`,
  `aspnet-backend-scaffold`, `react-frontend-scaffold`, `herdr-crew`). `check`
  is the third entry point, the self-check (see "Herdr mode" below). When the
  agreement's `Stack:` line sets up a new project or layer, `line` invokes
  `project-setup` before Phase 2. It holds the **stack catalog** (one row per
  stack, today a .NET backend and a React frontend, each naming its scaffold
  skill) and the questions `refine` asks the Dev Lead for that line, reads the
  answers from it, freezes a skeleton contract and dispatches the
  `project-scaffolder` agent with the chosen rows. The split is deliberate:
  the build's trail (two implementers' reports, every gate, the smoke, the
  context write-up) stays in the agent's context instead of the
  orchestrator's. The agent
  dispatches `impl-backend` and `impl-frontend` with scope `project scaffold`,
  checks their work, smokes the halves together, builds the project context
  and lands the skeleton on the base branch; `project-setup` then checks the
  result cheaply. Adding a stack is a catalog row plus a scaffold skill;
  nothing else names a stack. The two scaffold skills began as standalone
  skills and keep their feature-slice guidance, but the line loads only their
  bootstrap. Skills run in the main session; `context-updater` in
  particular must never be dispatched as a subagent and runs once per story
  from the orchestrator. `refine`, `line` and `check` set
  `disable-model-invocation: true`: their descriptions stay out of every
  session's skill listing, and they run only when the user types
  `/jidoka:refine`, `/jidoka:line` or `/jidoka:check`. The companions must not
  set it. The flag also blocks the Skill tool and subagent `skills:`
  preloading, and that is how the orchestrator and the agents reach them.
  Instead they set `user-invocable: false`, which drops them from the `/` menu
  but leaves them in the model's listing. `just test` enforces all of this.
- **Agents** (`src/agents/`) - subagents the orchestrator dispatches via the
  Task tool with `agent_type: "jidoka:<name>"`: `code-explorer`,
  `code-architect`, `plan-reviewer`, `impl-backend`, `impl-frontend`,
  `impl-simplify`, `code-reviewer`, `security-reviewer`, `test-plan-walker`,
  `project-scaffolder`. `project-scaffolder` dispatches the two implementers
  itself, which Claude Code supports.
  `impl-simplify` owns no rules of its own - it is a thin context boundary that
  invokes the built-in `simplify` skill in an isolated window; only its worker
  render carries simplification rules. Either way it then applies the house
  conventions (`react-best-practices`, `restful-api-design`) to the
  whole-story diff without changing behaviour. The implementers deliberately
  do not load those skills, so their context goes to the ACs. `code-architect`
  also loads `restful-api-design`, because the API-surface rules (paths, status
  codes, error envelope) belong in the frozen contract, which nothing
  downstream may change.
- **Hooks** (`src/hooks/`) - `PostToolUse` on `Edit|Write|MultiEdit`: secrets
  scan, prettier, biome, TypeScript typecheck, plus a sourced `_lib.sh` (not
  itself a hook). `hook_init` in `_lib.sh` extracts the edited file's path
  from `tool_input.file_path`; `emit_context` replies through
  `hookSpecificOutput.additionalContext`. The scripts self-gate (exit silently
  when the edited file doesn't apply) so they're safe in a generic plugin, and
  the ts-typecheck hook deliberately reports only the edited file's
  diagnostics (their indented detail lines included), checks a
  `tsconfig.json` with `references` (create-vite's layout, which lists no
  files) with `tsc -b`, and treats workspace sibling-import errors as
  non-blocking advisories - preserve those properties when editing them. The
  scripts also run under macOS's bash 3.2, so no bash 4 syntax such as
  `declare -A`. `just test-hooks` checks all of this. Three further properties
  are load-bearing:
  - **Prettier auto-writes; Biome only reports.** Formatting needs no judgement,
    and an advisory the agent may decline is not a gate - a formatting-only CI
    failure reached `main` while the report-only version of this hook was
    installed and firing. Lint findings stay advisory because many Biome
    autofixes are marked unsafe. Biome is the only linter hook - there is
    deliberately no ESLint one, matching `frontend-styling-standard`'s
    Biome-over-ESLint recommendation.
  - **Each hook runs from the directory that owns its tool's config**, resolved
    by `find_tool_root` in `_lib.sh`, _not_ from the nearest `package.json`. In
    a pnpm/npm workspace those differ: configs sit at the workspace root while
    every app under `apps/*` has its own `package.json`, and starting in the app
    directory silently drops the root `.prettierignore`, producing violations on
    generated output CI never checks.
  - **Biome's exit code is not a usable signal per file** - it is also non-zero
    when the path is ignored by `biome.json`. `biome-on-change.sh` keys off
    `--reporter=json`'s `.summary.errors`, which stays 0 for infos and warnings,
    matching what a `biome lint` CI step actually fails on.

### Herdr mode

Inside herdr (`HERDR_ENV=1`) `line` invokes `herdr-crew`, and every subagent
dispatch goes through `scripts/crew.sh` instead of the task tool. Each worker is
a full agent session in a pane of a `jidoka crew` tab. The tab starts as one
free pane; a worker takes it or splits the rightmost pane to the right, and
crew.sh evens the columns out. Release closes a worker's column; the first tab
keeps its last pane, free. A fifth concurrent worker, or a column under 40
cells, opens another tab. The orchestrator's herdr agent is renamed `lead` and
can answer a worker through `crew.sh send`. `~/.config/jidoka/herdr.conf` picks
each agent's harness (`agent.<agent>`, `role.<role>`, `harness`, then the
lead's own) and `yolo.<harness> = on` adds its no-prompts flag;
`/jidoka:check` shows and changes it.

A Claude worker runs the agent natively (`claude --agent jidoka:<agent>`) when
the plugin is installed or the plugin root carries a manifest, and reports via
the last turn of its transcript. Any other worker reads the worker render and
writes its report to a file in `~/.local/state/jidoka/herdr/<lead pane>/`
(`--add-dir`; a named herdr session's name leads the folder name, since each
session has its own pane ids). Crew panes set `JIDOKA_CREW_ROLE=worker`, so a
worker that dispatches agents (`project-scaffolder`) uses its own task tool.
Load-bearing, verified on herdr 0.9.5 on 2026-11-06:

- **The pane's shell sends the tint.** herdr ties an OSC 11 background to the
  sending process group and restores the host colors when it exits, so `paint`
  types the shell's `printf` builtin; a child script's tint vanishes at random.
- **Release waits for the whole process group.** Helpers (Copilot's native
  binary, MCP servers) outlive the shell's direct child and reset the colors on
  exit, after a kept pane is repainted.
- **crew.sh equalizes columns itself** (no herdr action): it reads `pane layout`
  and sets each split's ratio with the socket API's `layout.set_split_ratio`,
  which has no CLI command, through `nc -U`. herdr answers one request per
  connection and closes it. A split id ends in its tree path (`split_3_11`:
  root, second, second), sent as booleans. It re-runs after a release or a pane
  someone closed; without `nc` the columns stay uneven and `/jidoka:check` says
  so.
- **Only a Claude worker gets a brief twice, and only when its transcript lacks
  it.** A paste into a starting TUI can be lost (Claude Code on Fable at
  xhigh), so the first prompt waits for a still screen; a lagging screen means
  other harnesses never get a second copy.
- **herdr's state for Copilot is a fallback guess** (`herdr agent explain`:
  `default_known_agent_idle_fallback`; Copilot CLI 1.0.10x). A file-reporting
  worker is ready once its file is newer than its prompt; no report and a still
  screen for two minutes is `quiet`.
- Claude Code's TUI keeps no scrollback in a pane, so reports come from a
  transcript or a file.
- **The run lock is a file bash creates with `noclobber` (`O_EXCL`), not a
  `mkdir`.** uutils coreutils' `mkdir` (0.10, the system one on recent Ubuntu)
  lets two racing calls both succeed; in a test with six crew.sh processes,
  half the rounds had two holders.

## Registrations and versioning

- The jidoka plugin's `agents` and `skills` arrays in
  `.claude-plugin/marketplace.json` are rendered from `src/`. For
  `utility-skills`, new skills go in `utility-skills/skills/<name>/SKILL.md` and
  the path `./skills/<name>` must be added to its `skills` array by hand -
  adding a file alone does not register it.
- **Plugins carry no version, on purpose.** Claude Code keys a plugin's
  version off the marketplace's commit SHA when neither a
  `<plugin>/.claude-plugin/plugin.json` nor the plugin's `marketplace.json`
  entry sets a `version`, so every merge to `main` is a new version and
  auto-update ships it on the next session start with nothing to bump. Do not
  add a Claude manifest or a `version` field anywhere: a `version` switches the
  plugin to explicit versioning and updates stop until someone remembers to
  bump it. `metadata.version` in `marketplace.json` is informational - bump it
  when a plugin is added or removed.

## Conventions

- Commit messages are prefixed with what they touch: `jidoka: ...` for anything
  under `src/` or the rendered plugin, `utility-skills: ...`,
  `code-to-prd: ...`, `clinical-lecture-brief: ...`, or `marketplace: ...` for
  the marketplace, renderer, justfile and CI.
- Skill/agent prose is written as direct instructions to the executing agent
  ("You are...", numbered phases where order matters, explicit announce lines
  and return-report formats) - match that style. Keep agent and
  companion-skill prose harness-neutral ("the task tool", "on Claude Code,
  ..."): in herdr mode a worker on Codex or Copilot CLI reads the worker
  render and the skills as they are. Text only the plugin's agent or only the
  worker should see goes in an agent's render section.
- `utility-skills` skills are user-invocable: their description must clearly
  state trigger phrases and argument requirements; no `[Internal subagent...]`
  prefix.
- Markdown prose wraps at 80 columns (MD013); tables, code blocks, headings and
  frontmatter are exempt. A command or string too long to wrap goes in a fenced
  block, not inline code. `just lint` enforces this and the other markdownlint
  rules; skills and agents count their frontmatter `name:` as the title (MD041).
