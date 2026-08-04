# Vault conventions and query syntax

Read this before editing query blocks in `work/TODOs.md` or the `work/Work Board.base` file.
Every item below is a mistake that was actually made and cost a debugging round trip.

## Bases (`.base` files)

Bases queries **notes with frontmatter properties**. It cannot see inline `- [ ]` checkboxes at
all. This is why threads exist as notes with a `status` property - it is the only reason a board
view is possible.

Native view types: `table`, `cards`, `list`, `map`. **There is no native board/kanban view.**
A cards view grouped by `status` is the closest thing. Drag-and-drop needs a community plugin.

### Property naming is inconsistent by section

Obsidian normalises `.base` files when it saves them, and the canonical form uses **bare
property names everywhere**:

```yaml
filters:
  and:
    - file.inFolder("work/threads")
properties:
  status:                    # bare name
    displayName: Status
views:
  - type: cards
    name: Board
    groupBy:
      property: status       # bare name
      direction: ASC         # required - omitting it throws "groupBy must be a object"
    order:
      - file.name
      - project              # bare name
```

The published docs show a `note.` prefix in `groupBy` and `order`. Obsidian accepts it but
rewrites it away. Match whatever is already in the file rather than reintroducing the prefix.

`groupBy` needs **both** `property` and `direction`. Supplying only `property` produces the
misleading error `"groupBy" must be a object` - the value *is* an object, it is just incomplete.

View-level filters use quoted expressions: `- 'status != "done"'`.

## Tasks plugin queries

Verified working: `not done`, `done`, `due before today`, `has due date`, `tags include #x`,
`sort by due`, `sort by done reverse`, `limit N`.

**Invalid:** `due before in 14 days`. A relative range cannot follow `before`. Use
`due before today` for overdue, or `has due date` plus `sort by due` for everything scheduled.

An invalid line breaks the whole query block, though the failure is contained - it renders an
error box in place of that block rather than breaking the note. Prefer a plain working query
over a clever broken one.

## Dataview queries

`FROM "" AND -"folder"` is not reliably documented and should not be trusted. Filter folders in
the `WHERE` clause instead:

```dataview
TASK
WHERE !completed
  AND !contains(file.path, "archive/")
  AND !contains(file.path, "specs/")
  AND !contains(file.path, "/processed/")
  AND !contains(file.path, "work/threads/")
  AND file.name != "TODOs"
GROUP BY file.link
```

Extend the exclusion list with whichever folders in your own vault use checkbox syntax for
something other than todos.

`TASK ... GROUP BY file.link` is the standard idiom and works. `FROM "Journals"` (a positive
folder source) is fine. Sorting grouped results by `rows.length` is unverified - leave it out.

Note the two exclusions that prevent double-display: `work/threads/` is rolled up separately in
its own section, and `TODOs` is the hub itself.

Ticking a checkbox rendered by a Dataview `TASK` query writes back to the source file, which is
what makes the aggregate-not-move model work.

## Excluded from all task queries

Checkbox syntax gets used for plenty of things that are not todos. In a real vault this is
easily dozens of phantom items, so audit before trusting a roll-up. Common culprits:

| Kind of file | Why its checkboxes are not todos |
|---|---|
| Requirement and user-story specs | acceptance criteria |
| Archive folders | already dead |
| Decision records and tradeoff analyses | options being compared, not actions |
| Implementation runbooks | ordered steps, owned by whoever runs them |

Audit a candidate before adding it to the queries:

```bash
grep -rl "^\s*- \[ \]" --include="*.md" . | head -30
```

## Project-scoped lists

A vault usually grows per-project todo files alongside the project's own notes. Leave them
where they are; the hub surfaces them by query. Migrating their contents into the central hub
strips them of the context that made them meaningful.

## Tags

`#doing` (in progress, individual tasks only), `#waiting` (blocked on another person), plus
one tag per project. Keep the project tag vocabulary short enough to hold in your head.

Dates use Tasks plugin syntax: due `📅 YYYY-MM-DD`, completed `✅ YYYY-MM-DD`.

## Linking to HTML artifacts

There is no such thing as a relative `file://` link - the scheme requires an absolute path.
Practical consequence for linking a report from a thread:

- `[../html/report.html](../html/report.html)` - relative, portable across synced devices,
  opens Obsidian's attachment pane where "Open in default app" launches the browser.
- `[[report.html]]` - same behaviour, resolves by basename.
- `[label](file:///absolute/path)` - one click straight to the browser, but breaks on any
  other machine.

Keeping a relative link plus an absolute one is a reasonable trade rather than a redundancy.
