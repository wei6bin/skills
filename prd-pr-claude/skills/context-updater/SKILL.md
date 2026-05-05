---
name: context-updater
description: Updates docs/project_context/prod_spec/ after implementation — captures product decisions, domain rules, config choices, and feature specs from the session. Source code changes are explicitly excluded. Run this after any backend or frontend implementation session.
allowed-tools: Read, Grep, Glob, Write, Edit, AskUserQuestion
---

# Context Updater

**Scope**: Post-implementation knowledge capture only. Extract product-level knowledge from the completed session and persist it to `docs/project_context/prod_spec/`. Do **not** record source code, file paths, or implementation details.

---

## What Belongs in Product Context

Capture what an engineer holds in their head — not what a `git diff` shows:

| Category | Examples |
|---|---|
| **Domain rules** | "OrderStatus can only transition forward: Draft → Active → Shipped → Delivered", "a Booking cannot overlap an existing Booking for the same resource" |
| **Business invariants** | "an Invoice total must always equal the sum of its line items", "a User must have at least one Role" |
| **Config decisions + rationale** | "JWT access tokens expire in 15 min (security requirement), refresh tokens in 7 days (UX requirement)" |
| **Feature behaviour** | "soft-delete only — records are never physically removed; use `deleted_at IS NULL` in queries" |
| **Integration rules** | "always call the downstream Payment service idempotently using `X-Idempotency-Key` header" |
| **Design decisions** | "chose optimistic concurrency on Orders (version column) instead of pessimistic locks to avoid deadlocks under high load" |

**Explicitly exclude**: file paths, class names, method signatures, SQL schemas, code snippets, package versions — those belong in the code or `codebase-context-builder` files.

---

## Phase 1 — Identify What Was Built

Review the completed implementation session (via conversation history or summary from the calling agent):

1. What feature or capability was implemented?
2. What domain rules were enforced in the code?
3. What configuration values were set — and why?
4. What design choices were made that are not obvious from the code?
5. What invariants does the system now rely on?

If uncertain, use `AskUserQuestion` to confirm before writing anything.

---

## Phase 2 — Locate or Initialise `prod_spec/`

```bash
ls docs/project_context/prod_spec/ 2>/dev/null || echo "NOT_FOUND"
```

If the folder does not exist, create it with these seed files:

```
docs/project_context/prod_spec/
├── index.md              ← table of all prod_spec files + short description
├── features.md           ← user-visible features and their acceptance criteria
├── domain_rules.md       ← business rules, invariants, state machines
├── config_decisions.md   ← configuration choices + rationale
└── decisions.md          ← design / architectural decisions (ADR-lite)
```

---

## Phase 3 — Update Files

For each piece of knowledge identified in Phase 1, append to the appropriate file:

### `features.md`
```markdown
## [Feature Name]  <!-- e.g. "Booking Cancellation" -->
**Added**: YYYY-MM-DD
**User behaviour**: [what the user can now do]
**Key rules**:
- [rule 1]
- [rule 2]
```

### `domain_rules.md`
```markdown
## [Entity or Domain] — [Rule Name]
**Rule**: [one sentence]
**Rationale**: [why this rule exists]
**Where enforced**: [domain layer / API layer / DB constraint / all three]
```

### `config_decisions.md`
```markdown
## [Config Key or Setting]
**Value**: [the value or range]
**Rationale**: [why this value was chosen]
**Owner**: [team or component that controls it]
```

### `decisions.md`
```markdown
## [Decision Title]
**Date**: YYYY-MM-DD
**Context**: [the problem or trade-off faced]
**Decision**: [what was chosen]
**Rationale**: [why]
**Consequences**: [what this means going forward]
```

---

## Phase 4 — Update Index

Append any new files or sections to `docs/project_context/prod_spec/index.md`.
Ensure `docs/project_context/00_index.md` references `prod_spec/index.md` if not already present.

---

## Rules

- Write in plain English — no code blocks, no file paths
- Keep entries atomic: one rule, one decision, one feature per block
- If an entry already exists (same heading), update it — do not duplicate
- If nothing new was discovered, write nothing — do not pad files
- Always record **rationale**, not just the decision itself
