## Context

The pieces this sits between are measured, not assumed (2026-08-22):

- **The wire into the pty is BINARY, and has no JSON key for input.** The browser sends
  keystrokes as raw binary websocket frames — `term.onData(d => ws.send(encoder.encode(d)))`
  (`web/src/components/FleetTerminal.tsx:492-495`), with the only text message on that socket
  being `{"resize":{rows,cols}}`. The server writes them straight through
  (`lib/set_orch/api/fleet.py:1430-1432` → `OwnerStream.write`). So "type the path into the
  terminal" needs no protocol at all: it is one more binary frame on a socket the panel
  already holds.
- **A clipboard image never reaches that socket by itself.** Measured with a capture-phase
  probe on the live terminal: the working paste key delivers `types: ["text/plain"]`, and
  xterm's own paste handler reads `getData("text/plain")` only. The bytes stay in the
  browser.
- **There is no upload route anywhere in the API package.** `media.py` serves blobs and never
  writes; the single write endpoint is `PUT /api/fleet/files/content` in `files.py`, which is
  text-only and guarded to a project root. Routers are registered with **no prefix** and
  full paths spelled out (`lib/set_orch/api/__init__.py:39-58`), and the order there is
  load-bearing — `files_router` precedes the `/api/{project}/...` families.
- **A durable per-user root already exists**: `SET_TOOLS_DATA_DIR`
  (`$XDG_DATA_HOME/set-core`, fallback `~/.local/share/set-core`) at
  `lib/set_orch/paths.py:32`, with `SetRuntime` (`paths.py:86`) as the per-project layer
  above it.

The reader's two decisions, taken 2026-08-22 and recorded here because a decision that lives
only in a conversation is not a decision: the store goes **outside every project tree**, and
the panel **types the path with a trailing space and no Enter**.

## Goals / Non-Goals

**Goals:**
- A pasted screenshot becomes something the agent in that terminal can open, in one gesture.
- The framework writes only where it owns the ground, and keeps no record of what it carried.
- A failure is visible; a success is quiet, because the typed path is its own receipt.

**Non-Goals:**
- Serving the stored image back to a browser. Nothing reads these over HTTP.
- Drag-and-drop, a file picker, or pasting images anywhere other than a terminal.
- Making the agent do anything with the path.
- Any change to text paste, which was just repaired (`b4d7aa87`) and is not to be disturbed.

## Decisions

### D1 — A NEW module, not an endpoint added to `files.py`

`files.py` owns one project file, read or written in place, and its own header states what it
must never become: *a cache*, *a file manager*, *a merge tool*. A blob store is all three
shapes at once — it creates files, it keeps them, and it is not the reader's file. It also
has an opposite guard: `files.py` confines every path to a **project** root, and this must
confine every path **away** from one.

Alternative considered: a `store=` flag on the existing write endpoint. Rejected — it makes
one guard serve two opposite policies, and the confusion would sit in the single most
safety-relevant function in the repository.

New module `lib/set_orch/api/paste.py`, one route: `POST /api/fleet/paste`. Registered
beside `files_router` in `__init__.py`, before the `/api/{project}/...` families, since its
path is fixed and cannot be shadowed.

### D2 — Content-addressed name, caller's name discarded

Stored as `<sha256-of-bytes>.<ext-from-sniffed-type>` under
`SET_TOOLS_DATA_DIR/paste/`. The caller's file name never touches the path — not sanitised,
**discarded** — which removes the whole class of traversal and encoding bugs rather than
defending against it. Re-pasting the same image is idempotent and costs no space.

Alternative: a random id. Equivalent on safety, worse on duplicates, and it makes a test for
"the same bytes give the same answer" impossible to write.

### D3 — The type is SNIFFED, not believed

The declared `Content-Type` is a claim by the caller. The stored extension and the accept
decision come from the magic bytes (PNG, JPEG, GIF, WebP), and a mismatch is a refusal. A
type check that reads the header is a statement about the request; this needs a statement
about what lands on disk.

### D4 — Expiry is computed from disk, on use — no timer, no daemon

A sweep runs at the start of each store operation: remove entries past the maximum age, then,
while the total exceeds the ceiling, remove oldest-first. Bounds: **8 MB per item, 256 MB
total, 7 days**, all named in one place.

Alternative: a background task. Rejected on this repository's own evidence — a long-lived
service holds the code it started with, and a cleanup that only runs while something is alive
leaves entries behind precisely when the process died, which is when nobody is looking. A
sweep on use has the property the spec asks for: nothing survives merely because the
framework was stopped.

### D5 — Text wins over an image on a mixed paste

A rich-text copy from a browser or a document routinely carries a bitmap of itself beside the
text. Uploading on every such paste would send content nobody chose to send. The panel
therefore reads `text/plain` first and only looks for an image when there is no text — which
also means the repaired text path is untouched in the common case.

### D6 — Where the panel puts the path

Straight onto the existing terminal socket as a binary frame — the same call `onData` makes.
No new message type, no server-side "type this" command, and therefore nothing that could
inject into a terminal from anywhere but the panel the reader is looking at.

### D7 — Logging the shape only

One log line per operation: content type, byte count, outcome, and the rule that refused it
when refused. Never the bytes, never the caller's name, never the stored name. The pattern to
copy is `db_safety.py`, which logs a URL's scheme and nothing else.

## Risks / Trade-offs

- **The agent may not read an absolute path outside the project.** → The reader can move or
  reference it; and the alternative — writing into the consumer's tree — is the operation the
  safety track closed. If this turns out to bite, it is a decision to revisit **with the
  reader**, not a default to quietly change.
- **A store outside a project is a store nobody prunes by hand.** → Bounded three ways
  (per item, total, age) and swept on use, with the bounds in one named place.
- **Sniffing rejects an image type nobody thought of.** → The refusal names the reason, so it
  reads as "this type is not accepted" rather than as a broken paste. Adding a type is one
  constant.
- **A paste can be large and the socket is not the transport.** → The upload is a separate
  HTTP request with its own timeout; the terminal stays usable while it is in flight, and the
  panel says a paste is on its way.
- **The image half looks like the text half and is not.** → The unit tests must assert that a
  text-only paste uploads NOTHING; otherwise a regression that uploads on every paste would
  pass every test that only checks the image case.

## Migration Plan

Additive. A new route and a new directory that is created on first use. No existing endpoint,
schema, or stored state changes. Rollback is removing the route; the store directory can be
deleted at any time, since nothing depends on an entry existing.

## Open Questions

- None blocking. The two that would have blocked — where the bytes land, and what reaches the
  pty — were decided by the reader on 2026-08-22 and are recorded above.
