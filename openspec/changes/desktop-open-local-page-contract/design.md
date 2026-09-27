## Context

`lib/set_orch/api/desktop.py` guards an act rather than a location: a path may be OPENED,
never RUN. Its refusal classes grew by measurement — `.desktop` from the start, the
run-or-install list after a 644 `.jar` reached a JVM (`B-89`), the macOS launcher classes after
the framework started running on macOS.

One class in that file has never been written down: `_ASSOCIATION_INTERPRETS`, the documents a
browser renders at a `file://` origin. Nor has the request field that lifts it. Both are code
with no requirement (`B-153`).

This change would be pure documentation, except that stating the class made its one gap
visible. That is the ordinary reason to write a spec for shipped behaviour, and it is worth
recording as an outcome rather than an accident.

## Goals / Non-Goals

**Goals**
- The class and its lifting field are requirements, so the next reader widening this guard has
  the boundary stated rather than inferable from control flow.
- The class's membership rests on measurement, including the member that was excluded.

**Non-Goals**
- Probing the local desktop at request time. The guard answers from the path alone so the same
  input gives the same verdict on every machine — measurement informs the LIST, at design time,
  and never runs inside `refusal()`.
- Any change to the route, the answer keys, or the other refusal classes.
- Deciding what a non-browser desktop does with `.svg`. One machine's table is evidence that an
  SVG *can* reach a browser, which is enough for a floor; it is not a claim about every desktop.

## Decisions

**1. `.svg` and `.svgz` join the class, reversing an explicit exclusion.** The comment that
excluded them gave two grounds: an image that opened before must still open, and nobody had
measured them. Both have changed, and the order matters — the measurement alone would not have
been enough to reverse somebody's recorded decision.

- *Measured.* Sweeping this machine's association table for every suffix the "ordinary file"
  test hands over: `.png`, `.pdf`, `.webp`, `.gif` → Preview; `.mp4` → VLC; `.docx` → Pages;
  `.md`, `.py`, `.xml`, `.json` → Xcode; `.txt` → TextEdit; `.svg`, `.svgz` → **the browser**.
  The exclusion's premise — that an SVG is an image a viewer shows — is false on this desktop.
- *The cost fell.* `viewed` did not exist when the exclusion was written. Refusing `.svg` then
  meant it could not be opened at all; now it means it cannot be opened from a path an agent
  PRINTED, while the file view's own button still opens it. The exclusion was priced against a
  cost that no longer applies.
- *And the capability's own spec settles the remainder:* a refusal that lets one of these
  through is a hole, one that stops an ordinary file is an inconvenience, and when the two are
  in tension the refusal wins.

*Alternative rejected:* leave it excluded and register the measurement. That keeps a hole open
while publishing prose about the class it belongs to — the failure this repository has already
paid for, where documents accumulate in front of a guard nobody changes.

**2. It joins the INTERPRETS class, not the RUN class.** Nothing executes an SVG outside the
renderer, and the reason a caller is given must name the fact that is true. Putting it in the
run-or-install list would also make it unliftable by `viewed`, which would refuse it in the
file view as well — a harsher change, for a worse reason.

**3. The tests assert the endpoint's verdict, not the tuple's membership.** A test reading
`_ASSOCIATION_INTERPRETS` would pass on a restructure that stopped consulting the tuple. What
is under test is what a caller is told.

## Risks / Trade-offs

- **A person activating an `.svg` path in a terminal now gets a refusal where they used to get
  a picture.** → Accepted, and narrowed rather than waved away: the file view's button still
  opens it, so what is lost is the route where the path was named by text an agent printed —
  the route the class exists for.
- **A test written beside a fix that passes without it looks like proof forever.** → The
  `viewed`-lift test does pass on unfixed source, because an `.svg` refused by nothing is also
  handed over with the flag. Its docstring says so, and the refusal test is the one measured
  red without the widening.
- **One machine's association table is one measurement.** → Which is why the requirement says
  the class rests on what an association does, and lists a floor rather than claiming
  completeness — the same wording the run-or-install class already carries.

## Migration Plan

None. No stored state and no API shape change; the field was already accepted. The behaviour
is live when the server process restarts, and a shipped commit is not a running system.

## Open Questions

- Whether a desktop exists that opens `.svg` in a viewer and would be inconvenienced by this.
  Unanswerable from here without asking each machine, which the guard deliberately never does;
  the `viewed` route is the answer to anyone who finds themselves inconvenienced.
