---
name: context-updater
description: Updates docs/project_context/prod_spec/ after implementation - captures product decisions, domain rules, config choices and feature behaviour in prose, and maintains prod_spec/graph.md, the knowledge graph a later agent reads first to answer "what do we already have, and where do I start?". Source code changes are excluded. Run in the main session after any implementation session.
allowed-tools: Read, Grep, Glob, Write, Edit, Bash, AskUserQuestion
---

# Context Updater

Two outputs under `docs/project_context/prod_spec/`, maintained in the same pass:

1. **Prose files** - `features.md`, `domain_rules.md`, `decisions.md`, `config_decisions.md`: durable product knowledge in plain English, free of code.
2. **`graph.md`** - a compact typed index over those entries: capabilities, the entities they touch, which entries supersede which, and coarse code anchors. A later agent reads it first and usually needs only the twenty lines of prose it points to.

## What belongs in the prose

What an engineer holds in their head, not what a diff shows: domain rules and state transitions, business invariants, config values with rationale, feature behaviour, integration rules, design decisions with the trade-off. Never file paths, class names, signatures, schemas, snippets or package versions.

The one exception is `graph.md`, where each capability carries **directory-level anchors** (`backend/src/Api/Features/Roster/`), never `file.cs:412`. Directories move rarely; line numbers are wrong by the next commit.

## Entry IDs

Every prose heading carries a stable ID: `## [DR-045] Roster drafts - overlapping time for the same doctor is rejected`. Prefixes: `FT-` features, `DR-` domain rules, `DC-` decisions, `CFG-` config. IDs are monotonic and permanent, never renumbered or reused; heading text may change, the ID may not. Match on ID, not heading, when deciding update-vs-append.

```bash
# next free number
grep -ho '\[\(FT\|DR\|DC\|CFG\)-[0-9]*\]' docs/project_context/prod_spec/*.md | sort -t- -k1,1 -k2,2n | tail -20
# resolve a reference
grep -n "\[DR-045\]" docs/project_context/prod_spec/*.md
```

## Phase 0 - Bootstrap the graph (once per repo)

When `prod_spec/` has prose but no `graph.md` or no IDs: script the ID stamping into every heading in file order, read all four prose files in full (the `supersedes`/`conflicts-with` edges are locked in the prose as English and only a full read finds them), and write `graph.md` per the schema below. A forward-only graph over an established `prod_spec/` leaves the accumulated knowledge invisible.

## Phase 1 - Identify what was built

From the session or the calling agent's summary: the capability implemented, domain rules enforced, config values and why, design choices not obvious from code, invariants now relied on, **which earlier entries this session contradicted, narrowed or replaced** (the most-skipped question, and the one whose omission does the most damage), and which directories the work landed in. Ask with `AskUserQuestion` if unsure.

## Phase 2 - Locate or seed `prod_spec/`

If missing, create `graph.md`, `index.md`, `features.md`, `domain_rules.md`, `config_decisions.md`, `decisions.md`. `index.md` is a file manifest only, never a session log.

## Phase 3 - Prose entries

Append, or update in place by ID:

```markdown
## [FT-nnn] Feature Name
**Added**: YYYY-MM-DD
**User behaviour**: what the user can now do
**Key rules**: bullets

## [DR-nnn] Entity - Rule Name
**Rule**: one sentence
**Rationale**: why
**Where enforced**: domain / API / DB constraint / all

## [CFG-nnn] Setting
**Value**: value or range
**Rationale**: why
**Owner**: team or component

## [DC-nnn] Decision Title
**Date**: YYYY-MM-DD
**Context**: the trade-off
**Decision**: what was chosen
**Rationale**: why
**Consequences**: what follows
```

**Superseding**: never delete or rewrite the old entry; the overturned reasoning is what stops the next agent re-proposing it. Add `**Status**: SUPERSEDED by [DC-078] (YYYY-MM-DD)` (or `AMENDED by [DR-102]` when narrowed) above the unchanged body, and record the edge in the graph.

## Phase 4 - `graph.md`

One file, read whole; keep it under ~40KB by tightening, not splitting. Five sections:

**1. Capability map** - one row per coherent unit of product behaviour, not per story; several stories usually converge on one row.

```markdown
| ID | Capability | Surfaces | Entities | Stories | Anchors | Rules | Decisions | Config | Status |
|---|---|---|---|---|---|---|---|---|---|
| CAP-07 | Roster publish + SAP sync | admin-portal, api | RosterSlot, Publication | usr-061, usr-062 | backend/src/Api/Features/Roster/, frontend/apps/admin-portal/src/pages/roster/ | DR-036, DR-041 | DC-030, DC-078 | CFG-012 | Live |
```

Entities are the join keys; use identical names across rows. Status: `Live`, `Partial`, `Deferred`, `Dropped`, `Superseded`.

**2. Entity map** - the reverse index.

```markdown
| Entity | Constrained by | Touched by | Notes |
|---|---|---|---|
| RosterSlot | DR-036, DR-041 | CAP-06, CAP-07 | Draft and published slots are separate tables |
```

**3. Edges** - every non-containment relationship, typed.

```markdown
| From | Type | To | Note |
|---|---|---|---|
| DC-078 | supersedes | DC-030 | Coverage guard now enforced everywhere |
| CAP-09 | depends-on | CAP-07 | Cannot export an unpublished roster |
| DR-055 | conflicts-with | DR-012 | Same quirk, two features chose differently, both deliberate |
```

Vocabulary: `supersedes`, `amends`, `resolves` (an entry's predicted follow-up arrived), `depends-on`, `extends`, `constrains` (a cross-cutting invariant governing a capability), `conflicts-with` (not a defect: two deliberate answers a new feature must choose between), `implements`, `integrates`, `blocked-by`. Always the singular verb form, whatever the From side, so one `grep '| supersedes |'` finds every edge of that type.

**4. External integrations** - `| System | Direction | Used by | Status | Rules | Notes |`, with status such as "Live, contract verified" or "mocked".

**5. Open questions and no-go zones** - `| ID | Question | Blocks | Owner | Raised |` (`OQ-nn`): deferred work, unratified decisions, known gaps.

Maintenance per session: update the existing capability row (a graph that grows a row per session is a session log wearing a table's clothes), add the new IDs to its columns, cross-link new entities, add every `supersedes`/`amends` edge from Phase 1, refresh moved anchors, and move resolved open questions into a decision entry.

## Phase 5 - Indexes

`prod_spec/index.md` lists `graph.md` first as the entry point; `docs/project_context/00_index.md` sends "what do we already have / where does this belong" to `prod_spec/graph.md`; add a row to the project's `CLAUDE.md` context table if it has one.

## Rules

- One rule, decision or feature per entry; always record rationale.
- Every prose entry is reachable from `graph.md`; an orphan is an entry no future agent finds.
- If nothing new was learned, write nothing.
