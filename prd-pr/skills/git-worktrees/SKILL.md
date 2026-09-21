---
name: git-worktrees
description: Use when starting feature work that needs isolation from the current workspace or before executing an implementation plan - creates an isolated git worktree on a new branch, verifies the directory is git-ignored, runs project setup and confirms a clean test baseline.
allowed-tools: Read, Bash, AskUserQuestion
---

# Git Worktrees

**Announce at start:** "I'm using the git-worktrees skill to set up an isolated workspace."

## Where

In priority order:

1. An existing `.worktrees/` (preferred) or `worktrees/` directory in the repo.
2. A location named in `CLAUDE.md` (`grep -i "worktree.*director" CLAUDE.md`).
3. Otherwise ask: `.worktrees/` (project-local, hidden) or `~/.config/prd-pr/worktrees/<project>/` (global).

For a project-local directory, verify it is ignored (`git check-ignore -q <dir>`, where `<dir>` is `.worktrees` or `worktrees`, whichever was chosen); if not, add it to `.gitignore` and commit before creating the worktree, so worktree contents never get tracked.

## Create

```bash
git worktree add "$path/$BRANCH_NAME" -b "$BRANCH_NAME"    # $path absolute
cd "$path/$BRANCH_NAME"
```

Then run the project's dependency install (detect from `package.json`, `Cargo.toml`, `pyproject.toml`/`requirements.txt`, `go.mod`, `*.sln`/`*.csproj`) and the test suite to establish a clean baseline. If tests fail, report the failures and ask whether to proceed or investigate; a dirty baseline makes new bugs indistinguishable from pre-existing ones.

## Report

```
Worktree ready at <full-path>
Tests passing (<N> tests, 0 failures)
Ready to implement <feature-name>
```
