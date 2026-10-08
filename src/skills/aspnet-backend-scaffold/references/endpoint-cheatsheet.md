# Endpoint handler conventions

These are common patterns in vertical-slice Minimal API codebases. Confirm each
against the repo's own reference feature(s) before relying on it - treat the
code below as illustrative, not a literal template.

## Return types per verb

Minimal API endpoints in this style typically return `TypedResults` (or
`Results<T1, T2, ...>` union types when there's more than one possible outcome),
not bare `IResult` or `Results.Ok()` - the typed variants keep the generated
OpenAPI schema (and therefore any generated client) accurate.

| Verb / situation | Return type | Notes |
| --- | --- | --- |
| GET list | `Task<Ok<PagedResult<TResponse>>>` | See pagination below |
| GET by id | `Task<Results<Ok<TResponse>, NotFound>>` | |
| POST create | `Task<Created<TResponse>>`, or a union with a conflict branch (`Results<Ok<T>, ProblemHttpResult>`) if the create can fail on a uniqueness constraint (e.g. duplicate email on registration) | |
| PUT update | `Task<Results<Ok<TResponse>, NotFound>>` | |
| DELETE | `Task<Results<NoContent, NotFound>>` | |
| Auth failure surfaced deliberately (not via `[Authorize]`/`RequireAuthorization`) | Include `UnauthorizedHttpResult` in the `Results<>` union | e.g. a login endpoint returning 401 on bad credentials rather than throwing |

`Created<T>` takes the new resource's location string first:
`TypedResults.Created($"/{route}/{id}", response)`.

## Endpoint filters - when to add which

If the repo uses endpoint filters (`IEndpointFilter`, chained via
`.AddEndpointFilter<T>()`), a mutating endpoint commonly chains something like:

```csharp
group.MapPost("/", CreateThingAsync)
    .AddEndpointFilter<AntiforgeryEndpointFilter>()   // if the repo has one
    .AddEndpointFilter<ValidationFilter<CreateThingRequest>>();
```

- **A CSRF/antiforgery filter** - if the repo uses cookie-based auth with
  *per-endpoint* antiforgery, add its filter to *every* state-mutating endpoint
  (POST/PUT/DELETE/PATCH) reachable by a browser session. Skip it for endpoints
  that don't rely on cookie auth (e.g. a bearer-token-only API). If the repo
  instead has a global CSRF middleware (as in the greenfield default in
  `references/cookie-session-auth.md`, a `CsrfHeaderMiddleware`), there is
  nothing to add per endpoint. Don't layer an antiforgery filter on top of it.
- **A validation filter** - add whenever the endpoint binds a request record
  that has a matching validator. It should short-circuit to a 400 before your
  handler runs, so the handler body can assume the request is already valid.
- **Rate limiting** - for sensitive, often-unauthenticated endpoints (login,
  registration, password reset), to blunt credential-stuffing/enumeration. Any
  named policy must already be registered in the app's rate-limiter
  configuration; don't invent a policy name the pipeline doesn't know about.
- **Authorization requirement** - at the route-group level if the whole feature
  requires a signed-in user, or per-endpoint if it's a mix (e.g. a public
  login/register endpoint alongside an authenticated "current user" endpoint in
  the same group).

## Ownership scoping (per-user data)

When a resource belongs to a user, the common pattern is to extract the caller's
id and filter every query by it - ownership enforced by the query itself, not a
separate authorization layer:

```csharp
private static Guid GetUserId(ClaimsPrincipal user) =>
    Guid.Parse(user.FindFirstValue(ClaimTypes.NameIdentifier)!);
```

Then every query includes `.Where(t => t.UserId == userId)` (or an equivalent
`FirstOrDefaultAsync(x => x.Id == id && x.UserId == userId)`). A record
belonging to someone else should come back as `NotFound`, **not** `Forbidden` -
returning 404 instead of 403 avoids confirming to an attacker that the resource
exists at all.

This kind of helper is often duplicated per feature file rather than pulled into
a shared location - that's a defensible choice consistent with keeping each
vertical slice self-contained. Don't "clean this up" into a shared abstraction
unless asked; a one-line private helper usually isn't worth the coupling.

## Pagination

A common shape:

```csharp
public record PagedResult<T>(IReadOnlyList<T> Items, int Page, int PageSize, int TotalCount);
```

Clamp inputs in the handler rather than validating them (bad paging params
aren't a client error worth a 400, just default them):

```csharp
page = Math.Max(page, 1);
pageSize = Math.Clamp(pageSize, 1, 100);
```

If only one existing feature needs paging, this record type may live in that
feature's own contracts file rather than in a shared location. Whether a second
feature that also needs paging should duplicate the record or promote it to a
shared location is a genuine judgment call - ideally ask the user. If you're
scaffolding unattended and can't ask, default to **duplicating** the record into
the new feature's own contracts file (keeps features independent, matches the
vertical-slice philosophy, and is trivially easy to consolidate later) rather
than promoting it to a shared location on your own - a wrong "keep separate"
choice costs a small refactor later, a wrong "shared abstraction" choice adds a
cross-feature dependency that's more awkward to unwind.

## Query tracking

If using EF Core: `.AsNoTracking()` on read-only queries; no `AsNoTracking()` on
queries that will be mutated and saved (load the entity tracked so
`SaveChangesAsync` picks up the change).

## IDs and timestamps

New rows commonly get `Id = Guid.NewGuid()` and a UTC creation timestamp
assigned explicitly in the handler (e.g. `CreatedAtUtc = DateTime.UtcNow`)
rather than relying on a database default - check the repo's entity conventions
(`references/entities-and-data.md`) for the exact property naming it uses.
