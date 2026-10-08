# skills - Claude Code plugin marketplace

Plugin marketplace hosting dev-workflow plugins and standalone utility skills.

| Plugin                   | For         | Description                                                                                     |
| ------------------------ | ----------- | ----------------------------------------------------------------------------------------------- |
| `jidoka`                 | Claude Code | 10-phase plan-then-build dev workflow                                                           |
| `jidoka-copilot`         | Copilot CLI | The same workflow, rendered for Copilot's agent and hook formats                                |
| `jidoka-cursor`          | Cursor      | The same workflow as a Cursor plugin, listed in `.cursor-plugin/marketplace.json`               |
| `utility-skills`         | Claude Code | Standalone user-invocable skills: `teach-me`, `learn-it`, `spec-me`, `html-it`, `my-work`       |
| `code-to-prd`            | Claude Code | Reverse-engineer a codebase into a complete PRD                                                 |
| `clinical-lecture-brief` | Claude Code | Turn a clinical/medical YouTube lecture into a published, audience-calibrated teaching artifact |

Two marketplace files sit at the repo root: `.claude-plugin/marketplace.json`
for Claude Code and Copilot CLI, and `.cursor-plugin/marketplace.json` for
Cursor (it lists `jidoka-cursor`).

The name `jidoka` comes from the Toyota Production System: automation that
stops the line and calls a human when something is off. The plugin does the
same, pausing at the clarifying-question and plan-review gates. `line` is its
entry-point skill: it runs one user story down the line to a PR.

Start it yourself: `/jidoka:line` followed by the story, acceptance criteria or
ticket in Claude Code, or `line` from the `/` menu in Copilot CLI and Cursor.
The skill sets `disable-model-invocation`, so it stays out of every session's
skill listing, and pasting a story without the command does not start it. The
companion skills are the reverse: `user-invocable: false` keeps them out of
Claude Code's `/` menu, but they stay visible to the model because the
orchestrator and the subagents invoke them.

---

## One source, three harnesses

The three `jidoka*` directories are build outputs. Everything is authored once
under `src/` and rendered by `make build`:

| Source                          | Rendered to                                                                                      |
| ------------------------------- | ------------------------------------------------------------------------------------------------ |
| `src/agents/<name>.md`          | `jidoka/agents/`, `jidoka-copilot/agents/*.agent.md`, `jidoka-cursor/agents/`                    |
| `src/skills/<skill>/`           | `jidoka/skills/`, `jidoka-copilot/skills/`, `jidoka-cursor/skills/` (dispatch strings rewritten) |
| `src/hooks/hooks.json` + `*.sh` | `jidoka/hooks/`, `jidoka-copilot/hooks/`, `jidoka-cursor/hooks/`                                 |

Each agent source carries one shared body and a frontmatter block per harness
(tool names, model ids, flags), so a change to an agent's instructions lands in
all three harnesses from one edit. Rendered files are never hand-edited: edit
the source, run `make build`, commit both. They carry no inline "generated"
marker, because every skill and agent file loads into the model's context when
it runs; `.gitattributes` marks them `linguist-generated` instead. `make check`
(also run in CI) fails when the committed outputs are stale. The renderer needs
Python 3 with PyYAML; `scripts/render.py` documents the source format.

## Model routing

Agents name a role, not a model. `src/models.yaml` maps roles to tiers and
tiers to a model per harness:

| Role           | Agents                                                       | Tier     | Claude Code | Copilot CLI (first the plan allows)  | Cursor            |
| -------------- | ------------------------------------------------------------ | -------- | ----------- | ------------------------------------ | ----------------- |
| reasoning      | code-architect                                               | frontier | `fable`     | `claude-opus-4.8`, `claude-sonnet-5` | `claude-opus-4-8` |
| verification   | plan-reviewer, code-reviewer, security-reviewer              | strong   | `opus`      | `claude-opus-4.8`, `claude-sonnet-5` | `gpt-5.5`         |
| implementation | impl-backend, impl-frontend, impl-simplify, test-plan-walker | standard | `sonnet`    | `claude-sonnet-5`                    | `composer-2.5`    |
| exploration    | code-explorer                                                | standard | `sonnet`    | `claude-sonnet-5`                    | `composer-2.5`    |

Two agents pin a harness: impl-simplify runs on the economy tier in Copilot
and Cursor, and security-reviewer stays on Claude Opus in Cursor. To change
the routing, edit `src/models.yaml` and run `make build`. To change it for one
machine without touching the plugin:

- Claude Code: `ANTHROPIC_DEFAULT_OPUS_MODEL` (or `SONNET`, `HAIKU`, `FABLE`)
  in `settings.json` `env` remaps a tier; `CLAUDE_CODE_SUBAGENT_MODEL` sets a
  default that frontmatter still beats; a same-named agent in
  `.claude/agents/` replaces the plugin's.
- Copilot CLI: `subagents.agents.<name>.model` in `~/.copilot/settings.json`
  or `.github/copilot/settings.json`. Copilot downgrades a subagent to the
  session model's price tier, so run the session on an Opus-tier model when
  you want verification on Opus.
- Cursor: copy the plugin's agents into `.cursor/agents/` and edit `model:`
  there (plugin subagents ignore the field today).

On Claude Code the `line` skill also overrides per dispatch in two cases:
refactor-tier stories review on `sonnet`, and an implementer re-dispatched
after a failed review or evidence check goes up to `opus`.

Test it with `make test` (renderer and routing rules), `make check` (render
drift), `make lint` (markdownlint over every Markdown file) and
`make smoke-claude` (one real dispatch per role on Claude Code, reporting the
model each ran on; costs a few API calls). `make eval-claude` is the end-to-end
verifier: in a container, `claude plugin eval` runs `/jidoka:line` on a minimal
story in a scaffolded repo and grades every phase's output (see
`jidoka/evals/README.md`; a whole workflow per run, so not in CI).

---

## Prerequisites

Before installing either plugin, make sure your machine has:

1. **Azure CLI signed in to your ADO organisation** - required for ADO ticket
   lookups and task creation in the workflow.

   ```bash
   az login
   az account show          # verify the right tenant/subscription
   az devops configure --defaults organization=https://dev.azure.com/<your-org> project=<your-project>
   ```

2. **Git** - required by the `git-worktrees` and `raise-pr` skills. Confirm with
   `git --version`; ensure `user.name` and `user.email` are set
   (`git config --global --list`).

---

## Install in Claude Code (`jidoka`)

Run inside a Claude Code session (slash commands):

```text
# 1. Register the marketplace (one-time)
/plugin marketplace add wei6bin/skills

# 2. Install the plugin
/plugin install jidoka@skills

# 3. Refresh discovery after edits (no restart needed)
/reload-plugins

# 4. Run one story down the line
/jidoka:line <user story, acceptance criteria or ticket>

# Browse / verify / manage
/plugin                                       # picker, "Installed" tab
/plugin marketplace list
/plugin disable   jidoka@skills
/plugin enable    jidoka@skills
/plugin uninstall jidoka@skills
```

Plugin contents land at `~/.claude/plugins/cache/skills/jidoka/`.

After editing the plugin source, refresh with `/reload-plugins`.

---

## Install in Copilot CLI (`jidoka-copilot`)

Run inside a Copilot CLI session:

```text
# 1. Register the marketplace (one-time)
/plugin marketplace add wei6bin/skills

# 2. Install the plugin
/plugin install jidoka-copilot@skills
```

The plugin carries the same `line` skill, companion skills and nine subagents
as `jidoka`, rendered into Copilot's `.agent.md` format with Copilot tool
aliases and model ids, plus the after-edit hooks as a Copilot `postToolUse`
hook set. Dispatch strings use the `jidoka-copilot:` prefix. The hooks expect
the plugin at `~/.copilot/installed-plugins/skills/jidoka-copilot/`, which is
where a marketplace install lands.

---

## Install utility skills (`utility-skills`)

```text
# 1. Register the marketplace (one-time)
/plugin marketplace add wei6bin/skills

# 2. Install the plugin
/plugin install utility-skills@skills

# 3. Reload
/reload-plugins
```

| Skill      | Invoke              | Description                                                                                             |
| ---------- | ------------------- | ------------------------------------------------------------------------------------------------------- |
| `teach-me` | `/teach-me`         | Deep-understanding teaching session for code or any technical topic                                     |
| `learn-it` | `/learn-it <task>`  | Runs a task in background, explains progress in plain language                                          |
| `spec-me`  | `/spec-me @file.md` | Interviews you to flesh out a spec, then rewrites the file                                              |
| `html-it`  | `/html-it`          | Generates a visual HTML implementation plan with mockups and code snippets                              |
| `my-work`  | `/my-work`          | Personal work tracker over an Obsidian vault: thread notes, a status ranking, and an HTML review report |

Adding a new skill: create `utility-skills/skills/<name>/SKILL.md` and add
`./skills/<name>` to the `skills` array in `.claude-plugin/marketplace.json`. A
skill may also bundle `scripts/` and `references/` alongside its `SKILL.md`;
reference them by skill-relative path.

---

## Install in Cursor (`jidoka-cursor`)

`jidoka-cursor` is a Cursor plugin rendered from the same source: skills and
agents already use Cursor's bare `subagent_type` and picker-slug models, the
hooks ship as `afterFileEdit` plugin hooks, and `rules/jidoka-cursor.mdc` is an
always-on rule with the per-phase dispatch table. Cursor discovers it through
`.cursor-plugin/marketplace.json` at the repo root:

1. **Customize → Plugins → Import from Repo**, paste
   `https://github.com/wei6bin/skills`, install `jidoka-cursor`, and turn on
   **Enable Auto Refresh** so pushes to `main` re-index within ten minutes.
2. Or add the repo as a **team marketplace** from the dashboard.
3. For local testing, symlink or copy `jidoka-cursor/` into
   `~/.cursor/plugins/local/`.

Do not also install the Claude Code `jidoka` plugin in Cursor: its skills carry
the same names and would collide.

**Known Cursor limitation.** Subagents loaded from a marketplace plugin run on
the parent model; Cursor ignores their `model:` frontmatter (forum reports
157485 and 168771). Project agents are honoured and take precedence, so to pin
models copy the plugin's agents into the project and re-copy after updates:

```bash
cp ~/.cursor/plugins/cache/*/jidoka-cursor/*/agents/*.md .cursor/agents/
```

See `jidoka-cursor/README.md` for the model tier table and
`jidoka-cursor/SMOKE-TEST.md` to verify the routing.

---

## License

[MIT](LICENSE).
