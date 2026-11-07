---
name: git-worktrees
description: Internal - creates an isolated git worktree on a new branch with a recorded test baseline, or checks out an existing branch to resume it. Invoked by the orchestrator.
user-invocable: false
allowed-tools: Read, Bash
---

# Git Worktrees

**Announce at start:** "I'm using the git-worktrees skill to set up an isolated
workspace."

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

## Create

```bash
git worktree add "$path/$BRANCH_NAME" -b "$BRANCH_NAME"    # $path absolute
cd "$path/$BRANCH_NAME"
```

Then run the project's dependency install (detect from `package.json`,
`Cargo.toml`, `pyproject.toml`/`requirements.txt`, `go.mod`, `*.sln`/`*.csproj`)
and the test suite to establish the baseline. If tests fail, report each
failing test by name as the baseline. A dirty baseline makes new bugs
indistinguishable from pre-existing ones, so the orchestrator decides whether
the failures touch the story (an andon stop) or stay as the known baseline.

## Resume an existing branch

When the orchestrator resumes a story whose branch an earlier run left, check
it out instead of creating it:

- **A worktree already has it** (`git worktree list` shows the branch): use
  that path.
- **Only the remote has it:** `git fetch origin {branch}`, then
  `git worktree add "$path/{branch}" {branch}`.
- **Otherwise:** `git worktree add "$path/{branch}" {branch}`, without `-b`.

Then install dependencies and run the suite as above; the report's baseline is
the branch's own.

## Report

```text
Worktree ready at <full-path>
Tests passing (<N> tests, 0 failures)
Ready to implement <feature-name>
```
