# notes-api

A small in-memory notes REST API on `node:http`. No dependencies.

- `npm start` serves on `PORT` (default 3000).
- `npm test` runs the suite with the built-in `node:test` runner.

## Endpoints

| Method | Path       | Success               | Errors                                      |
| ------ | ---------- | --------------------- | ------------------------------------------- |
| GET    | /notes     | 200, array of notes   | -                                           |
| POST   | /notes     | 201, the created note | 400 `invalid_json`, 422 `validation_failed` |
| GET    | /notes/:id | 200, the note         | 404 `note_not_found`                        |

Every error body is `{ "error": { "code": "...", "message": "..." } }`.

## Backlog

Story status lives in `BACKLOG.md`, the single source of truth for what is
ready, in progress and done.
