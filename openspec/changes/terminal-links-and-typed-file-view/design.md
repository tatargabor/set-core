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

**Precision on the oracle argument, because it does not say what it first appears to.** VS
Code's terminal resolves links by asking the filesystem whether each candidate exists — the
opposite of the rule above — and it is right to, because there its detector and the filesystem
sit inside one trust boundary. Ours do not. But INSIDE a checkout the framework serves, the
listing already enumerates every file, so a per-path existence question would reveal nothing
the caller cannot already read. The oracle concern is real only OUTSIDE those roots, which is
exactly where `fleet-open-external-path` already decided not to probe. So the reason for
shipping roots rather than listings is SIZE, not secrecy — and the no-probe rule stands
undisturbed on the desktop branch, where it was always the one that mattered.

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

**Revised after looking at how VS Code solved the same problem (2026-08-27).** Its terminal
does NOT make a binary link/text decision. It ranks by CONFIDENCE: a *file link* is one it
verified on disk and underlines; a *word link* is a fallback that "won't display underlines or
tooltips unless you hold Ctrl/Cmd". So a low-confidence token costs no visual noise while
staying reachable.

That is strictly better than dropping the token, and it dissolves the trade-off the paragraph
above was accepting. The rule becomes:

```
inside a known checkout                          → internal, underlined
≥2 segments AND an extension on the last segment → desktop, underlined
anything else that is absolute and path-shaped   → LOW CONFIDENCE: no underline, no tooltip,
                                                   activatable only while the modifier is held
neither                                          → text
```

xterm.js supports this directly — `ILink.decorations` carries `underline` and `pointerCursor`
per link, so the third row is a decoration decision, not a second link system.

What it buys, measured: the 1 464 false-link occurrences stop drawing underlines, and
`/tmp` and `~/bin/mytool` — extensionless, outside every checkout, and previously destined to
be dropped — stay reachable. Both halves of the old trade-off are avoided rather than
balanced.

### D4 — Suffix resolution is a UNIQUENESS test, not a best match

`actions/dashboard.ts` names `src/app/actions/dashboard.ts` — 50 such tokens over the corpus
resolve to exactly one listing entry, 13 to more than one. Only the unique ones resolve.
Never "the shortest", never "the first": a wrong file that opens looks exactly like a right
one, and nothing on the screen says otherwise. The match is on a path boundary (`endsWith('/'
+ token)`), so `actions/dashboard.ts` does not match `.../my-actions/dashboard.ts`.

**But an ambiguous match is offered, not discarded — VS Code's answer again.** Its word links
"search the workspace for the word. If a single match exists, it opens automatically; multiple
matches display as search results." Discarding is a third behaviour neither of those, and it
is the one that leaves the reader with nothing. So: one match opens; several offer the
matches; none is text. That recovers the 13 ambiguous tokens the uniqueness rule alone throws
away.

Cost: the listing is up to 30 121 entries and the check runs per token per rendered row. A
precomputed suffix index built once per listing keeps this off the render path; the link
provider already re-registers when the listing arrives, so there is a natural place for it.

### D5 — Binaries are served by a separate byte route, not base64 in the JSON

`<img src>` wants a URL. Base64 in the existing JSON costs 33 % size, forces the whole file
through the JSON parser, and gives the panel a data URI to manage. A second route
(`GET /api/fleet/files/raw`) returns bytes with a media type, behind the SAME `_known_root`
and `_confine` calls — the guard is the function, not the endpoint.

**The security decision inside this one is the load-bearing part, and research changed it.**
GitHub does not serve user content from its own origin at all — `raw.githubusercontent.com`
exists precisely so that "subdomain isolation securely separates user-supplied content from
other portions of GitHub". A local dashboard cannot buy a second origin. What it CAN do is
never serve a renderable response in the first place:

- the raw route answers with `Content-Disposition: attachment` and
  `X-Content-Type-Options: nosniff`, so the browser will not render whatever it holds;
- the panel `fetch`es it, checks the media type against its OWN allow-list, and builds a
  `Blob` with that type, rendering `URL.createObjectURL(blob)`;
- **the type that reaches the renderer is therefore chosen by the panel, not carried by the
  response.** A file whose bytes look like HTML cannot become an inline document, because
  nothing ever asks the browser to interpret the response body.

The server-side allow-list stays as well — two independent gates, not one moved.

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

### D9 — The recogniser carries explicit limits, copied from a system that has hit them

Nothing in the current recogniser bounds its work, and the suffix index makes that worse: it
runs per token, per rendered row, against a listing of up to 30 121 entries. VS Code's
terminal link stack carries hard caps, and they are the shape to copy rather than to invent:
`MaxLineLength = 2000`, `MaxResolvedLinksInLine = 10`, `MaxResolvedLinkLength = 1024`, and a
500-character cap on word-based detection.

The framework adopts the same four, with its own numbers where the situation differs. The
reason to state them rather than let them be implicit: an unbounded scan degrades under
exactly the condition this screen is for — an agent producing output flat out — and a terminal
that stutters while an agent works is indistinguishable from an agent that has stalled.

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

## Open Questions — both answered by research, 2026-08-27

### RESOLVED: PDF is handed over, not embedded

Three findings, and they point the same way:

- **GitLab serves PDFs as downloads**, not inline. Adding `application/pdf` to its
  `allowedInlineTypes` is still an open request, not shipped behaviour — a project with far
  more at stake in file rendering than this one has declined to embed.
- **Gitea does embed, via pdf.js, and hit exactly the framing problem** — its viewer request
  carries `X-Frame-Options: DENY`, so the PDF does not display.
- **A sandboxed iframe may not render PDF at all.** Chrome implements PDF through a plugin,
  and the WHATWG has an open interop issue that a PDF "might or might not render in a
  sandboxed iframe depending on a browser". So the safe framing and the native viewer are in
  direct tension.

Embedding therefore means bundling pdf.js (a large offline dependency, since the artifact CSP
forbids a CDN) to solve a problem the machine already solves: this is a local dashboard, and
`xdg-open` opens a PDF in the reader the person chose. **The panel names the type and hands
over.** If a reader asks for inline PDF later it is a change of its own, with pdf.js costed
honestly.

### RESOLVED: an image counts in the remembered-file behaviour, with no special case

VS Code restores the previous session wholesale — "the folder, layout and opened files are
preserved" — with no type-based exception; an image tab comes back like any other. The
assumption was right, and it now rests on something. The remembered value stays a path, so
nothing in that mechanism changes.

### Still open

- **What the low-confidence tier looks like in practice** (D3). The decoration is settled;
  whether a tooltip appears on modifier-hold, and whether the status row should say the tier
  exists, is a thing to decide by looking at the screen rather than on paper.
