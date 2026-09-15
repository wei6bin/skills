---
name: test-plan-walkthrough
description: Playbook for the Phase 9 walkthrough - turns each slice's end-to-end demo in 05-test-plan.md into a Playwright spec that self-captures screenshots, runs the specs headless, writes 06-walkthrough.md and screenshots/ into the user-story folder, and persists the specs into the project's existing e2e suite. Invoked by the test-plan-walker subagent.
allowed-tools: Read, Write, Edit, Bash, AskUserQuestion
---

# Test Plan Walkthrough

Spec-first, not browse-first: write each slice's spec from the concrete demo steps in `05-test-plan.md`, with `page.screenshot()` at every demoable checkpoint, and let Playwright drive headless. Hand-driving each step through an LLM-controlled browser is the slow path this skill replaces; `agent-browser` is only for recovering a locator.

**Announce at start:** "I'm using the test-plan-walkthrough skill spec-first - writing Playwright specs that self-capture screenshots and running them headless."

Runs after Phase 8 is fully green (this is the story's first and only end-to-end demo, against the integrated stack) and before `raise-pr`. Inputs: the demo steps and `e2e`-type cases in `05-test-plan.md`, the slice list in `04-task-plan.md`, credentials/seed data per `02-technical-plan.md`'s "Dev/Demo Data Recovery", and the app URL. Ask rather than guess if any is missing.

## Outputs

1. One Playwright spec per slice, appended to the project's **existing** e2e suite in its location and style, committed with the story.
2. `06-walkthrough.md` and `screenshots/slice-{NN}-{step-NN}-{kebab-name}.png` in the user-story folder, produced by the specs (`page.screenshot({ path })` pointed there). One screenshot per demoable checkpoint (each `→` in the demo line that lands on a visible state), not per keystroke.

No existing Playwright suite → do not create one. Skip output 1, record *"No Playwright e2e suite in this project - persisted specs skipped; recommend adding one"* under "Issues found", and still produce output 2 as far as possible.

## Steps

### 1. Locate the e2e suite

`find . -maxdepth 3 \( -name 'playwright.config.*' -o -name '*.spec.ts' -o -name '*.spec.js' \) -not -path '*/node_modules/*'`. Record the spec directory and naming, the run command (`package.json` scripts or `npx playwright test`), and the house style from one existing spec: imports, auth/login fixture, `baseURL`, locator conventions. Your specs must look like the same hand wrote them.

### 2. Verify the stack

Confirm the app is reachable (`docker compose ps`, a health endpoint); bring it up with the project's standard command if not. Stale seed data → follow "Dev/Demo Data Recovery". Never invent credentials.

### 3. Author the specs

`mkdir -p docs/new-feature/{folder}/screenshots`. For each slice's demo row, in slice order:

- Decompose the demo line into checkpoints (one assertion + one screenshot each), e.g. *"Sign in as Doctor → open Checked-In appointment → save 1 drug → reload → restored"* is four.
- One `test()` per slice, named after its behaviour, using the project's login fixture and `baseURL`. Locators from the concrete roles, labels and expected text in `05-test-plan.md` (`getByRole`, `getByLabel`, `getByTestId`); a step too vague to locate is a test-plan gap - ask, do not improvise. Assert the same expected states the plan lists, cover the slice's `e2e`-type cases, and screenshot after each assertion passes:
  ```ts
  await expect(page.getByText('Paracetamol')).toBeVisible();
  await page.screenshot({ path: 'docs/new-feature/{folder}/screenshots/slice-01-03-rx-saved.png' });
  ```
- Only when an element's accessible name genuinely cannot be known blind, take **one** `agent-browser snapshot` of that page to read the locator and encode it. Verification still happens in the headless run.

Playwright's `fill()`/`click()` fire native events, so React Hook Form usually works; if a field still will not update, use the native value setter + `InputEvent` + `form.requestSubmit()` from `page.evaluate` (see `frontend-implementer`'s "Driving React Hook Form programmatically"). A page with nested `<form>`s (the inner submit posts the outer form as GET, serialising fields into the URL) is a known FE bug: record it under "Issues found" and assert around it via a direct `request` call.

### 4. Run headless and triage

Run the new specs with the project's command against the running stack. A green spec is the verification and produces its screenshots. Per failure: a spec bug (selector, missing auto-wait, timing) → fix the spec, recovering the locator with one `agent-browser snapshot` if needed, and re-run; an app bug → record under "Issues found", mark the slice ❌, leave the spec in place (expected-red until fixed), and never patch app code. Never report a green spec you did not run.

On a re-dispatch after a fix, re-run only the affected slices' specs and amend only their rows and screenshots.

### 5. Write `06-walkthrough.md`

```markdown
# {USR-NNN} - End-to-end Walkthrough

**Date:** {YYYY-MM-DD} · **Branch:** {branch} · **Stack:** {git rev-parse --short HEAD}

> Demo steps mirror `05-test-plan.md` § "End-to-End Test (manual demo per slice)". Screenshots in `./screenshots/`.

## Pre-flight
- [x] Stack up: {N} services healthy
- [x] Auth: signed in as `{role}`
- [x] Seed data: {recovery steps applied, if any}

## Slice-by-slice results

### SLICE-01 - {behaviour}
**Demo:** {verbatim from 05-test-plan.md}
**Persisted spec:** `{path}` - ✅ green / ❌ red / - none (BE-only or no e2e suite)

| # | Step | Result | Screenshot |
|---|------|--------|------------|
| 1 | Sign in as Doctor | ✅ Redirected to `/doctor` | ![](screenshots/slice-01-01-login.png) |

## Issues found during walkthrough
| Slice | Severity | Issue | Status |
|---|---|---|---|
(write "None" if everything passed)

## Summary
- Slices walked: {N} · all AC demos passed: ✅/❌
- Persisted specs added: {N} (all green: ✅/❌) - or "none: no e2e suite"
- New bugs surfaced: {N}
```

Every slice in `04-task-plan.md` appears; BE-only slices get *"BE only - no UI; verified via API smoke."* Demo lines are pasted verbatim so the report stands alone. Never paste credentials.

### 6. Commit

```bash
git add docs/new-feature/{folder}/06-walkthrough.md docs/new-feature/{folder}/screenshots/ {new spec files}
git commit -m "test({slug}): e2e walkthrough + persisted Playwright specs"
```

One commit per run (`docs({slug}): e2e walkthrough - screenshots + 06-walkthrough.md` when there is no e2e suite). A re-run amends or adds a commit; no orphan files in the tree. Prefer headless; if a slice needs headed mode (print preview), note it under Pre-flight.
