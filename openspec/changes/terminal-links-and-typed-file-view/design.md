## Context

Three shipped changes built the route this one repairs. `fleet-view` put the terminal on the
screen, `fleet-file-tree-fidelity` made the panel's listing honest, and
`fleet-open-external-path` added the desktop hand-over for what the panel cannot read. Each
was right about the case in front of it. Together they left a boundary drawn in the wrong
place: **the recogniser decides what the framework may read from ONE checkout's listing**, and
everything else falls through to `xdg-open`.

The measurement in the proposal is the evidence, and its shape matters for the design: the
defects are not in the guards. `files.py:_known_root` already accepts every registered project
and every non-prunable worktree; `desktop.py:refusal` correctly refuses to run anything. What
is wrong is **which of the two routes a token is sent down**, and that decision is made in the
browser with less knowledge than the server has.

Constraints that shape every decision below:

- **No existence oracle.** `project-file-access` refuses to answer "is there a file at X" for
  arbitrary paths, one polite request at a time. Any design that resolves links by asking the
  server about a path is refused before it is evaluated.
- **Terminal text is data.** Every token was written by whatever an agent ran. Widening what
  counts as a link widens what that text can steer.
- **The dashboard's own origin.** Anything the browser renders inline runs in the origin that
  holds the fleet screen, its terminals and its write endpoint.

## Goals / Non-Goals

**Goals:**

- A file the framework may read opens in the framework, whichever registered checkout it is
  in — including one the agent is not standing in.
- The executable bit stops mattering to the read route; it keeps mattering to the run route.
- A binary the panel can draw is drawn; one it cannot is named, not merely refused.
- A directory reveals in the structure pane instead of launching a file manager.
- The single-segment `/word` false links stop — 1 464 occurrences over the measured corpus.

**Non-Goals:**

- Joining a path broken across a terminal line wrap (497 distinct tokens exceed 80 columns).
  The recogniser sees one row; joining rows needs its own mechanism and its own failure modes.
- Editing binaries. The panel displays them.
- Widening what the file endpoints will serve. This change consumes the existing verdict; it
  does not extend it.
- Any change to `desktop.py`.

## Decisions

### D1 — The browser is told which checkouts exist; it does not ask about paths

The recogniser needs to answer "is this absolute path inside something the server would
serve". Three ways to get there:

| option | why not |
|---|---|
| ask the server per token | the existence oracle `project-file-access` exists to refuse |
| ship every checkout's listing | one consumer checkout listed **30 121** files; 43 registered projects makes this absurd |
| **ship the checkout ROOTS** ✔ | a few dozen strings, no oracle, and prefix-matching is exact |

So the fleet payload gains two fields, both derived from knowledge the server already holds:

- `home` — the absolute home directory of the account the framework runs as, for `~/`
  expansion. The browser must never guess this; a wrong guess produces a link to a file
  belonging to somebody else's account.
- `FleetProject.checkouts: string[]` — the project root plus its non-prunable worktrees,
  from the same `_start_location_verdict` that already gates both starting an agent and
  reading a file. **Derived, not a second definition** — the failure that already cost this
  repo a live report was two enumerations of "what this screen knows" drifting apart.

A LISTING is still fetched for one checkout at a time, as today: it is what relative tokens
and suffix matching need, and it is only needed for the checkout the reader is looking at.

**Consequence, stated rather than discovered later:** an absolute path into a registered
checkout links even when its listing has not been fetched, because the prefix answers. The
panel then opens it and the endpoint decides — which is the correct division: the endpoint is
the guard, the browser is a router.

### D2 — Prefix matching is on path boundaries, longest match wins

`/home/u/proj` must not swallow `/home/u/proj-other`, and a worktree
(`<project>-wt-<name>`) is exactly the string that looks like a sibling of its project. So a
candidate matches only at `root` or `root + '/'`, and where several match, the LONGEST wins —
a worktree path also matches nothing else, but a project nested under another one would.

This is not a new rule; `fileReference` already compares this way. It is written down because
the two places must not drift.

### D3 — The absolute branch's shape test: two segments AND an extension, unless it is inside a known checkout

The measured false links are almost entirely single-segment absolute tokens. But the naive
repair — "an absolute path must have ≥2 segments" — still links `/api/v1/items`, and the
naive strong repair — "must be inside a known checkout" — kills the case
`fleet-open-external-path` was built for, the `/tmp/…/screenshot-*.jpg` an agent just wrote.

The rule that separates them:

```
inside a known checkout            → internal reference   (/home/u/proj/src/a.ts, /home/u/proj/docs)
otherwise, ≥2 segments AND the last segment has an extension
                                   → desktop reference    (/tmp/run-4/shot.png)
otherwise                          → text                 (/opsx:ff, /api/v1/items, /tmp)
```

The same ASCII path-character class both branches already use is applied to both, which
disposes of `/items/[id]`-shaped route tokens (`[`, `<` are not path characters here).

What this deliberately loses: an extensionless file or a directory outside every registered
checkout — `~/bin/mytool`, `/tmp` — stays text. Accepted, and the direction is the reason: a
missed link costs a right-click; a wrong one costs the reader's trust in every underline.

### D4 — Suffix resolution is a UNIQUENESS test, not a best match

`actions/dashboard.ts` names `src/app/actions/dashboard.ts` — 50 such tokens over the corpus
resolve to exactly one listing entry, 13 to more than one. Only the unique ones resolve.
Never "the shortest", never "the first": a wrong file that opens looks exactly like a right
one, and nothing on the screen says otherwise. The match is on a path boundary (`endsWith('/'
+ token)`), so `actions/dashboard.ts` does not match `.../my-actions/dashboard.ts`.

Cost: the listing is up to 30 121 entries and the check runs per token per rendered row. A
precomputed suffix index built once per listing keeps this off the render path; the link
provider already re-registers when the listing arrives, so there is a natural place for it.

### D5 — Binaries are served by a separate byte route, not base64 in the JSON

`<img src>` wants a URL. Base64 in the existing JSON costs 33 % size, forces the whole file
through the JSON parser, and gives the panel a data URI to manage. A second route
(`GET /api/fleet/files/raw`) returns bytes with a media type, behind the SAME `_known_root`
and `_confine` calls — the guard is the function, not the endpoint.

**The security decision inside this one is the load-bearing part.** Anything served inline
runs in the dashboard's origin. So the raw route serves inline **only media types on an
allow-list that cannot execute** — raster images and PDF — and everything else is refused
before it is served, with `X-Content-Type-Options: nosniff` and an explicit
`Content-Disposition` so no sniffing can promote a file into something executable.

**SVG is deliberately NOT rendered as an image.** It is XML that can carry script, and it is
also text — so it takes the text route and opens in the editor, which is the honest answer:
an SVG in a repository is source.

### D6 — Type is decided by decode attempt first, extension never

`Makefile`, `.env`, a shebang script with no suffix, `.gitignore` — all text, none with a
useful extension. And a `.md` file can hold bytes that are not UTF-8. So: try UTF-8; if it
decodes, it is text (this is also what makes an executable script open, since permission bits
are never consulted). Only if it does not decode is a media type determined, and only then
does the extension participate — as a hint for a file whose bytes are already known not to be
text.

A null byte in the first block is treated as binary even if a decode would have succeeded, so
a UTF-16 file or a sparse binary does not reach the editor as mojibake.

### D7 — Two size caps, because they answer different questions

`MAX_BYTES` (2 MiB) exists because the editor holds the whole file in a string and a write
sends it back. A byte stream does neither. Screenshots routinely exceed 2 MiB, and refusing
one *as too large* to an endpoint that only streams it would be a limit the framework does
not actually have. So the raw route carries its own, higher cap, and the panel states which
cap refused it.

### D8 — Reveal is a panel operation, not a file open

A directory activation calls the panel with a *reveal* intent: expand ancestors, scroll to
the node, mark it. It must not touch what is open — the panel already refuses to lose an
unsaved edit, and a reveal that quietly closed a dirty file would be that same loss through a
new door.

## Risks / Trade-offs

- **`fleet-open-external-path` is not archived, and this change modifies its requirements** →
  its deltas and these disagree about what the base spec said. Mitigation: it archives first;
  its one open task is a browser check this change performs anyway on the same surface. Named
  as a task here so it cannot be forgotten at archive time.
- **The raw route is a new way for bytes to leave the machine into a page** → the allow-list
  and the confinement are the mitigation, and both are asserted by tests that pass a hostile
  path and a hostile type. Note the class: *extending a configurable protection can weaken
  it* — the question to ask in review is which branch the new route takes OVER, not which one
  it adds to.
- **Widening what links makes agent output steer more of the UI** → nothing opens without a
  person's modifier-click, and no route reads outside `_known_root`. What widens is what the
  reader can reach in one gesture, not what the framework does on its own.
- **The suffix index could mask a stale listing** → a resolved suffix names a file the listing
  claims exists; if it was deleted since, the endpoint answers 404 and the panel says so. Same
  failure as any other stale link, and it is stated rather than silent.
- **`checkouts` could become the third definition of "what the screen knows"** → it is
  computed from `_start_location_verdict`, not enumerated beside it, and a test asserts the
  two agree for a worktree.

## Migration Plan

No data migration; no stored shape changes. The order that matters:

1. Archive `fleet-open-external-path` (spec base).
2. Lib-only changes (`fleetFiles.ts`) — fully measurable without a browser, and they retire
   most of the risk: the false links stop and the missed ones start working.
3. Payload fields (`home`, `checkouts`) and the terminal wiring — behaviour changes only for
   tokens that were previously handed to the desktop.
4. The typed endpoint and the panel's non-text view.

Rollback is per-step: each step is independently revertable, and no step leaves a stored
artifact behind.

## Open Questions

- **PDF in the panel, or hand-over?** The spec says a document format the panel supports;
  browsers render PDF in an `<embed>` well, but inside a docked band it may be unusable.
  Decide when the panel view is built, by looking at it — not on paper.
- **Does an image count against the panel's remembered-file behaviour?** Reopening the panel
  restores where the reader was; an image is a fine thing to restore, but the remembered value
  is a path and nothing here changes that. Assumed yes, no special case, until it looks wrong.
