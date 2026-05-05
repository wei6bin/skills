# Agentic Coding Workshop — prd-pr workflow plugins

This repository hosts a Claude Code / Copilot CLI plugin marketplace with two variants of the same dev-workflow plugin:

| Plugin name | For | Agent format |
|---|---|---|
| `prd-pr-copilot` | Copilot CLI  | `agents/*.agent.md`, frontmatter uses `tools: ['read', 'edit', ...]` |
| `prd-pr-claude`  | Claude Code  | `agents/*.md` (no `.agent.` suffix), frontmatter uses `tools: Read, Edit, ...` |

Both tools read the same `.claude-plugin/marketplace.json` at the repo root. Skills are shared — `prd-pr-claude/skills` is a symlink to `prd-pr-copilot/skills`, so editing a skill once updates both variants.

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

## Copilot CLI

Run inside a Copilot CLI session (slash commands):

```text
# 1. Register the marketplace (one-time)
/plugin marketplace add wei6bin/agentic-coding-workshop

# 2. Install the Copilot variant
/plugin install prd-pr-copilot@agentic-coding-workshop

# 3. Verify
/plugin list

# After upstream changes, refresh the installed copy
/plugin update prd-pr-copilot@agentic-coding-workshop

# Uninstall later
/plugin uninstall prd-pr-copilot@agentic-coding-workshop
/plugin marketplace remove agentic-coding-workshop
```

Plugin contents land at `~/.copilot/installed-plugins/agentic-coding-workshop/prd-pr-copilot/`.

---

## Claude Code

Run inside a Claude Code session (slash commands):

```text
# 1. Register the marketplace (one-time)
/plugin marketplace add wei6bin/agentic-coding-workshop

# 2. Install the Claude Code variant (note the `-claude` suffix)
/plugin install prd-pr-claude@agentic-coding-workshop

# 3. Refresh discovery after edits (no restart needed)
/reload-plugins

# Browse / verify / manage
/plugin                                                              # picker, "Installed" tab
/plugin marketplace list
/plugin disable   prd-pr-claude@agentic-coding-workshop
/plugin enable    prd-pr-claude@agentic-coding-workshop
/plugin uninstall prd-pr-claude@agentic-coding-workshop
```

Plugin contents land at `~/.claude/plugins/cache/agentic-coding-workshop/prd-pr-claude/`.

---

## Side-by-side

| Step | Copilot CLI (slash) | Claude Code (slash) |
|---|---|---|
| Add marketplace | `/plugin marketplace add wei6bin/agentic-coding-workshop` | `/plugin marketplace add wei6bin/agentic-coding-workshop` |
| Install plugin | `/plugin install prd-pr-copilot@agentic-coding-workshop` | `/plugin install prd-pr-claude@agentic-coding-workshop` |
| Refresh after edit | `/plugin update prd-pr-copilot@agentic-coding-workshop` | `/reload-plugins` |
| List installed | `/plugin list` | `/plugin` → Installed tab |
| Install location | `~/.copilot/installed-plugins/agentic-coding-workshop/prd-pr-copilot/` | `~/.claude/plugins/cache/agentic-coding-workshop/prd-pr-claude/` |
| Uninstall | `/plugin uninstall prd-pr-copilot@agentic-coding-workshop` | `/plugin uninstall prd-pr-claude@agentic-coding-workshop` |

Both tools **copy** on install (not symlink). After editing the plugin source, refresh on each side: `/plugin update ...` for Copilot, `/reload-plugins` for Claude Code.
