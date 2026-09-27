## Why

`POST /api/desktop/open` refuses a seventh class of path that no requirement anywhere
describes, and accepts a request field that LIFTS that refusal which no requirement
describes either. Measured 2026-09-28 while archiving the previous change against this
capability: `grep -rn 'viewed\|allow_pages\|local page\|html' openspec/specs/desktop-open/spec.md`
returns nothing, and `grep -rl 'ASSOCIATION_INTERPRETS\|opens as a local page' openspec/`
returns nothing anywhere under `openspec/` — not a change, not an archive. Registered as
`B-153`.

Both behaviours shipped as direct commits: `_ASSOCIATION_INTERPRETS` in `38a534c6` (part of
a measured defect fix), and `OpenRequest.viewed` / `refusal(allow_pages=...)` in `55b961c2`.
A measured defect fix may be a direct commit here — unless it changes contract behaviour,
which both of these do, one of them by adding a field to the request body.

**The code is correct, and that is what makes the absence expensive rather than urgent.**
Verified live against a restarted server: `.html` with `viewed: true` is handed over, the
same file without the flag is refused, and a `.app` and a `.dmg` stay refused WITH the flag
set. So what is missing is not a guard, it is the statement of where the flag's boundary
runs. The next reader widening this guard reads a spec listing six refusal classes while the
code has seven, and finds no requirement saying why a caller-supplied field may lift one of
them or what must stay refused when it does. A spec exists to prevent exactly that reading.

**This proposal was written to implement nothing — and writing it found one thing.** Reading
the class in order to state it surfaced that `.svg` and `.svgz` are excluded from it, with a
comment saying the exclusion rests on nobody having measured them. Sweeping this machine's
association table measured them: every other suffix the endpoint hands over resolves to a
viewer or an editor, and `.svg`/`.svgz` resolve to the **browser**. So the class gains two
members in the same change that first states it, which is the honest place for them —
widening a list nobody has written down yet is how a list stops meaning anything.

## What Changes

Two requirements added to the existing `desktop-open` capability:

- **A local page is its own refusal class.** `.html`, `.htm`, `.xhtml`, `.xht`, `.shtml`,
  `.mhtml` are refused by default, and the reason given names what makes them different from
  the RUN class: a local page is *interpreted*, with read access to this machine's files.
  It is not a launcher and nothing executes it, so the existing "what must never be handed
  over" requirement does not and should not cover it.
- **A caller may declare the page is already open, and that lifts THIS class only.** The
  request body carries `viewed`. The requirement states the boundary in both directions: what
  it lifts, and what stays refused with it set — a launcher, a file the association runs, and
  an executable. It also states plainly that the server cannot verify the flag, which the code
  comment says and no requirement does.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `desktop-open`: the refusal list gains a class that is neither a launcher nor
  association-run, and the request body gains a field — so the endpoint's contract is no
  longer "one absolute path and nothing else".

## Impact

- `lib/set_orch/api/desktop.py` — two suffixes added to `_ASSOCIATION_INTERPRETS`, and the
  comment that excluded them replaced by the measurement that includes them. Nothing else.
- `tests/unit/test_desktop_open_api.py` — `diagram.svg` moves out of the "ordinary file is
  still handed over" list, and two tests take its place: the refusal, and the `viewed` lift.
  Only the first goes red on unfixed source, and its sibling says so in its own docstring
  rather than being counted as proof it is not.
- **A behaviour change for one route and not the other**: a path activated in a **terminal**
  no longer opens an SVG, because there the path was named by text an agent printed. The
  **file view's** button still does, because the reader has that file open. The whole cost of
  the widening lands on the route that was never the reason to allow it.
- `openspec/specs/desktop-open/spec.md` gains two requirements at archive time, which is the
  point of the change.
- Closes `B-153`. The register entry's own proof of a fix is that the two greps quoted above
  return the requirement instead of nothing.
