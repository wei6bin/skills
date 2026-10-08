---
name: react-frontend-scaffold
description: Internal - React + TypeScript SPA scaffold (Vite, Ant Design, TanStack Query, feature slices). Bootstraps a new frontend. Invoked by impl-frontend.
user-invocable: false
allowed-tools: Read, Grep, Glob, Bash, Write, Edit
---

# React Frontend Scaffold

This skill is for React SPA frontends organized as **feature slices** -
typically `features/{name}/` folders, a shared `components/` (or similarly
named) folder for reusable UI primitives, and a `lib/` (or `common/`, `shared/`)
folder for cross-cutting API/state code. If the repo you're in is a Next.js app
built around server components/actions, or organizes by technical layer
(`pages/`, `containers/`, `services/`) rather than by feature, treat this skill
as a starting point for reasoning, not a literal template - the underlying
judgment calls (hook shape, error handling, test coverage) still transfer.

## In the jidoka workflow

`impl-frontend` runs this skill under the scope
`project scaffold - frontend - skill: react-frontend-scaffold - root: {dir}`,
dispatched by `project-scaffolder` on a repo with no frontend. Under that scope:

- Do **Bootstrapping a new app** below and nothing else. Run every command from
  the root the scope names (`frontend/` by default), and stop once the empty
  app is green; step 4's first feature slice is the story's job, built later by
  the line's own TDD loop.
- The dispatch carries a **skeleton contract** that settles what this skill
  would otherwise ask or default: the project name, the dev URLs, the `/api`
  proxy, the CSRF header, the auth endpoints and the look (`Look:` names the
  preset in `references/antd-app-setup.md`, or a brand colour to seed it with;
  do not hand off to `frontend-design` from a subagent). You run as a subagent
  and cannot ask the user; where the contract and a reference disagree, the
  contract wins, and you report the disagreement.
- The backend half is being scaffolded at the same time in its own root, so
  build against the contract with MSW handlers, never against a running
  backend. Stage and commit only paths under your root, one commit per
  bootstrap step (`chore(frontend): scaffold - {step}`).

Outside the scaffold, the rest of this skill (feature slices, the hook, form and
test references) is reference material: the line's implementers do not load it
per slice, and `docs/project_context/` carries the conventions the scaffold
established.

## Step zero: read this repo's own reference feature(s), and verify docs against code

Every codebase in this style differs in the details - which server-state
library, which API client shape, which form pattern, which UI library (if any).
Before applying anything below, find 1-2 existing features in *this* repo and
read them fully:

- Look for a `features/` (or `modules/`) directory with subfolders per resource;
  read every file in the richest one (ideally one with a list, a create form,
  and an update/delete flow).
- Grep for how a typed API call is actually made (`apiClient.`, a generated SDK
  function, a raw `fetch`) - don't trust `package.json` dependencies alone. A UI
  library or codegen tool can be installed, and even have a build/codegen script
  wired up, without a single file in `src` importing from it; grep for real
  imports before assuming a listed dependency is the convention.
- If the repo has a design doc, RFC, or scaffold spec describing the intended
  architecture, treat it as a hypothesis, not ground truth - compare it against
  what the code actually imports and does, and defer to the code wherever they
  disagree. Docs drift; running code doesn't.
- Check the test setup (`test/`, `__tests__/`, or co-located `*.test.tsx`) for
  shared render helpers or mock-server setup - reuse them, don't reimplement.

Treat what you find there as the source of truth. Everything below describes the
shape you're *likely* to find and how to reason about each piece - confirm
against the actual code rather than assuming a specific file name, library, or
convention exists.

## Decide what's actually being added

| Ask is... | Do this |
| --- | --- |
| A brand-new frontend with no app, app shell or styling yet | **Bootstrapping a new app** below, then come back for the first feature slice |
| Creating the app itself: Vite, packages, scripts, dev proxy, API client, auth routes, test setup | `references/app-bootstrap.md` |
| A new resource with its own page(s) (e.g. "add a Notes feature", "add a Comments list") | Follow **Adding a feature slice** below - this is the common case |
| A new shared UI primitive used by 2+ features | Add it alongside the repo's existing shared primitives, matching their prop-typing and styling approach. Give it a co-located test if the repo's other primitives have one. |
| A new route or route guard | Add it to the repo's routing folder/convention and wire it into the router. See `references/testing.md` for how route guards are typically tested. |
| Writing/reviewing query or mutation hooks | `references/api-hooks.md` - client usage, error handling, query key conventions, pagination |
| Writing a create/edit form | `references/forms-and-optimistic-ui.md` - action-based forms, field-error mapping, optimistic update patterns |
| Writing the test file(s) for a feature | `references/testing.md` |
| Touching global styling/theme | `references/styling-and-components.md` - it routes to the Ant Design references below when they apply |
| Setting up styling for an app that has none yet | `references/antd-app-setup.md` - packages, theme presets, app shell, anti-default checklist |
| Building any feature in an app that uses Ant Design | `references/antd-component-patterns.md` - component mapping, forms, list/loading/empty/error states |
| Feature needs shared client-side state beyond server data (not already covered by a query hook) | Match the repo's existing global-state approach if it has one; otherwise see **Default tooling choices** below |

## Bootstrapping a new app

Only when there's genuinely nothing to match - a new frontend, or one whose
components are all unstyled. If any real styling approach exists, step zero
governs and this section doesn't apply.

Do this **before** the first feature slice. Retrofitting a theme and an app
shell after three features exist means rewriting all three.

1. Read `references/app-bootstrap.md` and follow it: the Vite app, packages and
   scripts, lint and format, the dev proxy, the typed API client, the auth
   routes, and the test setup. It is the foundation the next step themes.
2. Read `references/antd-app-setup.md` and follow it: packages, provider stack,
   `theme/theme.ts` from a preset, a `ColorModeProvider`, `app/AppShell.tsx`.
3. Confirm the app renders with the shell, in both colour modes, before writing
   any feature, and that every script in `app-bootstrap.md`'s checklist passes.
4. Work the anti-default checklist at the end of `antd-app-setup.md`. This is
   the step that decides whether the result looks like a product or like an
   unstyled component gallery.
5. Then continue to **Adding a feature slice**, with
   `references/antd-component-patterns.md` open.

The point of front-loading this: everything a later session sees becomes the
convention it copies. A theme and a shell laid down first are what make "match
the existing code" produce a consistent app three features later.

## Adding a feature slice

Walk through the repo's richest existing feature side-by-side as you do this.

**1. Create the folder** `features/{name}/` under the repo's source root
(lowercase, matching the repo's existing feature folder names).

**2. Query hook** - a `use{Feature}.ts`-style file: exports the domain type(s)
the way the repo's other features do (hand-written interfaces are common when
the API client is a thin typed wrapper; imported generated types are common when
it's a full codegen SDK), and a `use{Feature}()` hook wrapping the repo's
server-state library. Match the repo's existing query-key convention - see
`references/api-hooks.md`.

**3. Mutation hooks** - one exported async fetch/call function plus one hook
wrapper per mutation, each updating cache on success (invalidate vs. direct
cache write - match whichever the repo's other mutations already do). See
`references/api-hooks.md`.

**4. Page/component files** - match the repo's existing file granularity. Some
codebases in this style nest each feature into `/components`, `/api`, `/hooks`
subfolders; others keep flat files directly in the feature folder (check step
zero's findings - a design doc can call for one while the code does the other).
Don't introduce a nesting convention the rest of the repo doesn't already use,
even if it looks cleaner. Name by role, matching existing patterns
(`{Feature}ListPage`, `{Feature}Row`, `Add{Feature}Form`, etc.).

**5. Barrel export** - export only what other features/routes actually need (a
public hook, the main page component, the domain type). Keep internal pieces
(row components, mutation hooks only the feature itself uses) unexported, unless
the repo's existing barrels already export everything unconditionally - match
whichever pattern is already established.

**6. Route wiring** - add the page to the repo's router, wrapped in whatever
auth/guard components the repo's other protected routes use.

**7. Styling** - match the repo's actual styling approach (utility classes, CSS
Modules, a component library, CSS-in-JS). See
`references/styling-and-components.md` for how to tell which one is real versus
just installed, and for which reference applies. If the app uses Ant Design,
`references/antd-component-patterns.md` covers the per-feature component
choices; if it has no styling at all yet, stop and do **Bootstrapping a new
app** first.

**8. Tests** - match the repo's existing test co-location and mocking
convention. See `references/testing.md`.

**9. Verify** - run the repo's type-check, lint, and test scripts (check
`package.json` for the actual script names - commonly `type-check`/`tsc`,
`lint`, `test`). Don't report the feature done without all three passing. If the
repo has no lint/format tooling configured at all, see **Default tooling
choices** below.

## Things that might be deliberately missing, or quietly unused

A UI library, codegen tool, or architecture pattern can sit in `package.json` or
a design doc without actually being used anywhere in `src` - step zero's
import-grep is what catches this. If you find such a mismatch (a listed
dependency nothing imports, a doc-mandated pattern the code doesn't follow),
don't silently "fix" the code to match the doc or the dependency as a side
effect of an unrelated feature - flag the discrepancy to the user and follow
what the code actually does for the feature you're adding.

## One thing worth checking before regenerating API types

If the frontend consumes a generated or hand-typed client built from a backend
OpenAPI schema, check which output file is actually imported by feature code
before trusting a README's regeneration instructions - a repo can have more than
one codegen script (e.g. left over from a migration between tools) where only
one of them produces the file that's actually wired in. Regenerating the wrong
one silently does nothing, and the README isn't guaranteed to have been updated
when the switch happened. If there's no codegen set up at all and the feature
genuinely needs one, see **Default tooling choices** below rather than
hand-typing a large schema.

## Default tooling choices - only when a repo has nothing established yet

Step zero's whole point is to match what a repo already does, so treat this
table as a last resort, not a preference to introduce by default: it applies
only when a repo has no existing choice for the need in question and adding a
feature genuinely requires picking one. Never use it to justify replacing or
second-guessing a working existing setup as a side effect of an unrelated
feature - that's exactly the drift this skill exists to avoid (see this skill's
origin story: a UI library and a codegen tool both sitting unused in a real
template's `package.json`).

| Need | Prefer | Over | Why this is the fallback |
| --- | --- | --- | --- |
| UI components & styling | Ant Design - see `references/antd-app-setup.md` | Tailwind + hand-rolled primitives | A themed component library gives a consistent, accessible, keyboard-navigable baseline immediately. Hand-rolled primitives drift in style with every session that adds one, which is exactly the inconsistency this skill exists to prevent. |
| Form handling & validation | antd's own `Form` + `Form.Item` rules | react-hook-form, `useActionState`, Formik | `Form.Item` already owns the label, validation rules, error text, and the accessible wiring between them, for no extra dependency. antd's controls are all controlled components, so a third-party form library means a `<Controller>` around nearly every field. Keep zod where a schema is genuinely shared with the backend contract, bridged through a `rules: [{ validator }]`. |
| Tabular list UI | antd's `Table` | a hand-rolled sortable table | Sorting, filtering, pagination, row selection, and keyboard navigation are tedious to re-derive per feature and easy to get subtly wrong - and in antd they're in core, so a real data table costs no extra package. Use `List` when the data isn't columnar - see `references/antd-component-patterns.md`. |
| Linting & formatting | Biome for lint, Prettier for format (Biome's formatter off) | ESLint or Oxlint (Vite's templates ship one), Biome's formatter | One linter with one config. Prettier keeps formatting because jidoka's post-edit hook auto-writes Prettier but only reports Biome, so a Biome-formatted repo collects formatting failures the hook never fixes. |
| Generating TS types from an OpenAPI schema | `@hey-api/openapi-ts` | `openapi-typescript` | Simpler setup for the common case of schema-to-types-and-client generation. |
| Client-side/global state (state not already owned by the server-state library, e.g. TanStack Query) | Zustand | Redux | Far less boilerplate for the store sizes typical of a single feature slice. |

If the repo already uses the "Over" column's tool (or any other tool doing the
same job), match that instead - swapping it out is a separate, deliberate
migration decision for the user to make, not something to fold into a
feature-slice task.
