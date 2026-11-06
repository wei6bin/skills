# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## What this repo is

A Claude Code **plugin marketplace** (defined in
`.claude-plugin/marketplace.json`) hosting:

- The **jidoka** dev-workflow family, authored once under `src/` and rendered
  into three harness variants (see "One source, three renders" below):
  - `jidoka/` - the Claude Code plugin: agents, skills, hooks.
  - `jidoka-copilot/` - the Copilot CLI plugin: the same agents as
    `agents/*.agent.md` with Copilot tool aliases, dotted model ids and
    `user-invocable: false`, the same skills with every `jidoka:` prefix
    rewritten to `jidoka-copilot:`, and the hooks as a Copilot `postToolUse`
    set.
  - `jidoka-cursor/` - the Cursor plugin, listed in the repo-root
    `.cursor-plugin/marketplace.json` (Cursor's own marketplace file; Cursor
    does not use the Claude one). Rendered: `agents/<agent>.md` with Cursor
    picker-slug `model:` frontmatter and a derived `readonly:` flag, `skills/`
    with `agent_type: "jidoka:x"` rewritten to `subagent_type: "x"` and skill
    ids to bare names, and `hooks/` (Cursor `afterFileEdit` hooks.json plus
    scripts). Hand-written: `.cursor-plugin/plugin.json`,
    `rules/jidoka-cursor.mdc` (always-applied rule with the per-phase dispatch
    table, model guidance and worktree discipline), `README.md` and
    `SMOKE-TEST.md`.
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

## One source, three renders

`src/` is the only place the jidoka family is edited. `just build` runs
`scripts/render.py` (Python 3 with PyYAML) and rewrites every rendered path
listed below; `just check` fails when the committed outputs are stale and is
what CI runs (`.github/workflows/render-check.yml`).

- `src/agents/<name>.md` - one agent: a shared body plus frontmatter with
  `name`, `description`, `tools` (Claude tool names) and a `role`, which
  `src/models.yaml` resolves to a model per harness (see "Model routing"). An
  optional `model:` map pins one or more harnesses when an agent must deviate
  from its role; say why in a comment. Optional `claude:`, `copilot:` and
  `cursor:` blocks add harness-only frontmatter keys (`effort`, which beats the
  role's, `omitClaudeMd`, `is_background`) or override `description` and
  `tools`. Text only some harnesses get goes in a harness section of the body:
  a line `<!-- harness: claude -->` (or `copilot cursor`) opens it, the next
  marker or `<!-- harness: end -->` closes it, and the renderer drops the
  sections that do not name the harness (format in `scripts/render.py`). Today
  only `impl-simplify` has them, because on Claude Code it wraps the built-in
  `simplify` skill while Copilot and Cursor get the simplification rules. A
  section may also name `worker`, the pseudo-harness of the worker render
  below; `impl-simplify`'s generic sections do, since a Codex worker has no
  built-in `simplify`. One file per agent; the renderer rejects a
  `<name>.<harness>.md`.
- `src/skills/<skill>/` - copied into all three plugins. Dispatch strings are
  written as `agent_type: "jidoka:<agent>"`; the Copilot copy gets the prefix
  rewritten and the Cursor copy gets `subagent_type` plus bare skill ids, so
  skill prose stays harness-neutral (`line` opens with a legend that says so).
  A bundled script (a non-Markdown file starting `#!`) gets the hooks' one-line
  GENERATED comment; other files are copied byte for byte.
- The worker render: every agent is also written, identical in all three
  plugins, to `<plugin>/skills/herdr-crew/agents/<name>.md` for herdr mode (see
  "Architecture"): the shared body plus the `worker` sections, no prefix
  rewrite, under a flat frontmatter (`role`, `tools`, `claude-model`,
  `claude-effort`, `copilot-model`) that `crew.sh` reads. A worker without the
  jidoka plugin (Codex, a bare Copilot session) reads it as its instructions.
  `src/skills/herdr-crew/agents/` must not exist; the renderer refuses it.
- `src/hooks/hooks.json` - the canonical `afterFileEdit` script list, rendered
  to Claude's `PostToolUse` (matcher `Edit|Write|MultiEdit`,
  `${CLAUDE_PLUGIN_ROOT}`), Copilot's `postToolUse` (matcher `edit|create`,
  scripts addressed at
  `$HOME/.copilot/installed-plugins/skills/jidoka-copilot/hooks` because Copilot
  documents no plugin-root variable) and Cursor's plugin `afterFileEdit`
  (`bash "${CURSOR_PLUGIN_ROOT}/hooks/<script>"`, the pattern Cursor's own
  plugins use). `src/hooks/*.sh` are copied to all three.
- The `agents` and `skills` arrays of the `jidoka` and `jidoka-copilot` entries
  in `marketplace.json` are rendered too: adding a file under `src/agents/` or
  `src/skills/` registers it on the next build.

Rendered paths are generated and never hand-edited:
`jidoka/{agents,skills,hooks}/`, all of `jidoka-copilot/`,
`jidoka-cursor/{agents,skills,hooks}/`, and the two marketplace arrays. To
change one, edit its source under `src/`, run `just build` and commit both. The
rendered Markdown carries no inline marker on purpose: every skill, skill
reference and agent file loads into the model's context when it runs, so the
header comment it used to carry cost tokens on every load in every harness. This
rule is the marker instead, backed by `.gitattributes`, which marks the same
directories `linguist-generated` (GitHub collapses them in a diff) and which
`just test` checks against the renderer. Hook and skill scripts are executed,
never loaded into context, so each keeps a one-line comment under its shebang
naming its source. `jidoka/evals/` is hand-written: `claude plugin eval` is
Claude Code only, so the suite has no Copilot or Cursor render.

Harness facts the renderer relies on (verified against the harness docs on
2026-10-01): Copilot CLI reads `.claude-plugin/marketplace.json`, accepts
Claude tool names case-insensitively and ignores unknown ones, loads custom
agents only from its own locations (not `.claude/agents/`), and has hooks.
Cursor reads `.claude/agents/` and `.claude/skills/` directly and installs
plugins from a repo's `.cursor-plugin/marketplace.json`, but a marketplace
plugin's subagents ignore `model:` (open bug), so the Cursor README documents
copying the agents into `.cursor/agents/` to pin models.

## Model routing

Models are not written into agent files. Each agent names a `role`, and
`src/models.yaml` holds two tables: `roles` (role to tier, plus Claude's
`effort`) and `tiers` (tier to model per harness). Today reasoning is
`frontier` (code-architect), verification is `strong` (plan-reviewer,
code-reviewer, security-reviewer, project-scaffolder), and implementation and
exploration are `standard`. Three layers, in order of how often they change:

1. **Source** - edit `src/models.yaml` to move a role between tiers or change a
   tier's model, then `just build`. Pin a single agent with its `model:` map
   only when it must deviate (impl-simplify runs cheaper on Copilot and Cursor;
   security-reviewer stays on Claude Opus in Cursor).
2. **Run time, Claude Code only** - `line` passes `model` on a Task call for two
   exceptions: refactor-tier stories review on `sonnet`, and an implementer
   re-dispatched after `FIXES_NEEDED` or a failed evidence check goes up to
   `opus`. Claude's Task `model` beats frontmatter; Copilot and Cursor have no
   usable per-dispatch override.
3. **Environment, no plugin edit** - Claude renders aliases (`fable`, `opus`,
   `sonnet`, `haiku`), so `ANTHROPIC_DEFAULT_<TIER>_MODEL` in a settings file's
   `env` remaps a whole tier, `CLAUDE_CODE_SUBAGENT_MODEL` sets a default that
   frontmatter still beats, and a same-named agent in `.claude/agents/` beats
   the plugin's. Copilot renders `models` (a priority list) with
   `modelPolicy: preferred`, so `subagents.agents.<name>.model` in
   `~/.copilot/settings.json` or `.github/copilot/settings.json` overrides; its
   cost-multiplier guard downgrades a subagent to the session model's price
   tier, so verification on Opus needs the session on Opus. Cursor ignores
   `model:` on plugin subagents; project copies in `.cursor/agents/` are the
   override and the only routing there.

## Testing

The task runner is [just](https://just.systems): `just` alone lists the recipes
and the knobs they take, and a knob goes between `just` and the recipe
(`just HOST=1 eval-claude`).

- `just test` - unit tests for the renderer (`scripts/test_render.py`): role
  resolution per harness, pins and `claude.effort` precedence, error cases,
  the Copilot and Cursor rewrites, no inline marker in rendered Markdown,
  `.gitattributes` covering exactly the rendered paths, and determinism on the
  real tree. CI runs it together with `just check` and `just lint`.
- `just check` - the committed renders match `src/`. `claude plugin validate .`
  checks the marketplace loads.
- `just lint` - markdownlint-cli2 (version pinned in the `justfile`, needs Node)
  over every Markdown file, rendered ones included, per
  `.markdownlint-cli2.jsonc`. The rendered files are linted because the Copilot
  render turns every `jidoka:` into `jidoka-copilot:`, 8 characters longer, so a
  source line holding a dispatch string needs that much slack under 80.
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
  `just HOST=1 eval-claude` runs on the host instead). Two cases.
  `line-minimal-story` scaffolds a zero-dependency Node API as a git repo,
  types `/jidoka:line` with a two-AC backend story, and grades the dispatch
  order plus the end state (plan docs, ledger, merged code and tests, backlog
  closed, worktree gone).
  `line-greenfield-scaffold` starts from an empty repo, asks for a new project,
  and grades the new-project branch: `project-setup` invoked, the
  `project-scaffolder` agent dispatched, a .NET + React skeleton and project
  context merged into `main`, and no story phase run. One run is a whole
  workflow, up to an hour and several dollars, so it is not in CI; run it
  before merging a change to the `line` flow (`just eval-claude --case <name>`
  runs one).
  The container needs a credential in `~/.config/jidoka/eval.env`
  (`CLAUDE_CODE_OAUTH_TOKEN` from `claude setup-token`, or
  `ANTHROPIC_API_KEY`). Harness facts it relies on: the case's
  `plugins: ["../.."]` is what loads `jidoka/` without a manifest;
  `AskUserQuestion` is not offered headless, so the case's
  `append_system_prompt` stands in for the developer; a Bash-granting eval
  refuses to start while the host's Docker credential store holds a symlink
  (Docker Desktop's "User" CLI install mode links its tools there), which is
  why the container is the default; and the eval's bubblewrap sandbox only
  starts in a container run with `seccomp=unconfined` and
  `systempaths=unconfined`. A run's Bash also has no network beyond the
  domains the operator grants (`--allow-tools "WebFetch(domain:...)"`; a case
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
- Copilot and Cursor have no scripted test here. Copilot: install the plugin
  from a local path, run the session on an Opus-tier model, dispatch an agent
  and check the model in the session log. Cursor: copy the agents into
  `.cursor/agents/` and run `jidoka-cursor/SMOKE-TEST.md`.

## Architecture

The jidoka plugins implement one 10-phase orchestrator-driven flow (discovery →
exploration → clarifying questions → architecture → plan docs → review → summary
→ slice-by-slice implementation → test-plan walkthrough with screenshots → PR).
The full phase → subagent/skill → artifact map, drawn as an inline SVG flow, is
in `docs/orchestrator-workflow.html` - open it in a browser.

Three component types:

- **Skills** (`src/skills/<name>/SKILL.md`, one file per skill) - `line` is the
  entry point; the rest are companions it invokes (`vertical-slicing`,
  `git-worktrees`, `raise-pr`, `backend-implementer`, `frontend-implementer`,
  `sweep-implementer`, `reuse-ladder`, `codebase-context-builder`,
  `context-updater`, `react-best-practices`, `frontend-styling-standard`,
  `restful-api-design`, `test-plan-walkthrough`, `project-setup`,
  `aspnet-backend-scaffold`, `react-frontend-scaffold`, `herdr-crew`). `check`
  is the second entry point, the self-check (see "Herdr mode" below). In a
  folder with no
  source code, or on a request for a new project, `line` invokes
  `project-setup` before Phase 2. It holds the **stack catalog** (one row per
  stack, today a .NET backend and a React frontend, each naming its scaffold
  skill), asks the user which to set up, freezes a skeleton contract and
  dispatches the `project-scaffolder` agent with the chosen rows. The split is
  deliberate: only the main session can ask the user, and the build's trail
  (two implementers' reports, every gate, the smoke, the context write-up)
  stays in the agent's context instead of the orchestrator's. The agent
  dispatches `impl-backend` and `impl-frontend` with scope `project scaffold`,
  checks their work, smokes the halves together, builds the project context
  and lands the skeleton on the base branch; `project-setup` then checks the
  result cheaply. Adding a stack is a catalog row plus a scaffold skill;
  nothing else names a stack. The two scaffold skills began as standalone
  skills and keep their feature-slice guidance, but the line loads only their
  bootstrap. Skills run in the main session; `context-updater` in
  particular must never be dispatched as a subagent and runs once per story
  from the orchestrator (the old Copilot variant had the implementers invoke it;
  that divergence was retired with the single source). `line` and `check` set
  `disable-model-invocation: true` (honoured by all three harnesses): their
  descriptions stay out of every session's skill listing, and they run only
  when the user types `/jidoka:line` or `/jidoka:check`. The companions must
  not set it. The flag also
  blocks the Skill tool and subagent `skills:` preloading, and that is how the
  orchestrator and the agents reach them. Instead they set
  `user-invocable: false`, which drops them from the `/` menu on Claude Code
  but leaves them in the model's listing. Copilot CLI documents that field for
  agents only and Cursor not at all, so there they may still show in the menu.
  `just test` enforces all of this.
- **Agents** (`src/agents/`) - subagents the orchestrator dispatches via the
  task tool with `agent_type: "jidoka:<name>"` (`jidoka-copilot:<name>` in the
  Copilot render, bare `subagent_type` on Cursor): `code-explorer`,
  `code-architect`, `plan-reviewer`, `impl-backend`, `impl-frontend`,
  `impl-simplify`, `code-reviewer`, `security-reviewer`, `test-plan-walker`,
  `project-scaffolder`. `project-scaffolder` dispatches the two implementers
  itself, which Claude Code supports; the Copilot and Cursor renders carry a
  fallback that builds the halves in the agent when nesting is refused, not
  yet exercised on either.
  `impl-simplify` on Claude Code owns no rules of its own - it is a thin context
  boundary that invokes the built-in `simplify` skill in an isolated window; the
  Copilot and Cursor renders carry the rules in the shared body. On every
  harness it then applies the house conventions (`react-best-practices`,
  `restful-api-design`) to the whole-story diff without changing behaviour. The
  implementers deliberately do not load those skills, so their context goes to
  the ACs. `code-architect` also loads `restful-api-design`, because the
  API-surface rules (paths, status codes, error envelope) belong in the frozen
  contract, which nothing downstream may change.
- **Hooks** (`src/hooks/`) - after-file-edit on all three harnesses: secrets
  scan, prettier, biome, TypeScript typecheck, plus a sourced `_lib.sh` (not
  itself a hook). `hook_init` in `_lib.sh` detects the harness from the payload
  shape and extracts the edited file's path; `emit_context` replies in that
  harness's format (Claude `hookSpecificOutput.additionalContext`, Copilot
  top-level `additionalContext`, nothing on Cursor, whose `afterFileEdit` has no
  context channel, so only Prettier's on-disk effect lands there). The Copilot
  and Cursor paths are rendered from the docs and not yet exercised end to end;
  the Copilot `toolArgs` file-path field in particular is a guess (`path`,
  `file_path`, `filePath`). The scripts self-gate (exit silently when the edited
  file doesn't apply) so they're safe in a generic plugin, and the ts-typecheck
  hook deliberately reports only the edited file's diagnostics and treats
  workspace sibling-import errors as non-blocking advisories - preserve those
  properties when editing them. Three further properties are load-bearing:
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

## Registrations and versioning

- The jidoka plugins' `agents` and `skills` arrays in
  `.claude-plugin/marketplace.json` are rendered from `src/`. For
  `utility-skills`, new skills go in `utility-skills/skills/<name>/SKILL.md` and
  the path `./skills/<name>` must be added to its `skills` array by hand -
  adding a file alone does not register it.
- **Plugins carry no version, on purpose.** Claude Code and Cursor key a
  plugin's version off the marketplace's commit SHA when neither a
  `<plugin>/.claude-plugin/plugin.json` nor the plugin's `marketplace.json`
  entry sets a `version`, so every merge to `main` is a new version and
  auto-update ships it on the next session start with nothing to bump. Do not
  add a Claude manifest or a `version` field anywhere: a `version` switches the
  plugin to explicit versioning and updates stop until someone remembers to
  bump it. `jidoka-cursor/.cursor-plugin/plugin.json` exists because Cursor
  needs a manifest, and sets no `version` for the same reason. Do not add a root
  `<plugin>/plugin.json` with an Agent Plugins `$schema` either: Copilot CLI
  and Cursor would switch to that loading mode (shared `skills/` plus
  `com.github.copilot/` and `com.anysphere.cursor/` namespaces), which this
  repo has not adopted. `metadata.version` in `marketplace.json` is
  informational - bump it when a plugin is added or removed.

## Conventions

- Commit messages are prefixed with what they touch: `jidoka: ...` for anything
  under `src/` or the rendered plugins, `jidoka-cursor: ...` for the
  hand-written adapter files, `utility-skills: ...`, `code-to-prd: ...`,
  `clinical-lecture-brief: ...`, or `marketplace: ...` for the marketplace,
  renderer, justfile and CI.
- Skill/agent prose is written as direct instructions to the executing agent
  ("You are...", numbered phases where order matters, explicit announce lines
  and return-report formats) - match that style, and keep it harness-neutral:
  harness-specific syntax belongs in the renderer or in a `<harness>` block.
- `utility-skills` skills are user-invocable: their description must clearly
  state trigger phrases and argument requirements; no `[Internal subagent...]`
  prefix.
- Markdown prose wraps at 80 columns (MD013); tables, code blocks, headings and
  frontmatter are exempt. A command or string too long to wrap goes in a fenced
  block, not inline code. `just lint` enforces this and the other markdownlint
  rules; skills and agents count their frontmatter `name:` as the title (MD041).
