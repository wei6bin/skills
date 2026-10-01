# jidoka-cursor

The Cursor render of the **jidoka** dev-workflow plugin: the `line` skill and
its companions, nine subagents, an always-on rule and the after-edit hooks,
generated from `src/` in this repo by `make build`. `README.md`,
`SMOKE-TEST.md`, `.cursor-plugin/plugin.json` and `rules/jidoka-cursor.mdc` are
hand-written; everything else here is rendered and carries a `GENERATED`
header.

## Install

Cursor reads this repo's `.cursor-plugin/marketplace.json`:

1. **Customize → Plugins → Import from Repo**, paste
   `https://github.com/wei6bin/skills`, install `jidoka-cursor`, and turn on
   **Enable Auto Refresh** so pushes to `main` re-index within ten minutes.
2. Or add the repo as a **team marketplace** from the dashboard and install
   from there.
3. For local development, symlink or copy this directory into
   `~/.cursor/plugins/local/` (an admin must allow local imports on
   Enterprise).

Installed copies land under
`~/.cursor/plugins/cache/<marketplace>/jidoka-cursor/<commit>/`. The plugin
sets no `version` on purpose: Cursor keys the version off the marketplace
commit, so every merge is a new version with nothing to bump.

Do not also install the Claude Code `jidoka` plugin in Cursor: its skills carry
the same names and would collide with this plugin's.

## What the render changes for Cursor

- Agents: Cursor frontmatter (`model:` picker slug, `readonly:` derived from
  the tool list; no `tools:` key).
- Skills and agents: `agent_type: "jidoka:x"` becomes `subagent_type: "x"` and
  skill ids become bare names, so nothing needs translating at run time.
- Hooks: `hooks/hooks.json` registers the four scripts as `afterFileEdit`
  hooks via `${CURSOR_PLUGIN_ROOT}`. They self-gate, so they stay silent in
  projects without the tool. Cursor gives this event no reply channel, so only
  Prettier's on-disk formatting is visible; the other three run but cannot
  report back.

## Model tiers

| Agent                           | `model:`            | Rationale                                  |
| ------------------------------- | ------------------- | ------------------------------------------ |
| `code-explorer`                 | `composer-2.5`      | Fast parallel exploration                  |
| `code-architect`                | `claude-opus-4-8`   | Strongest blueprint / slicing              |
| `plan-reviewer`                 | `gpt-5.5`           | Independent review pass                    |
| `impl-backend`, `impl-frontend` | `composer-2.5`      | Implementation (standard tier)             |
| `impl-simplify`                 | `composer-2.5-fast` | Cheap whole-story cleanup                  |
| `code-reviewer`                 | `gpt-5.5`           | Independent review of the whole-story diff |
| `security-reviewer`             | `claude-opus-4-8`   | Adversarial review of the whole-story diff |
| `test-plan-walker`              | `composer-2.5`      | Spec-first Playwright run                  |

Slugs must match **Cursor Settings → Models** on your account; verify with
[SMOKE-TEST.md](./SMOKE-TEST.md). They come from the `cursor` column of
`src/models.yaml` through each agent's role (reasoning is the frontier tier,
verification strong, implementation and exploration standard); impl-simplify
and security-reviewer pin their slugs in their source files. Change the table
or a pin and re-render.

**Known Cursor limitation.** Subagents loaded from a marketplace plugin run on
the parent model; Cursor ignores their `model:` (forum reports 157485 and
168771, still open as of September 2026). Project agents are honoured and take
precedence, so to pin models copy the plugin's agents into the project and
re-copy after updates:

```bash
cp ~/.cursor/plugins/cache/*/jidoka-cursor/*/agents/*.md .cursor/agents/
```

**Task `model`:** Omit on spawn so frontmatter applies. Only pass Task `model`
to override one call (same slug as picker).

## Orchestrator

Phase 0-10 runs in the **parent** via the `line` skill, not as a subagent.
Start it with `/line` and the story; it sets `disable-model-invocation`, so the
agent does not pick it up from a pasted story on its own. See
`rules/jidoka-cursor.mdc` for the dispatch table and the worktree rule.
