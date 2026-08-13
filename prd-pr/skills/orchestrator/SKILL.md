---
name: orchestrator
description: Entry point for new feature or enhancement work. Runs the full 10-phase new-enhancement workflow — discovery, parallel codebase exploration, clarifying questions, architecture design, document creation, plan review, summary, slice-by-slice implementation, end-to-end test-plan walkthrough with screenshots, and branch completion. Writes structured plan files to docs/new-feature/{id}-{summary}/. Use this skill whenever the user says "work on this user story", "new enhancement", "implement this feature", "plan this feature", or describes a feature to build. Even if the user doesn't explicitly mention the workflow, trigger this skill when they paste a user story, acceptance criteria, or an Azure DevOps ticket.
---

# Dev Workflow — New Enhancement

You are guiding a developer through a new feature or enhancement. Follow these phases in order. Track progress with a numbered todo list.

**Announce at start:** "I'm using the orchestrator skill to guide this enhancement through the full workflow."

---

## Phase 1 — Discovery

**Goal**: Understand what needs to be built and gather metadata.

1. Create a todo list covering all 10 phases.
2. Ask the user for a short description of the feature, if not already provided.
   Extract and store: **Title · Problem statement · Acceptance Criteria (numbered) · Stakeholders · Constraints · Dependencies**
3. Confirm your understanding before proceeding.

---

## Phase 2 — Codebase Exploration

**Goal**: Understand relevant existing code and patterns before designing anything.

1. Check if `docs/project_context/` exists and is populated.
   - If missing or empty → invoke the `codebase-context-builder` skill to generate it, then continue.
   - If populated → read `docs/project_context/00_index.md` and load 2–4 relevant files.

2. **Query the knowledge graph before searching the tree.** If `docs/project_context/prod_spec/graph.md` exists, read it in full — it is one file, deliberately small — and resolve the request against it:
   - **Capability map** → which existing capabilities this feature touches, and their **code anchors** (directories). These are your search starting points; do not rediscover them.
   - **Entity map** → every domain rule already constraining the entities involved.
   - **Edges** → any `supersedes` / `amends` edge in scope. An overturned decision reads exactly like a current one in the prose, so applying a superseded entry is a real and likely failure mode. Also read `conflicts-with` edges: two deliberate answers to the same question mean you must pick a side knowingly, not "reconcile" them.
   - **Open questions** → whether this work is blocked, deferred, or gated on a business decision. If it is, say so **now**, before designing anything.

   Then load only the entry IDs those rows cite (`grep -n "\[DR-114\]" docs/project_context/prod_spec/*.md`) — typically a couple of hundred lines, not the whole folder.

   If there is no `graph.md`, skip this step; consider invoking `context-updater` afterwards so the next feature has one.

3. Launch **2–3 `code-explorer` subagents in parallel** using the task tool with `agent_type: "prd-pr:code-explorer"`, each targeting a different aspect. **Seed each prompt with the anchors and entry IDs from step 2** so they start inside the right directories instead of searching blind:
   - Subagent 1: *"Find features similar to [feature] and trace through their full implementation — entry points, handlers, services, data access, frontend. Start from [anchors]. Return 5–10 key files."*
   - Subagent 2: *"Map the architecture and patterns for [domain area] — layers, naming conventions, DTO shapes, error handling, auth. Start from [anchors]. Return 5–10 key files."*
   - Subagent 3 (if full-stack): *"Trace the frontend patterns for [feature area] — component structure, data fetching usage, form patterns, state. Start from [anchors]. Return 5–10 key files."*

4. After subagents return, read all key files they identified.

5. Present a structured summary:
   - Reference implementation found (closest existing feature to follow)
   - **Capabilities and entities this touches** (graph IDs), and **any superseded decision or open question in scope**
   - Architecture layers affected
   - Reusable components, hooks, services, or utilities
   - Conventions to follow (naming, DTO shape, error handling pattern)

---

## Phase 3 — Clarifying Questions

**Goal**: Resolve every ambiguity before designing. **Do not skip.**

Interview the user relentlessly about every aspect of the plan until you reach a shared understanding. Walk down each branch of the design tree, resolving dependencies between decisions one-by-one.

1. Review the codebase findings and the feature request / ticket ACs.
2. Identify underspecified areas: edge cases, error handling, role/permission boundaries, data model questions, integration points, out-of-scope boundaries.
3. **If a question can be answered by exploring the codebase, explore the codebase instead** — don't spend the user's attention on something the code already settles. Note your finding as an assumption and move on.
4. **Ask the questions one at a time.** For each remaining ambiguity:
   - State the question.
   - State your **recommended answer** with a one-line rationale.
   - End your turn and wait for the user's reply (a "use your recommendation" answer is fine).
   - Let the answer inform the next question — later questions depend on earlier answers.
5. Stop when no material ambiguity remains. Summarise the resolved decisions before Phase 4.

If the user says "whatever you think is best" → state your assumption explicitly and ask for confirmation.

---

## Phase 4 — Architecture Design & Documents

**Goal**: Design a concrete implementation plan, sliced vertically, and get the six plan documents written — with the doc-writing done by the architect subagent, not transcribed by you.

### Step 0 — Workspace (worktree) — do this before dispatching the architect

The architect writes the six plan files to disk, so the isolated worktree must exist first. If you are not already in an isolated worktree on a feature branch, invoke the `git-worktrees` skill now, passing the feature slug as the intended branch name. It creates the worktree, checks out a new branch, runs project setup, and verifies a clean test baseline. Only proceed once it returns. (If a worktree was set up earlier in the session, skip this.)

**Fallback when no `skill` tool is exposed.** Subagent dispatch may give you only `Read`, `Bash`, `Edit`, `Write`. In that case do *not* silently proceed on the current branch — fall back to creating the worktree manually via Bash:

```
git worktree add -b {feature-slug} {repo-root}/.worktrees/{feature-slug} {base-branch}
```

Always pass an **absolute path** for the worktree location — relative paths resolve against your current CWD, which may have drifted into another worktree from earlier `cd` calls and silently nest the new worktree inside it. Verify placement with `git worktree list`. If even `Bash` is unavailable, stop and ask the user — never silently proceed on the current branch.

Create the user-story folder path using a short slug: `docs/new-feature/{id}-{summary}/` (e.g. `docs/new-feature/usr-012-pwa-shell/`).

### Step 1 — Dispatch the architect (it designs *and* writes the docs)

Launch **1 `code-architect` subagent** using the task tool with `agent_type: "prd-pr:code-architect"`, providing full context from Phases 2–3 **and the absolute path to the user-story folder** you just chose:
- Feature description, extracted ACs, answers from Phase 3
- Reference implementation found in Phase 2
- Loaded context files from `docs/project_context/`
- The folder path — instruct it to write `00-overview.md` … `05-test-plan.md` **directly** into it

The architect designs the blueprint and **writes all six documents itself**. You do **not** transcribe a returned blueprint into files — that hand-copy used to cost ~20 minutes of dead main-agent time between design and review and dropped detail every time it was abbreviated. The architect's final message is a short **manifest**: a one-line summary, the slice list (ID · behaviour · AC · Layers · Contract · Blocked-by · size), the six file paths it wrote, and key risks.

### Step 2 — Review and confirm the slice list

1. **Read the six documents the architect wrote** (they are the source of truth now — the manifest is only a table of contents). Spot-check that each slice has a card in `04-task-plan.md`, a frozen `Contract:` where `Layers: BE + FE`, and concrete demo steps in `05-test-plan.md`. Confirm `04-task-plan.md` opens with a `## Dependency graph` block whose edge table matches the cards' `Blocked by:` lines.
2. **Present the plan to the user and confirm before implementation.** Confirming the slice list — and which slices are parallel-safe (`Blocked by: —`) — is the most important decision in this phase. Show the **Waves and Critical path** from the block alongside the slice list — the user sees what runs concurrently and which chain sets the wall-clock.
3. If the user wants changes, edit the docs directly (small changes) or re-dispatch the architect with the correction (structural changes). Do not proceed to Phase 6 until the slice list is confirmed.

---

## Phase 5 — Finalize Documents

**Goal**: Confirm the six plan files are complete and index them. (The architect already wrote them in Phase 4 — this phase is verification, not authoring.)

1. Verify all six files exist and are non-empty in `docs/new-feature/{id}-{summary}/`. If any is missing or a stub, re-dispatch the architect to complete it — do not fill it in by hand-transcription (that reintroduces the gap this restructure removed).
2. Sanity-check cross-document consistency: every slice in `04-task-plan.md` has matching test cases in `05-test-plan.md` and change sites in `03-implementation-plan.md`; every `BE + FE` slice's `Contract:` also appears in `02-technical-plan.md`. Also verify the `## Dependency graph` edge table agrees with the cards — each `Blocked by:` matches its row, every blocker is a real slice ID, no cycle. A mismatch is a planning bug: fix the table and re-derive (don't just patch prose).
3. Update or create `docs/new-feature/README.md` with an index entry for this enhancement.

---

## Phase 6 — Quality Review

**Goal**: Catch gaps and inconsistencies before handing off to development.

Launch **2 `plan-reviewer` subagents in parallel** using the task tool with `agent_type: "prd-pr:plan-reviewer"`, each reviewing from a different angle:
- Reviewer 1: *"Review `docs/new-feature/{folder}/` focusing on AC coverage, security, edge cases, and business/technical plan consistency."*
- Reviewer 2: *"Review `docs/new-feature/{folder}/` focusing on task completeness, dependency ordering, test coverage, and estimate reasonableness."*

Present the consolidated review findings. Fix any critical or important issues in the documents.

---

## Phase 7 — Summary

**Goal**: Confirm completion and orient the developer for implementation.

Present:
1. Path to the generated folder: `docs/new-feature/{folder}/`
2. Key decisions made (architecture choices, assumptions from Phase 3)
3. Risks flagged by the reviewers
4. Next steps:
   - Review the 6 plan documents
   - Create Azure DevOps tasks from `04-task-plan.md` — one ADO Task per slice under the parent User Story (manual)
   - Start implementation with **SLICE-01** (the walking skeleton)

---

## Phase 8 — Slice-by-Slice Implementation

**Goal**: Implement every slice's layer-halves first — BE against the frozen contract, FE against a **mock** of it, concurrently, **without integrating per slice**. Only *after* every slice is implemented, run one consolidated round that **integrates the whole story once**, then reviews, refactors, smokes, and regression-tests it. Per-slice looping is for implementation only; integration/review/refactor/smoke/regression run once, over the whole diff. This is safe because each backend conformance-tests its own contract at build time, so deferring integration to the end takes N per-slice passes off the critical path. The story's browser-level e2e is **not** run here — it's a persisted Playwright spec run once in Phase 9 by the `test-plan-walker`, from the same pass that captures the PR screenshots.

### Step 0 — Progress ledger (create or resume)

Loop position must survive compaction and session restarts — the plan docs are durable but "which step of which slice am I on" is not, unless you write it down.

- **If `docs/new-feature/{folder}/07-progress.md` already exists**: you are resuming. Read it, cross-check the last ✅ against `git log --oneline` (the `feat(...)` commits and the single consolidated checkpoint are the ground truth if the ledger is stale). If any slice's row in the **per-slice implementation** table has an ⬜ in BE/FE, resume in **Step 1** at that slice. Once every slice's BE/FE is ✅, resume in **Step 2** at the first ⬜ row of the **Final QA round** table, in the order the table lists them. Do not redo completed steps.
- **If it does not exist**: create it now — one row per slice for implementation, and a *separate*, single-row-per-step table for the consolidated round (not one row per slice — these steps run once, not per slice):

```markdown
# Progress — {id}-{summary}

## Per-slice implementation

| Slice | BE | FE |
|-------|----|----|
| SLICE-01 | ⬜ | ⬜ |

## Final QA round (once, after every slice above is implemented)

| Step | Status |
|------|--------|
| Integration (whole story — point every FE at the real backends, fix contract drift) | ⬜ |
| Code review (full diff, branch point → HEAD) | ⬜ |
| Security review (full diff, branch point → HEAD) | ⬜ |
| Refactor / simplify (whole story) | ⬜ |
| Smoke (every slice's smoke sequence, consolidated) | ⬜ |
| Test suite / regression (whole diff — unit + integration + any existing e2e) | ⬜ |
| Context capture | ⬜ |
| Checkpoint commit | ⬜ |
```

Statuses: `⬜` pending · `✅` done · `❌` failed/blocked (add a one-line note under the table). Mark N/A cells `—` (e.g. FE on a BE-only slice). **Update a row immediately after it completes — not in batches.** This file is orchestrator-owned: implementer/reviewer subagents must not write to it.

### Step 1 — Implement slices: parallel halves, parallel slices

**Two axes of parallelism apply here (both from the `vertical-slicing` skill) — use them; do not walk everything serially:**

- **Within a `BE + FE` slice**, the backend and frontend halves run **concurrently** against the slice's frozen `Contract:`.
- **Across slices**, every parallel-safe slice (`Blocked by: —`) runs **concurrently** in its own worktree. Only serialise a slice behind another when its `Blocked by:` names it.

**Schedule from the `## Dependency graph` block in `04-task-plan.md`** — don't re-derive dependencies by eye. Its edge table is authoritative; combine it with the ledger's `✅` state:

- **Ready-frontier** = slices whose every `Blocked by:` is `✅` (roots — `—` — start ready). Start each ready slice that has a free worktree slot.
- **Refresh the frontier the instant a blocker's BE/FE both go ✅** — start the unblocked slice now, don't wait for its wave. (Waves are the coarse batch view; frontier-driven is never slower.)
- **Ready slices > free slots → start critical-path slices first** (the block names it); it sets the minimum wall-clock. Break ties by larger size.

For each slice you start:

1. **Dispatch the layer-halves concurrently.** Per the slice's `Layers:` field, dispatch the implementer subagent(s) using the task tool **in a single batch so they run in parallel**:
   - If `BE + FE`: in one batch, dispatch `agent_type: "prd-pr:impl-backend"` (scope `"SLICE-NN backend half — implement AND conformance-test the frozen contract"`) **and** `agent_type: "prd-pr:impl-frontend"` (scope `"SLICE-NN frontend half — build against the frozen contract with a typed mock; stay on the mock, integration is one whole-story pass in Step 2"`). Both get the slice card with the frozen `Contract:`.
     - **Exception**: if the card says `Contract: unfrozen — serial`, fall back to BE first, then FE — that slice's response shape genuinely can't be known until the backend exists.
   - If `BE only` or `FE only`: dispatch only that implementer.
   - **Append the lean mode to every implementer scope**, derived from the slice card's story-point size: `lean: lite` for 1–2 points, `lean: full` for 3+ (the default). Large slices (8+ / spike) still get `full` — the implementer flags over-scope in its Return Report rather than dropping ACs; a slice never silently loses an AC to laziness. Example scope: `"SLICE-03 backend half — lean: full"`. This tunes reuse-ladder strictness only; AC coverage is unchanged and still verified below.

   Each implementer receives the slice card (behaviour/outcome, AC list, contract, reference patterns) — **not** a pre-listed file-task table. It runs **TDD red-green-refactor against each AC behaviour in its layer-half**, discovering files as the tests demand them. It commits per behaviour: `feat({layer}): SLICE-NN — {short behaviour, e.g. "reject malformed NRIC with 422"}`.

   > **No per-slice integration.** The FE half stays on its mock — don't re-dispatch it to wire in the real backend now; that's one whole-story pass in Step 2. (The `unfrozen — serial` slice is the only FE that touches the real backend in Step 1.)

2. **Verify each Return Report independently** before marking the slice done. The report was written by the agent it describes — never accept its test counts on trust:
   - Run the relevant test suite yourself via Bash (the command comes from `docs/project_context/` or the slice card) and compare actual pass/fail counts against the report — for a BE+FE slice, run both the backend suite (including its contract-conformance tests) and the frontend suite (against its mock).
   - Confirm AC coverage: every AC the slice card assigns to a layer-half appears in the report with a named backing test.
   - On any mismatch — fewer tests than reported, failures the report calls green, missing AC rows — re-dispatch the owning implementer with the discrepancy quoted verbatim, or finish the work directly and note the takeover. A missing report section is treated the same as a mismatch.

3. **Mark BE/FE ✅ for this slice in the per-slice implementation table.** Nothing else happens per slice — no integration, no simplify, no review, no smoke, no e2e, no context capture, no checkpoint commit. Move on: start any slice this one was blocking.

**Worktree note:** running parallel-safe slices concurrently needs a worktree per concurrent slice (they touch disjoint files by definition, but separate worktrees keep their commits and test runs from interleaving). If only one worktree is available, run parallel-safe slices sequentially but still parallelise each slice's BE/FE halves. Sizing and independence rules are in the `vertical-slicing` skill.

### Step 2 — Consolidated quality round (once, after every slice is implemented)

**Precondition**: every slice's BE/FE cells in the per-slice table are ✅. This round runs exactly once, over the accumulated diff from the branch point to `HEAD` — not once per slice.

1. **Integrate the whole story once.** Dispatch `agent_type: "prd-pr:impl-frontend"` once, scoped `"whole-story integration — replace every slice's contract mock with the real backends, run integration/e2e tests, fix any contract drift"`, passing the full slice list and changed-file set. Each backend already conformance-tested its contract, so this is mostly mechanical wiring; if drift belongs on the backend, re-dispatch `impl-backend` for that slice with the mismatch quoted. Mark "Integration" ✅ once every FE is on the real backend and its integration tests pass. (Skip `unfrozen — serial` slices — already integrated in Step 1.)

2. **Review the whole story — code and security, in parallel.** In one batch (so they run concurrently), dispatch two independent reviewers over the full diff (branch point → `HEAD`), each also given the user-story folder path and `04-task-plan.md` so it can map files back to ACs and slices:
   - `agent_type: "prd-pr:code-reviewer"` — the independent check on self-graded work: AC *intent* vs test assertions, error paths, convention adherence, and test author-bias.
   - `agent_type: "prd-pr:security-reviewer"` — the adversarial check on the threat surface: authorisation, input validation, injection, secrets/PII exposure, and unsafe dependencies (reads the threat model in `02-technical-plan.md`).

   Act on the **combined** verdict — the round passes only when *both* return `APPROVED`:
   - **Both `APPROVED`** → proceed to the refactor.
   - **Either `FIXES_NEEDED`** → re-dispatch whichever implementer(s) own the flagged files (`impl-backend` / `impl-frontend`) with the Blocker rows from both reports quoted verbatim, then re-dispatch **only the reviewer(s) that flagged issues**, scoped to the amended diff. Loop until both are `APPROVED`. Non-blocker rows don't gate — collect them as PR follow-ups.
   Mark the "Code review" and "Security review" rows ✅.

3. **Refactor / simplify the whole story.** Dispatch `agent_type: "prd-pr:impl-simplify"` once, scoped to `"whole story — all files changed since the branch point"`, passing the full changed-file list. Runs only after review approval, so it's cleaning up code already checked for correctness. Mark the "Refactor / simplify" row ✅.

4. **Run the consolidated smoke.** Execute every slice's `Smoke:` sequence from `04-task-plan.md`, in slice order, against the running stack, in one pass. If any step fails, fix it (re-dispatch the owning implementer or fix directly) and re-run only the failed sequence(s) — do not restart the whole round. Mark the "Smoke" row ✅ once every sequence passes.

5. **Run the full test suite as a regression gate.** Over the whole diff, run the project's existing test suite (unit + integration + component + any pre-existing e2e) in one pass — the command comes from `docs/project_context/` or the slice cards. This catches cross-slice breakage the per-slice runs in Step 1 couldn't see. Fix any failure before marking the row ✅. The story's *new* browser-level e2e specs are authored and run in Phase 9 — do **not** try to write or run them here.

6. **Capture product knowledge once.** Invoke the `context-updater` skill (main-session, not a subagent) once for the whole story, summarising all slices together: feature/UI behaviour implemented, domain rules enforced, config decisions made, design choices not obvious from the code. Mark the "Context capture" row ✅.

7. **Mark completion.** `git commit --allow-empty -m "checkpoint: {story} — all slices integrated after consolidated review/refactor/smoke/e2e"`. Mark the "Checkpoint commit" row ✅.

### Step 3 — Report

After implementation and the consolidated quality round both complete, present:
1. **Slice-by-slice summary** — behaviour/outcome and files changed per slice
2. What the consolidated refactor pass changed, across the story
3. The consolidated review/smoke/regression outcome (the browser-level e2e runs in Phase 9)
4. **Learning points** — patterns observed, conventions reinforced
5. Any slices skipped or flagged, with reason
6. Next steps (run full test suite, walk through e2e demos in a real browser, open PR, review commits)

---

## Phase 9 — Test Plan Walkthrough

**Goal**: turn `05-test-plan.md`'s end-to-end demos into **persisted Playwright specs per slice** that produce their own screenshots, run headless, and are committed to the project's existing e2e suite — so verification is fast and deterministic and the story's use case becomes a permanent regression test. The walker is **spec-first**: it writes the spec (with `page.screenshot()` at each demoable checkpoint), runs it headless for pass/fail, and only drops to LLM-driven browsing to repair a failing locator. That is what keeps this phase from ballooning — the old approach hand-drove every micro-step through the browser and took ~an hour per pass. Two outputs: (1) `06-walkthrough.md` + spec-produced screenshots for Phase 10's PR body, and (2) the committed specs.

**Pre-condition**: in `07-progress.md`, every slice's BE/FE cells are ✅ *and* every row of the Final QA round table (integration, code review, security review, refactor, smoke, test-suite regression, context capture, checkpoint) is ✅. If any cell is still ⬜ or ❌, return to Phase 8.

**Dispatch the `test-plan-walker` subagent** (`agent_type: "prd-pr:test-plan-walker"`) in a clean context — the walkthrough produces dozens of screenshots that would otherwise balloon the main session. Pass it: user-story folder path, current branch name, app URL, and a pointer to where demo credentials live (never the credentials themselves).

**Act on the Return Report verdict:**

- **`ALL_GREEN`** → proceed to Phase 10.
- **`FIXES_NEEDED`** → for each Blocker row, re-dispatch the appropriate implementer (`impl-frontend` / `impl-backend`) scoped to that slice with the issue description. After the implementer returns, re-dispatch `test-plan-walker` scoped to **just the affected slices** — it re-runs only those slices' specs (regenerating only their screenshots) and amends `06-walkthrough.md`. It must **not** re-walk passing slices: re-running a green spec is seconds, re-driving a whole slice is not. Loop until `ALL_GREEN`.
- **`PARTIAL`** → resolve the environmental issue the report names, then re-dispatch with `Resume from: SLICE-NN step-NN`.

Non-Blocker findings don't gate the PR — they get listed as follow-ups in the PR body.

---

## Phase 10 — Branch Completion

**Invoke the `raise-pr` skill.** It runs the test suite, re-dispatches the `test-plan-walker` subagent if walkthrough artifacts are missing, presents the 4-option choice (merge / PR / keep / discard), embeds the walkthrough summary + screenshots into the PR body for the PR option, and cleans up the worktree from Phase 4.
