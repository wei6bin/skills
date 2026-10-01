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

`src/` is the only place the jidoka family is edited. `make build` runs
`scripts/render.py` (Python 3 with PyYAML) and rewrites every rendered path
listed below; `make check` fails when the committed outputs are stale and is
what CI runs (`.github/workflows/render-check.yml`). Rendered files carry a
`GENERATED` header comment: never hand-edit them, edit the source, re-render and
commit both.

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
  `simplify` skill while Copilot and Cursor get the simplification rules.
  There is one file per agent; the renderer rejects a `<name>.<harness>.md`.
- `src/skills/<skill>/` - copied into all three plugins. Dispatch strings are
  written as `agent_type: "jidoka:<agent>"`; the Copilot copy gets the prefix
  rewritten and the Cursor copy gets `subagent_type` plus bare skill ids, so
  skill prose stays harness-neutral (`line` opens with a legend that says so).
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

Rendered paths: `jidoka/{agents,skills,hooks}/`, all of `jidoka-copilot/`,
`jidoka-cursor/{agents,skills,hooks}/`, and the two marketplace arrays.

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
code-reviewer, security-reviewer), and implementation and exploration are
`standard`. Three layers, in order of how often they change:

1. **Source** - edit `src/models.yaml` to move a role between tiers or change a
   tier's model, then `make build`. Pin a single agent with its `model:` map
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

- `make test` - unit tests for the renderer (`scripts/test_render.py`): role
  resolution per harness, pins and `claude.effort` precedence, error cases,
  the Copilot and Cursor rewrites, and determinism on the real tree. CI runs
  it together with `make check` and `make lint`.
- `make check` - the committed renders match `src/`. `claude plugin validate .`
  checks the marketplace loads.
- `make lint` - markdownlint-cli2 (version pinned in the `Makefile`, needs Node)
  over every Markdown file, rendered ones included, per
  `.markdownlint-cli2.jsonc`. The rendered files are linted because the Copilot
  render turns every `jidoka:` into `jidoka-copilot:`, 8 characters longer, so a
  source line holding a dispatch string needs that much slack under 80.
- `make smoke-claude` - end to end on Claude Code: loads `jidoka/` through
  `--plugin-dir` (from a temp copy carrying a throwaway manifest), dispatches
  one agent per role with a trivial prompt, then reads the session's subagent
  transcripts under `~/.claude/projects/` to report the model each actually
  ran on against the alias in its frontmatter. Costs a few short API calls, so
  it is not in CI. `ARGS=--override` also exercises the Task `model` parameter.
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
  `sweep-implementer`, `reuse-ladder`, `codebase-context-builder`, `context-updater`,
  `react-best-practices`, `frontend-styling-standard`, `restful-api-design`,
  `test-plan-walkthrough`). Skills run in the main session; `context-updater` in
  particular must never be dispatched as a subagent and runs once per story
  from the orchestrator (the old Copilot variant had the implementers invoke it;
  that divergence was retired with the single source). `line` sets
  `disable-model-invocation: true` (honoured by all three harnesses): its
  description stays out of every session's skill listing, and it runs only when
  the user types `/jidoka:line`. The companions must not set it. The flag also
  blocks the Skill tool and subagent `skills:` preloading, and that is how the
  orchestrator and the agents reach them. Instead they set
  `user-invocable: false`, which drops them from the `/` menu on Claude Code
  but leaves them in the model's listing. Copilot CLI documents that field for
  agents only and Cursor not at all, so there they may still show in the menu.
  `make test` enforces all of this.
- **Agents** (`src/agents/`) - subagents the orchestrator dispatches via the
  task tool with `agent_type: "jidoka:<name>"` (`jidoka-copilot:<name>` in the
  Copilot render, bare `subagent_type` on Cursor): `code-explorer`,
  `code-architect`, `plan-reviewer`, `impl-backend`, `impl-frontend`,
  `impl-simplify`, `code-reviewer`, `security-reviewer`, `test-plan-walker`.
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
  renderer, Makefile and CI.
- Skill/agent prose is written as direct instructions to the executing agent
  ("You are...", numbered phases where order matters, explicit announce lines
  and return-report formats) - match that style, and keep it harness-neutral:
  harness-specific syntax belongs in the renderer or in a `<harness>` block.
- `utility-skills` skills are user-invocable: their description must clearly
  state trigger phrases and argument requirements; no `[Internal subagent...]`
  prefix.
- Markdown prose wraps at 80 columns (MD013); tables, code blocks, headings and
  frontmatter are exempt. A command or string too long to wrap goes in a fenced
  block, not inline code. `make lint` enforces this and the other markdownlint
  rules; skills and agents count their frontmatter `name:` as the title (MD041).
