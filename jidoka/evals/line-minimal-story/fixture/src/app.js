import { createServer } from "node:http";
import { createStore } from "./store.js";

const MAX_BODY_BYTES = 16 * 1024;

function send(res, status, payload) {
  if (payload === undefined) {
    res.writeHead(status);
    res.end();
    return;
  }
  res.writeHead(status, { "content-type": "application/json" });
  res.end(JSON.stringify(payload));
}

// Every error response uses this envelope: { error: { code, message } }.
function sendError(res, status, code, message) {
  send(res, status, { error: { code, message } });
}

async function readJson(req) {
  let size = 0;
  const chunks = [];
  for await (const chunk of req) {
    size += chunk.length;
    if (size > MAX_BODY_BYTES) throw new Error("body too large");
    chunks.push(chunk);
  }
  return JSON.parse(Buffer.concat(chunks).toString("utf8"));
}

export function createApp(store = createStore()) {
  return createServer(async (req, res) => {
    const { pathname } = new URL(req.url, "http://localhost");
    const match = pathname.match(/^\/notes(?:\/([^/]+))?$/);
    if (!match) return sendError(res, 404, "not_found", "Route not found");
    const id = match[1];

    if (!id && req.method === "GET") return send(res, 200, store.list());

    if (!id && req.method === "POST") {
      let input;
      try {
        input = await readJson(req);
      } catch {
        return sendError(res, 400, "invalid_json", "Body must be JSON");
      }
      if (typeof input?.title !== "string" || input.title.trim() === "") {
        return sendError(res, 422, "validation_failed", "title is required");
      }
      const body = typeof input.body === "string" ? input.body : "";
      return send(res, 201, store.create({ title: input.title.trim(), body }));
    }

    if (id && req.method === "GET") {
      const note = store.get(id);
      if (!note) return sendError(res, 404, "note_not_found", `Note ${id} not found`);
      return send(res, 200, note);
    }

    return sendError(res, 405, "method_not_allowed", `${req.method} not allowed`);
  });
}
