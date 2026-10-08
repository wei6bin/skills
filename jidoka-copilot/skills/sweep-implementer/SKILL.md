---
name: sweep-implementer
description: Internal - mechanical rewrite of one sweep slice's file set, backend or frontend. Invoked by impl-backend and impl-frontend.
user-invocable: false
allowed-tools: Read, Grep, Glob, Bash, Write, Edit, AskUserQuestion
---

# Sweep Implementer

A `kind: sweep` slice rewrites existing files to a new form and adds no
behaviour - a helper or API migration, a hook or component rename, a prop
migration, a call-site sweep - so there is no TDD loop, no contract and no mock.
The card's `Files:` set and inline verification steps are the whole spec, and
that set is disjoint from every other sweep's, which run concurrently.

1. Build the file list from the card's `Files:` line. Per file, read only the
   sites that need a verdict (a grep with context, not the whole file), decide,
   then apply the mechanical form change with `sed` or a short script over the
   file. Never Read a whole file and Write it back to change a dozen arguments;
   that pattern carries the whole file in context on every one of a sweep's
   hundreds of turns.
2. Gate on the build after each file or small batch (frontend: the typecheck
   and build), plus the tests that live in or beside the files you touched -
   in-memory backend tests, unit and component tests. **Do not run the
   container-bound suite, the whole frontend suite or any e2e**: the
   orchestrator's regression gate runs them once for the whole story, and other
   sweeps are running concurrently on the same machine.
3. Record per-site findings as data: one line per site appended with `echo >>`
   to `docs/new-feature/{folder}/08-findings-SLICE-NN.csv` - your slice's own
   file, because other sweeps are writing theirs in other worktrees and a shared
   path diverges and conflicts on merge. Write the header
   `file,line,helper,verdict,note` first and double-quote `note` (free text; a
   bare comma in it corrupts the row). Commit the file with the slice. The
   orchestrator concatenates the per-slice files and renders any Markdown table
   the story requires, once, in its Step 2. A table that says "no defect" on
   hundreds of rows should cost one short line per row, not a hand-written
   Markdown table.
4. Commit per file or coherent batch:
   `feat({backend|frontend}): SLICE-NN - {file}: {what changed}`.
5. Before reporting, tabulate the project's test marker (`[Fact]`/`[Theory]`,
   `[Test]`, `it(`/`test(`, `def test_`) per touched file at the branch point
   and at HEAD: `git show {branch-point}:{file} | grep -c '{marker}'` against
   `grep -c '{marker}' {file}`. The orchestrator verifies the sweep from that
   table, not from a suite run, so a row whose columns differ needs a one-line
   reason.

Stay inside the card's `Files:` set. A site that needs a behaviour change, not
a form change, is a finding to record and flag, not an edit to make here.

Report per the calling agent's Return Report format, with the test-marker table
in place of test counts.
