---
name: test-plan-walkthrough
description: Playbook for the Phase 9 walkthrough — drives 05-test-plan.md's end-to-end manual demos through agent-browser, writes 06-walkthrough.md and screenshots/ into the user-story folder. Invoked by the test-plan-walker subagent.
allowed-tools: Read, Write, Edit, Bash, AskUserQuestion
---

# Test Plan Walkthrough

You are walking through the end-to-end manual demo of every slice using a real browser, then producing a structured report with screenshots that the PR description will reference.

**Announce at start:** "I'm using the test-plan-walkthrough skill to drive the e2e demos and capture screenshots."

---

## When this skill runs

- After **all slices in `04-task-plan.md` are demoable** (Phase 8 complete — every slice's e2e test passing, every checkpoint commit landed).
- **Before** `raise-pr`. The PR body depends on the artifacts this skill produces.

If you arrive here with unfinished slices, stop — go back and finish Phase 8 first.

---

## Inputs

| Input | Where |
|---|---|
| Manual demo steps | `docs/new-feature/{folder}/05-test-plan.md` → "End-to-End Test (manual demo per slice)" section |
| Slice list | `docs/new-feature/{folder}/04-task-plan.md` |
| Demo credentials / seed data | `docs/new-feature/{folder}/02-technical-plan.md` → "Dev/Demo Data Recovery" section, if present |
| App URL | Project `docker-compose.yml` / `README.md` / `02-technical-plan.md` |

If any of these are missing, ask the user before proceeding — do not guess.

---

## Output

Writes `06-walkthrough.md` and `screenshots/*.png` into the user-story folder. Screenshot naming: `slice-{NN}-{step-NN}-{short-kebab-name}.png` — `NN` two-digit, zero-padded. One screenshot per demo step.

---

## The Process

### Step 1 — Verify environment is up

```bash
# From repo root, confirm the stack is reachable
docker compose ps                # or whatever the project uses
curl -fsS http://localhost:{port}/health   # or equivalent
```

If the stack is down, bring it up per the project's standard command (e.g. `docker compose up -d`). If seed data is stale (e.g. demo passwords already rotated), follow the "Dev/Demo Data Recovery" steps from `02-technical-plan.md`. Do **not** invent credentials.

### Step 2 — Prepare agent-browser

The skill assumes `agent-browser` is on `PATH`. If not, fail fast with a clear message — do not silently shell out.

```bash
agent-browser --version || { echo "agent-browser missing — install it first"; exit 1; }
mkdir -p docs/new-feature/{folder}/screenshots
agent-browser --screenshot-dir docs/new-feature/{folder}/screenshots open {app-url}
```

For headed / live-stream debugging, the user can attach to the auto-started WebSocket stream — surface its port with `agent-browser stream status` and tell the user the URL only if they ask.

### Step 3 — Drive each slice's demo

For each row in the `05-test-plan.md` "Manual demo per slice" table, in slice order:

1. **Read the demo line.** Example from USR-018:
   > Slice 01: *"Sign in as Doctor → Checked-In appointment → save 1 drug → reload → restored"*

2. **Decompose into discrete steps.** Each `→` becomes one step. Each step gets one screenshot.

3. **For each step:**
   a. Perform the action via agent-browser commands. Prefer `snapshot -i` → use refs → re-snapshot after navigation.
   b. Take the screenshot **after the action lands**, not before:
      ```bash
      agent-browser screenshot slice-{NN}-{step-NN}-{name}.png
      ```
   c. Verify the expected state via DOM (`agent-browser get text @ref`) or URL (`agent-browser get url`). Record observed vs expected.
   d. If the step fails: stop driving this slice, record `❌` with the error, screenshot the failure state, move to the next slice. Do **not** retry silently.

4. **React Hook Form note.** If a form does not respond to `agent-browser fill`, follow the `frontend-implementer` skill's "Driving forms programmatically" section — RHF needs the native value-setter + `InputEvent`, not synthetic events. Pattern:
   ```bash
   agent-browser eval "(() => {
     const el = document.querySelector('input[name=\"{field}\"]');
     const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
     setter.call(el, '{value}');
     el.dispatchEvent(new InputEvent('input', { bubbles: true }));
   })()"
   ```
   Submit via `form.requestSubmit()` not synthetic button click.

5. **Nested-form gotcha.** Some pages have invalid nested `<form>` elements (the inner form's submit button submits the outer form as GET, serialising fields into the URL). If you observe this — query string filling with form fields — work around by calling the API directly via `fetch` from `agent-browser eval`, and record this as a known FE bug in `06-walkthrough.md`'s "Issues found during walkthrough" section. Do not silently skip.

### Step 4 — Write `06-walkthrough.md`

Use this template. Keep the body terse — one bullet per step.

```markdown
# {USR-NNN} — End-to-end Walkthrough

**Date:** {YYYY-MM-DD}
**Branch:** {feat/usr-NNN-…}
**Stack:** {commit hash from `git rev-parse --short HEAD`}
**Browser:** {output of `agent-browser --version`}
**Driver:** Copilot CLI + `test-plan-walkthrough` skill

> Demo steps mirror `05-test-plan.md` § "End-to-End Test (manual demo per slice)". One screenshot per step lives in `./screenshots/`.

## Pre-flight

- [x] Stack up: `docker compose ps` shows {N} containers healthy
- [x] Auth: signed in as `{role/email}`
- [x] Seed data: {note any recovery steps applied}

## Slice-by-slice results

### SLICE-01 — {demoable behaviour}

**Demo:** {verbatim from 05-test-plan.md}

| # | Step | Result | Screenshot |
|---|------|--------|------------|
| 1 | Sign in as Doctor | ✅ Redirected to `/doctor` | ![](screenshots/slice-01-01-login.png) |
| 2 | Open Checked-In appointment Q-001 | ✅ Visit page loaded for Chua Hui Ling | ![](screenshots/slice-01-02-visit.png) |
| 3 | Add Paracetamol 500 mg TID × 5 days | ✅ Row saved, qty auto = 15 | ![](screenshots/slice-01-03-rx-saved.png) |
| 4 | Reload page | ✅ Line item still present | ![](screenshots/slice-01-04-reload-restored.png) |

… repeat for every slice …

## Issues found during walkthrough

| Slice | Severity | Issue | Status |
|---|---|---|---|
| 01 | … | … | Open / Fixed in {commit} |

(Leave the section but write "None" if everything passed.)

## Summary

- Slices walked: {N}
- All AC demos passed: ✅ / ❌
- New bugs surfaced: {N} (see table above)
```

For each entry, paste the **verbatim** demo line from `05-test-plan.md` so the report is self-contained — a reviewer should not have to cross-reference the test plan to understand what was tested.

### Step 5 — Commit the artifacts

```bash
git add docs/new-feature/{folder}/06-walkthrough.md docs/new-feature/{folder}/screenshots/
git commit -m "docs({slug}): e2e walkthrough — screenshots + 06-walkthrough.md"
```

Single commit per walkthrough run. If a re-run replaces screenshots, amend or add a new commit — do not leave orphan files in the working tree.

## Red flags

- **Faking screenshots.** If a step's screenshot would be misleading (captured before the action landed, or showing a stale state), retake it.
- **Skipping a slice.** Every slice in `04-task-plan.md` must appear in `06-walkthrough.md`. Backend-only slices get an entry: *"BE only — no UI; verified via API smoke."*
- **Inventing demo steps.** Steps come verbatim from `05-test-plan.md`. If ambiguous, ask — do not improvise.
- **Headed-mode requirement that breaks in WSL/CI.** Prefer headless. If headed is required (print preview etc.), note the dependency in "Pre-flight".
- **Committing credentials.** Never paste passwords into `06-walkthrough.md`. Reference `02-technical-plan.md`'s seed-data section instead.
