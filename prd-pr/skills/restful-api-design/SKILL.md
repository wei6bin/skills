---
name: restful-api-design
description: House conventions for REST APIs in any language - OpenAPI-first, the error envelope, pagination shapes, controller/service/repository layering, JWT/OAuth2 choices, validation and versioning. Apply when designing or implementing REST endpoints; project conventions in docs/project_context/ override it.
license: MIT
allowed-tools: Read, Grep, Glob, Bash, Write, Edit, AskUserQuestion
---

# RESTful API Design

House conventions. Project conventions in `docs/project_context/` override these.

## Design-first

Write or update the OpenAPI 3.1 spec (`openapi.yaml` at the root or in `docs/`) before code; schemas as `$ref` components; validate requests against it at runtime where the framework supports it. Plural kebab-case nouns, no verbs, nesting at most two levels, RPC-style actions as `POST /resources/{id}/actions/approve`, version in the path (`/api/v1/`).

## Status codes

201 create · 200 read/update · 204 delete · 202 async accepted. Errors: 400 validation (with field-level details) · 401 unauthenticated · 403 unauthorised (404 instead when existence is sensitive) · 404 · 409 conflict · 422 business-rule violation · 429 with `Retry-After` · 500 never exposing internals.

## Error envelope

```json
{ "error": { "code": "VALIDATION_FAILED", "message": "Request validation failed",
             "details": [{ "field": "email", "message": "Must be a valid email address" }],
             "traceId": "abc-123" } }
```

`code` is a SCREAMING_SNAKE_CASE constant, `message` is safe to display, `traceId` correlates to logs and is never omitted.

## Layering

Controller (parse, validate, call service, format response) → Service (business logic, testable without HTTP) → Repository (data access only, testable with a fake). DTOs are separate from domain entities. Validate at the controller boundary with a schema library and reject unknown fields.

## Pagination

Cursor-based for large or real-time sets, offset for simple admin UIs:

```json
{ "data": [], "pagination": { "nextCursor": "…", "hasMore": true, "pageSize": 20 } }
{ "data": [], "pagination": { "page": 2, "pageSize": 20, "total": 150, "totalPages": 8 } }
```

Default page size 20, max 100, always enforced. `?sort=createdAt:desc,name:asc`, `?filter[status]=active`, `?fields=id,name`.

## Auth

JWT: short-lived access token (~15 min) in memory, long-lived refresh token (~7 days) in an `HttpOnly` secure cookie, rotated or denylisted on logout; validate signature, expiry, `aud`/`iss` on every request. OAuth2/OIDC: Authorization Code + PKCE for users, Client Credentials for services, always via a provider. Authorisation (RBAC/ABAC) lives in the service layer via policy objects or guards, not in controllers.

## Resilience and observability

Per-client rate limiting, request timeouts, circuit breakers on downstream calls, `Idempotency-Key` on non-idempotent POSTs. Structured JSON logs with `traceId`, `userId`, method, path, status, latency. `GET /health` (status, version) and `GET /ready` (dependencies). Deprecate versions with `Deprecation` + `Sunset` headers.

## Testing

Unit for services and repositories; integration through the full HTTP cycle (Supertest / httpx / RestAssured); contract via OpenAPI validation or Pact; load via k6 when the NFRs demand it.
