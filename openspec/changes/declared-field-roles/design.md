## Context

Three envelope keys already exist for the same purpose: letting a project say something about its
own fields that the framework must not infer. `deprecated` says a field is no longer stood behind,
`caveats` attaches a warning to a value, `follow` says a field's value is a path worth watching.
All three use the same selector — a **bare field name, matched at any depth** — and all three count
presence from the DATA, using the declaration only to know what to look for.

`display` is the fourth, and it is the one that carries the most risk, because a "how it looks" key
is one short step from `"bold"`, `"red"`, `"%.2f"` — at which point the project is styling the
framework and the abstraction is gone.

Measured before designing (2026-08-02), on a live producer's opening answer:

- `pid: 3218705` rendered as `3,218,705` — the renderer groups every integer
- `elapsedSec: 1151` rendered raw
- `tasksDone: 6` and `tasksTotal: 7` fourteen fields apart
- the producer already emits `display` with a closed role vocabulary; the framework's reader
  discards the key, so `display` never reaches the API (`NOT CARRIED` on all eleven commands)

## Goals / Non-Goals

**Goals:**
- A project can say what a field IS, in a vocabulary neither side can extend by accident.
- The framework decides entirely how that is drawn, and can change its mind without asking.
- Two fields that form one fact (done/total, used/limit) can be rendered as one thing.
- A declaration that the data does not back is silently inert, never a visible claim.

**Non-Goals:**
- Styling. No colour, weight, format string, width, or position crosses the contract.
- Units other than the one this vocabulary names. `duration-seconds` is a role, not a unit system;
  a project with milliseconds converts on its side or asks for a new role.
- Deriving a role from a field name, a value's magnitude, or a heuristic. Undeclared is undecided.
- Layout decisions per field. Where a field sits is already decided elsewhere.

## Decisions

### D1 — The role says WHAT the data is, never HOW it looks

`"pid": "id"` — not `"pid": "no-thousands-separator"`. The difference is not stylistic
fastidiousness: the second form freezes today's rendering into the producer's output, so improving
the surface later requires every producer to re-ship. Dropping the thousands separator, choosing a
human duration form, drawing a bar, picking a warning colour — all of it stays a framework decision.

This is also the boundary that keeps the vocabulary small. There are few things a value can BE and
unlimited ways it can look.

### D2 — The vocabulary is CLOSED, and an unknown role is ignored rather than refused

`id` · `path` · `duration-seconds` · `count` · `{progressOf: <field>}` · `{limitOf: <field>}`.

Closed, because `display` is precisely the key style would leak through, and a rule only holds if it
is enforced rather than remembered. Both sides hold it in a test.

Ignored rather than refused, because the fail direction decides which mistake is cheap. A refusal
would mean a producer shipping a new role blanks a working surface; ignoring means the value renders
the way it does today. Extension must not be able to break rendering.

### D3 — The selector is a bare field name at any depth — the same one, a fourth time

Not a path expression, not a dotted key. Three reasons, all already paid for by `caveats` and
`follow`:

- A producer may move a field under a `debug` object without their declaration going stale.
- A dotted key matches nothing and does so SILENTLY — the producer's declaration looks right and no
  role is applied. Held as a test rather than a comment.
- A fourth selector language would be a fourth thing to learn and a fourth place to drift.

Its known cost, carried deliberately: a repeated name gets ONE meaning across the whole answer. That
is correct here in a way it is not for `follow` — a name that means "an identifier" in one object
means it in the next. When it genuinely differs, the producer renames the field.

### D4 — A paired role without its partner IN THE SAME OBJECT is dropped

`{progressOf: "tasksTotal"}` on `tasksDone` needs `tasksTotal` beside it — a sibling key of the same
object, not merely somewhere in the answer. Two failure modes decided this:

- **Missing partner.** Rendering "6" as a bar with an invented denominator is a confident lie. The
  honest fallback is the plain number the reader would have got anyway.
- **Wrong partner.** A search at any depth would find *a* `tasksTotal` belonging to a different run,
  and the resulting bar is not merely wrong but plausible — the worst of the two.

So the partner lookup is the one place the any-depth rule does NOT apply. The role is resolved
against the object that carries the field; nowhere else.

### D5 — Presence is counted from the DATA; the declaration only says what to look for

A declaration naming ten fields on an answer carrying three produces three roles, not a note about
seven. This is the defect class both sides have now hit three times — a declaration that speaks
about absent data becomes an announcement, and an announcement about nothing is worse than silence.

The corollary the producer must hold up: the declaration itself must be **constant**, not computed
from the data present in that answer. Measured on the live producer while idle — the declaration had
shrunk from eleven entries to five, exactly the fields that survive between runs. Self-consistent
per answer, and it quietly stops being a contract: the framework can only ever learn what is already
visible, so "this project does not do this" and "it is not doing it right now" become the same
answer. That distinction is what a status screen exists to draw.

### D6 — `count` exists so that a number can be marked as ordinary

It looks redundant — the renderer already treats every integer as a quantity. It is not, and the
reason is the same one that makes `deprecated` useful: a producer that declares roles for its
identifiers and durations has *chosen* for those fields. Without `count`, silence is ambiguous
between "this is an ordinary number" and "we have not got to this field yet". With it, a declared
answer is a complete statement about the fields it names.

## Risks / Trade-offs

- **The vocabulary will be asked to grow** — a byte size, a percentage, a timestamp. That is
  expected and is why unknown roles are inert: a new role can ship on the producer's side first and
  start working when the framework catches up, with no coordinated release.
- **`duration-seconds` fixes a unit in the role name.** Accepted deliberately: a bare `duration`
  would need a unit somewhere, and a unit in the declaration is one step from a format.
- **A repeated field name gets one role for the whole answer** (D3). The alternative is a path
  language whose failures are silent.
- **A progress bar can hide a stall.** A bar at 6/7 looks like progress on a run that has not moved
  in an hour. The bar therefore replaces neither the numbers nor any caveat attached to them — it is
  drawn WITH the value, never INSTEAD of it. This is the same rule that governs every other
  compaction on this surface: a tidier screen may not report calm it has not verified.
