# prd-pr subagents (Cursor)

Project-local copies of the **prd-pr** plugin agents, adapted for Cursor subagent routing.

## Why this folder exists

The marketplace plugin (`wei6bin-skills/prd-pr`) targets **Claude Code**:

- Dispatch: `agent_type: "prd-pr:code-explorer"`
- Models: `model: sonnet | opus | haiku` in plugin `agents/*.md`

**Cursor** uses:

- Dispatch: `Task(subagent_type="code-explorer", ...)`
- Models: frontmatter in **`.cursor/agents/*.md`** (`inherit` or picker IDs such as `composer-2.5-fast`)

Plugin `model: sonnet` is **not** applied automatically in Cursor.

## Model tiers (this repo)

| Agent | `model:` | Rationale |
|-------|----------|-----------|
| `code-explorer` | `composer-2` | Fast parallel exploration |
| `code-architect` | `claude-opus-4-7` | Strongest blueprint / slicing |
| `plan-reviewer` | `gpt-5.5` | Independent review pass |
| `impl-backend`, `impl-frontend` | `composer-2.5` | Implementation (standard tier) |
| `impl-simplify` | `composer-2.5-fast` | Cheap post-slice cleanup |
| `test-plan-walker` | `inherit` | Long browser run — matches parent |

Slugs must match **Cursor Settings → Models** on your account. Verify with
[SMOKE-TEST.md](./SMOKE-TEST.md).

**Task `model`:** Omit on spawn so frontmatter applies. Only pass Task `model` to override
one call (same slug as picker).

## Syncing from upstream plugin

Upstream playbooks (when refreshing content):

```text
~/.cursor/plugins/cache/wei6bin-skills/prd-pr/*/agents/*.md
```

After copying body text from upstream, **keep** Cursor frontmatter (`model: inherit` / `composer-2.5-fast`) — do not restore `sonnet` / `opus` / `haiku`.

## Skills (workflows)

Subagents call **skills** from the installed **prd-pr** plugin (not duplicated in this repo).

```text
~/.cursor/plugins/cache/wei6bin-skills/prd-pr/*/skills/{name}/SKILL.md
```

| Example | Skill |
|---------|--------|
| Parent runs full workflow | `orchestrator` |
| `impl-backend` | `backend-implementer`, `restful-api-design` |
| `test-plan-walker` | `test-plan-walkthrough` |
| After each slice (parent) | `context-updater` |

Plugin skills use Claude Code `agent_type: "prd-pr:…"` in places — **ignore that** in Cursor;
follow `.cursor/rules/prd-pr-cursor.mdc` (`Task` + `subagent_type`).

## Orchestrator

Phase 0–10 runs in the **parent** via the plugin `orchestrator` skill, not as a subagent here.

See also: `.cursor/rules/prd-pr-cursor.mdc`, `AGENTS.md`.
