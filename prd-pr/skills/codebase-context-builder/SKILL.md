---
name: codebase-context-builder
description: Generates docs/project_context/ by analysing a codebase from scratch - stack, structure, conventions, domain entities, build environment - and seeds prod_spec/ for the context-updater. Context generation only; no story analysis or task breakdown. Invoked by the orchestrator when project context is missing, or directly to bootstrap a repo ("build project context", "analyse this codebase").
allowed-tools: Read, Grep, Glob, Bash, Write, Edit
---

# Codebase Context Builder

Context generation only. Return control when done; do not proceed to story analysis.

## Analyse

1. **Stack**: read manifests (`package.json`, `*.csproj`/`*.sln`, `pyproject.toml`/`requirements.txt`, `pom.xml`/`build.gradle`, `go.mod`), Dockerfiles/compose, CI files, `CLAUDE.md`/`AGENTS.md`/`README.md`. Extract languages, frameworks, build/test/run scripts, key dependencies (UI lib, ORM, test framework, state), deployment target.
2. **Structure**: map source directories 2-3 levels deep (skip `node_modules`, build output). Identify feature modules, shared code, API/service/data layers, test layout.
3. **Conventions**: sample 2-3 files per layer (endpoints, services, repositories, models/DTOs, UI components) and extract naming, imports, error handling, DTO shape, DI usage.
4. **Domain**: read 3-5 core model files; extract entities, key fields, relationships, lifecycle states.

## Generate `docs/project_context/`

Always:

- `00_index.md` - task-to-file lookup with actual file references
- `01_architectural_overview.md` - layers, patterns, tech found
- `02_domain_model.md` - entities and workflows inferred from code
- `04_build_environment.md` - how the dev loop actually runs, because a hot-reload rebuild that contends with an implementer's edit on `obj/` or `.vite/deps/` looks like a product bug ("API is dead"). Seed, marking `[TODO: confirm]` where uncertain: hot-reload runner (host/container `dotnet watch`, `vite`, none); rebuild-trigger globs; binary-lock paths during rebuild; multi-file edit recipe (pause the watcher, `--no-restore`, `--no-hot`); each shared dev service (db, api, redis) with its **non-destructive** restart, never `docker compose down -v`.

By detected stack: `16_frontend_react_typescript.md`, `15_dotnet_aspnet_patterns.md`, `17_python_patterns.md`, `18_java_legacy_patterns.md`, `19_database_schema.md` (ORM found), `05_api_contracts.md` (REST endpoints found), `20_deployment_pipeline.md` (CI found). Use any templates already in the folder as the base; leave placeholders where a value is not discoverable from code.

Always seed `docs/project_context/prod_spec/` for the `context-updater` skill: `graph.md` (the five section headings from that skill), `index.md` (file manifest, `graph.md` first), `features.md`, `domain_rules.md`, `config_decisions.md`, `decisions.md`, each a heading plus `<!-- Populated by context-updater -->`.

Add a `## Project Context Files` lookup table to `CLAUDE.md` if absent, and an agent workflow guide to `AGENTS.md` referencing the context files.

## Report

```
Project context generated:
  ✅ docs/project_context/00_index.md
  ... (every generated file)

Sections requiring manual input:
  ⚠️  02_domain_model.md - business rules (not inferrable from code)
  ... (every gap)

Ready for the orchestrator.
```
