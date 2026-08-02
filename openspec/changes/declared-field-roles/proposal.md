## Why

The status surface renders a project's answer without knowing what any field *is*, and that is the
design. But rendering still has to make a choice for every value, and with nothing to go on the
renderer applies one rule to all of them: every integer is a quantity.

Measured on a live producer (2026-08-02), on the answer that opens the screen:

- a process identifier rendered as `3,218,705` — thousands separators on a number that is a name
- an elapsed time rendered as `1151`, raw seconds, next to a duration a human would read in minutes
- `tasksDone: 6` and `tasksTotal: 7` — one progress fact, split into two independent numbers
  scattered among fourteen fields

None of this is fixable by looking at the field NAME. `pid` is `processId` at the next project, and
somewhere a field called `pid` really is a quantity. The framework must not learn one project's
vocabulary — that rule is why `caveats` and `follow` are declared rather than guessed.

The producer already publishes the missing information: a `display` map from field name to a role,
shipped and green on their side. The framework does not carry it at all — measured across all
eleven declared commands: `display: NOT CARRIED`. The reader drops the key before the API sees it.

## What Changes

- The envelope gains `display`: a map from **bare field name** to a **role** — what the data *is*,
  never how it should look. Matched at any depth, exactly like `caveats` and `follow`.
- The role vocabulary is **closed and tested on both sides**: `id`, `path`, `duration-seconds`,
  `count`, plus the two paired forms `{progressOf: <field>}` and `{limitOf: <field>}`. An unknown
  role is **ignored silently**, so a producer adding one cannot break a rendering surface.
- A paired role requires its **partner field in the same object**. Without the partner the role is
  dropped, because half a pair rendered as a whole is confident and false.
- Presence is counted from the **data**, never from the declaration — the declaration only says what
  to look for.
- The surface renders: a **progress bar** for `progressOf` pairs, a threshold marker for `limitOf`,
  identifiers without grouping, durations in human form.

## Capabilities

### New Capabilities
- `project-status-field-roles`: how a project declares what a field *is*, and what the framework may
  and may not do with that declaration.

### Modified Capabilities
<!-- none: the envelope's existing requirements are unchanged; this adds a key alongside them -->

## Impact

- `lib/set_orch/project_status.py` — parse and carry `display` on `StatusResult`; a selector that
  resolves declared roles against the data.
- `lib/set_orch/api/project_status.py` — carry `display` in the response.
- `web/src/lib/api.ts`, `web/src/components/statusShape.tsx`, `StatusValue.tsx`, `StatusTable.tsx` —
  render the roles.
- No project-side change required beyond the declaration the producer already ships.
