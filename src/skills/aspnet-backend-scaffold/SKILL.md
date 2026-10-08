---
name: aspnet-backend-scaffold
description: Internal - ASP.NET Core Minimal API scaffold (vertical-slice features, EF Core, cookie-session auth). Bootstraps a new API. Invoked by impl-backend.
user-invocable: false
allowed-tools: Read, Grep, Glob, Bash, Write, Edit
---

# ASP.NET Backend Scaffold

This skill is for ASP.NET Core **Minimal API** backends (no MVC controllers)
organized as **vertical slices by feature** - typically `Features/{Name}/`
folders, a `Common/` (or similarly named) folder for cross-cutting concerns, and
a single shared `DbContext`. If the repo you're in uses MVC controllers instead,
or organizes by technical layer (`Controllers/`, `Services/`, `Repositories/`)
rather than by feature, treat this skill as a starting point for reasoning, not
a literal template - the underlying judgment calls (return-type shape, ownership
scoping, test coverage) still transfer.

## In the jidoka workflow

`impl-backend` runs this skill under the scope
`project scaffold - backend - skill: aspnet-backend-scaffold - root: {dir}`,
dispatched by `project-scaffolder` on a repo with no backend. Under that scope:

- Do **Bootstrapping a new API** below and nothing else. Run every command from
  the root the scope names (`backend/` by default), and stop once the empty
  scaffold is green; step 5's first feature slice is the story's job, built
  later by the line's own TDD loop.
- The dispatch carries a **skeleton contract** that settles what this skill
  would otherwise ask or default: the project name, the dev URL, the CSRF
  header, how passwords are verified (`Credentials:`), the dev login and the
  schema strategy. You run as a subagent and cannot ask the user; where the
  contract and a reference disagree, the contract wins, and you report the
  disagreement.
- The frontend half is being scaffolded at the same time in its own root. Stage
  and commit only paths under yours, one commit per bootstrap step
  (`chore(backend): scaffold - {step}`).

Outside the scaffold, the rest of this skill (feature slices, the handler and
test references) is reference material: the line's implementers do not load it
per slice, and `docs/project_context/` carries the conventions the scaffold
established.

## Step zero: read this repo's own reference feature(s)

Every codebase in this style differs in the details - which validation library,
which auth scheme, what the test factory is called. Before applying anything
below, find 1-2 existing features in *this* repo and read them fully:

- Look for a `Features/` (or `Modules/`, `Endpoints/`) directory with subfolders
  per resource.
- Grep for `MapGroup(` or files matching `*Endpoints.cs` / `*Endpoint.cs` to
  find the endpoint-mapping convention.
- Check the test project for an existing `WebApplicationFactory<T>` subclass and
  any test-helper extension methods (auth helpers, token helpers) - reuse them,
  don't reimplement.

Treat what you find there as the source of truth. Everything in this skill
describes the shape you're *likely* to find and how to reason about each piece -
confirm against the actual code rather than assuming a specific file name,
package, or convention exists.

## Decide what's actually being added

| Ask is... | Do this |
| --- | --- |
| A brand-new API with no project, DbContext, or feature folders yet | **Bootstrapping a new API** below, then come back for the first feature slice |
| A new resource with its own endpoints (e.g. "add a Notes feature", "add a Projects API") | Follow **Adding a feature slice** below - this is the common case |
| Just a new entity/table, no endpoints yet | `references/entities-and-data.md` |
| A new migration for entities that already exist | The migration command in `references/entities-and-data.md` |
| A new middleware, endpoint filter, or other cross-cutting concern (not tied to one feature) | `references/common-concerns.md` |
| Writing/reviewing the actual endpoint handler code | `references/endpoint-cheatsheet.md` - return-type mapping, filter combos, ownership scoping, pagination |
| Writing the test file for a feature | `references/testing.md` |
| Setting up a project/solution, DI, validation filter, or test factory that doesn't exist yet | `references/api-bootstrap.md` |
| Login/logout/session auth or an auth audit log, where the repo has **no** auth scheme yet (including every greenfield API) | `references/cookie-session-auth.md`: the default, server-side cookie sessions via `ITicketStore` |

## Bootstrapping a new API

Only when there's genuinely nothing to match - no project, no `DbContext`, no
feature folders. If even one feature slice exists, step zero governs and this
section doesn't apply.

Do this **before** the first feature slice. The pieces below are ones every
feature depends on, and retrofitting them once three features exist means
touching all three.

1. Read `references/api-bootstrap.md` and follow it: project/solution layout,
   packages, `Program.cs` wiring, `Common/ValidationFilter.cs`, and the
   `WebApplicationFactory` test fixture.
2. Lay down the default authentication from `references/cookie-session-auth.md`:
   an HttpOnly `__Host-` session cookie backed by a `UserSession` table through
   `ITicketStore`, idle/absolute expiry plus a background sweep, CSRF header
   middleware, `/auth/login|me|logout`, and an `AuditLog` row for every login,
   logout and expiry. Every feature's `RequireAuthorization()` and CSRF
   expectations depend on it, so it goes in before the first feature. The one
   input you can't default is how passwords are verified
   (`ICredentialValidator`): if neither the repo nor the request says, ask the
   user.
3. Confirm `dotnet build` and `dotnet test` both pass on the empty scaffold
   before writing a feature.
4. Work the checklist at the end of `api-bootstrap.md` - it covers the traps
   that fail confusingly rather than loudly.
5. Then continue to **Adding a feature slice**.

Note that step zero above and this section are the same instruction from
opposite ends: match what exists, and when nothing exists, establish it
deliberately so the *next* session has something worth matching.

## Adding a feature slice

Walk through the repo's richest existing feature (ideally one with full CRUD,
ownership, and pagination) side-by-side as you do this.

**1. Create the folder** `Features/{Name}/` (PascalCase, plural if the resource
is a collection - e.g. `Todos`, not `Todo`) alongside the repo's existing
feature folders.

**2. Contracts file** (commonly `Contracts.cs`) - plain C# `record`s for every
request and response shape, no data-annotation attributes if the repo uses a
separate validation library (validation lives in step 3 in that case).

**3. Validators file** (commonly `Validators.cs`) - one validator per request
record that needs validation, named to match the repo's existing convention
(e.g. `{RequestName}Validator` for FluentValidation). Only requests bound from a
body typically need one (query params like `page`/`pageSize` don't). Give every
`string` property a length bound - an unbounded text field is an unbounded
storage/payload liability, not a feature. Short fields (titles, names) commonly
cap around 200 characters; longer free-text fields (body, description, notes)
have no universal precedent, so pick a bound generous enough for real content
but still finite - a few thousand to ~10,000 characters is a reasonable default
absent other guidance from the repo's own conventions.

**4. Entity** (if the feature needs a new table) - see
`references/entities-and-data.md` for the class shape, then wire it into the
shared `DbContext` and add a migration there too.

**5. Endpoints file** (commonly `{Name}Endpoints.cs`) - the bulk of the logic:

- A static class with one extension method on `IEndpointRouteBuilder` (commonly
  `Map{Name}Endpoints`), matching whatever the repo's existing features name
  theirs.
- A route group with a lowercase prefix (e.g. `/todos`). Put an authorization
  requirement on the whole group if *every* endpoint needs a signed-in user;
  apply it per-endpoint instead if it's mixed.
- Handlers as `private static` methods below the map method, taking dependencies
  as parameters (DbContext, `ClaimsPrincipal`, etc. - minimal API DI, no
  constructor injection).
- Read `references/endpoint-cheatsheet.md` before writing the handlers - it
  covers which typed result to return per HTTP verb, when to add
  auth/CSRF/validation filters, the per-user ownership-scoping pattern, and the
  pagination shape.

**6. Wire it into the app's startup** (`Program.cs` or `Startup.cs`) - add the
`using` for the feature's namespace and call its `Map{Name}Endpoints()`
alongside the other feature-mapping calls. Middleware/pipeline *order* in
ASP.NET Core is usually deliberate (auth before CSRF checks, CORS before rate
limiting, exception handling early, etc.) - don't reorder existing lines to fit
a new feature in; only append, and see `references/common-concerns.md` if you're
unsure where something new belongs.

**7. Tests** - one integration-test file per feature in the test project,
following the repo's existing naming and fixture pattern. See
`references/testing.md` for conventions and a minimum coverage checklist.

**8. Verify** - run the repo's build and test commands (typically `dotnet build`
then `dotnet test` from the solution root). Don't report the feature done
without both passing; a scaffold that doesn't compile or breaks existing tests
isn't done.

## Things that might be deliberately missing

Authentication is the exception for greenfield APIs: server-side cookie sessions
are the default there (see `references/cookie-session-auth.md`). In an existing
repo, whatever auth it already has (or deliberately lacks) wins, and switching
schemes is never a side effect of another request.

Minimal/template backends often deliberately omit things like JWT bearer auth,
full ASP.NET Core Identity, or CI/containerization, and document the omission in
a README as a scope decision rather than an oversight. Check for such a note
before adding any of these as a side effect of an unrelated feature - if the
request sounds like it wants one of these, flag it to the user as a bigger
decision than a scaffold, rather than building it silently.

## One repo-wide side effect worth flagging

If a frontend consumes a generated API client from this backend's OpenAPI schema
(check its `package.json`/build scripts for a codegen step - `openapi-ts`,
NSwag, Autorest, etc.), mention after adding or changing endpoints that the
frontend client needs regenerating. Actually running that regeneration is
outside this skill's scope.
