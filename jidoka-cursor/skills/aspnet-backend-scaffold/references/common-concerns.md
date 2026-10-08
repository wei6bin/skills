# Cross-cutting concerns

Vertical-slice codebases in this style commonly keep a `Common/` (or `Shared/`,
`Infrastructure/`) folder for things not owned by any one feature -
correlation-id middleware, a global exception handler, security/antiforgery
helpers, a generic validation filter. A new cross-cutting concern goes there, in
its own subfolder named for the concern, mirroring whatever structure already
exists - not inside a feature folder, even if the first thing that needs it is
one specific feature.

If the `Common/` folder doesn't exist yet because the API is new,
`references/api-bootstrap.md` has a validation filter to start from - that one
is a prerequisite for the first feature rather than something to add later.

## Middleware vs. endpoint filter

- **Middleware** (registered via `app.UseMiddleware<T>()` or `app.Use...()`) -
  for behavior that applies to *every* request regardless of route, like a
  correlation-id header or request logging.
- **Endpoint filter** (`IEndpointFilter`, registered via
  `.AddEndpointFilter<T>()` on specific endpoints/groups) - for behavior that
  only some endpoints need, like antiforgery validation or request validation.
  Prefer this over global middleware when the concern doesn't apply everywhere -
  it keeps "which endpoints do X" answerable by grepping the endpoint-mapping
  files instead of reasoning about implicit global behavior.

## Pipeline order is usually load-bearing

A common (and generally correct) ordering in `Program.cs`/`Startup.cs` looks
something like:

```text
correlation-id / request-logging middleware
exception handling
CORS
rate limiting
authentication
authorization
antiforgery / CSRF validation
```

That ordering assumes **token-based** antiforgery (a token tied to the
authenticated user). The greenfield default in
`references/cookie-session-auth.md` uses a **custom-header** CSRF check instead.
It needs no identity, so it runs *before* authentication and rejects cheaply,
and the rate limiter moves after authentication so per-user limiters can read
claims:

```text
exception handling → HSTS/HTTPS → CORS → CSRF header → authentication → rate limiting → authorization
```

Match whichever of the two the repo already uses.

The reasoning: correlation-id first so every downstream log line carries it;
exception handling early so anything below it that throws still gets a clean
error response; CORS before rate limiting/auth so preflight requests aren't
rejected by policies that don't apply to them; antiforgery *after*
authentication/authorization, since validating a CSRF token only makes sense
once the (cookie-authenticated) caller is known.

Treat this as a sensible default, not gospel - always check the actual
`Program.cs`/`Startup.cs` in the target repo before assuming it matches, and
never reorder existing lines to make room for something new; insert at the point
that matches the new middleware's actual dependency (needs correlation id
already set? needs auth already resolved?). If unsure where something belongs,
ask rather than guess - pipeline ordering bugs are easy to introduce and easy to
miss until a specific request path exercises them.

## Don't reach for what's deliberately not there

Minimal/template backends often document scope cuts in a README - no JWT bearer
auth, no full framework Identity system, no CI/containerization - because those
are genuine future decisions, not oversights. If a request sounds like it wants
one of these (e.g. "add API key auth for a mobile client," "add user roles"),
that's a bigger decision than a scaffold - flag it to the user rather than
silently building it as a side effect of an unrelated feature.
