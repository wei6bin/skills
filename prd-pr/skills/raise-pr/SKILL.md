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

### Step 1.5: HITL Demo

Read `04-task-plan.md`. For any slice with `Type: HITL`:

1. Ask: **"Run the HITL demo via agent-browser before opening the PR? [Y/skip]"**

2. **If Y** — drive each HITL slice's demo steps end-to-end:
   - For form interactions, follow the `frontend-implementer` skill's "Driving forms programmatically" section.
   - Per step: report ✅ / ❌ with URL and observed state (e.g. "✅ Step 3: change-password 200, redirected to `/`").
   - If any step fails: stop, report, do **not** proceed to PR creation.
   - For bootstrap/seed recovery, follow `02-technical-plan.md` "Dev/Demo Data Recovery".

3. **If skip** — note "HITL demo skipped by user" in the PR body.

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

```bash
git push -u origin <feature-branch>
gh pr create --title "<title>" --body "## Summary\n<bullets>\n\n## Test Plan\n- [ ] <steps>"
```

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

**Never:** proceed with failing tests, proceed past a failed HITL demo step, merge without re-running tests on result, delete work without typed confirmation.

**Always:** verify tests before options, run or skip-confirm the HITL demo for any HITL slice, present exactly 4 options, clean up worktree for Options 1 & 4 only.

## Integration

Pairs with `git-worktrees` — cleans up the worktree that skill created.
Called at the end of the `orchestrator` Phase 8 after all tasks are complete.
