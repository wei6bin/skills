---
name: raise-pr
description: Use when implementation is complete, all tests pass, and you need to decide how to integrate the work - guides completion of development work by presenting structured options for merge, PR, or cleanup
allowed-tools: Read, Bash, AskUserQuestion
---

# Finishing a Development Branch

## Overview

Guide completion of development work by presenting clear options and handling chosen workflow.

**Core principle:** Verify tests → Present options → Execute choice → Clean up.

**Announce at start:** "I'm using the raise-pr skill to complete this work."

## The Process

### Step 1: Verify Tests

**Before presenting options, verify tests pass:**

```bash
# Run project's test suite — auto-detect from project files
npm test / cargo test / pytest / go test ./... / dotnet test
```

**If tests fail:** Show failures. Stop. Don't proceed to Step 2.

**If tests pass:** Continue to Step 1.5.

### Step 1.5: Test Plan Walkthrough (artifacts check)

The orchestrator's **Phase 9** drives `05-test-plan.md`'s end-to-end manual demos via the `test-plan-walkthrough` skill and produces:

- `docs/new-feature/{folder}/06-walkthrough.md` — per-step ✅/❌ status, observed-vs-expected, "Issues found"
- `docs/new-feature/{folder}/screenshots/slice-NN-step-NN-*.png` — one screenshot per demo step

**Verify both exist before continuing:**

```bash
ls docs/new-feature/*/06-walkthrough.md docs/new-feature/*/screenshots/ 2>/dev/null
```

- **If present** — read `06-walkthrough.md`. If any slice has a ❌ row or the "Issues found" table lists Blocker items, **stop**. Report the failing rows and tell the user to loop back to Phase 8 (`raise-pr` does not fix bugs).
- **If missing** — dispatch the `test-plan-walker` subagent (`agent_type: "prd-pr:test-plan-walker"`) per the orchestrator's Phase 9 contract. Wait for its Return Report. Do not invoke the `test-plan-walkthrough` skill inline — it must run in a clean subagent context.
- **If the slice list under `04-task-plan.md` has slices that aren't covered in `06-walkthrough.md`** — re-dispatch `test-plan-walker` scoped to the missing slices. Every slice must appear.

For any slice marked `Type: HITL` in `04-task-plan.md` that needs the user to physically verify something the skill cannot (e.g. printing a real receipt, scanning a QR code), ask: *"Run the HITL-only verification for SLICE-NN now? [Y/skip]"*. If skipped, note "HITL-only verification skipped by user" in the PR body.

### Step 2: Determine Base Branch

```bash
git merge-base HEAD main 2>/dev/null || git merge-base HEAD master 2>/dev/null
```

### Step 3: Present Options

Present exactly these 4 options:

```
Implementation complete. What would you like to do?

1. Merge back to <base-branch> locally
2. Push and create a Pull Request
3. Keep the branch as-is (I'll handle it later)
4. Discard this work

Which option?
```

### Step 4: Execute Choice

#### Option 1: Merge Locally

```bash
git checkout <base-branch>
git pull
git merge <feature-branch>
<test command>          # Verify on merged result
git branch -d <feature-branch>
```

Then: Cleanup worktree (Step 5)

#### Option 2: Push and Create PR

**Detect the remote host** (`git remote get-url origin`):

- `github.com/...` → GitHub PR via `gh pr create`
- `dev.azure.com/...` or `*.visualstudio.com/...` → Azure DevOps PR via `az repos pr create`
- anything else → stop and ask the user how to raise the PR

**Build the PR body from the walkthrough.** Compose this template — do not paste raw `06-walkthrough.md`; summarise it:

```markdown
## Summary
- {1–3 bullets from 00-overview.md → goal/scope}

## Acceptance Criteria
{paste verbatim from 01-business-plan.md — Acceptance Criteria}

## Slices shipped
| Slice | Demoable behaviour | e2e status |
|---|---|---|
| SLICE-01 | … | ✅ |
| SLICE-02 | … | ✅ |
…

## Test Plan Walkthrough
Full per-step report and screenshots: [`docs/new-feature/{folder}/06-walkthrough.md`]({path-to-walkthrough})

**Highlights:**
- {N} slices walked, {N} ✅, {N} ❌
- Issues surfaced: {N} (see walkthrough "Issues found" table)

**Screenshots:**
{embed 1–2 hero shots per slice — see "Embedding screenshots" below}

## Test Plan (automated)
- Backend: `dotnet test` → {X} passing / {Y} failing (baseline preserved)
- Frontend: `npm test` → {X} passing
- Smoke: per-slice `Smoke:` sequences from `04-task-plan.md` → all ✅

## Rollback
{paste verbatim from 05-test-plan.md — Rollback Plan}
```

**Embedding screenshots** — relative paths render inline on **GitHub** when the PR description is rendered against the head branch:

```markdown
![SLICE-01 Rx saved](docs/new-feature/{folder}/screenshots/slice-01-03-rx-saved.png)
```

For **Azure DevOps**, relative paths do **not** render. Use the raw item URL pointing at the head branch:

```
![SLICE-01 Rx saved](https://dev.azure.com/{org}/{project}/_apis/git/repositories/{repo}/items?path=/docs/new-feature/{folder}/screenshots/slice-01-03-rx-saved.png&versionDescriptor.version={branch}&versionDescriptor.versionType=branch&api-version=7.1)
```

Generate one such URL per embedded image. Pull `{org}/{project}/{repo}` from `git remote get-url origin`.

**Create the PR:**

```bash
# GitHub
git push -u origin <feature-branch>
gh pr create --title "<title>" --body-file /tmp/pr-body.md

# Azure DevOps (requires az CLI logged in, defaults configured)
git push -u origin <feature-branch>
az repos pr create \
  --source-branch <feature-branch> \
  --target-branch <base-branch> \
  --title "<title>" \
  --description "$(cat /tmp/pr-body.md)" \
  --output table
```

Title format: `{USR-NNN}: {short verb-phrase}` (e.g. `USR-018: Prescribe medications during consultation`). Keep under 70 chars.

After creation, return the PR URL to the user.

Then: Cleanup worktree (Step 5)

#### Option 3: Keep As-Is

Report: "Keeping branch <name>. Worktree preserved at <path>."
**Do not cleanup worktree.**

#### Option 4: Discard

Confirm first — require the user to type `discard` before proceeding:

```bash
git checkout <base-branch>
git branch -D <feature-branch>
git worktree remove <worktree-path>
```

### Step 5: Cleanup Worktree

For Options 1, 2, 4:

```bash
git worktree list | grep $(git branch --show-current)
git worktree remove <worktree-path>
```

For Option 3: keep worktree.

## Quick Reference

| Option | Merge | Push | Keep Worktree | Cleanup Branch |
|--------|-------|------|---------------|----------------|
| 1. Merge locally | ✓ | — | — | ✓ |
| 2. Create PR | — | ✓ | ✓ | — |
| 3. Keep as-is | — | — | ✓ | — |
| 4. Discard | — | — | — | ✓ (force) |

## Red Flags

**Never:** proceed with failing tests, open a PR when `06-walkthrough.md` is missing or has unresolved ❌ rows, merge without re-running tests on result, paste raw `06-walkthrough.md` (megabytes) into the PR body, delete work without typed confirmation.

**Always:** verify tests before options, verify walkthrough artifacts exist (run the skill if not), summarise the walkthrough in the PR body (link to the full file), present exactly 4 options, clean up worktree for Options 1 & 4 only, use raw-item URLs for Azure DevOps PR screenshots (relative paths only render on GitHub).

## Integration

Pairs with `git-worktrees` — cleans up the worktree that skill created.
Pairs with `test-plan-walkthrough` — consumes the screenshots + `06-walkthrough.md` it produces.
Called at the end of the `orchestrator` Phase 10 after the walkthrough is complete.
