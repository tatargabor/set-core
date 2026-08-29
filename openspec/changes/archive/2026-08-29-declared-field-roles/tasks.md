## 1. The reader carries the declaration (core — `lib/set_orch/`)

- [x] 1.1 `StatusResult` gains `display: dict` — bare field name → role, with the field enumerated
      in the class docstring the way `follow` and `caveats` are
- [x] 1.2 `_display_roles()` parses the key: an object of `str → (str | {progressOf|limitOf: str})`.
      Anything else is dropped with a SHAPE-only warning; a malformed key never costs the answer
- [x] 1.3 `parse` passes `display=_display_roles(payload.get("display"))`
- [x] 1.4 `to_dict()` carries `display`, so the API sees it
- [x] 1.5 `field_roles(data, display)` resolves declared roles against the data — bare name at any
      depth, into objects and into objects inside lists
- [x] 1.6 A paired role resolves its partner ONLY among the sibling keys of the object that carries
      the roled field; a missing or non-numeric partner drops the role
- [x] 1.7 An unrecognised role is dropped silently — no error, no log line per occurrence

## 2. The API hands it on (core — `lib/set_orch/api/`)

- [x] 2.1 `project_status.py` includes `display` in each command's payload
- [x] 2.2 Measured against a live producer: `display` reaches the API for every command that
      declares it (the same check that reported `NOT CARRIED` reports the roles)

## 3. The surface renders the roles (`web/src/`)

- [x] 3.1 `api.ts`: `display?: Record<string, unknown>` on `StatusCommandResult`
- [x] 3.2 `statusShape.tsx`: a `RoleView` context, built once per answer, mirroring `FollowView` —
      resolved from the DATA, never from the declaration alone
- [x] 3.3 `id` renders with no thousands separators
- [x] 3.4 `duration-seconds` renders in human form (`19m 11s`), with the raw seconds available on
      hover rather than lost
- [x] 3.5 `count` renders exactly as an ordinary number does today — it exists to make silence
      unambiguous, not to change anything
- [x] 3.6 `path` renders as a path: no grouping, no wrapping mid-segment
- [x] 3.7 `progressOf` renders a **progress bar** beside the numbers, never instead of them
- [x] 3.8 `limitOf` renders a threshold indication beside the numbers, never instead of them
- [x] 3.9 A caveat attached to a roled field stays visible where the reader is standing

## 4. Proof

- [x] 4.1 Reader tests: a well-formed declaration, a malformed one, an unknown role, a dotted key
- [x] 4.2 A test asserting a dotted declaration matches NOTHING — the shape a producer reaches for
      first, whose failure is silent
- [x] 4.3 A test asserting an undeclared field gets no role even when its name is `pid` — the
      load-bearing negative; make the renderer recognise the name and this is what fails
- [x] 4.4 A test asserting a partner in a DIFFERENT object is not borrowed
- [x] 4.5 A test asserting a declared-but-absent field produces nothing at all
- [x] 4.6 Surface tests for the resolver, including the paired-role drop
- [x] 4.7 Stash-and-rerun is DEGENERATE for this change and the mutation run carries the proof:
      every new test imports a symbol the change introduces (`field_roles`, `resolveRole`), so
      without it the files fail to import rather than failing an assertion. That proves nothing
      about whether the assertions bite — which is why 4.8 exists and why its four mutations,
      not this line, are the evidence
- [x] 4.8 Mutation check on the paired-partner rule, with the restore VERIFIED by re-reading the
      file, `PYTHONDONTWRITEBYTECODE=1`, and `__pycache__` cleared between runs
- [x] 4.9 Import-isolated baseline diff — no test that passed before fails now
- [x] 4.10 Looked at on screen. Structural counts prove it renders; they say nothing about whether
      it is readable or whether two fields now contradict each other

## Acceptance

- [x] AC-1 A live producer's `display` reaches the API on every command that declares it
- [x] AC-2 An identifier renders without thousands separators
- [x] AC-3 A duration renders in human form
- [x] AC-4 A declared pair renders a bar, and both numbers remain visible beside it
- [x] AC-5 A pair whose partner is absent renders as a plain number with no bar
- [x] AC-6 An unknown role changes nothing on screen and reports nothing
- [x] AC-7 A field named in `display` but absent from the data produces nothing at all
- [x] AC-8 The living record carries what was decided and what it was measured against
