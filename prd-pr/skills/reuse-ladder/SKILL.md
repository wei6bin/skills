---
name: reuse-ladder
description: The lean-implementation discipline shared by the prd-pr implementers — climb a reuse ladder (existing code → stdlib/platform → native framework feature → installed dependency → one line) before writing custom code, and apply the lean mode (lite/full) derived from a slice's story-point size. Invoked by the backend-implementer and frontend-implementer skills (and the impl-backend / impl-frontend agents) so the guidance lives in exactly one place.
allowed-tools: Read, Grep, Glob
---

# Reuse ladder & lean mode

One shared discipline for both implementer halves. The `backend-implementer` and `frontend-implementer` skills — and the `impl-backend` / `impl-frontend` agents — invoke this skill instead of embedding their own copy, so there is exactly one source of truth for the prompt. Apply it throughout the TDD red-green-refactor loop, at the strictness set by the current **lean mode**.

## Reuse ladder — before writing custom code

Before you write a new function, class, component, hook, or dependency to make a test pass, climb this ladder and **stop at the first rung that works**. The best code is the code you never wrote — TDD tells you *what* behaviour to add; the ladder tells you to add as little of your own as possible.

1. **Does this AC behaviour need new code at all?** If config, an existing path, or an existing page/route/component already satisfies the test, wire to that instead of building anew.
2. **Already in the codebase?** Grep for an existing helper, service, validator, hook, or component matching the slice's reference patterns — reuse beats re-implement, and it matches conventions for free. (Reuse the design-system component; don't re-style a bespoke one.)
3. **In the standard library / platform?** Prefer the language/runtime stdlib (dates, hashing, collections, HTTP, JSON, UUIDs) and native browser/platform features (`Intl`, native form validation, `<dialog>`, the URL/History API) over hand-rolling.
4. **A native framework feature?** Use the framework's built-in — ORM query, model validation, middleware, DI on the backend; router loader, form state, Suspense/error boundary, the existing data-fetching layer on the frontend — before custom plumbing.
5. **An already-installed dependency?** Check the manifest; if a dep already present (or the UI kit) solves it, use it. Do **not** add a *new* dependency without flagging it when you report back.
6. **Can it be one line?** Prefer the smallest expression or change that passes the test.

Never take a shortcut *through* the guardrails: input validation, error handling that prevents data loss (and error/empty/loading states in the UI), security, and accessibility (roles, labels, keyboard) are **never** simplified away — the `code-reviewer` and `security-reviewer` check exactly these.

## Lean mode

Derive the mode from the slice card's **story-point size** (or honour a `lean: lite|full` token if the orchestrator put one in your scope). It tunes how hard you enforce the reuse ladder — it never changes what the ACs require:

- **lean: lite** (1–2 points): Build what the AC asks. If a lazier path exists, note it in one line when you report back — do not block on it.
- **lean: full** (3+ points, default): Enforce the ladder — stop at the first rung that works before writing custom code.
- **Large slice (8+ / spike):** Still run `full`, **and** add a *"this slice may be over-scoped"* note when you report back so the orchestrator can decide. Never drop an AC — scope changes are the orchestrator's call, not yours.
