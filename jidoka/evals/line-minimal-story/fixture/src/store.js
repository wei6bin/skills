// In-memory note store. Ids are sequential strings so tests can predict them.
export function createStore() {
  const notes = new Map();
  let nextId = 1;

  return {
    list() {
      return [...notes.values()];
    },
    get(id) {
      return notes.get(id);
    },
    create({ title, body }) {
      const note = { id: String(nextId++), title, body };
      notes.set(note.id, note);
      return note;
    },
  };
}
