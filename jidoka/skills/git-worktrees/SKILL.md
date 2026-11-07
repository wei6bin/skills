---
name: git-worktrees
description: Internal - checks a story's base in a detached worktree before the claim, then makes it the story's branch; creates a worktree on a new branch from a named base; or checks out an existing branch to resume it, with the base merged in. Each records a test baseline. Invoked by the orchestrator.
user-invocable: false
allowed-tools: Read, Bash
---

# Git Worktrees

**Announce at start:** "I'm using the git-worktrees skill to set up an isolated
workspace."

The orchestrator names the branch (the story's slug) and the **base**: the
branch the story is cut from and lands on. With a remote, the start point is
`origin/{base}` after `git fetch origin {base}`; without one, `{base}`. Never
start from the checkout's `HEAD`: the checkout may be on any branch.

## Where

In priority order:

1. An existing `.worktrees/` (preferred) or `worktrees/` directory in the repo.
2. A location named in `CLAUDE.md` (`grep -i "worktree.*director" CLAUDE.md`).
3. Otherwise `.worktrees/` (project-local, hidden). This runs unattended, so
   take the default rather than asking.

For a project-local directory, verify it is ignored
(`git check-ignore -q <dir>`, where `<dir>` is `.worktrees` or `worktrees`,
whichever was chosen); if not, add it to `.gitignore` and commit before creating
the worktree, so worktree contents never get tracked.

## The baseline

In the worktree, run the project's dependency install (detect from
`package.json`, `Cargo.toml`, `pyproject.toml`/`requirements.txt`, `go.mod`,
`*.sln`/`*.csproj`), the build, and the test suite. If the build fails, report
its errors; if tests fail, report each failing test by name. A dirty baseline
makes new bugs indistinguishable from pre-existing ones, so the orchestrator
decides what the failures mean.

## Check the base (before the claim)

The story's worktree, detached at the base, so the base is tested before
anything claims the story or makes a branch:

```bash
git worktree add --detach "$path/$BRANCH_NAME" "$START"   # $path absolute
```

Run the baseline there and report it with the commit
(`git -C "$path/$BRANCH_NAME" rev-parse HEAD`). Then the orchestrator either:

- **keeps it:** after the claim, `git -C "$path/$BRANCH_NAME" switch -c
  "$BRANCH_NAME"` makes it the story's branch, starting at the checked
  commit. The check's baseline is the branch's baseline; do not run it again.
- **drops it:** `git worktree remove --force "$path/$BRANCH_NAME"`. Nothing
  else was made: no branch, no commit.

## Create

When no check was kept (the base moved since, or the orchestrator skipped
it):

```bash
git worktree add -b "$BRANCH_NAME" "$path/$BRANCH_NAME" "$START"   # $path absolute
```

Then run the baseline.

## Resume an existing branch

When the orchestrator resumes a story whose branch an earlier run left, check
it out instead of creating it:

- **A worktree already has it** (`git worktree list` shows the branch): use
  that path.
- **Only the remote has it:** `git fetch origin {branch}`, then
  `git worktree add "$path/{branch}" {branch}`.
- **Otherwise:** `git worktree add "$path/{branch}" {branch}`, without `-b`.

Then bring the base in, since it may have moved while the story waited (a
stop often waits on a fix that lands on the base):
`git merge --no-edit "$START"`. Merge, never rebase: the branch may be pushed,
and a rebased branch needs a force-push. On a conflict, run
`git merge --abort` and report the conflicting files instead of a baseline.
Otherwise run the baseline; it is the branch's own, with the base merged in.

## Report

```text
Worktree ready at <full-path>
Base: <base> at <commit>, <merged: N commits | already up to date | detached check>
Build: <ok | failed: first errors>
Tests: <N> passing, <M> failing (<names>)
```
