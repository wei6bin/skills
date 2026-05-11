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

2. Launch **2–3 `code-explorer` subagents in parallel** using the task tool with `agent_type: "prd-pr:code-explorer"`, each targeting a different aspect:
   - Subagent 1: *"Find features similar to [feature] and trace through their full implementation — entry points, handlers, services, data access, frontend. Return 5–10 key files."*
   - Subagent 2: *"Map the architecture and patterns for [domain area] — layers, naming conventions, DTO shapes, error handling, auth. Return 5–10 key files."*
   - Subagent 3 (if full-stack): *"Trace the frontend patterns for [feature area] — component structure, data fetching usage, form patterns, state. Return 5–10 key files."*

3. After subagents return, read all key files they identified.

4. Present a structured summary:
   - Reference implementation found (closest existing feature to follow)
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

## Phase 4 — Architecture Design

**Goal**: Design a concrete implementation plan, sliced vertically, before writing any documents.

1. Launch **1 `code-architect` subagent** using the task tool with `agent_type: "prd-pr:code-architect"`, providing full context from Phases 2–3:
   - Feature description, extracted ACs, answers from Phase 3
   - Reference implementation found in Phase 2
   - Loaded context files from `docs/project_context/`

2. Review the blueprint returned. Synthesise into a clear plan covering:
   - Slice list with demoable behaviour and AC coverage per slice
   - Tasks within each slice (ordered by layer dependency)
   - Files to create and files to modify (with exact paths)
   - API contracts (if new endpoints)
   - Data model changes (if any)

3. **Present the plan to the user and confirm before writing documents.** Confirming the slice list is the most important decision in this phase.

---

## Phase 5 — Write Documents

**Goal**: Produce 6 structured plan files in `docs/new-feature/{id}-{summary}/`.

**Workspace check — first thing in this phase, before any file is created.** This is the first phase that writes to disk. If you are not already in an isolated worktree on a feature branch, invoke the `git-worktrees` skill now, passing the feature slug as the intended branch name. The skill creates the worktree, checks out a new branch, runs project setup, and verifies a clean test baseline. Only proceed once it returns. (If a worktree was set up earlier in the session, skip this check.)

**Fallback when no `skill` tool is exposed.** Subagent dispatch may give you only `Read`, `Bash`, `Edit`, `Write`. In that case do *not* silently proceed on the current branch — fall back to creating the worktree manually via Bash:

```
git worktree add -b {feature-slug} {repo-root}/.worktrees/{feature-slug} {base-branch}
```

Always pass an **absolute path** for the worktree location — relative paths resolve against your current CWD, which may have drifted into another worktree from earlier `cd` calls and silently nest the new worktree inside it. Verify placement with `git worktree list` before writing any file. After creation, write all subsequent plan documents into the new worktree (use absolute paths in `Write` / `Edit`). If even `Bash` is unavailable, stop and ask the user — never silently proceed on the current branch and never rationalise the skip with "docs only".

Create the folder. Use the ticket ID if available (e.g. `US-1234-add-user-export`), otherwise use a short slug.

Write these files using the architecture blueprint from Phase 4:

| File | Contents |
|------|----------|
| `00-overview.md` | One-page summary: goal, scope, constraints, success criteria |
| `01-business-plan.md` | Problem statement, acceptance criteria (verbatim), stakeholders, out-of-scope |
| `02-technical-plan.md` | Architecture decisions, affected layers, API contracts, data changes, security, non-functional requirements |
| `03-implementation-plan.md` | A top-level **Change-Site Map** (every touched file × owning slice), then per slice: **reference patterns** (style hints) **and** **change sites** (file `path:line` anchor + target snippet for each touched file) **and** any data-model / API-contract notes. The change-site map carries no implied sequence — it is target geography the explorer already mapped, not a sequenced file-task list. The implementer still drives each AC behaviour through TDD; tests remain the spec, snippets are targets the tests drive toward. |
| `04-task-plan.md` | **One card per slice** — demoable behaviour, AC coverage, demo steps, type (AFK/HITL), layer-halves (BE / FE / both), blocked-by, rough story-point size. No `SLICE-NN.TASK-NN` table. ADO mapping: each slice = one ADO Task under the parent User Story; each layer-half = one impl-{layer} subagent dispatch. |
| `05-test-plan.md` | Test cases per AC, grouped by slice. Each slice must have at least one end-to-end test that exercises its demoable behaviour. Type (unit/integration/component/e2e), steps, expected outcome, rollback plan. |

Update or create `docs/new-feature/README.md` with an index entry for this enhancement.

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

**Goal**: Ship each slice end-to-end before starting the next, then simplify the changed code. The unit of work is the **slice**, not the layer.

### Step 1 — Loop over slices

For each slice in `04-task-plan.md`, in order:

1. **Implement backend half, then frontend half.** Per the slice's `Layers:` field, dispatch the relevant implementer subagent(s) using the task tool:
   - If `BE + FE`: dispatch `agent_type: "prd-pr:impl-backend"` with scope `"SLICE-NN backend half"`; wait; then dispatch `agent_type: "prd-pr:impl-frontend"` with scope `"SLICE-NN frontend half"`.
   - If `BE only` or `FE only`: dispatch only that implementer.

   Each implementer receives the slice card (demoable behaviour, AC list, reference patterns) — **not** a pre-listed file-task table. The implementer runs **TDD red-green-refactor against each AC behaviour in its layer-half**, discovering files as the tests demand them. It commits per behaviour: `feat({layer}): SLICE-NN — {short behaviour, e.g. "reject malformed NRIC with 422"}`.

   **Verify the implementer's Return Report** before moving on — confirm AC coverage and test counts match the slice card. If a section is missing or tests weren't actually run, re-dispatch the implementer with the gap, or finish the work directly and note the takeover.

2. **Simplify within the slice.** Dispatch `agent_type: "prd-pr:impl-simplify"` scoped to `"stay within SLICE-NN"`, passing the files changed during this slice.

3. **Run the slice's API smoke.** Execute the `Smoke:` sequence from the slice card against the running stack. If it fails, stop — do **not** proceed to e2e or context-updater. Re-dispatch the implementer with the failure, fix directly, or escalate. This catches the bug class unit tests miss (auth config, claim mapping, query binding, role-claim type) before HITL demo time.

4. **Verify the slice is demoable end-to-end.** Run the slice's e2e test from `05-test-plan.md`. If it fails, stop and fix before starting the next slice — do not roll problems forward.

5. **Capture product knowledge.** Dispatch `context-updater` once for the slice (BE + FE deltas combined), summarising: feature/UI behaviour implemented, domain rules enforced, config decisions made, design choices not obvious from the code.

6. **Mark the slice boundary.** `git commit --allow-empty -m "checkpoint: SLICE-NN demoable — {behaviour}"` so boundaries are visible in `git log`.

### Step 2 — Independent slices may run in parallel

When the plan flags slices as independent and a worktree is available, run multiple slice loops in parallel via separate worktrees. Sizing and independence rules are in the `vertical-slicing` skill.

### Step 3 — Report

After all slices complete, present:
1. **Slice-by-slice summary** — demoable behaviour, files changed, e2e test status per slice
2. What was simplified per slice
3. **Learning points** — patterns observed, conventions reinforced
4. Any slices skipped or flagged, with reason
5. Next steps (run full test suite, walk through e2e demos in a real browser, open PR, review commits)

---

## Phase 9 — Test Plan Walkthrough

**Goal**: drive `05-test-plan.md`'s end-to-end manual demos, screenshot each step, write `06-walkthrough.md` for Phase 10 to embed in the PR body.

**Pre-condition**: every slice in `04-task-plan.md` has a green e2e test from Phase 8 and a checkpoint commit. If anything is still red, return to Phase 8.

**Dispatch the `test-plan-walker` subagent** (`agent_type: "prd-pr:test-plan-walker"`) in a clean context — the walkthrough produces dozens of screenshots that would otherwise balloon the main session. Pass it: user-story folder path, current branch name, app URL, and a pointer to where demo credentials live (never the credentials themselves).

**Act on the Return Report verdict:**

- **`ALL_GREEN`** → proceed to Phase 10.
- **`FIXES_NEEDED`** → for each Blocker row, re-dispatch the appropriate implementer (`impl-frontend` / `impl-backend`) scoped to that slice with the issue description. After the implementer returns, re-dispatch `test-plan-walker` scoped to just the affected slices so it amends `06-walkthrough.md` and replaces only those screenshots. Loop until `ALL_GREEN`.
- **`PARTIAL`** → resolve the environmental issue the report names, then re-dispatch with `Resume from: SLICE-NN step-NN`.

Non-Blocker findings don't gate the PR — they get listed as follow-ups in the PR body.

---

## Phase 10 — Branch Completion

**Invoke the `raise-pr` skill.** It runs the test suite, re-dispatches the `test-plan-walker` subagent if walkthrough artifacts are missing, presents the 4-option choice (merge / PR / keep / discard), embeds the walkthrough summary + screenshots into the PR body for the PR option, and cleans up the worktree from Phase 5.
