---
name: orchestrator
description: Entry point for new feature or enhancement work. Runs the 10-phase workflow - discovery, parallel codebase exploration, clarifying questions, architecture and plan docs, plan review, summary, parallel slice implementation with one whole-story QA round, Playwright test-plan walkthrough, PR. Writes plan files to docs/new-feature/{id}-{summary}/. Trigger on "work on this user story", "new enhancement", "implement this feature", "plan this feature", or whenever the user pastes a user story, acceptance criteria or an Azure DevOps ticket, even without naming the workflow.
---

# Dev Workflow - New Enhancement

Guide the developer through the phases below in order, tracking them in a todo list. Phase 8's loop position lives in `07-progress.md` so the workflow survives compaction and restarts.

**Announce at start:** "I'm using the orchestrator skill to guide this enhancement through the full workflow."

## Phase 1 - Discovery

Capture **Title · Problem statement · Acceptance Criteria (numbered) · Stakeholders · Constraints · Dependencies** from the story (ask if not provided) and confirm your understanding before proceeding.

## Phase 2 - Codebase Exploration

1. If `docs/project_context/` is missing or empty, invoke `codebase-context-builder`; otherwise read `00_index.md` and load 2-4 relevant files.
2. **Query the knowledge graph before searching the tree.** If `docs/project_context/prod_spec/graph.md` exists, read it whole and resolve the request against it: the capability map gives code anchors (your search starting points), the entity map gives every rule already constraining the entities involved, the edges tell you which decisions are `supersedes`/`amends` (a superseded entry reads like a current one; do not apply it) or `conflicts-with` (pick a side knowingly), and the open questions say whether the work is blocked or deferred - if so, say so **now**. Then load only the cited entry IDs (`grep -n "\[DR-114\]" docs/project_context/prod_spec/*.md`), not the whole folder.
3. Dispatch **2-3 `code-explorer` subagents in parallel** (`agent_type: "prd-pr:code-explorer"`), seeded with the anchors and entry IDs from step 2: one tracing the closest similar feature end to end, one mapping the domain area's architecture and conventions, and (if full-stack) one tracing the frontend patterns. Each returns 5-10 key files.
4. Read the key files they name, then present: reference implementation, capabilities/entities touched (graph IDs) and any superseded decision or open question in scope, layers affected, reusable code, conventions to follow.

## Phase 3 - Clarifying Questions

Resolve every ambiguity before designing. **Do not skip.**

- If the codebase can answer a question, explore it instead of asking; record the finding as an assumption.
- Ask the remaining questions **one at a time**, each with your recommended answer and a one-line rationale, and let each answer shape the next. "Use your recommendation" is a valid answer; "whatever you think" means state your assumption and ask for confirmation.
- Summarise the resolved decisions before Phase 4.

## Phase 4 - Architecture Design and Documents

### Step 0 - Worktree first

The architect writes files to disk, so the isolated worktree must exist before it runs. Unless one was set up earlier in the session, invoke `git-worktrees` with the feature slug as the branch name. If no `Skill` tool is exposed, create it via Bash with an **absolute** path (`git worktree add -b {slug} {repo-root}/.worktrees/{slug} {base}`; a relative path resolves against a CWD that may have drifted into another worktree) and verify with `git worktree list`. Never silently proceed on the current branch.

Choose the user-story folder: `docs/new-feature/{id}-{summary}/` (e.g. `usr-012-pwa-shell`).

### Step 1 - Dispatch the architect

Dispatch **1 `code-architect`** (`agent_type: "prd-pr:code-architect"`) with the feature description and ACs, the Phase 3 answers, the Phase 2 findings and loaded context files, and the **absolute path** of the folder. It designs the blueprint and writes `00-overview.md` … `05-test-plan.md` itself; you transcribe nothing. Its final message is a manifest: summary, slice table, waves and critical path, files written, risks.

### Step 2 - Review and confirm the slice list

1. Read the six documents (they are the source of truth; the manifest is a table of contents). Check every slice has a card in `04-task-plan.md`, every `BE + FE` slice has a frozen `Contract:`, `05-test-plan.md` has concrete demo steps, and `04-task-plan.md` opens with a `## Dependency graph` block whose edge table matches the cards' `Blocked by:` lines.
2. Present the slice list with the waves and critical path and **confirm with the user before implementation**. Which slices are parallel-safe is the most important decision here.
3. Small changes: edit the docs. Structural changes: re-dispatch the architect. Do not continue until the slice list is confirmed.

## Phase 5 - Finalize Documents

1. All six files exist and are complete; re-dispatch the architect for any stub rather than filling it in by hand.
2. Cross-document consistency: every slice has test cases in `05-test-plan.md` and change sites in `03-implementation-plan.md`; every `BE + FE` contract also appears in `02-technical-plan.md`; the dependency-graph edge table agrees with the cards, every blocker is a real slice ID, no cycle. Fix the table and re-derive on a mismatch.
3. Add an index entry to `docs/new-feature/README.md` (folder, story, branch, later the merge commit). This is the plan-folder index, not the project's backlog tracker, and must not carry a status column that duplicates one; `raise-pr` Step 6 owns the tracker.

## Phase 6 - Quality Review

Dispatch **2 `plan-reviewer` subagents in parallel** (`agent_type: "prd-pr:plan-reviewer"`) over `docs/new-feature/{folder}/`: one focused on AC coverage, security, edge cases and business/technical consistency; one on slice completeness, dependency edges, test coverage and sizing. Present the consolidated findings and fix Critical and Important issues in the docs.

## Phase 7 - Summary

Present the folder path, key decisions and assumptions, reviewer-flagged risks, and next steps (review the docs; create one ADO Task per slice under the parent story, manually; start with SLICE-01).

## Phase 8 - Slice-by-Slice Implementation

Implement every slice's halves - BE against the frozen contract, FE against a **mock** of it, concurrently - **without integrating per slice**. Then run one consolidated round over the whole diff: integrate, review, refactor, smoke, regression. Deferring integration is safe because each backend conformance-tests its own contract. The browser-level e2e runs once in Phase 9, not here.

### Step 0 - Progress ledger

- **`07-progress.md` exists**: you are resuming. Read it and cross-check the last ✅ against `git log --oneline` (the `feat(...)` commits and the checkpoint are ground truth). Any ⬜ in the per-slice table → resume in Step 1 at that slice; otherwise resume in Step 2 at the first ⬜ row, in table order. Do not redo completed steps.
- **It does not exist**: create it:

```markdown
# Progress - {id}-{summary}

## Per-slice implementation

| Slice | BE | FE |
|-------|----|----|
| SLICE-01 | ⬜ | ⬜ |

## Final QA round (once, after every slice above is implemented)

| Step | Status |
|------|--------|
| Integration (whole story - every FE on the real backends, contract drift fixed) | ⬜ |
| Code review (full diff, branch point → HEAD) | ⬜ |
| Security review (full diff, branch point → HEAD) | ⬜ |
| Refactor / simplify (whole story) | ⬜ |
| Smoke (every slice's smoke sequence) | ⬜ |
| Test suite / regression (whole diff) | ⬜ |
| Context capture | ⬜ |
| Checkpoint commit | ⬜ |
```

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

2. **Verify each Return Report yourself.** The agent that wrote the report is the one it describes. Run the relevant suite(s) via Bash (backend including its conformance tests, frontend against its mock) and compare counts to the report; confirm every AC the card assigns to that half appears with a named backing test. On any mismatch or missing section, re-dispatch the owner with the discrepancy quoted verbatim, or finish the work yourself and note the takeover.

3. **Mark BE/FE ✅.** Nothing else happens per slice. Start whatever this slice was blocking.

### Step 2 - Consolidated quality round (once, over branch point → HEAD)

Precondition: every BE/FE cell is ✅.

1. **Integrate the whole story.** Dispatch `impl-frontend` once, scope `"whole-story integration - replace every slice's contract mock with the real backends, run integration/e2e tests, fix contract drift"`, with the full slice list and changed-file set. If drift belongs on a backend, re-dispatch `impl-backend` for that slice with the mismatch quoted. Skip `unfrozen - serial` slices (already integrated). Mark ✅.

2. **Review code and security in parallel.** In one batch, dispatch `agent_type: "prd-pr:code-reviewer"` and `agent_type: "prd-pr:security-reviewer"` over the full diff, each with the folder path and `04-task-plan.md`. The round passes only when **both** return `APPROVED`. On `FIXES_NEEDED` from either: re-dispatch the owning implementer(s) with the Blocker rows quoted verbatim, then re-dispatch only the reviewer(s) that flagged, scoped to the amended diff; loop until both approve. Non-blockers become PR follow-ups. Mark both rows ✅.

3. **Refactor.** Dispatch `agent_type: "prd-pr:impl-simplify"` once with the folder path, the branch-point ref and the changed-file list. It wraps the built-in `simplify` skill in its own context (a whole-story refactor read here would evict the plan docs and reports you still need), re-runs the suite and commits. Confirm its report shows a green suite (re-run it yourself if that line is missing); route any blocker under "Reported, not fixed" to the owning implementer. Mark ✅.

4. **Smoke.** Run every slice's `Smoke:` sequence from `04-task-plan.md` in slice order against the running stack. After a fix, re-run only the failed sequences. Mark ✅.

5. **Regression.** Run the project's full existing suite (unit, integration, component, pre-existing e2e) over the whole diff. Fix failures before marking ✅. Do not write or run the story's new browser e2e here; that is Phase 9.

6. **Capture product knowledge.** Invoke `context-updater` in the main session (never as a subagent) once for the whole story: behaviour implemented, domain rules enforced, config decisions, non-obvious design choices. Mark ✅.

7. **Checkpoint.** `git commit --allow-empty -m "checkpoint: {story} - all slices integrated after consolidated review/refactor/smoke"`. Mark ✅.

### Step 3 - Report

Slice-by-slice summary (behaviour, files), what the refactor changed, review/smoke/regression outcome, learning points, anything skipped or flagged, next steps.

## Phase 9 - Test Plan Walkthrough

Precondition: every cell in `07-progress.md` is ✅ (or `-`). Otherwise return to Phase 8.

Dispatch `agent_type: "prd-pr:test-plan-walker"` in a clean context (the walkthrough produces dozens of screenshots) with the folder path, branch name, app URL, and a pointer to where demo credentials live - never the credentials. It writes a Playwright spec per slice from `05-test-plan.md` (self-capturing screenshots), runs them headless, persists them into the project's e2e suite and writes `06-walkthrough.md`.

- `ALL_GREEN` → Phase 10.
- `FIXES_NEEDED` → re-dispatch the owning implementer per Blocker, then re-dispatch the walker scoped to **the affected slices only**; it re-runs those specs and amends `06-walkthrough.md`. Loop until green.
- `PARTIAL` → fix the environmental issue it names and re-dispatch with `Resume from: SLICE-NN step-NN`.

Non-blocker findings go into the PR body as follow-ups.

## Phase 10 - Branch Completion

Invoke `raise-pr`. It verifies the CI gate, checks the walkthrough artifacts (re-dispatching the walker if missing), offers merge / PR / keep / discard, embeds the walkthrough summary and screenshots in the PR body, cleans up the worktree, and in its Step 6 closes out the project's **backlog tracker** with the merge commit or PR number. That last step is the one the workflow used to drop: everything before it writes only inside `docs/new-feature/`, and a shipped story still reading `Ready` in the tracker gets rebuilt. If `raise-pr` finds status in more than one file, surface that to the user rather than updating them all.
