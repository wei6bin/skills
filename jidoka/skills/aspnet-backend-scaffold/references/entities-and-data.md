# Entities, DbContext, and migrations

## Entity class shape

Entities in this style typically live in a `Data/Entities/` (or similar) folder,
one class per file, as a plain mutable class rather than a `record` - entities
are tracked and mutated by EF Core, and a record's value-equality semantics
would be actively wrong for that:

```csharp
public class Todo
{
    public Guid Id { get; set; }
    public Guid UserId { get; set; }
    public required string Title { get; set; }
    public bool IsComplete { get; set; }
    public DateTime? DueDate { get; set; }
    public DateTime CreatedAtUtc { get; set; }
}
```

Common conventions:

- A `Guid Id` primary key.
- A `Guid {Owner}Id` foreign key property (e.g. `UserId`) whenever the row
  belongs to a user - this is what the endpoint layer's ownership scoping
  filters on (see `references/endpoint-cheatsheet.md`).
- The `required` modifier on non-nullable reference-type properties when
  nullable reference types are enabled, instead of a constructor.
- A `CreatedAtUtc`-style property (confirm the exact naming the repo already
  uses) on anything created once and read later.

## Wiring into the shared DbContext

Add a `DbSet` property:

```csharp
public DbSet<Todo> Todos => Set<Todo>();
```

And, in `OnModelCreating`, any indices or relationships the entity needs. Common
patterns to mirror:

```csharp
// Unique constraint
modelBuilder.Entity<User>()
    .HasIndex(u => u.Email)
    .IsUnique();

// FK to another entity, cascade delete
modelBuilder.Entity<Todo>()
    .HasOne<User>()
    .WithMany()
    .HasForeignKey(t => t.UserId)
    .OnDelete(DeleteBehavior.Cascade);
```

Use `OnDelete(DeleteBehavior.Cascade)` for owned data that should disappear with
its owner, and think twice before using it for anything else.

## Adding a migration

From the backend project's root (adjust paths to the repo's actual layout):

```bash
dotnet tool restore   # if the repo pins a dotnet-ef version via a local tool manifest - only needed once, or after that manifest changes
dotnet ef migrations add <Name> --project <path-to-API-project> --startup-project <path-to-API-project>
```

Name the migration for what it does (`AddNotesTable`, `AddNoteArchivedFlag`) -
PascalCase, no spaces, matching the naming style of the repo's existing
migrations.

Check whether the app applies migrations automatically on startup (commonly a
`db.Database.Migrate()` call gated to the Development environment in
`Program.cs`). If so, no manual step is needed to update the local database - it
updates itself the next time the app runs. Don't hand-edit the database file or
the generated migration files afterward.
