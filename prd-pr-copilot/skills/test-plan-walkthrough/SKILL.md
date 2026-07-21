---
name: test-plan-walkthrough
description: Playbook for the Phase 9 walkthrough — drives 05-test-plan.md's end-to-end manual demos through agent-browser, writes 06-walkthrough.md and screenshots/ into the user-story folder, and persists a Playwright e2e spec per slice into the project's existing e2e suite. Invoked by the test-plan-walker subagent.
allowed-tools: Read, Write, Edit, Bash, AskUserQuestion
---

# Test Plan Walkthrough

You are turning every slice's end-to-end demo into a **persisted Playwright spec that produces its own screenshots**, then running those specs headless. From that you produce **two** outputs: (1) the **persisted Playwright e2e spec per slice**, appended to the project's existing e2e suite so the story's use case becomes a permanent regression test — not a throwaway demo; and (2) a structured report referencing the screenshots the specs captured, which the PR description embeds.

**This skill is spec-first, not browse-first.** You do **not** hand-drive every micro-step of every slice through an LLM-controlled browser — that is what made this phase take ~an hour per pass, one slow model-in-the-loop round-trip per click. Instead you *write the spec* from `05-test-plan.md`'s concrete demo steps, put a `page.screenshot()` at each demoable checkpoint, and let Playwright do the driving headless — fast, deterministic, and re-runnable in seconds. LLM-driven browsing (`agent-browser`) is a **fallback only**, used to recover a locator when a spec fails to find an element — never the primary driver.

**Announce at start:** "I'm using the test-plan-walkthrough skill spec-first — writing Playwright specs that self-capture screenshots and running them headless."

---

## When this skill runs

- After **all slices in `04-task-plan.md` are implemented and the story is integrated** (Phase 8 complete — the consolidated round green over the whole diff: whole-story integration, refactor, regression, and the single consolidated checkpoint commit landed). Individual slices were built against contract mocks and are not demoed one-by-one; this phase is the story's first and only end-to-end demo, against the real, integrated stack.
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

1. One **Playwright spec per slice** appended to the project's **existing** e2e suite (whatever directory/naming/config the project already uses — you discover it in Step 0, you do not invent a location or scaffold a framework). These are production test files, committed with the story. Each spec captures its own screenshots via `page.screenshot()` at every demoable checkpoint.
2. `06-walkthrough.md` and `screenshots/*.png` into the user-story folder. The screenshots are **produced by the specs**, written to `docs/new-feature/{folder}/screenshots/` (point each `page.screenshot({ path })` there). Naming: `slice-{NN}-{step-NN}-{short-kebab-name}.png` — `NN` two-digit, zero-padded. One screenshot per demoable checkpoint (a `→` in the demo line that lands on a visible state), not per trivial keystroke.

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

### Step 2 — Author the per-slice specs (spec-first, self-screenshotting)

You write specs from the concrete demo steps — you do **not** drive the browser by hand to produce them. `mkdir -p docs/new-feature/{folder}/screenshots` for the screenshots the specs will write.

For each row in the `05-test-plan.md` "Manual demo per slice" table (plus that slice's `e2e`-type cases), in slice order:

1. **Read the demo line and decompose it into checkpoints.** Each `→` that lands on a visible state is one checkpoint (one screenshot + one assertion). Trivial keystrokes are not checkpoints. Example from USR-018:
   > Slice 01: *"Sign in as Doctor → Checked-In appointment → save 1 drug → reload → restored"* → checkpoints: after login, after opening the appointment, after save, after reload.

2. **Write one spec/`test()` per slice**, in the suite location and house style from Step 0:
   - Use the project's existing **auth/login fixture** (never inline credentials) and its `baseURL`.
   - Build locators from the **concrete roles/labels/expected text in `05-test-plan.md`** — `getByRole('button', { name: 'Save' })`, `getByLabel(...)`, `getByTestId(...)`. Phase 5 requires those steps be written concretely enough to translate without guessing. If a step is too vague to locate, that is a test-plan gap — ask the user, don't improvise a selector.
   - **Screenshot at each checkpoint**, after the action lands and the assertion passes:
     ```ts
     await expect(page.getByText('Paracetamol')).toBeVisible();
     await page.screenshot({ path: 'docs/new-feature/{folder}/screenshots/slice-01-03-rx-saved.png' });
     ```
   - Name the `test()` after the slice's demoable behaviour; assert the same expected states `05-test-plan.md` lists (URL, visible text, row present). Cover the slice's `e2e`-type case assertions too.
   - Reuse `react-best-practices`' Playwright references (`playwright-generate-test`) for structure — but integrate with the *existing* suite, do not stand up a parallel one.

3. **Only if you cannot author a locator blind** (a flow so dynamic you genuinely can't tell what an element's accessible name is), take **one** `agent-browser snapshot` of that single page to read the real locator, then encode it into the spec. This is a targeted locator lookup, not a manual walkthrough — verification still happens via the headless run in Step 3, not by hand. (`agent-browser --version` must succeed for this fallback; if it's absent and you hit a case that needs it, say so rather than guessing.)

**Driving forms in the spec.** Playwright's `fill()` / `getByRole().click()` trigger native events, so React Hook Form usually just works — unlike synthetic-event drivers. If an RHF field still won't update, set it via the native value-setter inside `page.evaluate`, dispatch `new InputEvent('input', { bubbles: true })`, and submit with `form.requestSubmit()` (see the `frontend-implementer` skill's "Driving forms programmatically").

**Nested-form gotcha.** Some pages have invalid nested `<form>` elements (the inner submit posts the outer form as GET, serialising fields into the URL). If a spec surfaces this — query string filling with form fields — record it as a known FE bug in `06-walkthrough.md`'s "Issues found" section and assert around it via a direct `request` call; do not silently skip.

### Step 3 — Run the specs headless and triage

Run the specs through the project's own e2e command from Step 0, headless, against the running stack:

```bash
npm run test:e2e -- {new spec paths}     # or: npx playwright test {paths}
```

A green spec **is** the verification and produces its screenshots as a side effect — there is no separate manual pass. Triage every failure:

- **Spec bug** (flaky/wrong selector, missing `await`/auto-wait, timing) — **fix the spec, not the app.** To recover a correct locator, take one `agent-browser snapshot` of the failing page. Re-run.
- **App bug** (the app is genuinely broken) — that's a real finding: record it in "Issues found", set the slice `❌`, and leave the spec in place (expected-red until the fix). Do **not** patch app code from here — report it so the orchestrator re-dispatches the implementer.

Never commit a green checkmark for a spec you did not actually run. Record each spec's pass/fail for the Return Report.

### Step 3c — Re-runs after a fix (changed-surface only)

When the orchestrator re-dispatches you after an implementer fix, re-run **only the affected slices' specs** — regenerating only their screenshots and amending only their rows in `06-walkthrough.md`. Do **not** re-author or re-run specs for slices that already passed: re-running a green spec is seconds and unnecessary, re-walking a whole story is the hour-long cost this skill exists to avoid. Independent slices' specs can also run in parallel (`playwright test` shards them) when the suite supports it.

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

### SLICE-01 — {behaviour}

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
git add {e2e spec dir}          # the new/appended *.spec.* files from Step 2
git commit -m "test({slug}): e2e walkthrough + persisted Playwright specs"
```

Single commit per walkthrough run. If a re-run replaces screenshots or specs, amend or add a new commit — do not leave orphan files in the working tree. If the project had no e2e suite, omit the second `git add` and use the message `docs({slug}): e2e walkthrough — screenshots + 06-walkthrough.md`.

## Red flags

- **Faking screenshots.** If a step's screenshot would be misleading (captured before the action landed, or showing a stale state), retake it.
- **Skipping a slice.** Every slice in `04-task-plan.md` must appear in `06-walkthrough.md`. Backend-only slices get an entry: *"BE only — no UI; verified via API smoke."*
- **Inventing demo steps.** Steps come verbatim from `05-test-plan.md`. If ambiguous, ask — do not improvise.
- **Headed-mode requirement that breaks in WSL/CI.** Prefer headless. If headed is required (print preview etc.), note the dependency in "Pre-flight".
- **Committing credentials.** Never paste passwords into `06-walkthrough.md` or a spec. Reference `02-technical-plan.md`'s seed-data section and use the project's login fixture instead.
- **Claiming a spec is green without running it.** A committed spec must have actually run and passed in Step 3. No exceptions.
- **Scaffolding a test framework.** If the project has no Playwright/e2e suite, you flag it and skip — you do not add Playwright, a config, dependencies, or a new `e2e/` tree. That's a decision for the team, not the walkthrough.
- **Parallel/duplicate suites.** Append to the existing suite in its own directory and style. Do not create a second e2e tree under `docs/new-feature/` or anywhere else.
</content>
</invoke>
