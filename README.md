# skills — prd-pr dev-workflow plugins

Plugin marketplace hosting two variants of the **prd-pr** dev-workflow plugin, plus a Cursor adapter.

| Variant | For | Agent format |
|---|---|---|
| `prd-pr` | Claude Code | `agents/*.md`, frontmatter uses `tools: Read, Edit, ...` |
| `prd-pr-copilot` | Copilot CLI | `agents/*.agent.md`, frontmatter uses `tools: ['read', 'edit', ...]` |
| `prd-pr-cursor` | Cursor | Not a marketplace plugin — a project-local `.cursor/` adapter (see below) |

Both run the same 10-phase orchestrator-driven flow — discovery → codebase exploration → clarifying questions → architecture → plan docs → review → summary → slice-by-slice implementation → end-to-end test-plan walkthrough with screenshots → PR.

The marketplace is defined in `.claude-plugin/marketplace.json` at the repo root.

---

## Prerequisites

Before installing either plugin, make sure your machine has:

1. **Azure CLI signed in to your ADO organisation** — required for ADO ticket lookups and task creation in the workflow.
   ```bash
   az login
   az account show          # verify the right tenant/subscription
   az devops configure --defaults organization=https://dev.azure.com/<your-org> project=<your-project>
   ```
2. **Git** — required by the `git-worktrees` and `raise-pr` skills. Confirm with `git --version`; ensure `user.name` and `user.email` are set (`git config --global --list`).

---

## Install in Claude Code (`prd-pr`)

Run inside a Claude Code session (slash commands):

```text
# 1. Register the marketplace (one-time)
/plugin marketplace add wei6bin/skills

# 2. Install the plugin
/plugin install prd-pr@skills

# 3. Refresh discovery after edits (no restart needed)
/reload-plugins

# Browse / verify / manage
/plugin                                       # picker, "Installed" tab
/plugin marketplace list
/plugin disable   prd-pr@skills
/plugin enable    prd-pr@skills
/plugin uninstall prd-pr@skills
```

Plugin contents land at `~/.claude/plugins/cache/skills/prd-pr/`.

After editing the plugin source, refresh with `/reload-plugins`.

---

## Install in Copilot CLI (`prd-pr-copilot`)

Run inside a Copilot CLI session:

```text
# 1. Register the marketplace (one-time)
/plugin marketplace add wei6bin/skills

# 2. Install the plugin
/plugin install prd-pr-copilot@skills
```

The orchestrator skill is the entry point — kick off a feature with a user story or ADO ticket URL and it will drive the 10-phase flow, dispatching the `.agent.md` subagents as needed.

---

## Use in Cursor (`prd-pr-cursor`)

Cursor cannot consume the agents from the marketplace plugin directly — it dispatches with `Task(subagent_type="...")` (no `prd-pr:` prefix) and reads `model:` frontmatter only from project-local `.cursor/agents/*.md` (picker slugs like `composer-2.5`, not `sonnet`/`opus` shorthands). `prd-pr-cursor/` is therefore an **adapter to copy into the target repo**, not a marketplace plugin:

```bash
# from the target repo root
cp -R <this-repo>/prd-pr-cursor/agents <this-repo>/prd-pr-cursor/rules .cursor/
```

- `agents/` — project-local copies of the seven prd-pr subagents with Cursor model tiers (see `agents/README.md` for the tier table and `agents/SMOKE-TEST.md` to verify models resolve).
- `rules/prd-pr-cursor.mdc` — an `alwaysApply` rule that maps the plugin's `agent_type: "prd-pr:…"` dispatch syntax to Cursor's `subagent_type`, pins per-phase routing, and points skills at the installed `wei6bin-skills/prd-pr` plugin cache.

Skills still come from the marketplace plugin (`~/.cursor/plugins/cache/wei6bin-skills/prd-pr/`); only agents and the rule live in the project. When the plugin's agent playbooks change, re-copy the body from `prd-pr/agents/*.md` and keep the Cursor `model:` frontmatter.
