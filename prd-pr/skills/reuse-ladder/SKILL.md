---
name: reuse-ladder
description: The lean-implementation discipline shared by the prd-pr implementers - climb a reuse ladder (existing code → stdlib/platform → framework feature → installed dependency → one line) before writing custom code, at a strictness set by the slice's lean mode (lite/full). Invoked by impl-backend and impl-frontend before their implementer skills.
allowed-tools: Read, Grep, Glob
---

# Reuse ladder and lean mode

Apply throughout the TDD loop, at the strictness set by the lean mode.

## Reuse ladder

Before writing a new function, class, component, hook or dependency to make a test pass, climb this ladder and **stop at the first rung that works**:

1. **No new code?** Config, an existing path or an existing page/route/component may already satisfy the test.
2. **Already in the codebase?** Grep for a helper, service, validator, hook or design-system component matching the slice's reference patterns.
3. **Standard library / platform?** Runtime stdlib (dates, hashing, collections, HTTP, JSON, UUIDs) and native browser features (`Intl`, native form validation, `<dialog>`, URL/History API).
4. **Framework built-in?** ORM query, model validation, middleware, DI; router loader, form state, Suspense/error boundary, the existing data-fetching layer.
5. **Already-installed dependency?** Check the manifest. Never add a *new* dependency without flagging it in your report.
6. **One line?** The smallest change that passes.

Guardrails are never simplified away: input validation, error handling that prevents data loss (and error/empty/loading states in the UI), security, accessibility (roles, labels, keyboard). The reviewers check exactly these.

## Lean mode

From the slice card's story points, or a `lean: lite|full` token in your scope. It tunes ladder strictness only; ACs are never dropped.

- **lite** (1-2 points): build what the AC asks; note a lazier path in one line if you see one.
- **full** (3+, default): enforce the ladder.
- **8+ / spike**: still `full`, plus a "this slice may be over-scoped" note in your report. Scope changes are the orchestrator's call.
