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
2. Ask the user **all at once** (single message):
   - Short description of the feature (if not already provided)
   - Priority: High / Medium / Low
   - Parent Azure DevOps ticket ID (optional — e.g. US-1234)
3. If a ticket ID is provided, ask: *"Please paste the ticket content — title, description, acceptance criteria, any notes."*
   Extract and store: **Title · Problem statement · Acceptance Criteria (numbered) · Stakeholders · Constraints · Dependencies**
4. Confirm your understanding before proceeding.

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

3. Launch **2–3 `code-explorer` subagents in parallel** using the task tool with `agent_type: "prd-pr-copilot:code-explorer"`, each targeting a different aspect. **Seed each prompt with the anchors and entry IDs from step 2** so they start inside the right directories instead of searching blind:
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

Create the user-story folder path in `docs/new-feature/{id}-{summary}/`. Use the ticket ID if available (e.g. `US-1234-add-user-export`), otherwise use a short slug.

### Step 1 — Dispatch the architect (it designs *and* writes the docs)

Launch **1 `code-architect` subagent** using the task tool with `agent_type: "prd-pr-copilot:code-architect"`, providing full context from Phases 2–3 **and the absolute path to the user-story folder** you just chose:
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
2. Sanity-check cross-document consistency: every slice in `04-task-plan.md` has matching test cases in `05-test-plan.md` and change sites in `03-implementation-plan.md`; every `BE + FE` slice's `Contract:` also appears in `02-technical-plan.md`. Also verify the `## Dependency graph` edge table agrees with the cards — each `Blocked by:` matches its row, every blocker is a real slice ID, no cycle. A mismatch is a planning bug: fix the table and re-derive (don't just patch prose). ADO mapping stays manual: each slice = one ADO Task under the parent User Story; each layer-half = one impl-{layer} subagent dispatch.
3. Update or create `docs/new-feature/README.md` with an index entry for this enhancement.

---

## Phase 6 — Quality Review

**Goal**: Catch gaps and inconsistencies before handing off to development.

Launch **2 `plan-reviewer` subagents in parallel** using the task tool with `agent_type: "prd-pr-copilot:plan-reviewer"`, each reviewing from a different angle:
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
   - Create Azure DevOps tasks from `04-task-plan.md` — one ADO Task per slice under the parent User Story (manual — no automated ADO integration in Copilot)
   - Start implementation with **SLICE-01** (the walking skeleton)

---

> **Note:** Unlike the OpenCode version, there is no `/create-dev-ops-tasks` automation in GitHub Copilot.
> You must manually create ADO tasks from `04-task-plan.md` (one Task per slice under the parent User Story), or use the OpenCode dev-workflow for that step.

---

## Phase 8 — Slice-by-Slice Implementation

**Goal**: Implement every slice's layer-halves first — backend against the frozen contract, frontend against a **mock** of it, concurrently, **without integrating per slice**. Only *after* every slice is implemented, run one consolidated round that **integrates the whole story once**, then refactors and regression-tests it. Per-slice looping is for implementation only; integration/refactor/regression run once, over the whole diff. This is safe because each backend conformance-tests its own contract at build time, so deferring integration to the end takes N per-slice passes off the critical path. The story's browser-level e2e is **not** run here — it's a persisted Playwright spec run once in Phase 9 by the `test-plan-walker`, from the same pass that captures the PR screenshots.

### Step 0 — Model cost check

Before dispatching any implementation agent, check which model the current session is running on.

If the session model is `claude-opus-4.8` or higher, pause and warn the user:

> ⚠️ **Cost notice:** `impl-backend` and `impl-frontend` are configured for `claude-sonnet-4.6`, but your current session model is `claude-opus-4.8`. The global model setting overrides per-agent configuration, so these agents will run on Opus — roughly **5× more expensive** than intended.
>
> To use Sonnet for implementation, switch your session model to `claude-sonnet-4.6` now (via the model picker), then confirm. Or type **proceed** to continue on Opus anyway.

Wait for the user to confirm before dispatching implementation agents.

### Step 1 — Implement slices: parallel halves, parallel slices

**Two axes of parallelism apply here (both from the `vertical-slicing` skill) — use them; do not walk everything serially:**

- **Within a `BE + FE` slice**, the backend and frontend halves run **concurrently** against the slice's frozen `Contract:`.
- **Across slices**, every parallel-safe slice (`Blocked by: —`) runs **concurrently** in its own worktree. Only serialise a slice behind another when its `Blocked by:` names it.

**Schedule from the `## Dependency graph` block in `04-task-plan.md`** — don't re-derive dependencies by eye. Its edge table is authoritative; combine it with the ledger's done-state:

- **Ready-frontier** = slices whose every `Blocked by:` is done (roots — `—` — start ready). Start each ready slice that has a free worktree slot.
- **Refresh the frontier the instant a blocker's BE/FE both complete** — start the unblocked slice now, don't wait for its wave. (Waves are the coarse batch view; frontier-driven is never slower.)
- **Ready slices > free slots → start critical-path slices first** (the block names it); it sets the minimum wall-clock. Break ties by larger size.

For each slice you start:

1. **Dispatch the layer-halves concurrently.** Per the slice's `Layers:` field, dispatch the implementer subagent(s) using the task tool **in a single batch so they run in parallel**:
   - If `BE + FE`: dispatch `agent_type: "prd-pr-copilot:impl-backend"` (scope `"SLICE-NN backend half — implement AND conformance-test the frozen contract"`) **and** `agent_type: "prd-pr-copilot:impl-frontend"` (scope `"SLICE-NN frontend half — build against the frozen contract with a typed mock; stay on the mock, integration is one whole-story pass in Step 2"`) together. Both get the slice card with the frozen `Contract:`.
     - **Exception**: if the card says `Contract: unfrozen — serial`, fall back to BE first, then FE — that slice's response shape genuinely can't be known until the backend exists.
   - If `BE only` or `FE only`: dispatch only that implementer.

   Each implementer receives the slice card (behaviour/outcome, AC list, reference patterns) — **not** a pre-listed file-task table. It runs **TDD red-green-refactor against each AC behaviour in its layer-half**, discovering files as the tests demand them. It commits per behaviour: `feat({layer}): SLICE-NN — {short behaviour, e.g. "reject malformed NRIC with 422"}`, and captures product knowledge via `context-updater` itself before returning.

   > **No per-slice integration.** The FE half stays on its mock — don't re-dispatch it to wire in the real backend now; that's one whole-story pass in Step 2. (The `unfrozen — serial` slice is the only FE that touches the real backend in Step 1.)

2. **Move on to the next slice.** Nothing else happens per slice — no integration, no simplify, no e2e, no checkpoint commit. Those run once, in the consolidated round below. Start any slice this one was blocking.

**Worktree note:** running parallel-safe slices concurrently needs a worktree per concurrent slice (they touch disjoint files by definition, but separate worktrees keep their commits and test runs from interleaving). If only one worktree is available, run parallel-safe slices sequentially but still parallelise each slice's BE/FE halves. Sizing and independence rules are in the `vertical-slicing` skill.

### Step 2 — Consolidated quality round (once, after every slice is implemented)

**Precondition**: every slice's BE/FE half is implemented. This round runs exactly once, over the accumulated diff from the branch point to `HEAD` — not once per slice.

1. **Integrate the whole story once.** Dispatch `agent_type: "prd-pr-copilot:impl-frontend"` once, scoped to `"whole-story integration — replace every slice's contract mock with the real backends, run integration/e2e tests, fix any contract drift"`, passing the full slice list and the changed-file set. Each backend already conformance-tested its contract, so this is mostly mechanical wiring; if a drift fix belongs on the backend, re-dispatch `impl-backend` for that slice with the mismatch quoted. (Slices flagged `unfrozen — serial` already integrated in Step 1 — skip those.)
2. **Refactor / simplify the whole story.** Dispatch `agent_type: "prd-pr-copilot:impl-simplify"` once, scoped to `"whole story — all files changed since the branch point"`, passing the full changed-file list. Runs only after integration, so it's cleaning up code already wired to the real backends.
3. **Run the full test suite as a regression gate.** Over the whole diff, run the project's existing test suite (unit + integration + component + any pre-existing e2e) in one pass — the command comes from `docs/project_context/` or the slice cards. This catches cross-slice breakage the per-slice runs in Step 1 couldn't see. If any fails, fix it (re-dispatch the owning implementer or fix directly) and re-run the failed test(s) — do not restart the round. The story's *new* browser-level e2e specs are authored and run in Phase 9 — do **not** try to write or run them here.
4. **Mark completion.** `git commit --allow-empty -m "checkpoint: {story} — all slices integrated after consolidated integration + refactor + regression"`.

### Step 3 — Report

After implementation and the consolidated quality round both complete, present:
1. **Slice-by-slice summary** — behaviour/outcome and files changed per slice
2. What the consolidated refactor pass changed, across the story
3. The consolidated regression outcome (the browser-level e2e runs in Phase 9)
4. **Learning points** — patterns observed, conventions reinforced
5. Any slices skipped or flagged, with reason
6. Next steps (run full test suite, walk through e2e demos in a real browser, open PR, review commits)

---

## Phase 9 — Test Plan Walkthrough

**Goal**: turn `05-test-plan.md`'s end-to-end demos into **persisted Playwright specs per slice** that produce their own screenshots, run headless, and are committed to the project's existing e2e suite — so verification is fast and deterministic and the story's use case becomes a permanent regression test. The walker is **spec-first**: it writes the spec (with `page.screenshot()` at each demoable checkpoint), runs it headless for pass/fail, and only drops to LLM-driven browsing (`agent-browser`) to repair a failing locator. That is what keeps this phase from ballooning — the old approach hand-drove every micro-step through the browser and took ~an hour per pass. Two outputs: (1) `06-walkthrough.md` + spec-produced screenshots for Phase 10's PR body, and (2) the committed specs.

**Pre-condition**: the consolidated whole-story integration + refactor + regression round from Phase 8 is green over the whole diff (every FE half is on the real backends, not its mock), and the single consolidated checkpoint commit has landed. If anything is still red, return to Phase 8.

**Dispatch the `test-plan-walker` subagent** (`agent_type: "prd-pr-copilot:test-plan-walker"`) in a clean context — the walkthrough produces dozens of screenshots that would otherwise balloon the main session. Pass it: user-story folder path, current branch name, app URL, and a pointer to where demo credentials live (never the credentials themselves).

**Act on the Return Report verdict:**

- **`ALL_GREEN`** → proceed to Phase 10.
- **`FIXES_NEEDED`** → for each Blocker row, re-dispatch the appropriate implementer (`impl-frontend` / `impl-backend`) scoped to that slice with the issue description. After the implementer returns, re-dispatch `test-plan-walker` scoped to **just the affected slices** — it re-runs only those slices' specs (regenerating only their screenshots) and amends `06-walkthrough.md`. It must **not** re-walk passing slices: re-running a green spec is seconds, re-driving a whole slice is not. Loop until `ALL_GREEN`.
- **`PARTIAL`** → resolve the environmental issue the report names, then re-dispatch with `Resume from: SLICE-NN step-NN`.

Non-Blocker findings don't gate the PR — they get listed as follow-ups in the PR body.

---

## Phase 10 — Branch Completion

**Invoke the `raise-pr` skill.** It runs the test suite, re-dispatches the `test-plan-walker` subagent if walkthrough artifacts are missing, presents the 4-option choice (merge / PR / keep / discard), embeds the walkthrough summary + screenshots into the PR body for the PR option, and cleans up the worktree from Phase 4.
