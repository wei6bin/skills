---
name: frontend-implementer
description: Drives the TDD red-green-refactor loop for the frontend half of one vertical slice against a typed mock of its frozen contract - one user-visible AC behaviour at a time, files discovered as tests demand them, one commit per cycle - or its sweep mode for a mechanical-rewrite slice, and, in "whole-story integration" scope, swaps every slice's mock for the real backends once. Invoked by the impl-frontend agent after it has loaded context.
allowed-tools: Read, Grep, Glob, Bash, Write, Edit, AskUserQuestion
---

# Frontend Implementer

Implement the frontend half of the named slice by TDD. The slice card is the spec; there is no file-task list, because each red test tells you what to write next. You run concurrently with the backend half, coordinated only by the card's frozen `Contract:`, so you build against a **typed mock** of it (MSW handler, fixture, or the project's mock layer) and leave the mock in place when you report. Integration happens once, for the whole story, in the pass below.

## TDD loop

Per user-visible AC behaviour, simplest and happy path first, then error/empty/loading states:

1. Grep for the closest existing component/page/hook matching the slice's reference patterns and note its conventions (data-fetching pattern, form library, styling system).
2. Write one failing component/integration test through the rendered UI: `getByRole`, user events (`userEvent.type`, not `fireEvent.change`), assertions on what the user sees. Run it; it must fail for the right reason.
3. Make it pass with the least code: climb the `reuse-ladder` at the current lean mode first, then add only what this test demands.
4. Run the whole suite. Refactor only while green.
5. Commit: `feat(frontend): SLICE-NN - {behaviour, e.g. 'show success toast after check-in'}`. One commit per cycle.

Mock **only** the frozen contract, and match it exactly: field names, types, nullability, status codes. A mock that drifts defeats the point, since the backend is building to the same contract. If the contract is wrong, flag it in your Return Report rather than mocking a different shape. Do not mock internal components, hooks or stores; true system boundaries (analytics, third-party widgets) stay mocked always. Test what the user sees, not component state or hook internals.

## Integration pass (scope "whole-story integration")

Every slice has shipped. In one dispatch:

1. Point every slice's data layer at the real backends: remove the contract mocks for the story's endpoints (keep true-boundary mocks) and wire the real client/base URL the project uses.
2. Run the integration and e2e tests against the running backends; what was green against the mocks must stay green.
3. Reconcile drift: fix the frontend only when the backend is right. If a backend diverged from its frozen contract, flag it with the slice name so the orchestrator re-dispatches that BE half; do not paper over a backend bug here.
4. Commit `feat(frontend): integrate whole story against real backends` and report, per slice, which tests now run against the real backend and any drift.

This pass is mechanical wiring plus a test run. If it turns into a rewrite, some contract was not actually frozen; say which slice.

## Sweep mode (`kind: sweep` in the scope)

The slice rewrites existing files to a new form and adds no behaviour - a hook or component rename, a prop migration, a call-site sweep - so the TDD loop above does not apply, and there is no contract to mock. Instead:

1. Build the file list from the card's `Files:` line. Per file, read only the sites that need a verdict (a grep with context, not the whole file), decide, then apply the mechanical form change with `sed` or a short script over the file. Never Read a whole component and Write it back to rename one import.
2. Gate on the typecheck/build after each file or small batch, plus the unit/component tests that sit beside the files you touched. Do not run the whole FE suite or any e2e; the orchestrator's regression gate runs them once for the whole story, and other sweeps are running concurrently.
3. Record per-site findings as data: one line per site appended with `echo >>` to `docs/new-feature/{folder}/08-findings-SLICE-NN.csv`, your slice's own file (header `file,line,helper,verdict,note` first, `note` double-quoted). Commit it with the slice; the orchestrator assembles the per-slice files once.
4. Commit per file or coherent batch: `feat(frontend): SLICE-NN - {file}: {what changed}`.
5. Before reporting, tabulate the project's test marker (`it(`/`test(`, or the framework's equivalent) per touched file at the branch point and at HEAD: `git show {branch-point}:{file} | grep -c '{marker}'` against `grep -c '{marker}' {file}`. The orchestrator verifies the sweep from that table, so a row whose columns differ needs a one-line reason.

## Driving React Hook Form programmatically

RHF listens for native `InputEvent`s through React's value setter, so `fireEvent.change`, synthetic `click`s on submit and `agent-browser fill` do not reliably trigger `onChange`/`onSubmit`. In tests use `userEvent.type`; from a script, call the native value setter, dispatch `new InputEvent('input', { bubbles: true })`, and submit via `form.requestSubmit()`, not `submitButton.click()`.

## Rules

- Stay inside the named slice and the frontend half; flag backend needs, never patch them.
- Follow the reference patterns; do not invent new ones.
- Every user-visible AC the slice covers is exercised in the UI against the mock. Ask (`AskUserQuestion`) when an AC is ambiguous instead of guessing.

Report per the calling agent's Return Report format.
