# Default authentication: server-side cookie sessions (`ITicketStore`) + audit log

This is the **default** auth model when bootstrapping a new API
(`references/api-bootstrap.md` links here). If the target repo already has an
auth scheme, step zero governs: match it. Don't swap JWT for cookies, or the
other way round, as a side effect of some other request. That's a migration the
user has to decide on.

## The model in one paragraph

The browser gets one HttpOnly `__Host-` cookie whose only payload is an **opaque
session key**: the id of a `UserSession` row. The serialized
`AuthenticationTicket`, the idle and absolute deadlines, and how and when the
session ended all live in the database. ASP.NET Core's own
`CookieAuthenticationOptions.SessionStore` (`ITicketStore`) hook does the work,
so there is no hand-rolled cookie writing. Every session event (login success or
failure, sign-out, idle timeout, absolute expiry) writes exactly one `AuditLog`
row. A single conditional `UPDATE … WHERE EndedAt IS NULL` decides which of
several possible callers "wins" ending a session, so concurrent requests, logout
and the background sweep can never write two audit rows for one session.

Why this over JWT: sessions can be ended server-side immediately (logout and
revocation actually work), idle timeout is enforced by the server rather than
trusted to the client, no token is reachable from JavaScript, and the audit
trail comes from the same writes that change session state.

## Files

```text
Common/
  Auth/
    AppClaimTypes.cs           custom claim names beyond ClaimTypes.*
    AuditActions.cs            AuditLog.Action constants
    AuditLogTruncate.cs        User-Agent → column length
    CookieAuthTicketStore.cs   ITicketStore: Store / Retrieve / Renew / Remove
    SessionAuditLog.cs         builds the AuditLog row for a session event
    SessionDeadline.cs         min(idle, absolute) + which one won
    SessionEndReasons.cs       UserSession.EndReason constants
    SessionEnding.cs           single-writer TryEndAsync
    SessionOptions.cs          + SessionOptionsValidator.cs
    SessionSweepService.cs     BackgroundService + PeriodicTimer
    SessionSweeper.cs          one sweep pass, directly testable
    UserPrincipalFactory.cs    AppUser → ClaimsPrincipal
    ICredentialValidator.cs    pluggable "is this password right" (AD/LDAP, IdP, hash…)
  Middleware/
    CsrfHeaderMiddleware.cs
Data/Entities/
  AppUser.cs  UserSession.cs  AuditLog.cs
Features/Auth/
  AuthEndpoints.cs  Contracts.cs  Validators.cs
```

Snippets below omit `using`s. Beyond what ImplicitUsings provides, they need:
`System.Security.Claims`, `System.ComponentModel.DataAnnotations`,
`Microsoft.AspNetCore.Authentication`,
`Microsoft.AspNetCore.Authentication.Cookies`,
`Microsoft.AspNetCore.Http.HttpResults`, `Microsoft.AspNetCore.DataProtection`
(`SetApplicationName`), `Microsoft.AspNetCore.RateLimiting`
(`AddFixedWindowLimiter`), `Microsoft.EntityFrameworkCore`,
`Microsoft.Extensions.Options`, and `FluentValidation`.

## Entities

If the repo already has a user entity, point `UserSession.UserId` and
`AuditLog.PerformedById` at it and use its login-name column wherever `Username`
appears below.

```csharp
public class AppUser
{
    public Guid Id { get; set; }
    [MaxLength(200)] public required string Username { get; set; }     // the login identifier
    [MaxLength(200)] public required string DisplayName { get; set; }
    [MaxLength(50)]  public required string Role { get; set; }
    public bool Active { get; set; }
}

// The cookie only ever carries this row's Id. Everything else about the session lives here.
public class UserSession
{
    public Guid Id { get; set; }
    public Guid UserId { get; set; }
    public DateTimeOffset CreatedAt { get; set; }
    public DateTimeOffset LastSeenAt { get; set; }
    public DateTimeOffset ExpiresAt { get; set; }       // sliding idle deadline, clamped to the absolute bound
    public DateTimeOffset? EndedAt { get; set; }
    [MaxLength(50)] public string? EndReason { get; set; }
    public byte[]? Ticket { get; set; }                 // nulled when the session ends

    public AppUser? User { get; set; }
}

// Append-only. PerformedById is nullable: a LoginFailed row for an unknown username has no user
// to point at, so PerformedByUsername (a snapshot, not a FK) is what "who" is read from.
public class AuditLog
{
    public Guid Id { get; set; }
    public Guid? PerformedById { get; set; }
    [MaxLength(200)] public string? PerformedByUsername { get; set; }
    [MaxLength(50)]  public required string Action { get; set; }
    [MaxLength(100)] public required string EntityReference { get; set; }   // "UserSession:{id}" / "Username:{name}"
    [MaxLength(100)] public string? Detail { get; set; }                    // failure errorCode
    [MaxLength(45)]  public string? IpAddress { get; set; }                 // fits IPv6
    [MaxLength(512)] public string? UserAgent { get; set; }
    public DateTimeOffset CreationDateTime { get; set; }

    public AppUser? PerformedBy { get; set; }
}
```

`OnModelCreating`:

```csharp
modelBuilder.Entity<UserSession>(e =>
{
    e.HasIndex(s => s.LastSeenAt).HasFilter("EndedAt IS NULL");   // keeps the sweep's open-session scan small
    e.HasIndex(s => new { s.UserId, s.CreatedAt });
    e.HasOne(s => s.User).WithMany().HasForeignKey(s => s.UserId).OnDelete(DeleteBehavior.Restrict);
});
modelBuilder.Entity<AuditLog>(e =>
{
    e.HasIndex(a => a.CreationDateTime);
    e.HasIndex(a => new { a.PerformedById, a.CreationDateTime });
    e.HasOne(a => a.PerformedBy).WithMany().HasForeignKey(a => a.PerformedById).OnDelete(DeleteBehavior.Restrict);
});
```

On SQL Server, you can also make the PK nonclustered and cluster on `CreatedAt`
(`HasKey(...).IsClustered(false)`, `HasIndex(s => s.CreatedAt).IsClustered()`),
because random-Guid PKs fragment a clustered index. `IsClustered` comes from the
SqlServer provider package, so leave it out on SQLite or Postgres.

## Constants and small helpers

```csharp
public static class AuditActions
{
    public const string LoginSucceeded = "LoginSucceeded";
    public const string LoginFailed = "LoginFailed";
    public const string SignedOut = "SignedOut";
    public const string SessionIdleTimeout = "SessionIdleTimeout";
    public const string SessionAbsoluteExpiry = "SessionAbsoluteExpiry";
    public const string SessionRevoked = "SessionRevoked";        // reserved for admin force-sign-out
}

public static class SessionEndReasons
{
    public const string SignedOut = "SignedOut";
    public const string IdleTimeout = "IdleTimeout";
    public const string AbsoluteExpiry = "AbsoluteExpiry";
    public const string Revoked = "Revoked";
}

public static class AppClaimTypes
{
    public const string DisplayName = "display_name";
}

public static class AuditLogTruncate
{
    private const int MaxUserAgentLength = 512;
    public static string? UserAgent(string? value) =>
        string.IsNullOrEmpty(value) ? value : value[..Math.Min(value.Length, MaxUserAgentLength)];
}

// Shared by the ticket store's Retrieve/Remove AND the sweep, so the "next request" path and the
// proactive path can never disagree about which bound expired.
public static class SessionDeadline
{
    public readonly record struct Result(DateTimeOffset AbsoluteBound, DateTimeOffset Deadline, bool IsAbsolute)
    {
        public string EndReason => IsAbsolute ? SessionEndReasons.AbsoluteExpiry : SessionEndReasons.IdleTimeout;
        public string AuditAction => IsAbsolute ? AuditActions.SessionAbsoluteExpiry : AuditActions.SessionIdleTimeout;
    }

    public static Result Resolve(DateTimeOffset createdAt, DateTimeOffset expiresAt, TimeSpan absoluteLimit)
    {
        var absoluteBound = createdAt + absoluteLimit;
        var deadline = expiresAt < absoluteBound ? expiresAt : absoluteBound;
        return new Result(absoluteBound, deadline, deadline == absoluteBound);
    }
}

public static class SessionAuditLog
{
    public static AuditLog Build(
        Guid userId, string username, string action, Guid sessionId, DateTimeOffset when,
        string? ipAddress = null, string? userAgent = null) => new()
    {
        Id = Guid.NewGuid(),
        PerformedById = userId,
        PerformedByUsername = username,
        Action = action,
        EntityReference = $"UserSession:{sessionId}",
        IpAddress = ipAddress,
        UserAgent = userAgent,
        CreationDateTime = when,
    };
}

public static class UserPrincipalFactory
{
    public static ClaimsPrincipal Create(AppUser user) => new(new ClaimsIdentity(
    [
        new Claim(ClaimTypes.NameIdentifier, user.Id.ToString()),
        new Claim(ClaimTypes.Name, user.Username),
        new Claim(AppClaimTypes.DisplayName, user.DisplayName),
        new Claim(ClaimTypes.Role, user.Role),
    ], CookieAuthenticationDefaults.AuthenticationScheme));
}
```

## Options, validated at startup

```csharp
public class SessionOptions
{
    public TimeSpan IdleTimeout { get; set; } = TimeSpan.FromMinutes(30);
    public TimeSpan AbsoluteLimit { get; set; } = TimeSpan.FromHours(12);
    public TimeSpan SweepInterval { get; set; } = TimeSpan.FromMinutes(1);
    public bool SweepEnabled { get; set; } = true;
}

// "Absolute > idle" is cross-property, so DataAnnotations can't express it.
public class SessionOptionsValidator : IValidateOptions<SessionOptions>
{
    public ValidateOptionsResult Validate(string? name, SessionOptions o)
    {
        var failures = new List<string>();
        if (o.IdleTimeout <= TimeSpan.Zero) failures.Add("IdleTimeout must be greater than zero.");
        if (o.SweepInterval <= TimeSpan.Zero) failures.Add("SweepInterval must be greater than zero.");
        if (o.AbsoluteLimit <= o.IdleTimeout) failures.Add("AbsoluteLimit must be greater than IdleTimeout.");
        return failures.Count == 0 ? ValidateOptionsResult.Success : ValidateOptionsResult.Fail(failures);
    }
}
```

`appsettings.json`:

```json
"Session": { "IdleTimeout": "00:30:00", "AbsoluteLimit": "12:00:00", "SweepInterval": "00:01:00", "SweepEnabled": true }
```

`SessionOptions` collides with `Microsoft.AspNetCore.Builder.SessionOptions`
(pulled in by ImplicitUsings). Add
`using SessionOptions = <Name>Api.Common.Auth.SessionOptions;` in `Program.cs`.

## The single-writer end (the piece everything else depends on)

```csharp
public static class SessionEnding
{
    // Exactly one caller ever gets a non-null result for a given session: logout, Retrieve's
    // expiry check, Remove's fallback, and the sweep can all race, and only the winner audits.
    public static async Task<SessionEndResult?> TryEndAsync(
        AppDbContext db, Guid sessionId, string endReason, DateTimeOffset endedAt, CancellationToken ct)
    {
        var session = await db.UserSessions.AsNoTracking()
            .Where(s => s.Id == sessionId)
            .Select(s => new { s.UserId, Username = s.User!.Username })
            .FirstOrDefaultAsync(ct);
        if (session is null) return null;

        var affected = await db.UserSessions
            .Where(s => s.Id == sessionId && s.EndedAt == null)
            .ExecuteUpdateAsync(set => set
                .SetProperty(s => s.EndedAt, endedAt)
                .SetProperty(s => s.EndReason, endReason)
                .SetProperty(s => s.Ticket, (byte[]?)null), ct);

        return affected > 0 ? new SessionEndResult(session.UserId, session.Username) : null;
    }
}

public record SessionEndResult(Guid UserId, string Username);
```

The affected-row count, not the preceding read, is what decides the winner.
Don't "simplify" this into load-entity, check `EndedAt`, then save. That
reintroduces the race and duplicates audit rows.

## `CookieAuthTicketStore`

It's a singleton, because `AddCookie`'s options are built before a request scope
exists, so it resolves a scoped `DbContext` per call through
`IServiceScopeFactory`. `CookieAuthenticationHandler` calls the
**`(…, HttpContext, CancellationToken)` overloads**, which are default interface
members on `ITicketStore`. Implement those, and make the four abstract members
delegate to them.

```csharp
public class CookieAuthTicketStore(
    IServiceScopeFactory scopeFactory, TimeProvider timeProvider, IOptions<SessionOptions> sessionOptions)
    : ITicketStore
{
    public const string SessionIdItemKey = "session.id";

    public Task<string> StoreAsync(AuthenticationTicket ticket) => StoreAsync(ticket, null, default);
    public Task RenewAsync(string key, AuthenticationTicket ticket) => RenewAsync(key, ticket, null, default);
    public Task<AuthenticationTicket?> RetrieveAsync(string key) => RetrieveAsync(key, null, default);
    public Task RemoveAsync(string key) => RemoveAsync(key, null, default);

    // Login. Session row + LoginSucceeded audit row in ONE SaveChangesAsync (one transaction).
    public async Task<string> StoreAsync(AuthenticationTicket ticket, HttpContext? http, CancellationToken ct)
    {
        using var scope = scopeFactory.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<AppDbContext>();
        var userId = Guid.Parse(ticket.Principal.FindFirstValue(ClaimTypes.NameIdentifier)!);
        var username = ticket.Principal.FindFirstValue(ClaimTypes.Name)!;
        var now = timeProvider.GetUtcNow();
        var deadline = now + sessionOptions.Value.IdleTimeout;
        ticket.Properties.ExpiresUtc = deadline;

        var session = new UserSession
        {
            Id = Guid.NewGuid(), UserId = userId,
            CreatedAt = now, LastSeenAt = now, ExpiresAt = deadline,
            Ticket = TicketSerializer.Default.Serialize(ticket),
        };
        db.UserSessions.Add(session);
        db.AuditLogs.Add(SessionAuditLog.Build(
            userId, username, AuditActions.LoginSucceeded, session.Id, now,
            http?.Connection.RemoteIpAddress?.ToString(),
            AuditLogTruncate.UserAgent(http?.Request.Headers.UserAgent.ToString())));
        await db.SaveChangesAsync(ct);
        return session.Id.ToString();
    }

    // Every authenticated request.
    public async Task<AuthenticationTicket?> RetrieveAsync(string key, HttpContext? http, CancellationToken ct)
    {
        if (!Guid.TryParse(key, out var id)) return null;
        using var scope = scopeFactory.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<AppDbContext>();

        var session = await db.UserSessions.FirstOrDefaultAsync(s => s.Id == id, ct);
        if (session is null || session.EndedAt is not null || session.Ticket is null) return null;

        var now = timeProvider.GetUtcNow();
        var current = SessionDeadline.Resolve(session.CreatedAt, session.ExpiresAt, sessionOptions.Value.AbsoluteLimit);
        var deadline = current.Deadline;

        if (now >= deadline)
        {
            // Lapsed: end + audit, timestamped at the COMPUTED deadline, not "now".
            if (await SessionEnding.TryEndAsync(db, id, current.EndReason, deadline, ct) is { } ended)
            {
                db.AuditLogs.Add(SessionAuditLog.Build(ended.UserId, ended.Username, current.AuditAction, id, deadline));
                await db.SaveChangesAsync(ct);
            }
            return null;
        }

        AuthenticationTicket? ticket;
        try { ticket = TicketSerializer.Default.Deserialize(session.Ticket); }
        catch (Exception) { return null; }          // corrupt blob → 401, never a 500
        if (ticket is null) return null;            // Deserialize can also return null without throwing

        // Throttled sliding touch: write at most once a minute per session.
        if (now - session.LastSeenAt > TimeSpan.FromMinutes(1))
        {
            session.LastSeenAt = now;
            var slid = now + sessionOptions.Value.IdleTimeout;
            session.ExpiresAt = slid < current.AbsoluteBound ? slid : current.AbsoluteBound;
            deadline = session.ExpiresAt;
            ticket.Properties.ExpiresUtc = deadline;                       // BEFORE re-serializing
            session.Ticket = TicketSerializer.Default.Serialize(ticket);
            await db.SaveChangesAsync(ct);
        }

        ticket.Properties.Items[SessionIdItemKey] = key;   // lets /auth/logout find "this request's session"
        ticket.Properties.ExpiresUtc = deadline;           // keep the framework's own expiry check in step with the DB
        return ticket;
    }

    // The framework's own sliding refresh. Same clamp, no audit.
    public async Task RenewAsync(string key, AuthenticationTicket ticket, HttpContext? http, CancellationToken ct)
    {
        if (!Guid.TryParse(key, out var id)) return;
        using var scope = scopeFactory.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<AppDbContext>();
        var session = await db.UserSessions.FirstOrDefaultAsync(s => s.Id == id && s.EndedAt == null, ct);
        if (session is null) return;

        var now = timeProvider.GetUtcNow();
        var absoluteBound = session.CreatedAt + sessionOptions.Value.AbsoluteLimit;
        var slid = now + sessionOptions.Value.IdleTimeout;
        session.ExpiresAt = slid < absoluteBound ? slid : absoluteBound;
        session.LastSeenAt = now;
        ticket.Properties.ExpiresUtc = session.ExpiresAt;
        session.Ticket = TicketSerializer.Default.Serialize(ticket);
        await db.SaveChangesAsync(ct);
    }

    // Fallback writer. /auth/logout has normally already ended the session, so this no-ops.
    // Derive the reason from the row instead of hardcoding SignedOut: the framework can call this for expiry too.
    public async Task RemoveAsync(string key, HttpContext? http, CancellationToken ct)
    {
        if (!Guid.TryParse(key, out var id)) return;
        using var scope = scopeFactory.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<AppDbContext>();
        var row = await db.UserSessions.AsNoTracking().Where(s => s.Id == id)
            .Select(s => new { s.CreatedAt, s.ExpiresAt }).FirstOrDefaultAsync(ct);
        if (row is null) return;

        var now = timeProvider.GetUtcNow();
        var d = SessionDeadline.Resolve(row.CreatedAt, row.ExpiresAt, sessionOptions.Value.AbsoluteLimit);
        var lapsed = now >= d.Deadline;
        var endedAt = lapsed ? d.Deadline : now;

        if (await SessionEnding.TryEndAsync(db, id, lapsed ? d.EndReason : SessionEndReasons.SignedOut, endedAt, ct) is { } ended)
        {
            db.AuditLogs.Add(SessionAuditLog.Build(
                ended.UserId, ended.Username, lapsed ? d.AuditAction : AuditActions.SignedOut, id, endedAt,
                lapsed ? null : http?.Connection.RemoteIpAddress?.ToString(),
                lapsed ? null : AuditLogTruncate.UserAgent(http?.Request.Headers.UserAgent.ToString())));
            await db.SaveChangesAsync(ct);
        }
    }
}
```

## Background sweep

`RetrieveAsync` only notices a lapsed session when its owner comes back. The
sweep handles the users who never do.

```csharp
public static class SessionSweeper
{
    public static async Task SweepOnceAsync(AppDbContext db, TimeProvider clock, SessionOptions options, CancellationToken ct)
    {
        var now = clock.GetUtcNow();
        // Only a null check runs server-side. SQLite can't reliably translate DateTimeOffset comparisons,
        // and the filtered index on EndedAt IS NULL keeps this set small on every provider.
        var open = await db.UserSessions.AsNoTracking()
            .Where(s => s.EndedAt == null)
            .Select(s => new { s.Id, s.CreatedAt, s.ExpiresAt })
            .ToListAsync(ct);

        foreach (var s in open)
        {
            var d = SessionDeadline.Resolve(s.CreatedAt, s.ExpiresAt, options.AbsoluteLimit);
            if (now < d.Deadline) continue;
            if (await SessionEnding.TryEndAsync(db, s.Id, d.EndReason, d.Deadline, ct) is { } ended)
            {
                db.AuditLogs.Add(SessionAuditLog.Build(ended.UserId, ended.Username, d.AuditAction, s.Id, d.Deadline));
                await db.SaveChangesAsync(ct);
            }
        }
    }
}

public class SessionSweepService(
    IServiceScopeFactory scopeFactory, TimeProvider clock, IOptions<SessionOptions> options,
    ILogger<SessionSweepService> logger) : BackgroundService
{
    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        if (!options.Value.SweepEnabled) return;          // same knob production and tests use

        using var timer = new PeriodicTimer(options.Value.SweepInterval, clock);
        while (await timer.WaitForNextTickAsync(stoppingToken))
        {
            try
            {
                using var scope = scopeFactory.CreateScope();
                var db = scope.ServiceProvider.GetRequiredService<AppDbContext>();
                await SessionSweeper.SweepOnceAsync(db, clock, options.Value, stoppingToken);
            }
            catch (Exception ex) when (ex is not OperationCanceledException)
            {
                logger.LogError(ex, "Session sweep pass failed; will retry on the next tick.");
            }
        }
    }
}
```

## CSRF: custom-header middleware

`SameSite=Strict` is the primary defence. Requiring a custom header on every
mutating verb is defence in depth: a cross-site `<form>` can't set custom
headers, and a cross-origin `fetch` that sets one triggers a CORS preflight,
which the CORS policy rejects. This replaces per-endpoint antiforgery-token
filters, and it covers `/auth/login` too.

```csharp
public class CsrfHeaderMiddleware(RequestDelegate next)
{
    public const string HeaderName = "X-App-Client";      // rename per app, keep the frontend in sync

    private static readonly HashSet<string> MutatingMethods = new(StringComparer.OrdinalIgnoreCase)
        { HttpMethods.Post, HttpMethods.Put, HttpMethods.Patch, HttpMethods.Delete };

    public async Task InvokeAsync(HttpContext context)
    {
        if (MutatingMethods.Contains(context.Request.Method) && context.Request.Headers[HeaderName] != "1")
        {
            context.Response.StatusCode = StatusCodes.Status403Forbidden;
            await context.Response.WriteAsJsonAsync(new
            {
                title = "This request is missing a required client header.",
                status = 403,
                errorCode = "CsrfHeaderMissing",
            });
            return;
        }
        await next(context);
    }
}
```

## Credential check is pluggable

The session machinery doesn't care how a password is verified. Put that behind
one interface and register whatever the organisation actually uses (AD/LDAP
bind, an IdP, a local password hash). If the identity source isn't obvious from
the repo or the request, **ask the user**. Don't invent a local password table
as a silent default. Tests always swap in a fake.

```csharp
public enum CredentialCheckResult { Success, InvalidCredentials, AccountLocked, AccountDisabled, ServiceUnavailable }

public interface ICredentialValidator
{
    Task<CredentialCheckResult> ValidateAsync(string username, string password, CancellationToken ct);
}
```

## `Features/Auth/AuthEndpoints.cs`

```csharp
public record LoginRequest(string Username, string Password);
public record LoginResponse(UserSummary User);
public record UserSummary(Guid Id, string Username, string DisplayName, string Role);

// Validators.cs: bounded lengths so the audit columns (Username 200) can't overflow.
public class LoginRequestValidator : AbstractValidator<LoginRequest>
{
    public LoginRequestValidator()
    {
        RuleFor(x => x.Username).NotEmpty().MaximumLength(200);
        RuleFor(x => x.Password).NotEmpty().MaximumLength(256);
    }
}

public static class AuthEndpoints
{
    public static IEndpointRouteBuilder MapAuthEndpoints(this IEndpointRouteBuilder app)
    {
        var group = app.MapGroup("/auth").WithTags("Auth");
        group.MapPost("/login", LoginAsync)
            .AddEndpointFilter<ValidationFilter<LoginRequest>>()
            .RequireRateLimiting("login");
        group.MapGet("/me", GetMe).RequireAuthorization();
        group.MapPost("/logout", LogoutAsync).RequireAuthorization();
        return app;
    }

    private static async Task<Results<Ok<LoginResponse>, ProblemHttpResult>> LoginAsync(
        LoginRequest request, HttpContext http, ICredentialValidator credentials,
        AppDbContext db, TimeProvider clock, CancellationToken ct)
    {
        // One LoginFailed row per failure branch; errorCode doubles as Detail. A 400 (validation)
        // or 429 (rate limit) never reaches this body, so neither is audited.
        async Task<ProblemHttpResult> FailAsync(string errorCode, string detail, int status)
        {
            var performedById = await db.AppUsers.AsNoTracking()
                .Where(u => u.Username == request.Username).Select(u => (Guid?)u.Id).FirstOrDefaultAsync(ct);
            db.AuditLogs.Add(new AuditLog
            {
                Id = Guid.NewGuid(),
                PerformedById = performedById,
                PerformedByUsername = request.Username,
                Action = AuditActions.LoginFailed,
                EntityReference = $"Username:{request.Username}",
                Detail = errorCode,
                IpAddress = http.Connection.RemoteIpAddress?.ToString(),
                UserAgent = AuditLogTruncate.UserAgent(http.Request.Headers.UserAgent.ToString()),
                CreationDateTime = clock.GetUtcNow(),
            });
            await db.SaveChangesAsync(ct);
            return TypedResults.Problem(detail: detail, statusCode: status,
                extensions: new Dictionary<string, object?> { ["errorCode"] = errorCode });
        }

        switch (await credentials.ValidateAsync(request.Username, request.Password, ct))
        {
            case CredentialCheckResult.ServiceUnavailable:
                return await FailAsync("ServiceUnavailable", "The authentication service is unavailable. Please try again later.", 503);
            case CredentialCheckResult.AccountLocked:
                return await FailAsync("AccountLocked", "This account is locked.", 401);
            case CredentialCheckResult.AccountDisabled:
                return await FailAsync("AccountDisabled", "This account is disabled.", 401);
            case CredentialCheckResult.InvalidCredentials:
                return await FailAsync("InvalidCredentials", "The username or password is incorrect.", 401);
        }

        // Provisioning and role checks come AFTER the credential check. Checking them first would let an
        // unauthenticated caller enumerate which usernames exist, or which hold a role, by comparing responses.
        var user = await db.AppUsers.AsNoTracking().FirstOrDefaultAsync(u => u.Username == request.Username && u.Active, ct);
        if (user is null)
        {
            return await FailAsync("NotProvisioned", "This account is not provisioned for this application.", 401);
        }

        // StoreAsync writes the UserSession row and the LoginSucceeded audit row.
        await http.SignInAsync(CookieAuthenticationDefaults.AuthenticationScheme, UserPrincipalFactory.Create(user));
        return TypedResults.Ok(new LoginResponse(new UserSummary(user.Id, user.Username, user.DisplayName, user.Role)));
    }

    private static Ok<UserSummary> GetMe(ClaimsPrincipal principal) => TypedResults.Ok(new UserSummary(
        Guid.Parse(principal.FindFirstValue(ClaimTypes.NameIdentifier)!),
        principal.FindFirstValue(ClaimTypes.Name)!,
        principal.FindFirstValue(AppClaimTypes.DisplayName)!,
        principal.FindFirstValue(ClaimTypes.Role)!));

    // Ends the session with SignedOut BEFORE SignOutAsync, so this call wins the single-writer race
    // and RemoveAsync's fallback writes nothing: exactly one SignedOut row.
    private static async Task<NoContent> LogoutAsync(HttpContext http, TimeProvider clock, CancellationToken ct)
    {
        var auth = await http.AuthenticateAsync(CookieAuthenticationDefaults.AuthenticationScheme);
        if (auth.Properties?.Items.TryGetValue(CookieAuthTicketStore.SessionIdItemKey, out var key) == true
            && Guid.TryParse(key, out var sessionId))
        {
            var db = http.RequestServices.GetRequiredService<AppDbContext>();
            var now = clock.GetUtcNow();
            if (await SessionEnding.TryEndAsync(db, sessionId, SessionEndReasons.SignedOut, now, ct) is { } ended)
            {
                db.AuditLogs.Add(SessionAuditLog.Build(
                    ended.UserId, ended.Username, AuditActions.SignedOut, sessionId, now,
                    http.Connection.RemoteIpAddress?.ToString(),
                    AuditLogTruncate.UserAgent(http.Request.Headers.UserAgent.ToString())));
                await db.SaveChangesAsync(ct);
            }
        }

        await http.SignOutAsync(CookieAuthenticationDefaults.AuthenticationScheme);
        return TypedResults.NoContent();
    }
}
```

If only one role may use the app at all (an admin portal, say), add a role gate
right after the provisioning check: audit `LoginFailed` with Detail
`"NotAuthorized"` and return 401 **without** calling `SignInAsync`, so no
session row is created. Keep it after the credential check for the same
enumeration reason.

## `Program.cs` wiring

```csharp
builder.Services.AddSingleton(TimeProvider.System);   // the store, sweep and endpoints all read this clock

builder.Services.AddSingleton<IValidateOptions<SessionOptions>, SessionOptionsValidator>();
builder.Services.AddOptions<SessionOptions>().Bind(builder.Configuration.GetSection("Session")).ValidateOnStart();

builder.Services.AddSingleton<ICredentialValidator, /* the real implementation */>();

// Explicit app name: two apps on one host must never be able to decrypt each other's cookies.
builder.Services.AddDataProtection().SetApplicationName("<Name>Api");

builder.Services.AddSingleton<ITicketStore, CookieAuthTicketStore>();
builder.Services.AddAuthentication(CookieAuthenticationDefaults.AuthenticationScheme)
    .AddCookie(options =>
    {
        options.Cookie.Name = "__Host-<name>.session";   // __Host- ⇒ Secure, Path=/, no Domain
        options.Cookie.HttpOnly = true;
        options.Cookie.SecurePolicy = CookieSecurePolicy.Always;
        options.Cookie.SameSite = SameSiteMode.Strict;
        options.Cookie.Path = "/";
        options.Cookie.IsEssential = true;
        // An API answers 401/403. It never redirects to a login page.
        options.Events.OnRedirectToLogin = ctx => { ctx.Response.StatusCode = 401; return Task.CompletedTask; };
        options.Events.OnRedirectToAccessDenied = ctx => { ctx.Response.StatusCode = 403; return Task.CompletedTask; };
    });
// SessionStore needs the DI-built ITicketStore, so it's set here rather than inside AddCookie.
builder.Services.AddOptions<CookieAuthenticationOptions>(CookieAuthenticationDefaults.AuthenticationScheme)
    .Configure<ITicketStore, IOptions<SessionOptions>>((options, store, session) =>
    {
        options.SessionStore = store;
        options.ExpireTimeSpan = session.Value.IdleTimeout;
        options.SlidingExpiration = true;
    });
builder.Services.AddAuthorization();
builder.Services.AddHostedService<SessionSweepService>();

builder.Services.AddRateLimiter(options =>
{
    options.RejectionStatusCode = StatusCodes.Status429TooManyRequests;
    options.AddFixedWindowLimiter("login", o =>
    {
        o.Window = TimeSpan.FromMinutes(1);
        o.PermitLimit = builder.Configuration.GetValue<int?>("RateLimiting:LoginPermitLimit") ?? 20;
        o.QueueLimit = 0;
    });
});
builder.Services.AddProblemDetails();
```

Pipeline, in this order:

```csharp
app.UseExceptionHandler();
// app.UseForwardedHeaders(...) behind a TLS-terminating proxy, so RemoteIpAddress in the audit log is the client's
if (!app.Environment.IsDevelopment()) app.UseHsts();
app.UseHttpsRedirection();
app.UseCors(...);
app.UseMiddleware<CsrfHeaderMiddleware>();   // needs no identity, so it runs before auth and rejects cheaply
app.UseAuthentication();
app.UseRateLimiter();                        // after auth, so per-user partitioned limiters can read claims
app.UseAuthorization();

app.MapAuthEndpoints();
```

### Data Protection keys must survive restarts

The cookie is protected by the Data Protection key ring. An in-memory key ring
is lost on restart or app-pool recycle, and every live session then turns into a
silent 401. In production, either persist keys explicitly
(`.PersistKeysToFileSystem(...)`, or a shared store for multi-node farms where
any node can serve any request), or confirm the host provides a persistent
profile (IIS: app pool **Load User Profile = true**). A startup check that
throws when no writable key location exists turns "random mass logouts" into a
deploy-time failure.

## Frontend contract

Hand this to whoever builds the client:

- Send `X-App-Client: 1` (or whatever you named it) on every
  POST/PUT/PATCH/DELETE, including login.
- Use `credentials: 'include'` or `'same-origin'`. There is no token to store,
  and nothing auth-related goes into `localStorage`.
- `SameSite=Strict` plus `__Host-` means the SPA should reach the API
  **same-origin**. In dev, that means a Vite/devserver proxy for `/api`, not
  cross-origin CORS calls.
- `GET /auth/me` returns the current user. Any 401 means the session ended
  (idle, absolute, logged out elsewhere), so sign the user out client-side.
- Logout is `POST /auth/logout` (204). Don't just clear client state.

## Testing

Add to the test factory (see `references/api-bootstrap.md`). Package:
`Microsoft.Extensions.TimeProvider.Testing`.

```csharp
public class FakeCredentialValidator : ICredentialValidator
{
    public const string ValidPassword = "P@ssw0rd!";
    public CredentialCheckResult? Override { get; set; }   // force AccountLocked / ServiceUnavailable / …

    public Task<CredentialCheckResult> ValidateAsync(string username, string password, CancellationToken ct) =>
        Task.FromResult(Override ?? (password == ValidPassword ? CredentialCheckResult.Success : CredentialCheckResult.InvalidCredentials));
}
```

```csharp
public readonly FakeTimeProvider Clock = new(DateTimeOffset.UtcNow);
public readonly FakeCredentialValidator Credentials = new();
public const string SessionCookieName = "__Host-<name>.session";

// in ConfigureWebHost:
builder.ConfigureAppConfiguration((_, config) => config.AddInMemoryCollection(new Dictionary<string, string?>
{
    // A live sweep would race the tests' own DB assertions whenever the fake clock moves.
    ["Session:SweepEnabled"] = "false",
}));
builder.ConfigureServices(services =>
{
    services.RemoveAll<TimeProvider>();
    services.AddSingleton<TimeProvider>(Clock);
    services.RemoveAll<ICredentialValidator>();
    services.AddSingleton<ICredentialValidator>(Credentials);
});

// Every client sends the CSRF header by default. Tests of the CSRF gate remove it explicitly.
protected override void ConfigureClient(HttpClient client)
{
    base.ConfigureClient(client);
    client.DefaultRequestHeaders.Add(CsrfHeaderMiddleware.HeaderName, "1");
}

// The test server talks plain http, so a client cookie jar won't replay a Secure cookie.
// Pull it out of Set-Cookie and send it as a Cookie header yourself.
public static async Task<string> LoginForSessionCookieAsync(HttpClient client, string username)
{
    var response = await client.PostAsJsonAsync("/auth/login", new LoginRequest(username, FakeCredentialValidator.ValidPassword));
    response.EnsureSuccessStatusCode();
    return response.Headers.GetValues("Set-Cookie")
        .Single(h => h.StartsWith(SessionCookieName + "=", StringComparison.Ordinal))
        .Split(';', 2)[0];
}
```

Seed users in `InitializeAsync`: an active user, an inactive one, and a username
the fake validator accepts but the DB doesn't contain (for NotProvisioned).

Audit assertions say "exactly one row", so they must not see rows written by
other tests. With a shared `IClassFixture` database, advance `Clock` at the
start of each test and only count rows whose `CreationDateTime` is later than
that point. Alternatively, give each auth test its own factory. Do the filtering
client-side: SQLite can't translate `DateTimeOffset` comparisons.

Auth test checklist:

- [ ] Login succeeds → `Set-Cookie` has `httponly`, `secure`, `samesite=strict`,
  `path=/`, and **no** `expires`/`max-age`. The cookie then works against
  `/auth/me`.
- [ ] Login succeeds → exactly one `LoginSucceeded` audit row and one open
  `UserSession`.
- [ ] Each credential failure → the right status and `errorCode`, one
  `LoginFailed` row with that `Detail`, and no `Set-Cookie`.
- [ ] Login without the CSRF header → 403 `CsrfHeaderMissing`, and **no** audit
  row (the credential validator never ran).
- [ ] Logout → 204 and exactly one `SignedOut` row. `/auth/me` with the same
  cookie then returns 401, and a second logout returns 401.
- [ ] `Clock.Advance(IdleTimeout + 1s)` → `/auth/me` returns 401, and the row
  ends with `IdleTimeout`.
- [ ] Past `AbsoluteLimit` with continuous activity → 401 with `AbsoluteExpiry`.
- [ ] `SessionSweeper.SweepOnceAsync` called directly after advancing the clock
  → ends the row and writes one audit row. Running it again writes nothing.
- [ ] `/auth/me` without a cookie → 401 with no `Location` header (never a
  redirect). A `Bearer` header never authenticates.
- [ ] Feature endpoints: unauthenticated → 401, and a mutating call without the
  CSRF header → **403**.

## When the default doesn't fit

| Situation | Adjust |
| --- | --- |
| Two apps (e.g. clinical + admin portal) share the `UserSession`/`AuditLog` tables | Add a required `Application` column to both. Stamp it on every write and add `&& s.Application == Current` to **every** session query: Store, Retrieve, Renew, Remove, `TryEndAsync`, and the sweep. Otherwise one app's sweep ends the other's sessions. Give each app its own cookie name (browsers don't isolate cookies by port) and its own Data Protection application name. |
| Pure machine-to-machine API, no browser | Cookies are the wrong tool. Use bearer tokens or client credentials, and raise it with the user. |
| Needs "sign out everywhere" or admin revoke | `SessionEnding.TryEndAsync(..., SessionEndReasons.Revoked, ...)` + `AuditActions.SessionRevoked`. The constants are already reserved. |
| More audit events later (data changes, not just auth) | Reuse `AuditLog` with a new `Action` constant and an `EntityReference` of `"{Entity}:{id}"`. Don't create a second audit table. |
