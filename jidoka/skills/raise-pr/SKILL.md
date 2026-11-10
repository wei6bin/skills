---
name: raise-pr
description: Internal - final CI gate, the pull request's summary with AC coverage and the line's decisions, the recorded exit, worktree cleanup, and the story's close-out. Invoked by the orchestrator.
user-invocable: false
allowed-tools: Read, Write, Bash
---

# Raise PR

**Announce at start:** "I'm using the raise-pr skill to complete this work."

This runs at the end of an unattended line run: nobody is there to answer a
menu or a question. Where this skill says **stop**, return to the orchestrator
with what you found; it decides between a fix and an andon stop.
`agreement.py` is the refine skill's `scripts/agreement.py`, the same script
the orchestrator uses.

## Step 1: Verify the CI gate

If the regression row in `docs/new-feature/{folder}/07-progress.md` names a
commit (`✅ at 1a2b3c4`) and `git diff --name-only {commit} HEAD` shows only
files under `docs/` and the walker's own commit (its persisted specs, which
Phase 9 just ran), skip the test suite and cite that commit as its result.
Run every other check below anyway: nothing has linted, typechecked or
format-checked the specs and docs written since, and those checks are quick
next to the suite. Anything else changed since, such as a fix from a
`FIXES_NEEDED` round: run the whole gate.

A green test suite is not a green pipeline: format and lint checks usually run
after tests, so a branch can pass every test and still turn CI red on
whitespace, and that red then lands on the base branch.

Read what CI actually runs (`.github/workflows/*.yml`, `.gitlab-ci.yml`,
`azure-pipelines.yml`, `Jenkinsfile`) and run each check **from the same working
directory and in the same order**; a job with `working-directory: frontend` must
be reproduced from `frontend/`, or the tool resolves a different config.
Typically build → typecheck → test → lint → format-check.

If anything fails, stop and show it. Fix formatting with the project's own write
command (`prettier --write`, `biome format --write`, `dotnet format`,
`cargo fmt`, `gofmt -w`, `ruff format`), never by hand. A formatting-only
failure is still a failure. If a check fails in a file this branch never
touched, the branch is behind its base: merge the base and re-run before
touching the file.

## Step 1.5: Walkthrough artifacts

Phase 9 should have produced `docs/new-feature/{folder}/06-walkthrough.md` and
`screenshots/`.

- **Present:** read `06-walkthrough.md`. Any ❌ slice row, a Blocker in
  "Issues found", or a verdict other than `ALL_GREEN` → stop. Phase 8 owns
  the fix; this skill does not fix bugs.
- **Missing, or slices from `04-task-plan.md` absent from it:** dispatch
  `agent_type: "jidoka:test-plan-walker"`, scoped to the missing slices if
  partial, and wait for its Return Report. Never run the
  `test-plan-walkthrough` skill inline; it needs a clean context.
  - Exception: a refactor-tier story (no `05-test-plan.md` in the folder) has
    its walkthrough written by the orchestrator from the story's own
    Verification section, one row per slice or task with a verdict. It needs
    no walker; only a missing file or a ❌ row is a stop.
- **A `Type: HITL` slice** needing physical verification (printing, QR
  scanning) cannot be verified unattended. List it in the summary under
  "Needs a person", with the steps to check it.

## Step 2: Base branch

Read the `Base:` line of `docs/new-feature/{folder}/07-progress.md`
(`grep -m1 '^Base:'`): the branch the orchestrator cut the worktree from.

- **If the line is missing, stop.** Never assume `main`, and do not derive the
  base from git. `@{upstream}` is the feature branch's own remote after
  `push -u`, and the branch reflog says `Created from HEAD` unless the base was
  named.
- A story cut from a release or integration branch and merged into `main`
  unattended is the wrong merge, with the feature branch deleted behind it.

The branch point for the diff is `git merge-base HEAD {base}`.

## Step 3: The recorded exit

Read the `Exit:` line of `07-progress.md` (`grep -m1 '^Exit:'`). It comes
from the agreement, which BA, Dev Lead and QE signed:

- **`merge`**: merge into `{base}` locally (Step 5, option 1);
- **`pr`**: push and open a pull request (Step 5, option 2).

Anything else, or no line, is a stop. Announce the exit in one line and go on.

## Step 4: Write the summary, and update a story file

The summary is `docs/new-feature/{folder}/10-summary.md`. It is the pull
request's body, the merge commit's message, and the story comment's source.
Build it from the files, never from memory. Summarise the walkthrough; never
paste it raw.

**AC coverage, by ID.** For each active AC in `story.md`'s section 4:

- **Tests:** find the tests that cite its ID (`AC-n`) in the diff
  (`git diff {branch-point}..HEAD -- {test files}`), and the persisted
  walkthrough spec.
- **Result:** from the Phase 8 regression run's result files and
  `06-walkthrough.md`.
- **Evidence:** the evidence section 5 asks for, as a link: a screenshot, the
  test that asserts the response body, the report.

An active AC with no test that cites it is a stop, not a blank row.

```markdown
# {id}: {title}

Built against story {id} rev {rev} ({hash}), signed by {BA}, {Dev Lead} and {QE}.
Opened by jidoka:line ({scheduled run on {$JIDOKA_HOST} | run by {git config user.name}}).

## Summary
- {1-3 bullets from story.md: the why from section 1, the change from section 3}

## Acceptance criteria
| AC | Then | Tests | Result | Evidence |
|---|---|---|---|---|
| AC-1 | {Then, shortened} | `{test name}`, `{spec name}` | ✅ | [screenshot]({absolute link}) |

## Decisions made by the line
{the table from 09-decisions.md, or "None."} Each is pending until its role
confirms it through /jidoka:refine; none blocks this merge.

## Slices shipped
| Slice | Behaviour | ACs | e2e status |
|---|---|---|---|

## Test Plan Walkthrough
Full report and screenshots: [06-walkthrough.md]({absolute link})
- {N} slices walked, {N} ✅, {N} ❌; issues surfaced: {N}
{1-2 hero screenshots per slice}

## Test Plan (automated)
- Backend / frontend suites: counts, baseline preserved
- Smoke: per-slice `Smoke:` sequences → all ✅
- E2E (Playwright): {N} persisted specs added, all green

## Needs a person
{HITL checks, or "Nothing."}

## Follow-ups
{non-blocker findings from the reviews and the walkthrough}

## Rollback
{verbatim from 05-test-plan.md}
```

**Refactor tier** (no `05-test-plan.md` in the folder): the template's
sources do not exist, so do not invent them.

- `## Acceptance criteria` still lists the agreement's ACs, with the
  verification that proves each.
- `## Slices shipped` and `## Test Plan Walkthrough` collapse into one
  `## Verification` table, copied from `06-walkthrough.md` (command, observed,
  ✅) under the full-report link, with no screenshots.
- `## Test Plan (automated)` keeps the suite-count line only.
- `## Rollback` is a revert of the merge, unless `04-task-plan.md` ends
  with a `## Rollback` section; then it is that section, verbatim.

**Screenshot and file links must be absolute and pinned to the head branch.** PR
descriptions are not rendered against the head branch on either host, so
relative paths 404.

- GitHub:
  `https://github.com/{owner}/{repo}/raw/{branch}/docs/new-feature/{folder}/screenshots/{file}.png`
  for images, `.../blob/{branch}/...` for markdown files.
- Azure DevOps:
  `https://dev.azure.com/{org}/{project}/_apis/git/repositories/{repo}/items?path=/docs/new-feature/{folder}/screenshots/{file}.png&versionDescriptor.version={branch}&versionDescriptor.versionType=branch&api-version=7.1`.
- With no remote (a local merge), link the files by their repository paths.

**A story file** (`Tracker: file` in `story.md`) travels with the branch, so
update it now, before the merge or the push carries it:

1. `agreement.py record {folder}/story.md --decisions {folder}/09-decisions.md`
   (skip it when the table has no rows).
2. `agreement.py status {folder}/story.md --set jidoka-done` for `merge`, or
   `--set jidoka-pr` for `pr`.

Commit the summary, and the story file if it changed:
`docs({slug}): summary and story close-out`.

## Step 5: Execute

**1. Merge locally.** In the main worktree, merge the feature branch and
re-run the CI gate on the merged result. The main worktree is the first
`worktree` entry of `git worktree list --porcelain`; `{base}` is checked out
there, so `git checkout {base}` fails inside the feature worktree.

```bash
git checkout {base}
git pull                                   # only when there is a remote
git merge --no-ff {slug} -m "{id}: {title}" -m "$(cat docs/new-feature/{folder}/10-summary.md)"
```

**2. Push and create the PR.** Run `git push -u origin {slug}`, then detect
the host from `git remote get-url origin`. The title is
`{id}: {short verb-phrase}`, under 70 characters, and the body is
`10-summary.md`. The `jidoka` label marks the pull requests the line opened.

A run that resumes after an andon stop already has a **draft** pull request
on this branch. Update that one instead of opening another: its title, its
body, the label, and mark it ready.

- `github.com`:

  ```bash
  gh label create jidoka --description "Opened by jidoka:line" --force
  gh pr view {slug} --json number,isDraft     # an earlier run's PR, if any
  # none:
  gh pr create --base {base} --title "{title}" --body-file docs/new-feature/{folder}/10-summary.md --label jidoka
  # one: update it, and take it out of draft
  gh pr edit {number} --title "{title}" --body-file docs/new-feature/{folder}/10-summary.md --add-label jidoka
  gh pr ready {number}
  ```

- `dev.azure.com` or `*.visualstudio.com`: Azure DevOps keeps at most 4000
  characters of a pull request's description. When `10-summary.md` is longer
  (`wc -m`), the description is the summary up to the end of its
  `## Decisions made by the line` section, then a link to the whole file on
  the branch.

  ```bash
  az repos pr list --source-branch {slug} --status active --query "[0].pullRequestId" -o tsv
  # none:
  az repos pr create --target-branch {base} --title "{title}" --labels jidoka --description "$(cat {description})"
  # one: update it, and take it out of draft
  az repos pr update --id {id} --title "{title}" --description "$(cat {description})" --draft false
  ```

- **Any other host:** stop.

If the head branch is deleted after merge, switch the links to the merge commit
SHA or `{base}`.

## Step 6: Close out the story and the backlog tracker

Run this from the feature worktree, before Step 7 removes it: the plan folder,
`story.md` and `09-decisions.md` are there, and on a pull request the base
branch has none of them.

Everything written so far (`07-progress.md`, the plan folder,
`docs/new-feature/README.md`) describes _this_ story. The story and the
project's **backlog tracker** are what the next session and the next scheduled
pick-up read. If they are not updated here, they never are.

1. **The work item** (`Tracker: ado ...` in `story.md`):
   - `agreement.py record {folder}/story.md --decisions {folder}/09-decisions.md`,
     when the table has rows.
   - `agreement.py comment {folder}/story.md --file {comment}`, where
     `{comment}` is a short Markdown file. It holds the pull request URL (or
     the merge commit), the AC coverage table, and the decisions made by the
     line.
   - `agreement.py status {folder}/story.md --set jidoka-pr` for a pull
     request, or `--set jidoka-done` for a merge.

   A story file was closed out in Step 4.
2. **Find the backlog tracker**, if the project keeps one besides the story:

   ```bash
   grep -rniE "single source of truth|backlog|story status|_index" CLAUDE.md AGENTS.md README.md
   ls user-stories/_index.* docs/backlog.* BACKLOG.md
   ```

   No tracker found: say so and skip; do not invent one. A work item's own
   state (Resolved, Done) belongs to the project's process; change it only
   when that is the tracker CLAUDE.md names.
3. **Update exactly one record** with evidence: merged → done/closed + merge
   commit SHA; PR raised → in review + PR number and URL. Add a short note of
   what actually shipped: the ACs delivered, the decisions made by the line,
   anything left out. The plan folder records intent; this is the record of
   outcome.
4. **Never leave a story parked at "PR raised".** Check whether the PR has
   already merged (`gh pr view <n> --json state,mergeCommit`) and record the
   commit; otherwise say in the final report that the record moves to done
   once PR #n lands.
5. **Status in more than one file:** update none of them. Name the copies in
   the summary's Follow-ups and in the final report, and recommend collapsing
   them to one record. It is the team's backlog to consolidate, not this run's.

## Step 7: Clean up

From the main worktree; removing the worktree you are standing in strands the
shell. Run `git worktree remove <path>` (find it with `git worktree list`).
For a merge, then `git branch -d {slug}`; a pull request keeps its branch.
Remove the worktree first: git refuses to delete a branch a worktree still has
checked out.
