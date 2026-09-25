---
name: codebase-context-builder
description: Generates docs/project_context/ files by analysing a codebase from scratch. Use this only for context GENERATION - it does NOT handle user stories or task breakdown. Called by the orchestrator when project context is missing. Can also be invoked directly to bootstrap a new repo.
allowed-tools: Read, Grep, Glob, Bash, Write, Edit
---

# Codebase Context Builder

**Scope**: Context file generation only — no user story analysis, no task breakdown.
Called automatically by the `orchestrator` skill when `docs/project_context/` is absent or empty.
Can be invoked directly to onboard a new repo.

---

## When to Invoke

- The `orchestrator` skill finds context missing → chains here
- User says: "build project context", "analyse this codebase", "set up project context"
- Fresh repo with no `CLAUDE.md` or empty one from `/init`

---

## Phase 1 — Stack Detection

Read whatever exists from this list:

```
package.json / package-lock.json
*.csproj, *.sln
pyproject.toml, requirements.txt, setup.py
pom.xml, build.gradle
Dockerfile, docker-compose.yml
azure-pipelines.yml, .github/workflows/*.yml
CLAUDE.md, AGENTS.md, README.md
```

Extract:
- Primary language(s) and frameworks
- Build/test/run scripts
- Key dependencies (UI lib, ORM, test framework, state management)
- Deployment target

---

## Phase 2 — Structure Scan

```bash
# Map source directory 2–3 levels deep (skip noise)
find . -maxdepth 3 -type d \
  | grep -v node_modules | grep -v .git | grep -v bin \
  | grep -v obj | grep -v __pycache__ | grep -v dist
```

Identify:
- Feature modules / bounded contexts (folders under `src/features/`, `src/modules/`, etc.)
- Shared / common code
- API / endpoint layer
- Service / business logic layer
- Data / repository layer
- Test layout (co-located vs separate `tests/`)

---

## Phase 3 — Pattern Sampling

Sample 2–3 representative files per layer found in Phase 2 (UI components, API endpoints/handlers, services, data access, domain models/DTOs) - files typical of the codebase, not just the first search hit.

Extract from samples:
- Naming conventions
- Import/using patterns
- Error handling style
- DTO/model shape
- How DI is used

---

## Phase 4 — Domain Entity Detection

Find and read the 3–5 core domain model files - the entities the rest of the code most often references.

Extract: entity names, key fields, relationships, lifecycle states.

---

## Phase 5 — Generate Context Files

Create `docs/project_context/` if it doesn't exist.

**Always generate:**
- `00_index.md` — filled with actual file references
- `01_architectural_overview.md` — actual layers, patterns, tech found
- `02_domain_model.md` — entities discovered, workflows inferred from code

**Generate based on detected stack:**

| Stack detected | File to generate |
|---------------|-----------------|
| React + TypeScript | `16_frontend_react_typescript.md` |
| ASP.NET Core / C# | `15_dotnet_aspnet_patterns.md` |
| Python (FastAPI/Django/Flask) | `17_python_patterns.md` |
| Java / WCF / WPF / SOAP | `18_java_legacy_patterns.md` |
| SQL + ORM (EF Core / SQLAlchemy) | `19_database_schema.md` |
| REST endpoints found | `05_api_contracts.md` |
| CI/CD pipeline file found | `20_deployment_pipeline.md` |

If `docs/project_context/` already holds template files, use them as the base structure; otherwise create the files in the table above.
Fill in discovered values; leave template placeholders where information is not discoverable from code.

**Always create `docs/project_context/prod_spec/`** — seed it with empty-but-structured files so the `context-updater` skill has a place to write product knowledge post-implementation:

```
docs/project_context/prod_spec/
├── index.md              ← "Product knowledge index — updated by context-updater after each implementation session"
├── features.md           ← "# Features\n\n<!-- Populated by context-updater -->"
├── domain_rules.md       ← "# Domain Rules\n\n<!-- Populated by context-updater -->"
├── config_decisions.md   ← "# Config Decisions\n\n<!-- Populated by context-updater -->"
└── decisions.md          ← "# Design Decisions\n\n<!-- Populated by context-updater -->"
```

**Update `CLAUDE.md`** — add `## Project Context Files` section with task-to-file lookup table if not already present.

**Update or create `AGENTS.md`** — add agent workflow guide referencing the context files.

---

## Completion Report

After generating files, output:

```
Project context generated:
  ✅ docs/project_context/00_index.md
  ✅ docs/project_context/01_architectural_overview.md
  ✅ docs/project_context/02_domain_model.md
  ✅ docs/project_context/16_frontend_react_typescript.md
  [list all generated]

Sections requiring manual input:
  ⚠️  02_domain_model.md — business rules (not inferrable from code)
  ⚠️  10_integration_points.md — external system credentials/URLs
  [list gaps]

Ready for the orchestrator.
```

Then **return control** — do not proceed to story analysis or task breakdown.
