# Test file conventions

Vertical-slice Minimal API backends commonly have one integration-test file per
feature, doing real HTTP round-trips through a
`WebApplicationFactory<TEntryPoint>` subclass (often backed by an in-memory or
throwaway database) rather than unit tests with mocked dependencies - that's
usually deliberate, since the thing worth testing is the whole pipeline (auth,
CSRF, validation) wired together correctly, not just handler logic in isolation.

```csharp
public class TodosEndpointsTests(TestWebApplicationFactory factory)
    : IClassFixture<TestWebApplicationFactory>
{
    [Fact]
    public async Task GetTodos_WithoutAuth_ReturnsUnauthorized() { ... }
}
```

If the test project has **no** `WebApplicationFactory` subclass yet because the
API itself is new, see `references/api-bootstrap.md` for one to start from -
including the two mistakes that make an in-memory database fail confusingly
rather than loudly.

## Reuse the repo's existing test helpers - don't reimplement them

Under the greenfield default auth (`references/cookie-session-auth.md`), the
helper is `LoginForSessionCookieAsync`. It returns a `name=value` string that
you send as a `Cookie` header on each request, because the test server is plain
http and a client cookie jar won't replay a `Secure` cookie.

Before writing a new test file, check the test project for existing helper
extension methods for things like: registering/authenticating a throwaway test
user, fetching a CSRF token, or seeding common fixtures. New test files should
call these, not duplicate that setup logic inline. If no such helpers exist yet
and the new tests need the same setup other tests will also need, consider
adding one - but don't invent parallel setup logic that quietly diverges from
what other tests already do.

## Response DTOs: check whether the repo defines private mirrors or reuses production contracts

Some codebases in this style declare small `private record` shapes inside the
test file for deserializing responses, deliberately decoupled from the feature's
production contract types, even though the test project could reference them
directly. Others just reuse the production records. Match whichever the repo's
existing test files already do - don't introduce a different approach for one
new feature's tests.

## Minimum coverage checklist

For a feature with ownership-scoped CRUD, this typically means at least:

- [ ] Unauthenticated request → `401 Unauthorized` (if the feature requires
  auth)
- [ ] Happy-path create/read/update/delete round-trip
- [ ] A second authenticated user cannot read/update/delete the first user's
  resource → `404 NotFound` (not `403` - see the ownership-scoping note in
  `references/endpoint-cheatsheet.md`)
- [ ] A mutating request without CSRF protection → the repo's rejection status
  (if the repo uses cookie auth + CSRF). Token-based antiforgery filters usually
  return `400 BadRequest`. The greenfield default's `CsrfHeaderMiddleware`
  returns `403 Forbidden` with `errorCode: "CsrfHeaderMissing"`. Its test
  factory adds the header to every client, so remove it in this test.
- [ ] A mutating request with invalid input (e.g. empty required field) →
  `400 BadRequest`, with the offending field name present in the response body,
  proving validation actually ran

Not every feature needs every one of these (a read-only feature has no
CSRF/validation cases, a public API has no ownership cases) - use judgment based
on what the feature actually does and what the repo's auth model actually is,
but don't skip ownership-isolation tests for anything user-scoped; that's the
check most likely to catch a real security bug.
