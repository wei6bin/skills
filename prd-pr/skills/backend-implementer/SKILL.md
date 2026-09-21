---
name: backend-implementer
description: Drives the TDD red-green-refactor loop for the backend half of one vertical slice - one AC behaviour at a time, files discovered as tests demand them, one commit per cycle, a conformance test against the slice's frozen contract. Invoked by the impl-backend agent after it has loaded context.
allowed-tools: Read, Grep, Glob, Bash, Write, Edit, AskUserQuestion
---

# Backend Implementer

Implement the backend half of the named slice by TDD. The slice card is the spec; there is no file-task list, because each red test tells you what to write next.

## TDD loop

For a `BE + FE` slice the frozen `Contract:` is a commitment: ship exactly that shape (or flag it upward) and include a **conformance test** asserting your responses match its schema - field names, types, nullability, status codes. Then, per AC behaviour, simplest and happy path first:

1. Grep for the closest existing handler/service/endpoint matching the slice's reference patterns and note its conventions.
2. Write one failing integration-style test through the public API (mirror Given/When/Then if the AC is written that way). Run it; it must fail for the right reason.
3. Make it pass with the least code: climb the `reuse-ladder` at the current lean mode first, then add only what this test demands. Nothing "for the next test".
4. Run the whole suite. Refactor only while green.
5. Commit: `feat(backend): SLICE-NN - {behaviour, e.g. 'register Booked patient as Checked-In'}`. One commit per cycle.

Do not write all tests first and then all implementation; that is horizontal layering inside the slice. Mock only at system boundaries (external APIs, time, randomness), never internal collaborators.

## Sweep mode (`kind: sweep` in the scope)

The slice rewrites existing files to a new form and adds no behaviour, so the TDD loop above does not apply. Instead:

1. Build the file list from the card's `Files:` line. Per file, read only the sites that need a verdict (a grep with context, not the whole file), decide, then apply the mechanical form change with `sed` or a short script over the file. Never Read a whole file and Write it back to change a dozen arguments; that pattern put ~300K tokens of context behind each of 454 turns on usr-093's largest sweep.
2. Gate on the build after each file or small batch, plus any in-memory tests that live in the files you touched. **Do not run the container-bound suite**: the orchestrator's regression gate runs it once for the whole story, and other sweeps are running concurrently on the same machine.
3. Record per-site findings as data: one line per site appended with `echo >>` to `docs/new-feature/{folder}/08-findings-SLICE-NN.csv` - your slice's own file, because other sweeps are writing theirs in other worktrees and a shared path diverges and conflicts on merge. Write the header `file,line,helper,verdict,note` first and double-quote `note` (free text; a bare comma in it corrupts the row). Commit the file with the slice. The orchestrator concatenates the per-slice files and renders any Markdown table the story requires, once, in its Step 2. A table that says "no defect" 283 times should cost 283 short lines, not 96 KB of hand-written Markdown.
4. Commit per file or coherent batch: `feat(backend): SLICE-NN - {file}: {what changed}`.
5. Before reporting, tabulate the project's test marker (`[Fact]`/`[Theory]`, `[Test]`, `it(`/`test(`, `def test_`) per touched file at the branch point and at HEAD: `git show {branch-point}:{file} | grep -c '{marker}'` against `grep -c '{marker}' {file}`. The orchestrator verifies the sweep from that table, not from a suite run, so a row whose columns differ needs a one-line reason.

## Rules

- Stay inside the named slice and the backend half; hand frontend needs to the FE half with a note.
- Follow the reference patterns; do not invent new ones.
- Every AC the slice covers gets at least one test. Ask (`AskUserQuestion`) when an AC is ambiguous instead of guessing.

Report per the calling agent's Return Report format: ACs backed by tests, files touched, anything flagged for the FE half or orchestrator.
