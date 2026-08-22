## Context

The fleet screen shows what every agent is doing and lets a person type at one. What it
cannot do is show the file an agent is talking about. Measured on 2026-08-22 before any of
this was written:

- `web/` has **no** code-rendering dependency at all — every code-shaped surface in the
  dashboard is a raw `<pre className="whitespace-pre-wrap">` (12 of them, e.g.
  `web/src/components/LogPanel.tsx:206`, `GateDetail.tsx:72`).
- `lib/set_orch/api/` has **no** file-tree endpoint and **no** general blob endpoint. What
  exists is narrow and per-purpose: `.log` tails (`media.py:25`), a reflection file
  (`media.py:48`), plan JSON (`orchestration.py:386`) and a screenshot server with a MIME
  whitelist (`media.py:217`).
- The guard pattern to copy does exist, twice: `media.py:238-262` resolves the path and
  requires `is_relative_to` one of a set of allowed roots, and `fleet.py:667` `_known_roots()`
  builds a `realpath` set of registered project roots.

A sibling project has already solved the same problem, and this change adopts its shape
rather than inventing a second one: `@monaco-editor/react@4.7`, a file list from
`git ls-files --cached --others --exclude-standard`, a 500 KB content cap, a content-hash
conflict check on write, and a `realpath` target guard.

Three decisions were taken by the user on 2026-08-22 and are inputs here, not open questions:
an **editor with saving** rather than a read-only viewer, **Monaco**, and a **panel in the
fleet grid** rather than a separate page.

## Goals / Non-Goals

**Goals:**
- Open the file an agent just named, at the line it named, without leaving the screen.
- Edit and save it, and refuse rather than clobber when somebody else changed it meanwhile.
- Add exactly one new write path into a project tree, and guard it at the endpoint.
- Keep the framework free of the consumer's domain: display everything, persist nothing.

**Non-Goals:**
- A second editor. This is not an IDE: no multi-file search, no rename, no create or delete,
  no git history, no diff against a ref.
- Editing anything outside a registered project root.
- Merging concurrent edits. A changed file is refused; the person decides.
- More than one file open at a time.

## Decisions

### D1 — Monaco, loaded lazily

`@monaco-editor/react`, dynamically imported inside the panel's effect exactly as
`FleetTerminal` imports xterm. A reader who never opens a file never downloads it.

*Why:* it is proven in the sibling project for this exact job, and it brings highlighting,
line marking, and the road to a diff view with it. *Alternatives:* CodeMirror 6 (~200 KB,
lighter, would need its own line-marking work) and Shiki (most accurate colouring, but static
HTML — jumping to a line and editing would both be ours to build). Both were offered; Monaco
was chosen.

*The cost, stated:* Monaco is the largest dependency in `web/`, and it wants web workers.
The dashboard is served from a local server with no CDN reachable, so the default
CDN-loading configuration must NOT be used — Monaco is bundled locally and the loader
pointed at it. A build that quietly falls back to the CDN would work on the developer's
machine and fail on an offline one, which is the failure direction that gets shipped.

### D2 — The file list comes from git, with a bounded walk as the fallback

`git ls-files --cached --others --exclude-standard` in the project root: one process, the
project's own ignore rules honoured for free, and files an agent wrote but has not committed
included — which is precisely the file a reader wants to open.

*Fallback:* a project that is not a git repository gets a bounded directory walk that skips
the usual heavy directories. It is a fallback, and the answer says which of the two produced
it, because "no files" from a non-repo and "no files" from an empty repo are different facts.

*The cap is stated, never silent.* The answer carries the entries, the cap, and whether it was
cut. A short list that reads as a complete one is the false-absence shape this repository
keeps meeting.

### D3 — One flat list, the tree built in the browser

The endpoint returns paths; the panel builds the directory tree from them. *Why:* one request
instead of one per expanded directory, no server-side state about what is expanded, and the
cap is a single number in a single place. *Trade-off:* a very large project sends more up
front — bounded by D2's cap, and measured against it.

### D4 — The guard is at the endpoint, on the RESOLVED path

Both endpoints resolve the requested path with symlinks followed, and refuse unless the result
is inside a registered project root (`realpath`, the `fleet.py:667` shape). The refusal is
identical whether or not anything exists at the path, so the endpoint cannot be used to probe
the filesystem.

*Why on the resolved path:* a link is exactly how a confined path reaches an unconfined place.
Checking the requested string — the `server.py:159` shape, `".." not in path` — passes a
symlink straight through.

### D5 — Conflict detection by content identity, not by timestamp

A read returns a sha256 of the bytes it served; a write must carry the identity the caller
last read, and is refused if the file no longer matches. *Why not mtime:* two writes inside
one second are indistinguishable by mtime, and on this screen the other writer is an agent
running flat out. *Why refuse rather than merge:* a merge that goes wrong here silently
destroys an agent's work.

### D6 — A new panel type, not a new page

`fleet-dockable-views` already types panels and docks them to edges, and explicitly puts
"what any particular view SHOWS" out of its scope. The file view is one more type under it, so
it inherits docking, sizing and the grid's remaining-space arithmetic without touching them.

Its instance identity is the **project**, not the agent: one file view per project, which is
also what makes "open this file from that agent's terminal" land somewhere predictable.

### D7 — The terminal link, and the route that has to exist anyway

A link provider registered on the terminal recognises project-relative and in-project absolute
paths with an optional `:line`, and activation opens the panel.

**The measured uncertainty, carried into a task rather than assumed away:** an agent's TUI
turns on mouse tracking (`enable-mouse-events`, measured on a live agent 2026-08-22), and in
that state xterm forwards mousedown to the application and cancels it unless Shift is held
(`shouldForceSelection` is `shiftKey` on Linux — read from the bundle). Whether the linkifier's
separate `click` handler still fires is **not measured**, and one attempt to measure it on a
live agent was inconclusive.

So the design does not depend on it. The panel and its file list are the route that always
works; mouse activation is an addition, and which modifier it needs is decided by a
measurement task, not by this document. Whatever the answer, the screen states the route —
a control that silently does nothing under the ordinary condition is worse than an absent one.

### D8 — What a write may touch, and what it says

The write endpoint touches exactly the one file named, inside a registered project root. It
does not create files, directories, or anything else, and it has no relationship with the
deploy manifest or the install ledger — this is a person editing their own project's file,
not the framework deploying into it. Each accepted write logs the project, the path and the
byte count at INFO. Never the content.

## Risks / Trade-offs

- **[A new, deliberate write path into a project tree]** → The repository's 2026-07-19 safety
  track exists because such paths were unguarded. Mitigation: the guard is a spec requirement
  with its own scenarios (traversal, symlink-out, indistinguishable refusal), tested against a
  real temporary tree, and the write is refused on any conflict rather than resolved.
- **[Monaco falls back to a CDN and the dashboard breaks offline]** → Bundle Monaco locally and
  configure the loader explicitly; a task asserts the built asset carries no external loader
  URL.
- **[Mouse activation may not reach the terminal while an agent holds the mouse]** → D7: the
  panel's own file list is the route that does not depend on it, and the modifier is settled by
  measurement before the control claims anything.
- **[A consumer's source reaches the dashboard]** → It is displayed and persisted nowhere: no
  server cache, no log line with content, no browser storage. Tests assert the last of these
  the way `fleetInstructSurface` already asserts it for a declared focus.
- **[A very large project makes the listing slow or huge]** → Capped, with the cap and the
  truncation stated in the answer; measured against this repository, which is one of the
  larger trees on the machine.
- **[Bundle size]** → Monaco is lazily imported, so the fleet screen's first paint is
  unchanged. A task measures the built chunk and records the number, rather than asserting it
  is "fine".

## Migration Plan

Additive throughout: new endpoints, a new panel type, one new dependency. Nothing existing
changes behaviour, and the URL-opening path in the terminal is explicitly left alone. Rollback
is removing the panel's entry point; the endpoints are inert when nothing calls them.

## Open Questions

- **Which modifier activates a terminal reference** — decided by the measurement in D7, in a
  task, on a live agent with mouse tracking on. Until that measurement, no control claims it.
