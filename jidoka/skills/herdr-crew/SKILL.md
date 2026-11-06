---
name: herdr-crew
description: Runs the line's subagents as workers in a herdr crew tab instead of through the task tool, with the orchestrator as herdr agent `lead`, when the session runs inside herdr. Invoked by `line` when HERDR_ENV is 1.
user-invocable: false
---

# Herdr Crew

You are the **lead**. Inside herdr you run each subagent as a **worker** in a
`jidoka crew` tab instead of through the task tool: same agent, same brief, and
you can answer a worker without re-dispatching it.

`crew.sh` below is `scripts/crew.sh` in this skill's folder; call it by its
absolute path.
On Claude Code that is `${CLAUDE_SKILL_DIR}/scripts/crew.sh`.
For anything it does not cover, use the `herdr` skill or `herdr --skill`.

## 1. Decide the mode

Run `crew.sh mode`.

- `task: {reason}`: announce "Herdr mode off: {reason}." and dispatch through
  the task tool as the line says. Stop reading this skill.
- `herdr`: run `crew.sh up`, then announce "Herdr mode: workers run in the
  `jidoka crew` tab; I am herdr agent `lead`."

## 2. Dispatch

Wherever the line, or a skill it invokes (`project-setup`, `raise-pr`), says to
dispatch an agent, run instead:

```bash
crew.sh dispatch code-explorer <<'BRIEF'
{exactly the prompt the task call would have carried}
BRIEF
```

The agent is the dispatch string's name, with or without its plugin prefix.
Where the line passes `model` on a task call, pass `--model {alias}` (Claude
workers only). The reply is `{name} dispatched slot {N} ({color}) {harness}
{mode}`; keep the name.

**A parallel batch is one dispatch per worker, then one wait for all of them.**

## 3. Wait

Run `crew.sh wait {name} [{name} ...]` with the tool's longest timeout. It
returns within 9 minutes, one line per worker:

- `ready`: run `crew.sh report {name}` and treat the text exactly as a Return
  Report from the task tool, evidence checks included.
- `working`: run the same wait again at once. Never end your turn while a
  worker is working.
- `blocked slot {N}`: a prompt waits in that worker's pane. Tell the user which
  worker and slot, then wait again. Do not answer it unless the user says to;
  `crew.sh peek {name}` shows it.
- `quiet`: no report and a still screen for two minutes. `crew.sh peek
  {name}`: answer a question with `send` (step 4), or `send` asking for the
  missing report.
- `exited`: try `crew.sh report {name}`; with no report, release it and
  dispatch again.

`blocked-at-start` from dispatch is the same, before the brief: wait sends the
brief once the user answers the prompt.

## 4. Talk to a worker

A worker whose report is a question, or that needs a short correction, stays
live. Answer it, then wait and report again:

```bash
crew.sh send {name} <<'MSG'
{your answer}
MSG
```

A re-dispatch the line calls for (after `FIXES_NEEDED` or a failed evidence
check, with its `model` step up) is a new worker: release the old one first.

## 5. Release and take down

- `crew.sh release {name}` once you accept its report.
- `crew.sh status` lists every crew pane and worker.
- After Phase 10, or when the run stops for good, `crew.sh down`. Keep the
  crew up while the run waits on the user, who may want to read a worker.

## If herdr fails

When `up`, `dispatch` or `send` fails, quote its error, run that dispatch
through the task tool and say so. Herdr mode never blocks the line.

## Where workers run

`~/.config/jidoka/herdr.conf` and `/jidoka:check` set each agent's harness
and yolo mode; `report` returns the report whatever ran the worker.
