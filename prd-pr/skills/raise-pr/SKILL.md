---
name: raise-pr
description: Use when implementation is complete, all CI checks pass, and you need to decide how to integrate the work - guides completion of development work by presenting structured options for merge, PR, or cleanup
allowed-tools: Read, Bash, AskUserQuestion
---

# Finishing a Development Branch

## Overview

Guide completion of development work by presenting clear options and handling chosen workflow.

**Core principle:** Verify the CI gate → Present options → Execute choice → Clean up.

**Announce at start:** "I'm using the raise-pr skill to complete this work."

## The Process

### Step 1: Verify the CI gate

**Before presenting options, run everything CI runs - not just the tests.**

A green test suite is not a green pipeline. Format and lint checks usually run
*after* tests, so a branch can pass every test, every typecheck and every lint rule
and still turn CI red on whitespace. That failure then lands on the base branch,
where it blocks everyone until someone raises a whitespace-only fix PR.

**First find out what CI actually runs. Read the workflow rather than guessing:**

```bash
ls .github/workflows/*.yml .gitlab-ci.yml azure-pipelines.yml Jenkinsfile 2>/dev/null
```

Run each check that workflow runs, **from the same working directory and in the same
order**. A monorepo CI job that sets `working-directory: frontend` must be reproduced
from `frontend/`, or the tool resolves a different config and gives a different verdict.
Typical gates, in the order they usually appear:

| Gate | JS/TS | .NET | Rust | Go | Python |
|---|---|---|---|---|---|
| Build | `npm run build` | `dotnet build` | `cargo build` | `go build ./...` | - |
| Typecheck | `npm run typecheck` | (in build) | (in build) | (in build) | `mypy .` |
| Test | `npm test` | `dotnet test` | `cargo test` | `go test ./...` | `pytest` |
| Lint | `npm run lint` / `biome lint .` | `dotnet format --verify-no-changes` | `cargo clippy` | `go vet ./...` | `ruff check` |
| Format | `npm run format:check` / `prettier --check .` | `dotnet format --verify-no-changes` | `cargo fmt --check` | `gofmt -l .` | `ruff format --check` |

**If any check fails:** show the failure. Stop. Do not proceed to Step 2.

- Fix formatting failures with the project's own write command - `prettier --write`,
  `biome format --write`, `dotnet format`, `cargo fmt`, `gofmt -w`, `ruff format`.
  Never hand-edit whitespace to satisfy a formatter.
- **A formatting-only failure is still a failure.** It is the cheapest possible red
  build and the easiest to leave behind, because nothing about the feature is broken.
- **If a check fails in a file this branch never touched, the branch is behind its
  base.** Merge the base branch and re-run before touching the file - the fix is
  probably already on main, and reformatting it by hand creates a redundant diff.

**If every check passes:** Continue to Step 1.5.

### Step 1.5: Test Plan Walkthrough (artifacts check)

The orchestrator's **Phase 9** dispatches the `test-plan-walker` subagent (which runs the `test-plan-walkthrough` skill as its playbook) and produces:

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
- E2E (Playwright): {N} persisted specs added this story (one per slice), all green — see `06-walkthrough.md` "Persisted spec" rows

## Rollback
{paste verbatim from 05-test-plan.md — Rollback Plan}
```

**Embedding screenshots** — PR descriptions are **not** rendered against the head branch on either GitHub or Azure DevOps. Relative image paths will 404 (the file doesn't exist on `main` yet at PR-open time). Always use absolute URLs that pin to the head branch.

For **GitHub**, use the `raw` URL pinned to the head branch (or a specific commit SHA for immutability):

```markdown
![SLICE-01 Rx saved](https://github.com/{owner}/{repo}/raw/{branch}/docs/new-feature/{folder}/screenshots/slice-01-03-rx-saved.png)
```

Also use absolute URLs for **markdown file links** (e.g. the walkthrough link) — same reason:

```markdown
[06-walkthrough.md](https://github.com/{owner}/{repo}/blob/{branch}/docs/new-feature/{folder}/06-walkthrough.md)
```

Pull `{owner}/{repo}` from `git remote get-url origin`. `{branch}` is the feature branch name.

For **Azure DevOps**, use the raw item URL pointing at the head branch:

```
![SLICE-01 Rx saved](https://dev.azure.com/{org}/{project}/_apis/git/repositories/{repo}/items?path=/docs/new-feature/{folder}/screenshots/slice-01-03-rx-saved.png&versionDescriptor.version={branch}&versionDescriptor.versionType=branch&api-version=7.1)
```

Generate one such URL per embedded image. Pull `{org}/{project}/{repo}` from `git remote get-url origin`.

**Note:** Once the PR merges, both forms still work — `raw/{branch}` resolves against whatever `{branch}` currently points to. If the head branch is deleted post-merge, switch the link to `raw/{merge-commit-sha}` or `raw/main` for long-term stability.

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

### Step 6: Close out the story tracker

For Options 1 and 2 only.

**Why this step exists.** Everything the workflow has written so far describes *this* story: `07-progress.md`,
the plan folder, `docs/new-feature/README.md`. None of it is what a person or a future agent reads to decide
**what to work on next**. That is the project's *backlog tracker*, and if it is not updated here it is never
updated at all - the next session opens a story that shipped weeks ago, reads `Status: Ready`, and rebuilds it.

**1. Find the tracker.** In order, stop at the first hit:

```bash
grep -rniE "single source of truth|backlog|story status|_index" CLAUDE.md AGENTS.md README.md 2>/dev/null
ls user-stories/_index.* docs/backlog.* BACKLOG.md 2>/dev/null
```

Also consider an external tracker (Azure DevOps, Jira, GitHub Issues) if the story id looks like a work-item
reference (`az boards work-item update --id <n> --state Resolved`). If you find no tracker, say so plainly and
skip the step. Do not invent one.

**2. Update exactly one record**, and make it evidence-bearing:

| Option taken | Status to set | Evidence to record |
|---|---|---|
| 1. Merged locally | done / closed | the merge commit sha |
| 2. PR raised | in review | the PR number **and** its URL |

Alongside the status, write a short note of **what actually shipped** - ACs delivered, decisions taken during
implementation that the story file did not anticipate, anything deliberately left out. That note is the only
durable record of the difference between the plan and the result; the plan folder records intent, not outcome.

**3. Never leave a story parked at "PR raised".** That state is a lie the moment the PR merges, and it is the
single most common source of tracker drift. On Option 2, either:
- check whether the PR has already merged (`gh pr view <n> --json state,mergeCommit`) and record the commit, or
- tell the user in your closing report, in one line: *"<story> is marked in-review; set it to done with the
  merge commit once PR #<n> lands."*

**4. If story status lives in more than one file, stop and report it.** Count the copies and name them. N
hand-maintained copies of one word always drift - the question is only when. Recommend collapsing to one
authoritative record, with the others either dropped or holding only facts the tracker does not (branch, merge
commit, plan-folder path). Do **not** quietly update all N: that hides the defect and guarantees the next
session inherits it. Ask the user before consolidating; it is their backlog.

## Quick Reference

| Option | Merge | Push | Keep Worktree | Cleanup Branch | Update Tracker |
|--------|-------|------|---------------|----------------|----------------|
| 1. Merge locally | ✓ | — | — | ✓ | ✓ done + sha |
| 2. Create PR | — | ✓ | ✓ | — | ✓ in-review + PR |
| 3. Keep as-is | — | — | ✓ | — | — |
| 4. Discard | — | — | — | ✓ (force) | — |

## Red Flags

**Never:** leave a merged story showing an in-progress status, maintain story status in more than one file without flagging it, proceed with any failing CI check - a format or lint failure is as red as a failing test, open a PR when `06-walkthrough.md` is missing or has unresolved ❌ rows, merge without re-running the CI gate on the result, paste raw `06-walkthrough.md` (megabytes) into the PR body, delete work without typed confirmation.

**Always:** close out the project's backlog tracker for Options 1 & 2 (Step 6) with the merge commit or PR number as evidence, verify the full CI gate (not just tests) before options, verify walkthrough artifacts exist (run the skill if not), summarise the walkthrough in the PR body (link to the full file), present exactly 4 options, clean up worktree for Options 1 & 4 only, use absolute branch-pinned URLs for PR-body images and walkthrough links on **both** GitHub and Azure DevOps (PR descriptions never render against the head branch — relative paths 404).

## Integration

Pairs with `git-worktrees` — cleans up the worktree that skill created.
Pairs with `test-plan-walkthrough` — consumes the screenshots + `06-walkthrough.md` it produces.
Called at the end of the `orchestrator` Phase 10 after the walkthrough is complete.
Step 6 is the workflow's only write to the project's own backlog tracker; the plan folder and `07-progress.md` never leave `docs/new-feature/`.
