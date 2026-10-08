#!/usr/bin/env bash
# Scaffold for the line-greenfield-scaffold eval: an empty git repository on
# `main` with no commits and no remote - the "folder with no source code" that
# makes /jidoka:line run project-setup before anything else.
#
# `claude plugin eval --scaffold` runs this as you, outside the agent's sandbox,
# in the empty workspace, with a minimal env (PATH, HOME, TMPDIR, TERM).
set -euo pipefail

git init -q -b main
# The run gets a fresh HOME with no global git identity; commits need one.
git config user.name "jidoka eval"
git config user.email "jidoka-eval@example.invalid"
