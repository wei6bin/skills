# jidoka Cursor — model smoke test

Verify that the jidoka subagents run on the intended models, not the parent
chat model. Cursor currently ignores `model:` on subagents loaded from a
marketplace plugin, so the models are pinned by copying the plugin's
`agents/*.md` into the project's `.cursor/agents/` (see README).

## Expected mapping (this repo)

| `subagent_type`     | Frontmatter `model:` | UI name (approx.)              |
| ------------------- | -------------------- | ------------------------------ |
| `code-explorer`     | `composer-2.5`       | Composer 2.5                   |
| `code-architect`    | `claude-opus-4-8`    | Claude 4.8 Opus                |
| `plan-reviewer`     | `gpt-5.5`            | GPT-5.5                        |
| `impl-backend`      | `composer-2.5`       | Composer 2.5                   |
| `impl-frontend`     | `composer-2.5`       | Composer 2.5                   |
| `impl-simplify`     | `composer-2.5-fast`  | Composer 2.5 Fast (cheap pass) |
| `code-reviewer`     | `gpt-5.5`            | GPT-5.5                        |
| `security-reviewer` | `claude-opus-4-8`    | Claude 4.8 Opus                |
| `test-plan-walker`  | `composer-2.5`       | Composer 2.5                   |

**Prerequisite:** In **Cursor Settings → Models**, enable every model above.
Opus 4.8 and GPT-5.5 may require **Max Mode** on your plan. If a model is
blocked, Cursor substitutes another model silently — the smoke test will look
“green” but wrong.

Confirm slugs match your picker (copy ID from Settings). If a slug fails, try
the variant shown in the UI (e.g. `gpt-5.5-fast`, `claude-opus-4-8-fast`).

---

## Step 0 — Static check (no LLM)

From repo root:

```bash
grep -H '^model:' .cursor/agents/*.md
```

Expect the table above. Until Cursor honours `model:` on plugin subagents, the
project copies must exist (the plugin cache alone is not enough):

```bash
ls .cursor/agents/code-explorer.md
```

---

## Step 1 — Parent chat setup

1. Open the repository you are testing with in Cursor. The smoke prompt below
   lists files under `backend/src`, so pick a repo that has one.
2. Start a **new** Agent chat.
3. Pick a **parent** model that is **different** from subagents (e.g. **Composer
   2.5 Fast** or anything except Opus-only), so a subagent that silently falls
   back to the parent model is distinguishable.
4. Ensure the **jidoka-cursor** plugin is enabled; do **not** use
   `agent_type: "jidoka:…"` in prompts.

---

## Step 2 — Paste smoke prompt (parent)

Paste this into the parent agent (one message). It spawns four subagents in
parallel with **readonly** scope — no repo writes.

```markdown
Run a jidoka **model routing smoke test**. Do not change any files.

For each row, spawn **one** Task with `subagent_type` and **omit** Task `model` (use
`.cursor/agents` frontmatter only). Use `readonly: true`. Same repo: the open workspace's root.

| subagent_type   | Task description (use as `description`) | Prompt (abbrev) |
|-----------------|----------------------------------------|-----------------|
| code-explorer   | smoke model code-explorer              | Reply with one line: `SMOKE code-explorer ok` then list 3 files under `backend/src` (paths only). |
| code-architect  | smoke model code-architect             | Reply with one line: `SMOKE code-architect ok` then one sentence: what is NGEMR Lite? (from CLAUDE.md). |
| plan-reviewer   | smoke model plan-reviewer              | Reply with one line: `SMOKE plan-reviewer ok` only. |
| impl-backend    | smoke model impl-backend               | Reply with one line: `SMOKE impl-backend ok` only. |

After all return, summarize in a table: subagent_type | completed | first line of output.

Do **not** pass `model:` on Task — we are testing frontmatter routing.
```

---

## Step 3 — What to verify in the UI

For **each** subagent run in the Cursor UI (subagent panel / trace):

| Check                              | Pass                                                           |
| ---------------------------------- | -------------------------------------------------------------- |
| Agent name matches `subagent_type` | e.g. `code-explorer`, not `explore`                            |
| Model badge / label                | Matches **Expected mapping** (Composer 2.5, Opus 4.8, GPT-5.5) |
| Output contains `SMOKE … ok`       | Subagent actually ran                                          |
| Parent did not implement inline    | Parent only dispatched Task                                    |

If the UI does not show model names, use **Step 4** (transcript) or **Step 5**
(override).

---

## Step 4 — Transcript check (optional)

After the smoke chat, inspect the latest parent transcript under:

`~/.cursor/projects/<workspace-slug>/agent-transcripts/<uuid>/`

The slug is the workspace's path, lowercased, with `/` as `-`: `/home/you/repo/app`
becomes `home-you-repo-app`.

- Parent `Task` tool inputs should have `"model": null` or no `model` key.
- Subagent folders under `subagents/` should exist for each spawn.

Transcripts often **do not** record the resolved runtime model — treat UI +
override test as authoritative.

---

## Step 5 — Override test (frontmatter vs Task)

Pick **one** subagent (e.g. `plan-reviewer`). Run two Tasks:

1. Omit `model` → should use `gpt-5.5` from frontmatter.
2. Pass `model: "composer-2.5-fast"` on Task → should run faster/cheaper if
   override works.

Compare UI model badge between runs. If both look identical, Task override may
be ignored on your plan — rely on frontmatter only.

---

## Step 6 — Negative checks

| Anti-pattern                                  | Expected                                          |
| --------------------------------------------- | ------------------------------------------------- |
| `Task(subagent_type="explore", model="fast")` | Do **not** use for jidoka phases                  |
| `Task(..., model: "opus")`                    | Invalid slug (failed in usr-031 session)          |
| Plugin-only agents, no `.cursor/agents/`      | Parent model (Cursor ignores plugin `model:`)     |

---

## Step 7 — Full jidoka path (optional)

After model smoke passes:

1. Parent: type `/line` with a tiny story (or dry-run Phase 2 only). The
   skill sets `disable-model-invocation`, so the agent never starts it on its
   own.
2. Confirm Phase 2 uses `subagent_type: code-explorer` (×2–3), Phase 4
   `code-architect`, Phase 6 `plan-reviewer` (×2).
3. Do **not** run Phase 8 until model routing is confirmed — implementation is
   expensive.

---

## Troubleshooting

| Symptom                            | Likely cause                                                                  |
| ---------------------------------- | ----------------------------------------------------------------------------- |
| All subagents same as parent       | Frontmatter ignored; check `.cursor/agents/` exists; restart Cursor           |
| Opus/GPT subagent runs as Composer | Max Mode off or model not on plan; slug typo                                  |
| `Task model: opus` rejected        | Use `claude-opus-4-8`, not `opus`                                             |
| Subagent uses `explore`            | Wrong `subagent_type`; follow `jidoka-cursor.mdc`                             |
| Two `line` skills                  | Plugin + duplicate project skill — we removed `.cursor/skills/` to avoid this |

To change a model, edit the `cursor:` entry under `model:` in the skills repo's
`src/agents/<agent>.md`, rebuild, re-copy into `.cursor/agents/`, then re-run
Step 0 and Step 2.
