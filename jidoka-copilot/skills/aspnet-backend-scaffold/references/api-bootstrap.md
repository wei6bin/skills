# Bootstrapping a new API (greenfield only)

Read this **only** when there's no API project to match - a brand-new backend,
or a repo where nothing resembling a feature slice exists yet. If the repo
already has even one feature folder, step zero governs: read it and match it,
and ignore everything here.

This file is read once per API. Everything after the first feature goes back
through the main skill.

## First: check the installed SDK, don't write from memory

The .NET SDK ships a new major every year and the templates change with it. Run
`dotnet --list-sdks` and read the generated `.csproj` before writing code - if
anything below disagrees with what the template actually produced, the template
wins.

Things that changed recently enough to catch you out (all verified against .NET
10 / EF Core 10):

| Assumption | Reality |
| --- | --- |
| The solution file is `.sln` | `dotnet new sln` now produces **`.slnx`**, an XML format. Don't hand-write the old format. |
| Swashbuckle for OpenAPI | Built-in `Microsoft.AspNetCore.OpenApi` - `AddOpenApi()` + `MapOpenApi()`, served at `/openapi/v1.json`, emitting **OpenAPI 3.1**. No Swashbuckle needed. |
| `Program` needs `public partial class Program;` before tests can reference it | Only up to .NET 9. On .NET 10 the SDK generates a public `Program` for top-level statements, so `WebApplicationFactory<Program>` compiles as-is (checked on SDK 10.0.300). Add the declaration only when targeting `net9.0` or earlier; on .NET 10 it is harmless but redundant. |
| `dotnet new webapi` means controllers | It defaults to **Minimal APIs** (`--use-controllers` defaults to `false`) and adds a `WeatherForecast` sample. `dotnet new web` is the barer empty host. Either is a fine starting point - just read what the template actually produced instead of assuming. |
| The dev port is stable | `dotnet new web` picks **random** ports in `Properties/launchSettings.json`. Set the `http` profile's `applicationUrl` to the port the frontend's dev proxy targets, or the two halves miss each other. `dotnet run` uses that first (`http`) profile. |
| `dotnet new xunit` means xUnit v3 | On SDK 10.0.300 it still installs **xUnit v2** (2.9), whose `IAsyncLifetime` returns `Task`; xUnit v3 returns `ValueTask`. Match the package the template installed. |

## Project layout

Two projects and a solution. Keep the API project's name as the root namespace.

```bash
dotnet new sln -n <Name>Api -o .
dotnet new web -n <Name>Api -o <Name>Api
dotnet new xunit -n <Name>Api.Tests -o <Name>Api.Tests
dotnet sln add <Name>Api/<Name>Api.csproj <Name>Api.Tests/<Name>Api.Tests.csproj
dotnet add <Name>Api.Tests/<Name>Api.Tests.csproj reference <Name>Api/<Name>Api.csproj
```

```text
<Name>Api/
  Program.cs                 host, DI, pipeline, feature mapping
  Common/                    cross-cutting only - see references/common-concerns.md
    ValidationFilter.cs
    Auth/                    session store, sweep, audit helpers - see references/cookie-session-auth.md
    Middleware/
      CsrfHeaderMiddleware.cs
  Data/
    AppDbContext.cs          one shared context
    Entities/                one class per file (AppUser, UserSession, AuditLog from day one)
  Features/
    Auth/                    login · me · logout
    {Name}/                  Contracts.cs · Validators.cs · {Name}Endpoints.cs
<Name>Api.Tests/
  <Name>ApiFactory.cs        WebApplicationFactory subclass, shared by every feature's tests
  {Name}EndpointsTests.cs    one per feature
```

Delete the template's `WeatherForecast` sample and the test project's
`UnitTest1.cs` - leaving them is how a scaffold starts looking like a tutorial.

## Packages

```bash
# API
dotnet add package Microsoft.EntityFrameworkCore.Sqlite      # or .SqlServer / .Npgsql
dotnet add package Microsoft.EntityFrameworkCore.Design
dotnet add package FluentValidation.DependencyInjectionExtensions
dotnet add package Microsoft.AspNetCore.OpenApi

# Tests
dotnet add package Microsoft.AspNetCore.Mvc.Testing
dotnet add package Microsoft.EntityFrameworkCore.Sqlite
dotnet add package Microsoft.Extensions.TimeProvider.Testing   # FakeTimeProvider for session-expiry tests
```

Cookie auth, Data Protection, rate limiting and `ITicketStore` are all in the
shared framework, so they need no extra package.

`Microsoft.EntityFrameworkCore.Design` is what makes `dotnet ef migrations`
work; without it the tooling fails with an unhelpful message.

## `Program.cs`

Registration order in the service collection doesn't matter. Order in the
**pipeline** does - see `references/common-concerns.md`, and don't deviate from
it without a reason you can state.

```csharp
var builder = WebApplication.CreateBuilder(args);

builder.Services.AddDbContext<AppDbContext>(options =>
    options.UseSqlite(builder.Configuration.GetConnectionString("Default") ?? "Data Source=app.db"));

builder.Services.AddValidatorsFromAssemblyContaining<CreateThingRequestValidator>();
builder.Services.AddOpenApi();

const string DevCorsPolicy = "DevCors";
var allowedOrigins = builder.Configuration.GetSection("Cors:AllowedOrigins").Get<string[]>()
    ?? ["http://localhost:5173"];
builder.Services.AddCors(options => options.AddPolicy(DevCorsPolicy, policy =>
    policy.WithOrigins(allowedOrigins).AllowAnyHeader().AllowAnyMethod()));

// Default auth: cookie sessions + audit log. The full registration block (TimeProvider,
// SessionOptions, ITicketStore, AddCookie, sweep, login rate limiter) is in
// references/cookie-session-auth.md, under "Program.cs wiring".

var app = builder.Build();

app.UseExceptionHandler();
if (!app.Environment.IsDevelopment()) app.UseHsts();
app.UseHttpsRedirection();

if (app.Environment.IsDevelopment())
{
    app.MapOpenApi();
    app.UseCors(DevCorsPolicy);
}

app.UseMiddleware<CsrfHeaderMiddleware>();
app.UseAuthentication();
app.UseRateLimiter();
app.UseAuthorization();

app.MapAuthEndpoints();
app.MapThingsEndpoints();   // one line per feature

app.Run();

// Up to .NET 9 only: top-level statements otherwise leave no accessible Program
// type for WebApplicationFactory<Program>. .NET 10 generates it; omit the line.
public partial class Program;
```

The session cookie is `SameSite=Strict`, so in practice the SPA reaches the API
same-origin, through the dev server's proxy. The CORS policy only exists for
tooling that calls the API directly. See "Frontend contract" in
`references/cookie-session-auth.md`.

Put the CORS origin list in configuration rather than hardcoding a port. A
frontend dev server that finds its default port taken silently moves to the next
one, and a hardcoded origin turns that into a CORS failure that looks like a
backend bug.

## `Common/ValidationFilter.cs`

Every feature's mutating endpoints chain this, so it has to exist before the
first feature. It short-circuits to a 400 so handlers can assume a valid
request.

```csharp
public class ValidationFilter<T>(IValidator<T> validator) : IEndpointFilter
{
    public async ValueTask<object?> InvokeAsync(
        EndpointFilterInvocationContext context, EndpointFilterDelegate next)
    {
        var request = context.Arguments.OfType<T>().FirstOrDefault();
        if (request is null)
        {
            return TypedResults.Problem("Request body was missing or malformed.",
                statusCode: StatusCodes.Status400BadRequest);
        }

        var result = await validator.ValidateAsync(request);
        if (!result.IsValid)
        {
            var errors = result.Errors
                .GroupBy(e => e.PropertyName)
                .ToDictionary(g => g.Key, g => g.Select(e => e.ErrorMessage).ToArray());
            return TypedResults.ValidationProblem(errors);
        }

        return await next(context);
    }
}
```

`TypedResults.ValidationProblem` emits an RFC 9110 problem document whose
`errors` keys are the **C# property names** - `Name`, `StockCount`, PascalCase.
A JavaScript client binding errors to camelCase form fields has to map them.
Mention this when handing the API to a frontend; it's a silent mismatch where
errors simply never appear next to their field.

## Test factory

The main skill says to reuse the repo's existing factory. On greenfield there
isn't one, so this is it - write it before the first feature's tests.

```csharp
public class <Name>ApiFactory : WebApplicationFactory<Program>, IAsyncLifetime
{
    private DbConnection _connection = null!;

    protected override void ConfigureWebHost(IWebHostBuilder builder)
    {
        // Anything but Development, so dev-only seeding and CORS stay out of the tests.
        builder.UseEnvironment(Environments.Staging);

        builder.ConfigureServices(services =>
        {
            var descriptor = services.SingleOrDefault(
                d => d.ServiceType == typeof(DbContextOptions<AppDbContext>));
            if (descriptor is not null) services.Remove(descriptor);

            _connection = new SqliteConnection("Data Source=:memory:");
            _connection.Open();
            services.AddDbContext<AppDbContext>(options => options.UseSqlite(_connection));

            using var provider = services.BuildServiceProvider();
            using var scope = provider.CreateScope();
            scope.ServiceProvider.GetRequiredService<AppDbContext>().Database.EnsureCreated();
        });
    }

    public Task InitializeAsync() => Task.CompletedTask;

    async Task IAsyncLifetime.DisposeAsync()
    {
        if (_connection is not null) await _connection.DisposeAsync();
        await DisposeAsync();
    }
}
```

Two things here are load-bearing and both fail confusingly if you skip them:

- **Hold the connection open for the fixture's lifetime.** An in-memory SQLite
  database is destroyed the moment its last connection closes, so a factory that
  opens and disposes per scope gives every test an empty schema.
- **Remove the existing `DbContextOptions` registration first.** Calling
  `AddDbContext` twice leaves the original provider registered and the tests
  quietly run against the real dev database.

The default auth adds more to this factory: a `FakeTimeProvider`, a fake
`ICredentialValidator`, `Session:SweepEnabled=false`, the CSRF header on every
client, and a `LoginForSessionCookieAsync` helper. Copy them from "Testing" in
`references/cookie-session-auth.md`, and seed the test users once in
`InitializeAsync`.

Sharing one fixture across a test class via `IClassFixture<T>` means tests share
a database. Either give each test unique keys, or reset state between tests -
don't write tests that assume an empty table.

## Dev data seeding

A new API with an empty database is hard to demo and hard to eyeball. A small
idempotent seeder gated to Development earns its keep:

```csharp
if (app.Environment.IsDevelopment())
{
    using var scope = app.Services.CreateScope();
    var db = scope.ServiceProvider.GetRequiredService<AppDbContext>();
    db.Database.EnsureCreated();
    SeedData.EnsureSeeded(db);   // returns immediately if the table is non-empty
}
```

`EnsureCreated()` and migrations are mutually exclusive strategies.
`EnsureCreated()` is fine for a demo or a spike; the moment the schema needs to
evolve against data worth keeping, switch to `dotnet ef migrations add` +
`Database.Migrate()` and don't mix them. See `references/entities-and-data.md`.

## Default tooling choices - only when nothing is established

This whole file already assumes greenfield, but these are the specific picks
worth stating. If a repo already uses the "Over" column, match that instead -
swapping is a deliberate migration, not a scaffold step.

| Need | Prefer | Over | Why |
| --- | --- | --- | --- |
| Request validation | FluentValidation + an endpoint filter | DataAnnotations | Keeps validation out of the contract records, handles cross-field rules, and gives one consistent 400 shape. |
| Dev database | SQLite | LocalDB, a container | Zero setup, one file, runs identically on every OS and in CI. Swap the provider for a real environment. |
| OpenAPI | `Microsoft.AspNetCore.OpenApi` | Swashbuckle, NSwag | First-party and maintained in lockstep with ASP.NET Core, and it reads the typed-results metadata the endpoints already declare. Still an explicit `PackageReference`, just not a third-party one. |
| Integration tests | xUnit + `WebApplicationFactory` + in-memory SQLite | Mocked-repository unit tests | The thing worth testing is the assembled pipeline - routing, filters, validation, serialization - not handler logic in isolation. |

## Before the first feature

- [ ] `dotnet build` and `dotnet test` both pass on the empty scaffold
- [ ] A throwaway test using the factory compiles (on .NET 9 and earlier only
  once `public partial class Program;` is present)
- [ ] `/openapi/v1.json` returns a document in Development
- [ ] The template's sample endpoint and `UnitTest1.cs` are deleted
- [ ] CORS origins come from configuration, not a hardcoded port
- [ ] Default auth is in place: `/auth/login`, `/auth/me` and `/auth/logout`
  pass the auth checklist in `references/cookie-session-auth.md`, and a login
  writes one `UserSession` row and one `LoginSucceeded` `AuditLog` row
- [ ] `Session` options and the Data Protection application name are in
  configuration/`Program.cs`, and production key persistence is decided (not
  left in memory)

Then go back to **Adding a feature slice** in the main skill.
