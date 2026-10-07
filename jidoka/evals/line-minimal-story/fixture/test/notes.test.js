import { after, before, test } from "node:test";
import assert from "node:assert/strict";
import { createApp } from "../src/app.js";

let server;
let base;

before(async () => {
  server = createApp();
  await new Promise((resolve) => server.listen(0, resolve));
  base = `http://127.0.0.1:${server.address().port}`;
});

after(() => server.close());

async function createNote(title, body) {
  const res = await fetch(`${base}/notes`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ title, body }),
  });
  return { status: res.status, json: await res.json() };
}

test("POST /notes creates a note", async () => {
  const { status, json } = await createNote("Groceries", "milk");
  assert.equal(status, 201);
  assert.equal(json.title, "Groceries");
  assert.ok(json.id);
});

test("POST /notes rejects a missing title with the error envelope", async () => {
  const { status, json } = await createNote("  ");
  assert.equal(status, 422);
  assert.equal(json.error.code, "validation_failed");
});

test("GET /notes lists created notes", async () => {
  const { json: note } = await createNote("Listed");
  const res = await fetch(`${base}/notes`);
  assert.equal(res.status, 200);
  const notes = await res.json();
  assert.ok(notes.some((n) => n.id === note.id));
});

test("GET /notes/:id returns one note", async () => {
  const { json: note } = await createNote("Single");
  const res = await fetch(`${base}/notes/${note.id}`);
  assert.equal(res.status, 200);
  assert.deepEqual(await res.json(), note);
});

test("GET /notes/:id returns 404 with the error envelope for an unknown id", async () => {
  const res = await fetch(`${base}/notes/does-not-exist`);
  assert.equal(res.status, 404);
  assert.equal((await res.json()).error.code, "note_not_found");
});
