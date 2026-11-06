# skills - Claude Code plugin marketplace

Plugin marketplace hosting dev-workflow plugins and standalone utility skills.

| Plugin                   | For         | Description                                                                                     |
| ------------------------ | ----------- | ----------------------------------------------------------------------------------------------- |
| `jidoka`                 | Claude Code | 10-phase plan-then-build dev workflow                                                           |
| `utility-skills`         | Claude Code | Standalone user-invocable skills: `teach-me`, `learn-it`, `spec-me`, `html-it`, `my-work`       |
| `code-to-prd`            | Claude Code | Reverse-engineer a codebase into a complete PRD                                                 |
| `clinical-lecture-brief` | Claude Code | Turn a clinical/medical YouTube lecture into a published, audience-calibrated teaching artifact |

The marketplace is `.claude-plugin/marketplace.json` at the repo root.

The name `jidoka` comes from the Toyota Production System: automation that
stops the line and calls a human when something is off. The plugin does the
same, pausing at the clarifying-question and plan-review gates. `line` is its
entry-point skill: it runs one user story down the line to a PR.

Start it yourself: `/jidoka:line` followed by the story, acceptance criteria or
ticket. The skill sets `disable-model-invocation`, so it stays out of every session's
skill listing, and pasting a story without the command does not start it. The
companion skills are the reverse: `user-invocable: false` keeps them out of
Claude Code's `/` menu, but they stay visible to the model because the
orchestrator and the subagents invoke them.

## Herdr mode

Run the line inside [herdr](https://herdr.dev), a terminal multiplexer for
coding agents, and its subagents become visible workers in a `jidoka crew` tab
beside yours, each in its own column with its own tint and emoji label. Watch
any worker and approve its prompts in its pane; the lead (your session, renamed
`lead`) can answer a worker's question without re-dispatching it. Outside
herdr nothing changes.

`/jidoka:check` shows whether herdr mode would engage and which harness each
agent would run on, and offers to change it. The routing lives in
`~/.config/jidoka/herdr.conf`:

```ini
harness = lead                      # default: the lead's own harness, or claude, copilot, codex, ...
role.verification = codex           # per role: reasoning, verification, implementation, exploration
agent.code-reviewer = copilot       # per agent, beats the role
yolo.copilot = on                   # no approval prompts for those workers (copilot --yolo)
args.codex = "-m gpt-5.5"           # extra flags for that harness's workers
enabled = false                     # never use herdr mode
tint = off                          # emoji labels only; light suits a light terminal theme
```

Claude Code workers run the jidoka agent with its model and tool limits; other
harnesses (Copilot, Codex, ...) read the agent's instructions instead. An
approval prompt waits in the worker's pane and herdr notifies you;
`yolo.<harness> = on` skips prompts. Needs herdr 0.9.5 or later and `jq`;
`nc` with `-U` evens out the columns.

---

## One source, two renders

`jidoka/agents/`, `jidoka/skills/` and `jidoka/hooks/` are build outputs.
Everything is authored once under `src/` and rendered by `just build`:

| Source                          | Rendered to                                                       |
| ------------------------------- | ----------------------------------------------------------------- |
| `src/agents/<name>.md`          | `jidoka/agents/`, and the worker render in `herdr-crew/agents/`   |
| `src/skills/<skill>/`           | `jidoka/skills/`                                                  |
| `src/hooks/hooks.json` + `*.sh` | `jidoka/hooks/`                                                   |

Each agent source carries one body and a frontmatter that names a role, not a
model. The renderer writes it twice: as the plugin's agent, and as the worker
render a herdr worker on another harness reads as its instructions. Rendered
files are never hand-edited: edit the source, run `just build`, commit both.
They carry no inline "generated" marker, because every skill and agent file
loads into the model's context when it runs; `.gitattributes` marks them
`linguist-generated` instead. `just check` (also run in CI) fails when the
committed outputs are stale. The renderer needs Python 3 with PyYAML;
`scripts/render.py` documents the source format.

## Model routing

Agents name a role, not a model. `src/models.yaml` maps roles to tiers and
tiers to a Claude Code alias, plus the model a herdr worker on Copilot CLI runs
on:

| Role           | Agents                                                       | Tier     | Claude Code | Copilot worker (herdr) |
| -------------- | ------------------------------------------------------------ | -------- | ----------- | ---------------------- |
| reasoning      | code-architect                                               | frontier | `fable`     | `claude-opus-4.8`      |
| verification   | plan-reviewer, code-reviewer, security-reviewer              | strong   | `opus`      | `claude-opus-4.8`      |
| implementation | impl-backend, impl-frontend, impl-simplify, test-plan-walker | standard | `sonnet`    | `claude-sonnet-5`      |
| exploration    | code-explorer                                                | standard | `sonnet`    | `claude-sonnet-5`      |

impl-simplify pins its Copilot worker to `claude-haiku-4.5`. To change the
routing, edit `src/models.yaml` and run `just build`. To change it for one
machine without touching the plugin: `ANTHROPIC_DEFAULT_OPUS_MODEL` (or
`SONNET`, `HAIKU`, `FABLE`) in `settings.json` `env` remaps a tier;
`CLAUDE_CODE_SUBAGENT_MODEL` sets a default that frontmatter still beats; a
same-named agent in `.claude/agents/` replaces the plugin's.

The `line` skill also overrides per dispatch in two cases:
refactor-tier stories review on `sonnet`, and an implementer re-dispatched
after a failed review or evidence check goes up to `opus`.

The recipes run through [just](https://just.systems); `just` alone lists them
and their knobs. Test it with `just test` (renderer and routing rules),
`just check` (render drift), `just lint` (markdownlint over every Markdown
file) and `just smoke-claude` (one real dispatch per role on Claude Code,
reporting the model each ran on; costs a few API calls). `just eval-claude` is
the end-to-end verifier: in a container, `claude plugin eval` runs
`/jidoka:line` on a minimal story in a scaffolded repo and grades every phase's
output (see `jidoka/evals/README.md`; a whole workflow per run, so not in CI).

---

## Prerequisites

Before installing `jidoka`, make sure your machine has:

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

## License

[MIT](LICENSE).
