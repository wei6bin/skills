---
name: test-plan-walkthrough
description: Playbook for the Phase 9 walkthrough — drives 05-test-plan.md's end-to-end manual demos through agent-browser, writes 06-walkthrough.md and screenshots/ into the user-story folder, and persists a Playwright e2e spec per slice into the project's existing e2e suite. Invoked by the test-plan-walker subagent.
allowed-tools: Read, Write, Edit, Bash, AskUserQuestion
---

# Test Plan Walkthrough

You are walking through the end-to-end manual demo of every slice using a real browser. From that **single** browser pass you produce **two** outputs: (1) a structured report with screenshots that the PR description references, and (2) a **persisted Playwright e2e spec per slice**, appended to the project's existing e2e suite so the story's actual use case becomes a permanent regression test — not a throwaway demo.

**Announce at start:** "I'm using the test-plan-walkthrough skill to drive the e2e demos, capture screenshots, and write persisted Playwright specs."

---

## When this skill runs

- After **all slices in `04-task-plan.md` are demoable** (Phase 8 complete — the consolidated refactor + regression round green over the whole diff, and the single consolidated checkpoint commit landed).
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

1. `06-walkthrough.md` and `screenshots/*.png` into the user-story folder. Screenshot naming: `slice-{NN}-{step-NN}-{short-kebab-name}.png` — `NN` two-digit, zero-padded. One screenshot per demo step.
2. One **Playwright spec per slice** appended to the project's **existing** e2e suite (whatever directory/naming/config the project already uses — you discover it in Step 0, you do not invent a location or scaffold a framework). These are production test files, committed with the story.

If the project has **no** existing Playwright/e2e suite (no config, no runner, no spec directory), you do **not** stand one up. Skip output #2, and record in `06-walkthrough.md`'s "Issues found" section: *"No Playwright e2e suite in this project — persisted specs skipped; recommend adding one."* Output #1 still ships.

---

## The Process

### Step 0 — Locate the project's existing e2e suite

Before driving anything, find where persisted specs must land — you append to the existing suite, never invent a parallel one.

```bash
# Playwright config + existing spec dir + run command
find . -maxdepth 3 \( -name 'playwright.config.*' -o -name '*.spec.ts' -o -name '*.spec.js' \) \
  -not -path '*/node_modules/*' 2>/dev/null | head -30
```

Determine, and record for later steps:
- **Spec directory & naming** (e.g. `e2e/`, `tests/e2e/`, `*.spec.ts`) — match it exactly.
- **The run command** (from `package.json` scripts, e.g. `npm run test:e2e`, or `npx playwright test`).
- **House style** — open one existing spec and copy its import paths, fixtures/auth helpers (e.g. a `loginAs()` fixture), `baseURL`, and locator conventions (`getByRole` / `getByTestId`). Your new specs must look like they were written by the same hand.

If none of this exists, note it (per **Output**) and skip spec authoring — do not scaffold Playwright, add dependencies, or write a config. Screenshots still proceed.

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
   d. **Capture the locator, not just the ref.** For every action and assertion, note the *stable* Playwright locator it maps to — accessible role + name (`getByRole('button', { name: 'Save' })`), label, or `data-testid` seen in the snapshot — and the concrete assertion (URL, visible text). agent-browser `@ref`s are ephemeral; you are collecting the durable selectors the spec will use. This is why you drive and author from one pass.
   e. If the step fails: stop driving this slice, record `❌` with the error, screenshot the failure state, move to the next slice. Do **not** retry silently — and do **not** write a spec for a slice whose demo did not pass.

4. **Author the slice's Playwright spec (only if the slice's demo passed end-to-end).** In the suite location and house style from Step 0, write one spec that reproduces the same steps you just drove — using the stable locators captured in 3d, the project's existing auth/login fixture (never inline credentials), and the project's `baseURL`. One `test()` per slice named after its demoable behaviour; assert the same expected states you verified in the browser. If `05-test-plan.md` lists `e2e`-type cases for the slice, cover their assertions too. Reuse `react-best-practices`' Playwright references (`playwright-generate-test`) for structure if helpful, but the spec must integrate with the *existing* suite, not stand alone.

5. **React Hook Form note.** If a form does not respond to `agent-browser fill`, follow the `frontend-implementer` skill's "Driving forms programmatically" section — RHF needs the native value-setter + `InputEvent`, not synthetic events. Pattern:
   ```bash
   agent-browser eval "(() => {
     const el = document.querySelector('input[name=\"{field}\"]');
     const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
     setter.call(el, '{value}');
     el.dispatchEvent(new InputEvent('input', { bubbles: true }));
   })()"
   ```
   Submit via `form.requestSubmit()` not synthetic button click.

6. **Nested-form gotcha.** Some pages have invalid nested `<form>` elements (the inner form's submit button submits the outer form as GET, serialising fields into the URL). If you observe this — query string filling with form fields — work around by calling the API directly via `fetch` from `agent-browser eval`, and record this as a known FE bug in `06-walkthrough.md`'s "Issues found during walkthrough" section. Do not silently skip.

### Step 4 — Run the persisted specs against the running stack

Run the specs you authored — through the project's own e2e command discovered in Step 0, headless, against the same stack you just drove:

```bash
npm run test:e2e -- {new spec paths}     # or: npx playwright test {paths}
```

Every new spec must pass. If one fails while its manual demo passed, the spec is wrong (flaky selector, timing, missing `await`/auto-wait) — **fix the spec, not the app**. If the spec fails because the *app* is actually broken, that's a real bug: record it in "Issues found" and set the slice `❌` (the spec stays but is expected-red until the fix). Never commit a green checkmark for a spec you did not actually run. Record each spec's pass/fail for the Return Report.

### Step 5 — Write `06-walkthrough.md`

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
**Persisted spec:** `{e2e/…/slice-01-….spec.ts}` — ✅ green / ❌ red / — none (BE-only or no e2e suite)

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
- Persisted Playwright specs added: {N} (all green: ✅ / ❌) — or "none: no e2e suite in project"
- New bugs surfaced: {N} (see table above)
```

For each entry, paste the **verbatim** demo line from `05-test-plan.md` so the report is self-contained — a reviewer should not have to cross-reference the test plan to understand what was tested.

### Step 6 — Commit the artifacts

Commit the walkthrough docs and the persisted specs together — one commit ties the evidence to the regression test it produced:

```bash
git add docs/new-feature/{folder}/06-walkthrough.md docs/new-feature/{folder}/screenshots/
git add {e2e spec dir}          # the new/appended *.spec.* files from Step 3.4
git commit -m "test({slug}): e2e walkthrough + persisted Playwright specs"
```

Single commit per walkthrough run. If a re-run replaces screenshots or specs, amend or add a new commit — do not leave orphan files in the working tree. If the project had no e2e suite, omit the second `git add` and use the message `docs({slug}): e2e walkthrough — screenshots + 06-walkthrough.md`.

## Red flags

- **Faking screenshots.** If a step's screenshot would be misleading (captured before the action landed, or showing a stale state), retake it.
- **Skipping a slice.** Every slice in `04-task-plan.md` must appear in `06-walkthrough.md`. Backend-only slices get an entry: *"BE only — no UI; verified via API smoke."*
- **Inventing demo steps.** Steps come verbatim from `05-test-plan.md`. If ambiguous, ask — do not improvise.
- **Headed-mode requirement that breaks in WSL/CI.** Prefer headless. If headed is required (print preview etc.), note the dependency in "Pre-flight".
- **Committing credentials.** Never paste passwords into `06-walkthrough.md` or a spec. Reference `02-technical-plan.md`'s seed-data section and use the project's login fixture instead.
- **Claiming a spec is green without running it.** A committed spec must have actually run and passed in Step 4. No exceptions.
- **Scaffolding a test framework.** If the project has no Playwright/e2e suite, you flag it and skip — you do not add Playwright, a config, dependencies, or a new `e2e/` tree. That's a decision for the team, not the walkthrough.
- **Parallel/duplicate suites.** Append to the existing suite in its own directory and style. Do not create a second e2e tree under `docs/new-feature/` or anywhere else.
