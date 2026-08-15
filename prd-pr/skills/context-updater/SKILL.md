---
name: context-updater
description: Updates docs/project_context/prod_spec/ after implementation - captures product decisions, domain rules, config choices, and feature specs from the session, and maintains prod_spec/graph.md, the project knowledge graph that lets a later agent answer "what do we already have, and where do I start?" without reading everything. Source code changes are explicitly excluded. Run this after any backend or frontend implementation session.
allowed-tools: Read, Grep, Glob, Write, Edit, Bash, AskUserQuestion
---

# Context Updater

**Scope**: Post-implementation knowledge capture. Two outputs, both under `docs/project_context/prod_spec/`:

1. **The prose files** - durable product knowledge in plain English (`features.md`, `domain_rules.md`, `decisions.md`, `config_decisions.md`). Deliberately free of code.
2. **`graph.md` - the knowledge graph.** A compact, typed index over those entries: what capabilities exist, what domain concepts they touch, which entries supersede which, and the coarse code anchors where each capability lives. This is the file a later agent reads *first*, and often the only one it needs before it knows which twenty lines of prose to load.

Without the graph the prose becomes an append-only log: correct, growing, and unreadable. Without the prose the graph is a table of contents pointing at nothing. Maintain both, in the same pass.

---

## What Belongs in Product Context

Capture what an engineer holds in their head - not what a `git diff` shows:

| Category | Examples |
|---|---|
| **Domain rules** | "OrderStatus can only transition forward: Draft to Active to Shipped to Delivered", "a Booking cannot overlap an existing Booking for the same resource" |
| **Business invariants** | "an Invoice total must always equal the sum of its line items", "a User must have at least one Role" |
| **Config decisions + rationale** | "access tokens expire in 15 min (security requirement), refresh tokens in 7 days (UX requirement)" |
| **Feature behaviour** | "soft-delete only - records are never physically removed" |
| **Integration rules** | "always call the downstream Payment service idempotently" |
| **Design decisions** | "chose optimistic concurrency on Orders instead of pessimistic locks to avoid deadlocks under high load" |

**Excluded from the prose files**: file paths, class names, method signatures, SQL schemas, code snippets, package versions.

**One controlled exception, in `graph.md` only**: each capability node carries **coarse code anchors** - directory or module paths such as `backend/src/Api/Features/Roster/`, never `path/file.cs:412`. A directory moves once a year; a line number is wrong by the next commit. Anchors are what turn "we already have this" into "start here", so the graph is worth the small maintenance cost. Keep them at the shallowest level that is still specific.

---

## Entry IDs - the primary key

Every entry in every prose file is prefixed with a stable ID in its heading:

```markdown
## [DR-045] Roster drafts - same doctor, same department, overlapping time is always rejected
```

| Prefix | File |
|---|---|
| `FT-` | `features.md` |
| `DR-` | `domain_rules.md` |
| `DC-` | `decisions.md` |
| `CFG-` | `config_decisions.md` |

Rules:

- IDs are **monotonic and permanent**. Allocate the next unused number; never renumber, never reuse an ID whose entry was superseded or removed.
- **Heading text is not the key.** Rewording a heading is fine; changing its ID is not. This is what makes "update, do not duplicate" reliable.
- An ID is greppable in one command, which is how agents resolve a graph reference to its prose:
  ```bash
  grep -n "\[DR-045\]" docs/project_context/prod_spec/*.md
  ```

Find the current high-water mark before allocating:

```bash
grep -ho '\[\(FT\|DR\|DC\|CFG\)-[0-9]*\]' docs/project_context/prod_spec/*.md | sort -t- -k1,1 -k2,2n | tail -20
```

---

## Phase 0 - Bootstrap the graph if it is missing

Run this **once per repository**, the first time this skill meets a `prod_spec/` that has prose but no `graph.md` (or no IDs). Skip straight to Phase 1 on every later run.

1. **Stamp IDs into every existing heading**, in file order, mechanically. Do not hand-edit hundreds of headings; script it.
2. **Read all four prose files in full.** The graph's edges are currently locked inside the prose as English - phrases like "superseding the earlier stance", "an earlier feature already faced this and chose differently", "see X below". These are the highest-value edges in the graph and the only pass that can find them is a full read.
3. **Write `graph.md`** per the schema below.

A forward-only graph over an established `prod_spec/` is close to worthless: all the accumulated knowledge stays invisible. Backfill properly, once.

---

## Phase 1 - Identify what was built

Review the completed implementation session (via conversation history or the calling agent's summary):

1. What feature or capability was implemented?
2. What domain rules were enforced?
3. What configuration values were set - and why?
4. What design choices were made that are not obvious from the code?
5. What invariants does the system now rely on?
6. **What did this session change its mind about?** Any earlier entry now contradicted, narrowed, or replaced. This is the question most often skipped, and the one whose omission does the most damage - a superseded decision that still reads as current will be applied again.
7. **Which directories did the work land in?** Needed for the anchors, at directory granularity.

If uncertain, use `AskUserQuestion` before writing anything.

---

## Phase 2 - Locate or initialise `prod_spec/`

```bash
ls docs/project_context/prod_spec/ 2>/dev/null || echo "NOT_FOUND"
```

If the folder does not exist, create it with these seed files:

```
docs/project_context/prod_spec/
├── graph.md              <- the knowledge graph (read first by every consumer)
├── index.md              <- table of all prod_spec files + short description
├── features.md           <- user-visible features and their acceptance criteria
├── domain_rules.md       <- business rules, invariants, state machines
├── config_decisions.md   <- configuration choices + rationale
└── decisions.md          <- design / architectural decisions (ADR-lite)
```

`index.md` is a **file manifest only**. Never let it accumulate a running session log - that turns the one small file an agent would happily read into the largest one in the folder. Session history belongs in git; capability history belongs in `graph.md`.

---

## Phase 3 - Update the prose files

For each piece of knowledge from Phase 1, append (or update in place, matching on ID) using these templates. Allocate a new ID for each new entry.

### `features.md`
```markdown
## [FT-nnn] Feature Name
**Added**: YYYY-MM-DD
**User behaviour**: what the user can now do
**Key rules**:
- rule 1
- rule 2
```

### `domain_rules.md`
```markdown
## [DR-nnn] Entity or Domain - Rule Name
**Rule**: one sentence
**Rationale**: why this rule exists
**Where enforced**: domain layer / API layer / DB constraint / all three
```

### `config_decisions.md`
```markdown
## [CFG-nnn] Config Key or Setting
**Value**: the value or range
**Rationale**: why this value was chosen
**Owner**: team or component that controls it
```

### `decisions.md`
```markdown
## [DC-nnn] Decision Title
**Date**: YYYY-MM-DD
**Context**: the problem or trade-off faced
**Decision**: what was chosen
**Rationale**: why
**Consequences**: what this means going forward
```

### Superseding an earlier entry

Never delete or silently rewrite a superseded entry - the reasoning that was overturned is often exactly what stops the next agent re-proposing it. Instead mark the old entry and let the new one carry the current answer:

```markdown
## [DC-031] The old decision title
**Status**: SUPERSEDED by [DC-078] (2026-08-13)
**Date**: 2026-07-20
... original body unchanged ...
```

and record a `supersedes` edge in the graph. Same treatment for a rule that was narrowed rather than replaced - use `**Status**: AMENDED by [DR-102]`.

---

## Phase 4 - Update `graph.md`

`graph.md` is a single markdown file, kept small enough to read whole (target: under 40KB - if it outgrows that, tighten the prose in it, do not split it). It has five sections.

### 1. Capability map

One row per capability - a coherent unit of product behaviour, not one row per story or slice. Several stories usually converge on one capability; say so in `Stories` rather than creating a row each.

```markdown
| ID | Capability | Surfaces | Entities | Stories | Anchors | Rules | Decisions | Config | Status |
|---|---|---|---|---|---|---|---|---|---|
| CAP-07 | Roster publish + SAP sync | admin-portal, api | RosterSlot, Publication, Department | usr-061, usr-062, usr-066 | backend/src/Api/Features/Roster/, frontend/apps/admin-portal/src/pages/roster/ | DR-036, DR-041, DR-052 | DC-030, DC-078 | CFG-012 | Live |
```

- **Surfaces**: the deployable or user-facing surfaces it appears on.
- **Entities**: the domain concepts it reads or writes - these are the graph's join keys, so use exactly the same names across rows.
- **Anchors**: directories, comma-separated, most important first.
- **Status**: `Live`, `Partial`, `Deferred`, `Dropped`, or `Superseded`.

### 2. Entity map

The reverse index. An agent arriving with "the new feature touches Departments" needs to reach every rule that constrains a Department without reading all of `domain_rules.md`.

```markdown
| Entity | Constrained by | Touched by | Notes |
|---|---|---|---|
| RosterSlot | DR-036, DR-041, DR-052 | CAP-06, CAP-07, CAP-09 | Draft and published slots are separate tables; existence in one is the state |
```

### 3. Edges

Everything that is not a containment relationship. Type each edge - an untyped "related to" link carries almost no information.

```markdown
| From | Type | To | Note |
|---|---|---|---|
| DC-078 | supersedes | DC-030 | Coverage guard moved from delete-only to enforced everywhere |
| CAP-09 | depends-on | CAP-07 | Cannot export a roster that was never published |
| DR-055 | conflicts-with | DR-012 | Same historical quirk, two features chose differently, both deliberate |
| CAP-11 | extends | CAP-04 | |
```

Vocabulary: `supersedes`, `amends`, `resolves`, `depends-on`, `extends`, `constrains`, `conflicts-with`, `implements`, `integrates`, `blocked-by`. Use `resolves` when an entry's own predicted follow-up arrived (the entry was not overturned, its future came true) and `constrains` for a cross-cutting invariant that governs a capability without being one.

**Always write the verb in this exact singular form, whatever sits on the From side.** `A, B | supersede | C` reads better and is a bug: `grep '| supersedes |'` then silently misses the row. The edge table is only useful if one grep per verb finds every edge of that type.

`conflicts-with` is not a defect report. Two parts of a product legitimately resolving the same tension differently is a fact a new feature must know before it picks a side.

### 4. External integrations

Boundaries the system crosses, and their current trust level. A new feature that touches one of these needs to know whether it is real, mocked, or provisional before it plans anything.

```markdown
| System | Direction | Used by | Status | Rules | Notes |
|---|---|---|---|---|---|
| SAP HR | outbound | CAP-07 | Live, contract verified | DR-041 | Not deployable until BA-27 is ratified |
```

### 5. Open questions and no-go zones

Where "start here" is actually "you cannot start here yet". Deferred work, unratified decisions, known gaps.

```markdown
| ID | Question | Blocks | Owner | Raised |
|---|---|---|---|---|
| OQ-03 | Ordering model for admin lists is undecided | usr-083 | BA | 2026-08-09 |
```

### Maintaining it

After writing the prose entries:

1. Add or update the capability row. **Prefer updating an existing row** - most sessions deepen a capability rather than inventing one. A graph that grows a row per session is a session log wearing a table's clothes.
2. Add the new entry IDs into that row's `Rules` / `Decisions` / `Config` columns.
3. Add any new entity to the entity map and cross-link it.
4. Add edges - especially every `supersedes` and `amends` from Phase 1 question 6.
5. Refresh anchors if the code moved.
6. Move any resolved open question out of section 5, into a decision entry with a `supersedes` edge if it overturned something.

---

## Phase 5 - Update the indexes

1. `docs/project_context/prod_spec/index.md` - keep it a file manifest, with `graph.md` listed first and marked as the entry point.
2. `docs/project_context/00_index.md` - make sure its task lookup table sends the reader to `prod_spec/graph.md` for "what do we already have / where does this feature belong", not just to `prod_spec/`.
3. If the project has a `CLAUDE.md` (or equivalent agent-facing readme) with a context lookup table, add a row for the graph there too. A graph nobody is told to read is a graph nobody reads.

---

## How a later agent uses this

Worth stating, because it is the reason for every rule above. Given a new feature request:

1. Read `graph.md` (one file, one Read).
2. Match the request against the capability map and entity map. Usually one to three capabilities are relevant.
3. Load only those rows' cited entry IDs from the prose files - typically 200 lines, not 8000.
4. Check the edges for `supersedes` (do not apply an overturned decision) and `conflicts-with` (a tension already resolved elsewhere).
5. Check section 5 - the work may be blocked before it starts.
6. Use the anchors as the starting directories for code exploration, instead of searching the tree blind.

---

## Rules

- Prose files: plain English, no code blocks, no file paths. Anchors live in `graph.md` only, at directory granularity.
- Keep entries atomic: one rule, one decision, one feature per block.
- Match on **ID**, not heading text, when deciding update-vs-append.
- Never renumber or reuse an ID.
- Never delete a superseded entry - mark it and link forward.
- If nothing new was discovered, write nothing - do not pad files.
- Always record **rationale**, not just the decision.
- Every prose entry must be reachable from `graph.md`. An orphaned entry is an entry no future agent will find.
