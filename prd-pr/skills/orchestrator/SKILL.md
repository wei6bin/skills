---
name: orchestrator
description: Entry point for new feature or enhancement work. Runs the 10-phase workflow - discovery, parallel codebase exploration, clarifying questions, architecture and plan docs, plan review, summary, parallel slice implementation with one whole-story QA round, Playwright test-plan walkthrough, PR. Writes plan files to docs/new-feature/{id}-{summary}/. Trigger on "work on this user story", "new enhancement", "implement this feature", "plan this feature", or whenever the user pastes a user story, acceptance criteria or an Azure DevOps ticket, even without naming the workflow.
---

# Dev Workflow - New Enhancement

Guide the developer through the phases below in order, tracking them in a todo list. Phase 8's loop position lives in `07-progress.md` so the workflow survives compaction and restarts.

**Announce at start:** "I'm using the orchestrator skill to guide this enhancement through the full workflow."

## Phase 1 - Discovery

Capture **Title · Problem statement · Acceptance Criteria (numbered) · Stakeholders · Constraints · Dependencies** from the story (ask if not provided) and confirm your understanding before proceeding.

**Then classify the story's shape** and record the tier in the todo list; it sizes every later phase, and Phase 4 writes it into `07-progress.md` as the `Tier:` line so later steps read the classification instead of re-deriving it from the diff.

| Shape | Explorers (Ph 2) | Architect writes (Ph 4) | Plan review (Ph 6) | Reviews (Ph 8) | Walkthrough (Ph 9) | Per-slice verify (Ph 8) |
|---|---|---|---|---|---|---|
| **Feature, BE + FE** (`full-stack`) | 2-3 | six docs | 2 reviewers | code + security | Playwright walker | run the suite |
| **Feature, one layer** (`one-layer`) | 1 | six docs | 1 reviewer | code + security | walker (Playwright or CLI) | run the suite |
| **Refactor / test-only / docs** (`refactor`) - no new behaviour, or production code untouched | 0 - your own Phase 2 census is the exploration | `00-overview.md` + `04-task-plan.md` only (flat tasks or `Kind: sweep` slices, verification steps inline) | none | code only, security brief folded in | none - run the story's own Verification section from the main session | build + greps |

The third row exists because the full workflow, applied to a test-only sweep, spends its architect on four documents nobody reads, its plan reviewers on finding nothing, its security reviewer on a diff with no production code, and its walker on evidence that is two shell commands. When a later phase says "per the tier", this table is what it means.

## Phase 2 - Codebase Exploration

1. If `docs/project_context/` is missing or empty, invoke `codebase-context-builder`; otherwise read `00_index.md` and load 2-4 relevant files.
2. **Query the knowledge graph before searching the tree.** If `docs/project_context/prod_spec/graph.md` exists, read it whole and resolve the request against it: the capability map gives code anchors (your search starting points), the entity map gives every rule already constraining the entities involved, the edges tell you which decisions are `supersedes`/`amends` (a superseded entry reads like a current one; do not apply it) or `conflicts-with` (pick a side knowingly), and the open questions say whether the work is blocked or deferred - if so, say so **now**. Then load only the cited entry IDs (`grep -n "\[DR-114\]" docs/project_context/prod_spec/*.md`), not the whole folder.
3. Per the tier, dispatch **`code-explorer` subagents in parallel** (`agent_type: "prd-pr:code-explorer"`), seeded with the anchors and entry IDs from step 2: one tracing the closest similar feature end to end, one mapping the domain area's architecture and conventions, and (if full-stack) one tracing the frontend patterns. Each returns 5-10 key files. **Refactor tier: none.** Do the census yourself with greps over the files the story names (declarations, call sites, counts); a refactor's exploration is a count, and explorers dispatched to re-map what you just grepped are the layer that gets thrown away.
4. Read the key files they name, then present: reference implementation, capabilities/entities touched (graph IDs) and any superseded decision or open question in scope, layers affected, reusable code, conventions to follow.

## Phase 3 - Clarifying Questions

Resolve every ambiguity before designing. **Do not skip.**

- If the codebase can answer a question, explore it instead of asking; record the finding as an assumption.
- **Batch independent questions; chain only dependent ones.** One `AskUserQuestion` call takes up to four questions: put every question whose answer does not depend on another's in the same call, each with your recommended answer and a one-line rationale. Ask a follow-up in a second call only when it genuinely depends on an earlier answer; three round-trips for three independent questions is three waits on the user. "Use your recommendation" is a valid answer; "whatever you think" means state your assumption and ask for confirmation.
- Summarise the resolved decisions before Phase 4.

## Phase 4 - Architecture Design and Documents

### Step 0 - Worktree first

The architect writes files to disk, so the isolated worktree must exist before it runs. Unless one was set up earlier in the session, invoke `git-worktrees` with the feature slug as the branch name. If no `Skill` tool is exposed, create it via Bash with an **absolute** path (`git worktree add -b {slug} {repo-root}/.worktrees/{slug} {base}`; a relative path resolves against a CWD that may have drifted into another worktree) and verify with `git worktree list`. Never silently proceed on the current branch.

Choose the user-story folder: `docs/new-feature/{id}-{summary}/` (e.g. `usr-012-pwa-shell`).

### Step 1 - Dispatch the architect

Dispatch **1 `code-architect`** (`agent_type: "prd-pr:code-architect"`) with the feature description and ACs, the Phase 3 answers, the Phase 2 findings and loaded context files, and the **absolute path** of the folder. It designs the blueprint and writes `00-overview.md` … `05-test-plan.md` itself; you transcribe nothing. Its final message is a manifest: summary, slice table, waves and critical path, files written, risks.

Tell the architect the tier and two facts about the machine, or it will over-serialise: how many worktree slots exist, and that `Kind: sweep` slices (see `vertical-slicing`) gate on the build, not on container tests, so disjoint sweeps are parallel-safe even when only one database container fits. **Refactor tier:** the architect writes `00-overview.md` and `04-task-plan.md` only.

### Step 2 - Review and confirm the slice list

1. Read the documents the tier calls for (they are the source of truth; the manifest is a table of contents). Every tier: every slice has a card in `04-task-plan.md`, and the file opens with a `## Dependency graph` block whose edge table matches the cards' `Blocked by:` lines. Feature tiers: every `BE + FE` slice has a frozen `Contract:` and `05-test-plan.md` has concrete demo steps. Refactor tier: every card or task carries its verification steps inline, and every `Kind: sweep` card names a `Files:` set disjoint from the other sweeps'.
2. Present the slice list with the waves and critical path and **confirm with the user before implementation** - one `AskUserQuestion` call carrying two questions. Q1: confirm the slice list (which slices are parallel-safe is the most important decision here). Q2: **the exit action once the QA round and walkthrough are green** - "Push and open a PR (Recommended)", "Merge to {base} locally", or "Stop and ask me". Then create `07-progress.md` in the folder from the Phase 8 Step 0 template: `Tier:` from Phase 1, `Base:` (the branch the worktree was cut from in Step 0), `Exit:` (this answer) and one ⬜ row per confirmed slice. Writing it now rather than in Phase 8 is what lets the decision survive a compaction in Phases 5-7; `raise-pr` reads `Base:` and `Exit:`, skips its menu, and merges into or targets the PR at that base instead of assuming `main`. This is the last question the user must be present for: everything after it runs unattended, and the next thing they see is the PR link. A menu at the end of a long unattended run is idle time measured in hours, not a decision.
3. Small changes: edit the docs. Structural changes: re-dispatch the architect. Do not continue until the slice list is confirmed.

## Phase 5 - Finalize Documents

1. Every file the tier calls for exists and is complete (six for a feature, two for a refactor); re-dispatch the architect for any stub rather than filling it in by hand.
2. Cross-document consistency. Every tier: the dependency-graph edge table agrees with the cards, every blocker is a real slice ID, no cycle; fix the table and re-derive on a mismatch. Feature tiers: every slice has test cases in `05-test-plan.md` and change sites in `03-implementation-plan.md`, and every `BE + FE` contract also appears in `02-technical-plan.md`. Refactor tier: the sweeps' `Files:` sets are pairwise disjoint and together cover the files the story names.
3. Add an index entry to `docs/new-feature/README.md` (folder, story, branch, later the merge commit). This is the plan-folder index, not the project's backlog tracker, and must not carry a status column that duplicates one; `raise-pr` Step 6 owns the tracker.

## Phase 6 - Quality Review

Per the tier, dispatch **`plan-reviewer` subagents in parallel** (`agent_type: "prd-pr:plan-reviewer"`) over `docs/new-feature/{folder}/`: one focused on AC coverage, security, edge cases and business/technical consistency; one on slice completeness, dependency edges, test coverage and sizing (a one-layer feature gets only the first). Present the consolidated findings and fix Critical and Important issues in the docs. **Refactor tier: skip** - your Phase 5 consistency check is the review.

## Phase 7 - Summary

Present the folder path, key decisions and assumptions, reviewer-flagged risks, and next steps (review the docs; create one ADO Task per slice under the parent story, manually; start Phase 8 from the ready slices in the dependency graph).

## Phase 8 - Slice-by-Slice Implementation

Implement every slice's halves - BE against the frozen contract, FE against a **mock** of it, concurrently - **without integrating per slice**. Then run one consolidated round over the whole diff: integrate, refactor, review, smoke, regression. Deferring integration is safe because each backend conformance-tests its own contract. The browser-level e2e runs once in Phase 9, not here.

### Step 0 - Progress ledger

Phase 4 Step 2 created `07-progress.md` with the `Tier:` / `Base:` / `Exit:` lines and one ⬜ row per confirmed slice (or per task, for a flat task list). Read it and cross-check the last ✅ against `git log --oneline` (the `feat(...)` commits and the checkpoint are ground truth). Any ⬜ in the per-slice table → start or resume in Step 1 at that slice; otherwise resume in Step 2 at the first ⬜ row, in table order. Do not redo completed steps. If the file is missing (a plan folder from before Phase 4 wrote it), create it now from this template, filling the three lines from the todo list:

```markdown
# Progress - {id}-{summary}

Tier: {full-stack | one-layer | refactor}
Base: {base}
Exit: {pr | merge | ask}

## Per-slice implementation

| Slice | BE | FE |
|-------|----|----|
| SLICE-01 | ⬜ | ⬜ |

## Final QA round (once, after every slice above is implemented)

| Step | Status |
|------|--------|
| Integration (whole story - every FE on the real backends, contract drift fixed) | ⬜ |
| Refactor / simplify (whole story) | ⬜ |
| Code review (full diff, branch point → HEAD) | ⬜ |
| Security review (full diff, branch point → HEAD) | ⬜ |
| Smoke (every slice's smoke sequence) | ⬜ |
| Test suite / regression (whole diff, one run - also the coverage gate and the "after" result files) | ⬜ |
| Context capture | ⬜ |
| Checkpoint commit | ⬜ |
```

`Tier:` is the Phase 1 classification, `Base:` the branch the worktree was cut from (Phase 4 Step 0), `Exit:` the Phase 4 answer. Keep the three lines bare - `raise-pr` and the tier branches below `grep '^Tier:'` / `'^Base:'` / `'^Exit:'` them. Cells that cannot apply - the FE column of a BE-only slice, the Integration and Smoke rows of a story made only of `Kind: sweep` slices - are `-` from the start.

`⬜` pending · `✅` done · `❌` failed/blocked (one-line note under the table) · `-` N/A (e.g. FE on a BE-only slice). Update a row the moment it completes. The file is orchestrator-owned; subagents never write to it.

### Step 1 - Implement: parallel halves, parallel slices

Schedule from the `## Dependency graph` block in `04-task-plan.md` combined with the ledger:

- **Ready frontier** = slices whose every `Blocked by:` is ✅ (roots start ready). Start each ready slice that has a free worktree slot, and refresh the frontier the moment a blocker's BE and FE both go ✅; do not wait for its wave.
- More ready slices than slots → start **critical-path slices first**, then larger ones.
- Each concurrent slice gets its own worktree. With one worktree, run slices sequentially but still parallelise each slice's halves.

For each slice you start:

1. **Dispatch the halves concurrently, in one batch**, per the card's `Layers:`:
   - `BE + FE`: `agent_type: "prd-pr:impl-backend"` with scope `"SLICE-NN backend half - implement AND conformance-test the frozen contract"` **and** `agent_type: "prd-pr:impl-frontend"` with scope `"SLICE-NN frontend half - build against the frozen contract with a typed mock; integration is one whole-story pass in Step 2"`. If the card says `Contract: unfrozen - serial`, run BE first, then FE.
   - `BE only` / `FE only`: dispatch that implementer.
   - Append the lean mode from the card's story points: `lean: lite` for 1-2, `lean: full` for 3+ (large slices still get `full`; the implementer flags over-scope rather than dropping ACs).

   Each implementer gets the slice card, not a file-task list, and commits per behaviour: `feat({layer}): SLICE-NN - {behaviour}`. The FE half stays on its mock; do not re-dispatch it to wire in the real backend now.

   For a `Kind: sweep` card the scope is `"SLICE-NN {backend | frontend} half - kind: sweep"` - no contract wording, there is none to conformance-test - and the implementer switches to its sweep mode (rules in `backend-implementer` and `frontend-implementer`): it gates on the compile step plus any in-memory tests in its own files, runs no container suite, applies mechanical rewrites by script rather than Read-whole-file / Write-whole-file, and writes per-site findings to its own `08-findings-SLICE-NN.csv` rather than a Markdown table. Sweeps over disjoint `Files:` sets run concurrently, one worktree each.

2. **Verify each Return Report against evidence you already hold.** The agent that wrote the report is the one it describes, so never accept it on trust - but pick the instrument by the slice's kind:
   - **Static checks first, always** (seconds): the build is clean; the card's greps return the counts it predicts; for a `Kind: sweep` or test-only slice every path in `git diff --name-only {branch-point}..HEAD` belongs to the card's `Files:` set (a path outside it is over-reach, whatever the repo layout); every AC the card assigns to that half appears in the report with a named backing test.
   - **`Kind: sweep`: compare, do not re-run.** The report carries a per-file table of test-marker counts at the branch point and at HEAD (the project's marker: `[Fact]`/`[Theory]`, `[Test]`, `it(`/`test(`, `def test_`). Re-derive it with the same one-liner (`git show {branch-point}:{file} | grep -c '{marker}'` against `grep -c '{marker}' {file}`) and require the columns to match file by file: a sweep that eats an attribute line still compiles, so the build alone proves nothing about lost tests. Re-run a file's classes only on a mismatch; the whole suite runs once, in Step 2.5, where the total is checked against the worktree baseline. Re-running a suite to confirm an accurate report is container time spent learning what the greps already showed.
   - **`Kind: feature`: re-run.** Run the relevant suite(s) via Bash (backend including its conformance tests, frontend against its mock) and compare counts to the report. This is where a self-graded "green" can be wrong.

   On any mismatch or missing section, re-dispatch the owner with the discrepancy quoted verbatim, or finish the work yourself and note the takeover.

3. **Mark BE/FE ✅.** Nothing else happens per slice. Start whatever this slice was blocking.

### Step 2 - Consolidated quality round (once, over branch point → HEAD)

Precondition: every BE/FE cell is ✅ (or `-`). If sweeps wrote `08-findings-SLICE-NN.csv` files, concatenate them now (header once) into `08-findings.csv`, render any table the story requires from it with a short script, and commit; this is the only point where findings are assembled, so no sweep waits on another.

1. **Integrate the whole story.** Dispatch `impl-frontend` once, scope `"whole-story integration - replace every slice's contract mock with the real backends, run integration/e2e tests, fix contract drift"`, with the full slice list and changed-file set. If drift belongs on a backend, re-dispatch `impl-backend` for that slice with the mismatch quoted. Skip `unfrozen - serial` slices (already integrated) and `Kind: sweep` slices (nothing to integrate); a story made only of sweeps skips the step and its row is `-`. Mark ✅.

2. **Refactor.** Dispatch `agent_type: "prd-pr:impl-simplify"` once with the folder path, the branch-point ref and the changed-file list. It wraps the built-in `simplify` skill in its own context (a whole-story refactor read here would evict the plan docs and reports you still need), runs the tests covering the files it touched, and commits. Confirm its report names that run and shows it green; a missing Verification line means re-dispatch, not a run of your own - the full suite runs once, in step 5. Route any blocker under "Reported, not fixed" to the owning implementer. Mark ✅. It runs **before** review so the reviewers read the diff that ships; a simplify pass after approval means the approved diff is not the merged one.

3. **Review code and security in parallel.** In one batch, dispatch `agent_type: "prd-pr:code-reviewer"` and `agent_type: "prd-pr:security-reviewer"` over the full diff, each with the folder path, `04-task-plan.md` and the `Tier:` line (a refactor-tier folder has no `02-technical-plan.md`; say so, so the reviewer does not go looking for it). The round passes only when **both** return `APPROVED`. On `FIXES_NEEDED` from either: re-dispatch the owning implementer(s) with the Blocker rows quoted verbatim, then re-dispatch only the reviewer(s) that flagged, scoped to the amended diff; loop until both approve. Non-blockers become PR follow-ups. Mark both rows ✅.

   **Refactor tier** (`Tier: refactor` in `07-progress.md`): dispatch **one** reviewer, `code-reviewer`, with the security reviewer's test-specific brief folded into its prompt - "every denial, scoping and visibility test still proves what its name says after the rewrite". The check is worth keeping; two agents reading the same diff for it is not. Mark the security row `-`.

4. **Smoke.** Run every `Kind: feature` slice's `Smoke:` sequence from `04-task-plan.md` in slice order against the running stack; sweeps have none, and a story made only of sweeps marks the row `-`. After a fix, re-run only the failed sequences. Mark ✅.

5. **Regression - one run serves every gate.** Run the project's full existing suite (unit, integration, component, pre-existing e2e) over the whole diff **once**, through the project's target that also measures coverage and keeps the test-result files (usually a Makefile target taking a results directory), so the same run is the regression gate, the coverage gate, the container-budget pin and the "after" half of any before/after diff the story requires. Its passing count must be at least the baseline `git-worktrees` reported at worktree creation plus the story's new tests; a lower total is a lost test, whatever the sweep reports said. Do not run a bare suite first for the result files and the coverage suite again for the threshold; that is the same suite twice. Fix failures before marking ✅. Do not write or run the story's new browser e2e here; that is Phase 9.

   **Gates run strictly one at a time.** Never launch one detached while another runs in the foreground: a coverage-instrumented container suite starved by a parallel build fails on database timeouts and the whole run is wasted. If a make target already chains the gates serially, call it rather than decomposing it.

   **Long jobs get a bounded watcher, never an open-ended one.** A job longer than the Bash tool's ceiling runs detached (`nohup run.sh &`) and writes its `DONE` marker from an `EXIT` trap, never from a last line: a last line is skipped when `set -e` aborts the script, and under `| tee` a bare `$?` is tee's 0, so the failure path - the one the marker exists for - never produces one.

   ```bash
   # run.sh
   set -o pipefail
   trap 'echo "exit=$?" > "$S/DONE"' EXIT
   make coverage RESULTS="$S" 2>&1 | tee "$S/run.log"   # the project's suite-with-coverage target
   ```

   The watcher must exit on its own before the ceiling, because its exit is what re-invokes you; a loop killed at the ceiling re-invokes nothing. The loop below sleeps up to 8.5 min, so call it with the tool's maximum timeout (`timeout: 600000`); under the default 2-minute ceiling shorten it to `seq 1 3`. If the harness blocks a foreground `sleep`, use its Monitor / until-loop tool on the same `DONE`-file condition instead:

   ```bash
   for i in $(seq 1 17); do [ -f "$S/DONE" ] && break; sleep 30; done
   if   [ -f "$S/DONE" ];                       then echo "DONE: $(cat "$S/DONE")"
   elif [ -n "$(find "$S/run.log" -mmin -3)" ]; then echo "RUNNING - re-arm the watcher"
   else echo "STALLED - log silent for 3 min; check uptime and orphaned test hosts before relaunching"; fi
   ```

   On `RUNNING` re-arm the same watcher immediately; on `STALLED` diagnose before relaunching. Never write "the watcher will need one re-arm" and stop; nothing re-arms it, and the session idles until the user notices.

6. **Capture product knowledge.** Invoke `context-updater` in the main session (never as a subagent) once for the whole story: behaviour implemented, domain rules enforced, config decisions, non-obvious design choices. Mark ✅.

7. **Checkpoint.** `git commit --allow-empty -m "checkpoint: {story} - all slices integrated after consolidated review/refactor/smoke"`. Mark ✅.

### Step 3 - Report

Slice-by-slice summary (behaviour, files), what the refactor changed, review/smoke/regression outcome, learning points, anything skipped or flagged, next steps.

## Phase 9 - Test Plan Walkthrough

Precondition: every cell in `07-progress.md` is ✅ (or `-`). Otherwise return to Phase 8.

**Refactor tier: no walker.** Run the story's own Verification section (or the cards' `Verify:` lines) from the main session and write `06-walkthrough.md` yourself: one row per slice or task with its command, observed output and ✅/❌, under an `ALL_GREEN` / `FIXES_NEEDED` verdict. Commit it (`git add docs/new-feature/{folder}/06-walkthrough.md && git commit -m "docs({slug}): verification walkthrough"`): the walker path commits in its own Step 6, and an uncommitted file 404s from the PR body and is discarded with the worktree. Then go to Phase 10; `raise-pr` Step 1.5 accepts this file as-is. A refactor has no browser flow to record.

Dispatch `agent_type: "prd-pr:test-plan-walker"` in a clean context (the walkthrough produces dozens of screenshots) with the folder path, branch name, app URL, and a pointer to where demo credentials live - never the credentials. It writes a Playwright spec per slice from `05-test-plan.md` (self-capturing screenshots), runs them headless, persists them into the project's e2e suite and writes `06-walkthrough.md`.

- `ALL_GREEN` → Phase 10.
- `FIXES_NEEDED` → re-dispatch the owning implementer per Blocker, then re-dispatch the walker scoped to **the affected slices only**; it re-runs those specs and amends `06-walkthrough.md`. Loop until green.
- `PARTIAL` → fix the environmental issue it names and re-dispatch with `Resume from: SLICE-NN step-NN`.

Non-blocker findings go into the PR body as follow-ups.

## Phase 10 - Branch Completion

Invoke `raise-pr`. It verifies the CI gate, checks the walkthrough artifacts (re-dispatching the walker if missing), executes the `Exit:` action recorded in `07-progress.md` (offering merge / PR / keep / discard only when it reads `ask`), embeds the walkthrough summary and screenshots in the PR body, cleans up the worktree, and in its Step 6 closes out the project's **backlog tracker** with the merge commit or PR number. Do not treat that last step as optional: everything before it writes only inside `docs/new-feature/`, and a shipped story still reading `Ready` in the tracker gets rebuilt. If `raise-pr` finds status in more than one file, surface that to the user rather than updating them all.
