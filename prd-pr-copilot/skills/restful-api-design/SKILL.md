---
name: restful-api-design
description: >-
  Framework-agnostic RESTful API design and implementation guide covering
  OpenAPI-first design, layered architecture (controller/service/repository),
  authentication (JWT/OAuth2), error handling, pagination, and API testing.
  Apply when designing or implementing REST APIs in any language/framework.
license: MIT
allowed-tools: Read, Grep, Glob, Bash, Write, Edit, AskUserQuestion
---

# RESTful API Design Best Practices

Apply these patterns when building or reviewing REST APIs.

## Design-First with OpenAPI

- **Write the OpenAPI 3.1 spec first**, before any code.
- Use `openapi.yaml` at the repo root or `docs/openapi.yaml`.
- Define all request/response schemas as `$ref` components — never inline.
- Generate server stubs and client SDKs from the spec (no spec drift).
- Validate requests against the spec at runtime (e.g., `express-openapi-validator`, FastAPI's built-in, Springdoc).

## URL Design

```
GET    /resources              # list (paginated)
POST   /resources              # create
GET    /resources/{id}         # read one
PUT    /resources/{id}         # full update
PATCH  /resources/{id}         # partial update
DELETE /resources/{id}         # delete

GET    /resources/{id}/sub-resources   # nested resource (max 2 levels)
POST   /resources/{id}/actions/approve  # RPC-style action as sub-resource
```

- **Plural nouns** for resources, lowercase, kebab-case.
- **No verbs** in URLs — use HTTP method semantics.
- **Avoid** deep nesting beyond 2 levels; flatten with query params instead.
- Version via URL path prefix: `/api/v1/` — not headers.

## HTTP Methods and Status Codes

| Scenario | Method | Success Code |
|---|---|---|
| Create resource | POST | 201 Created |
| Read resource | GET | 200 OK |
| Full update | PUT | 200 OK |
| Partial update | PATCH | 200 OK |
| Delete resource | DELETE | 204 No Content |
| Async action queued | POST | 202 Accepted |

**Error codes:**

| Code | When |
|---|---|
| 400 | Validation failed — include field-level errors |
| 401 | Not authenticated |
| 403 | Authenticated but not authorized |
| 404 | Resource not found |
| 409 | Conflict (duplicate, version mismatch) |
| 422 | Unprocessable entity (business rule violation) |
| 429 | Rate limit exceeded |
| 500 | Internal server error (never expose stack traces) |

## Consistent Error Response

Always return errors in this envelope:

```json
{
  "error": {
    "code": "VALIDATION_FAILED",
    "message": "Request validation failed",
    "details": [
      { "field": "email", "message": "Must be a valid email address" }
    ],
    "traceId": "abc-123"
  }
}
```

- `code`: machine-readable constant, SCREAMING_SNAKE_CASE.
- `message`: human-readable, safe to display.
- `traceId`: correlates to server logs; never omit in production.

## Layered Architecture

```
Controller  →  Service  →  Repository  →  Database
```

| Layer | Responsibility |
|---|---|
| **Controller** | Parse/validate HTTP request, call service, format HTTP response |
| **Service** | Business logic, orchestration, domain rules |
| **Repository** | Data access only — no business logic |
| **DTOs** | Request/response models (separate from domain entities) |

- Controllers are thin — no business logic.
- Services are testable without HTTP context.
- Repositories are testable with a fake/in-memory store.

## Pagination

Prefer **cursor-based** for large/real-time datasets, **offset** for simple admin UIs:

```json
// Cursor-based
{
  "data": [...],
  "pagination": {
    "nextCursor": "eyJpZCI6MTAwfQ==",
    "hasMore": true,
    "pageSize": 20
  }
}

// Offset-based
{
  "data": [...],
  "pagination": {
    "page": 2,
    "pageSize": 20,
    "total": 150,
    "totalPages": 8
  }
}
```

- Default `pageSize`: 20; Max: 100. Always enforce a maximum.
- Support `?fields=id,name` sparse fieldsets for bandwidth.
- Support `?sort=createdAt:desc,name:asc` for multi-column sorting.
- Support `?filter[status]=active&filter[role]=admin` for filtering.

## Authentication & Authorization

**JWT (stateless):**
- Access token: short-lived (15 min), stored in memory (not localStorage).
- Refresh token: long-lived (7 days), `HttpOnly` secure cookie.
- Validate signature, expiry, and `aud`/`iss` claims on every request.
- Invalidate refresh tokens server-side on logout (token denylist or rotation).

**OAuth2 / OIDC:**
- Use Authorization Code + PKCE flow for user-facing APIs.
- Use Client Credentials for service-to-service calls.
- Never implement your own OAuth2 — use a provider (Keycloak, Auth0, Azure AD).

**Authorization:**
- Apply RBAC or ABAC at the service layer, not controller.
- Use policy objects / guard middleware for consistent checks.
- Return `403` (not `404`) only when the resource existence is not sensitive.

## Input Validation

- Validate at the controller boundary before hitting business logic.
- Use schema-based validation (Zod, Joi, Pydantic, Jakarta Validation).
- Sanitize inputs; never trust client data.
- Reject unknown fields to prevent mass assignment vulnerabilities.

## Rate Limiting & Resilience

- Apply rate limiting per client (IP or API key): e.g., 100 req/min default.
- Return `429` with `Retry-After` header.
- Implement request timeouts; circuit breakers for downstream calls.
- Idempotency keys (`Idempotency-Key` header) for POST operations that must not duplicate.

## Security Headers

Always set:
```
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Strict-Transport-Security: max-age=31536000; includeSubDomains
Content-Security-Policy: default-src 'none'
X-Request-Id: <uuid>
```

Never expose:
- Stack traces in error responses.
- Internal IPs, hostnames, or framework version headers.
- Database error messages.

## API Versioning Strategy

- Version: `/api/v1/`, `/api/v2/` — URL path.
- Maintain at least 1 deprecated version alongside the current.
- Communicate deprecation via `Deprecation` + `Sunset` headers.
- Document breaking vs non-breaking changes in a CHANGELOG.

## Testing Strategy

| Layer | Tool | What to test |
|---|---|---|
| Unit | Jest/pytest/JUnit | Service logic, repository, DTOs |
| Integration | Supertest/httpx/RestAssured | Full HTTP request/response cycle |
| Contract | Pact / OpenAPI validation | Spec compliance |
| Load | k6 / Artillery | Throughput, latency percentiles |

**Integration test pattern:**
```ts
it('POST /api/v1/users returns 201 with created user', async () => {
  const res = await request(app)
    .post('/api/v1/users')
    .set('Authorization', `Bearer ${adminToken}`)
    .send({ email: 'test@example.com', name: 'Test User' });
  
  expect(res.status).toBe(201);
  expect(res.body.data).toMatchObject({ email: 'test@example.com' });
  expect(res.body.data.id).toBeDefined();
});
```

## Observability

- Structured JSON logging with `traceId`, `userId`, method, path, statusCode, latency.
- Health endpoint: `GET /health` → `{ status: "ok", version: "1.2.3" }`.
- Readiness: `GET /ready` — checks DB, cache, dependencies.
- Expose metrics in Prometheus format: request count, latency histogram, error rate.

## Companion Skills

- **`backend-implementer`** — Implements backend tasks from a plan document following TDD loop
- **`openapi-to-application-code`** (awesome-copilot) — Generate a complete production-ready application from an OpenAPI spec
