# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A Claude Code **plugin marketplace** (defined in `.claude-plugin/marketplace.json`) hosting:

- `prd-pr/` — dev-workflow plugin for Claude Code. Agents are `agents/*.md`; frontmatter uses `tools: Read, Edit, ...` (comma-separated names), `model: sonnet`, and descriptions prefixed with `[Internal subagent of workshop-dev-workflow — do not invoke directly]`.
- `prd-pr-copilot/` — dev-workflow plugin for Copilot CLI. Agents are `agents/*.agent.md`; frontmatter uses `tools: ['read', 'edit', ...]` (YAML list, lowercase), full model ids like `model: claude-sonnet-4.5`, and `user-invocable: false` instead of the description prefix.
- `prd-pr-cursor/` — for Cursor. **Not a marketplace plugin** (no plugin.json, no skills, not in marketplace.json): it's a project-local `.cursor/` adapter to copy into target repos — `agents/` (the seven subagents with Cursor picker-slug `model:` frontmatter, e.g. `composer-2.5`, plus `readonly:` flags) and `rules/prd-pr-cursor.mdc` (always-applied rule mapping `agent_type: "prd-pr:…"` to Cursor's bare `subagent_type`). Skills are consumed from the installed `prd-pr` plugin, so agent body changes in `prd-pr/agents/` should be re-copied here while keeping the Cursor frontmatter.
- `utility-skills/` — standalone user-invocable skills with no agents or hooks. Each skill is a `skills/<name>/SKILL.md` file, optionally with bundled `scripts/` and `references/` beside it (as `my-work` has). Skills may declare required `args:` in frontmatter (YAML list with `name`, `description`, `required`). Current skills: `teach-me`, `learn-it`, `spec-me`, `html-it`, `my-work`.

There is no build, lint, or test tooling — everything is markdown plus a few bash hook scripts. The "test" is installing the plugin and exercising it: `/plugin marketplace add wei6bin/skills`, `/plugin install prd-pr@skills`, then `/reload-plugins` after edits (no restart needed). Installed contents land at `~/.claude/plugins/cache/skills/<plugin-name>/`.

## Architecture

Both plugins implement the same 10-phase orchestrator-driven flow (discovery → exploration → clarifying questions → architecture → plan docs → review → summary → slice-by-slice implementation → test-plan walkthrough with screenshots → PR). The full phase → subagent/skill → artifact map, including a mermaid diagram, is in `docs/orchestrator-workflow.md` (Copilot variant: `prd-pr-copilot/docs/orchestrator-workflow.md`).

Three component types per plugin:

- **Skills** (`skills/<name>/SKILL.md`, one file per skill) — `orchestrator` is the entry point; the rest are companions it invokes (`vertical-slicing`, `git-worktrees`, `raise-pr`, `backend-implementer`, `frontend-implementer`, `codebase-context-builder`, `context-updater`, `react-best-practices`, `frontend-styling-standard` (prd-pr only), `restful-api-design`, `test-plan-walkthrough`). Skills run in the main session; `context-updater` in particular must never be dispatched as a subagent.
- **Agents** (`agents/`) — subagents the orchestrator dispatches via the task tool with `agent_type: "prd-pr:<name>"` (or `prd-pr-copilot:<name>`): `code-explorer`, `code-architect`, `plan-reviewer`, `impl-backend`, `impl-frontend`, `impl-simplify`, `code-reviewer`, `security-reviewer`, `test-plan-walker`. In `prd-pr`, `impl-simplify` owns no rules of its own — it is a thin context boundary that invokes Claude Code's built-in `simplify` skill in an isolated window; the Copilot and Cursor variants still carry the full rules in their own copies.
- **Hooks** (`prd-pr/hooks/` only — Copilot CLI has no hooks) — PostToolUse on Edit/Write/MultiEdit: secrets scan, prettier, eslint, TypeScript typecheck. The scripts self-gate (exit silently when the edited file doesn't apply) so they're safe in a generic plugin, and the ts-typecheck hook deliberately reports only the edited file's diagnostics and treats workspace sibling-import errors as non-blocking advisories — preserve those properties when editing them.

## Keeping registrations and versions in sync

- Every agent and skill must be listed in **both** its plugin's entry in `.claude-plugin/marketplace.json` (the `agents`/`skills` arrays) — adding a file alone does not register it.
- For `utility-skills`, new skills go in `utility-skills/skills/<name>/SKILL.md` and the path `./skills/<name>` must be added to its `skills` array in `marketplace.json`.
- Bump the relevant `plugin.json` version on plugin changes, and `metadata.version` in `marketplace.json` on marketplace-level changes.

## The two variants are siblings, not mirrors

Changes are usually ported between `prd-pr` and `prd-pr-copilot`, but the content has intentionally diverged beyond the frontmatter format: the Copilot variant has no hooks, no ADO task automation, no per-slice API smoke gate, and its implementer agents invoke `context-updater` themselves. When porting a change, diff the corresponding files first and translate (agent dispatch strings, tool names, model ids) rather than copy.

## Conventions

- Commit messages are prefixed with the plugin they touch: `prd-pr: ...`, `prd-pr-copilot: ...`, or `utility-skills: ...`.
- Skill/agent prose is written as direct instructions to the executing agent ("You are...", numbered phases, explicit announce lines and return-report formats) — match that style.
- `utility-skills` skills are user-invocable: their description must clearly state trigger phrases and argument requirements; no `[Internal subagent...]` prefix.
