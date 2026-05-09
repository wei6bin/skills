---
name: vertical-slicing
description: Use when designing the implementation plan for a feature, before writing the task list. Breaks a feature into thin end-to-end slices (schema → service → API → UI) so each slice is independently demoable and testable. Replaces horizontal-layer ordering ("all backend first, all frontend after") with vertical end-to-end ordering, giving AI agents a feedback loop after every slice instead of only at final integration.
allowed-tools: Read, Write
---

# Vertical Slicing

## Why

Horizontal sequencing — *all schema, then all services, then all APIs, then all UI* — leaves the agent blind until final integration. Bugs at layer boundaries (DTO drift, auth gaps, error-shape mismatches) surface last, when context is most fragmented.

A **slice** is a thin feature increment that traverses every layer it touches and ends in a runnable, demoable, testable behaviour. Each slice gives the agent a real feedback loop and a concrete pattern for the next slice to copy.

## What counts as a slice

A slice is **demoable end-to-end on its own**.

| Not a slice | A slice |
|-------------|---------|
| "Set up the schema" | "Award points for lesson completion, visible on dashboard" |
| "Build the service layer" | "Reject patient registration when NRIC is malformed, error shown in form" |
| "Wire up the endpoint" | "Show patient's last visit date on the response card" |

The smallest first slice is the **walking skeleton**: thinnest possible end-to-end path, hardcoded where it has to be, demoable today.

## Slicing order

1. **SLICE-01** — the user-facing happy path that proves the feature exists.
2. **Alternate happy paths** — different valid inputs, roles, entry points. One slice per meaningfully different code path; otherwise it's a test case inside an existing slice.
3. **Visible error paths** — validation failures, permission denials, not-found, conflict. *Internal* error handling (logging, retry) is a task inside the slice that surfaces it.
4. **Polish** — empty/loading states, accessibility, performance.

Stop when the acceptance criteria are covered.

Within a slice, tasks follow layer dependency (data → service → API → hook → component → e2e test). **Across slices, never order by layer** — the slice ships as a whole before the next one starts.

## Sizing

A slice is the size of one PR you'd happily merge.

- More than ~6 tasks → probably two slices.
- Single task, no demoable behaviour → fold into the previous slice.
- Rule of thumb: if removing the last task leaves the slice still demoable, that task belongs in a later slice.

## Independence and parallelism

Two slices are independent if neither's correctness depends on the other and they touch disjoint files. Independent slices can run in parallel worktrees. **When in doubt, sequence** — parallelism is worth the overhead only when slices share no code paths.

## Anti-patterns — reject and reslice

- **Schema-first slice** ("SLICE-01: design the schema") — not demoable.
- **All-backend / all-frontend slice** — horizontal layering relabelled.
- **A slice per layer** (SLICE-01: API, SLICE-02: UI) — same.
- **"Integrate everything" slice at the end** — earlier slices were not vertical.
- **A slice that needs a later slice's UI to demo it** — collapse the two.

## Output shape

A slice is described by a card, not a task table. Files, repositories, and helpers are *discovered during TDD*, not pre-listed at planning time — pre-listing is the same "outrun your headlights" mistake that horizontal slicing makes.

```
## Slices

### SLICE-01 — [demoable behaviour, one sentence]
- AC covered: AC-1 (and parts of AC-6, AC-7 if folded)
- Demoable as: [what someone clicks/runs to verify, end-to-end]
- Type: AFK | HITL                    # AFK = agent runs autonomously; HITL = needs a human decision mid-slice
- Layers: BE + FE | BE only | FE only # which layer-halves to dispatch implementers for
- Blocked by: SLICE-NN | —

### SLICE-02 — [next demoable increment]
...
```

Each slice produces **at most two implementer dispatches**: a backend half and/or a frontend half. The implementer agent receives the slice card and runs TDD red-green-refactor against the slice's AC — it discovers which files to touch as the tests demand them.

If you find yourself wanting to list "migration here, repository there, handler there" inside a slice card, stop. Either the slice is too thick (split it) or you are pre-imagining the implementation (let TDD discover it).

## When NOT to slice

Single-layer bugfixes and behaviour-preserving refactors. Use slicing for new features and behaviour-adding enhancements.
