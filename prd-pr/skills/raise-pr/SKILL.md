---
name: raise-pr
description: Use when implementation and the test-plan walkthrough are complete and the work needs integrating - verifies the full CI gate (build, typecheck, test, lint, format), checks the walkthrough artifacts, offers merge / PR / keep / discard, builds the PR body with embedded screenshots, cleans up the worktree and closes out the project's backlog tracker.
allowed-tools: Read, Bash, AskUserQuestion
---

# Raise PR

**Announce at start:** "I'm using the raise-pr skill to complete this work."

### Step 1: Verify the CI gate

A green test suite is not a green pipeline: format and lint checks usually run after tests, so a branch can pass every test and still turn CI red on whitespace, and that red then lands on the base branch.

Read what CI actually runs (`.github/workflows/*.yml`, `.gitlab-ci.yml`, `azure-pipelines.yml`, `Jenkinsfile`) and run each check **from the same working directory and in the same order**; a job with `working-directory: frontend` must be reproduced from `frontend/`, or the tool resolves a different config. Typically build → typecheck → test → lint → format-check.

If anything fails, stop and show it. Fix formatting with the project's own write command (`prettier --write`, `biome format --write`, `dotnet format`, `cargo fmt`, `gofmt -w`, `ruff format`), never by hand. A formatting-only failure is still a failure. If a check fails in a file this branch never touched, the branch is behind its base: merge the base and re-run before touching the file.

### Step 1.5: Walkthrough artifacts

Phase 9 should have produced `docs/new-feature/{folder}/06-walkthrough.md` and `screenshots/`.

- Present: read `06-walkthrough.md`. Any ❌ slice row or Blocker in "Issues found" → stop and send the user back to Phase 8; this skill does not fix bugs.
- Missing, or slices from `04-task-plan.md` absent from it: dispatch `agent_type: "prd-pr:test-plan-walker"` (scoped to the missing slices if partial) and wait for its Return Report. Never run the `test-plan-walkthrough` skill inline; it needs a clean context. Exception: a refactor-tier story (no `05-test-plan.md` in the folder) has its walkthrough written by the orchestrator from the story's own Verification section - one row per slice or task with a verdict - and needs no walker; only a missing file or a ❌ row is a stop.
- For any `Type: HITL` slice needing physical verification (printing, QR scanning): ask *"Run the HITL-only verification for SLICE-NN now? [Y/skip]"* and note a skip in the PR body.

### Step 2: Base branch

Read the `Base:` line of `docs/new-feature/{folder}/07-progress.md` (`grep -m1 '^Base:'`): the branch the orchestrator cut the worktree from. If the line is missing (a ledger written before it existed), ask; never assume `main` and do not derive it from git - `@{upstream}` is the feature branch's own remote after `push -u`, and the branch reflog says `Created from HEAD` unless the base was named. A story cut from a release or integration branch and merged into `main` unattended is the wrong merge, with the feature branch deleted behind it. The branch point for the diff is `git merge-base HEAD {base}`.

### Step 3: Execute the recorded exit, or present the options

If `docs/new-feature/{folder}/07-progress.md` has an `Exit:` line (`grep -m1 '^Exit:'`) reading `pr` or `merge`, that decision was taken at plan confirmation (orchestrator Phase 4): announce it in one line and go straight to Step 4 with that option. Present the menu only when the line is absent or reads `ask`. The menu at the end of a long unattended run is idle time measured in hours, not a decision.

```
Implementation complete. What would you like to do?

1. Merge back to <base-branch> locally
2. Push and create a Pull Request
3. Keep the branch as-is (I'll handle it later)
4. Discard this work
```

### Step 4: Execute

**1. Merge locally**: `git checkout {base} && git pull`, merge the feature branch, re-run the CI gate on the merged result, delete the feature branch. Then Step 5.

**2. Push and create PR**: `git push -u origin <feature-branch>`, then detect the host from `git remote get-url origin`: `github.com` → `gh pr create --base {base} --body-file`; `dev.azure.com` / `*.visualstudio.com` → `az repos pr create --target-branch {base} --description "$(cat body.md)"`; anything else → ask. Title `{USR-NNN}: {short verb-phrase}`, under 70 chars. Body from this template (summarise the walkthrough; never paste it raw):

```markdown
## Summary
- {1-3 bullets from 00-overview.md}

## Acceptance Criteria
{verbatim from 01-business-plan.md}

## Slices shipped
| Slice | Behaviour | e2e status |
|---|---|---|

## Test Plan Walkthrough
Full report and screenshots: [06-walkthrough.md]({absolute link})
- {N} slices walked, {N} ✅, {N} ❌; issues surfaced: {N}
{1-2 hero screenshots per slice}

## Test Plan (automated)
- Backend / frontend suites: counts, baseline preserved
- Smoke: per-slice `Smoke:` sequences → all ✅
- E2E (Playwright): {N} persisted specs added, all green

## Rollback
{verbatim from 05-test-plan.md}
```

**Refactor tier** (no `01-business-plan.md` or `05-test-plan.md` in the folder): the template's sources do not exist, so do not invent them. `## Summary` and `## Acceptance Criteria` come from `00-overview.md` (its success criteria are the ACs); `## Slices shipped` and `## Test Plan Walkthrough` collapse into one `## Verification` table copied from `06-walkthrough.md` (command · observed · ✅) under the full-report link, with no screenshots; `## Test Plan (automated)` keeps the suite-count line only; `## Rollback` is a revert of the merge unless `00-overview.md` says otherwise.

**Screenshot and file links must be absolute and pinned to the head branch.** PR descriptions are not rendered against the head branch on either host, so relative paths 404.

- GitHub: `https://github.com/{owner}/{repo}/raw/{branch}/docs/new-feature/{folder}/screenshots/{file}.png` for images, `.../blob/{branch}/...` for markdown files.
- Azure DevOps: `https://dev.azure.com/{org}/{project}/_apis/git/repositories/{repo}/items?path=/docs/new-feature/{folder}/screenshots/{file}.png&versionDescriptor.version={branch}&versionDescriptor.versionType=branch&api-version=7.1`.

If the head branch is deleted after merge, switch links to the merge commit SHA or `{base}`. Return the PR URL, then Step 5.

**3. Keep as-is**: report the branch and worktree path; do not clean up.

**4. Discard**: require the user to type `discard`, then delete the branch (`-D`) and remove the worktree.

### Step 5: Clean up the worktree

Options 1, 2 and 4: `git worktree remove <path>` (find it with `git worktree list`). Option 3 keeps it.

### Step 6: Close out the backlog tracker

Options 1 and 2 only. Everything written so far (`07-progress.md`, the plan folder, `docs/new-feature/README.md`) describes *this* story; the project's **backlog tracker** is what the next session reads to choose the next story, and if it is not updated here it never is.

1. **Find it**: `grep -rniE "single source of truth|backlog|story status|_index" CLAUDE.md AGENTS.md README.md`, then `ls user-stories/_index.* docs/backlog.* BACKLOG.md`. If the story id looks like a work-item reference, the tracker may be external (`az boards work-item update --id <n> --state Resolved`). No tracker found → say so and skip; do not invent one.
2. **Update exactly one record** with evidence: merged → done/closed + merge commit SHA; PR raised → in review + PR number and URL. Add a short note of what actually shipped: ACs delivered, decisions the story did not anticipate, anything left out. The plan folder records intent; this is the only record of outcome.
3. **Never leave a story parked at "PR raised".** Either check whether the PR already merged (`gh pr view <n> --json state,mergeCommit`) and record the commit, or tell the user in one line to set it to done once PR #n lands.
4. **Status in more than one file → stop and report** the copies by name. Recommend collapsing to one record; do not quietly update all of them, and ask before consolidating - it is the user's backlog.
