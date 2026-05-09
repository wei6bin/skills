# skills — prd-pr dev-workflow plugin

Claude Code plugin marketplace hosting the **prd-pr** dev-workflow plugin.

| Plugin name | For | Agent format |
|---|---|---|
| `prd-pr` | Claude Code | `agents/*.md`, frontmatter uses `tools: Read, Edit, ...` |

The marketplace is defined in `.claude-plugin/marketplace.json` at the repo root.

---

## Prerequisites

Before installing the plugin, make sure your machine has:

1. **Azure CLI signed in to your ADO organisation** — required for ADO ticket lookups and task creation in the workflow.
   ```bash
   az login
   az account show          # verify the right tenant/subscription
   az devops configure --defaults organization=https://dev.azure.com/<your-org> project=<your-project>
   ```
2. **Git** — required by the `git-worktrees` and `raise-pr` skills. Confirm with `git --version`; ensure `user.name` and `user.email` are set (`git config --global --list`).

---

## Install in Claude Code

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
