## Why

The fleet project header has four things that open, and each one was built on its own. Two of
them open **in place**, inside a `flex-wrap` row, so opening them grows the row and pushes the
rest of the screen down. In a measured example the waiters expander shoved the modules chip and
the entire window-control cluster into the middle of its own list.

The user's words, after seeing a mock-up that made the header taller on open:
*"never push on the elements, or sizes. I think that's a common request on UIs"*. That is now a
standing repository rule — [`.claude/rules/ui-quality.md`](../../../.claude/rules/ui-quality.md),
section *An overlay NEVER pushes* — and this change is the first work it binds.

The four openers today:

| chip | component | opens | has actions? |
|---|---|---|---|
| `↺` / `◷` restore | `web/src/components/FleetRestore.tsx:558` (`TheRest`) | **overlay** — the house pattern already | yes: restore, delete, close |
| `⧗` waiters | `web/src/components/FleetWaiters.tsx:195` | **in place** — pushes | yes: stops a process, per row |
| `⊞` modules | `web/src/components/FleetInstall.tsx:233` (`basis-full`) | **in place** — takes a whole new wrapped line | yes: writes files into the project's repo |

Three further facts make this a design problem rather than three bug fixes:

- **There is no project-header component.** The bar is inline JSX at `web/src/pages/Fleet.tsx:3693–3950`.
- **There is no shared disclosure helper.** Every expander carries its own `useState(false)`.
  `Chip` (`web/src/components/Chip.tsx:53`) is the shared *trigger* and owns no open state.
- **The restore panel is a fixed `70vw × 76vh` whatever it holds.** With one recorded session the
  entry is stranded at the top, the footer at the bottom, and roughly 380 px of nothing between
  them — a panel covering most of the screen to say one sentence.

Separately, the header carries three status sentences that are always on screen: a green restore
result (`web/src/lib/fleetRoster.ts:154`, rendered `FleetRestore.tsx:146`), an amber terminal
notice (`FleetTerminal.tsx:1194`) and an amber declaration warning (`web/src/pages/Fleet.tsx:1066`).
They occupy three different strips with three different alignments, and the green one wraps onto a
second line, making the whole top bar two rows tall.

## What Changes

- **One panel mechanism, shared by every opener in that batch.** A single "opens a panel"
  behaviour: absolutely positioned above the layout, never a sibling that participates in sizing,
  closable, with identical chrome. Icons are unchanged — the hourglass stays the waiters icon.
- **`FleetWaiters` and `FleetInstall` stop opening in place** and adopt it. `TheRest` already
  overlays and is the reference.
- **Panel chrome is uniform; panel *bodies* differ.** Restore keeps its footer of panel-wide
  actions because it has them. Waiters and modules have no panel-wide action, so their chrome is
  the close control alone. **Their per-row actions stay** — see the note below, it is the part
  most likely to be got wrong.
- **The restore panel's height follows its content**, up to a cap; past the cap the list scrolls
  while header and footer stay put.
- **Structured bodies.** Waiters becomes columns (pid · status · working directory · action)
  instead of a run-on row; modules becomes (module · state · files · action).
- **The three header sentences stop being permanently resident.** The two amber *states* collapse
  behind one badge that opens a floating panel; the green restore *event* floats and auto-closes
  after 10 s.
- **NOT changing any user-visible wording**, and not changing which actions exist.

**The correction that this proposal exists to record.** The request described waiters and modules
as carrying information only. They do not. `FleetWaiters.tsx:111` offers `remove (stops the
process)` behind a `sure? this stops process {pid}` confirm, and `FleetInstall.tsx:136` offers
`install for real — writes N file(s) into <root>`. Reducing either to a close button would delete a
guarded destructive action and a write path into a consumer tree. The close-only rule therefore
applies to panel **chrome**, never to row actions.

## Capabilities

### New Capabilities

- `fleet-panel-openers`: how the fleet's header openers behave — one panel mechanism, overlay
  positioning that never reflows the layout, uniform chrome with a close control, the rule that a
  panel may hide a sentence but never a fact, and the state-versus-event distinction that decides
  whether a notice persists or closes itself.

### Modified Capabilities

- `agent-fleet-restore`: two presentation requirements change shape, not meaning.
  `### Requirement: The result reports every entry separately, and a partial restore reads as partial`
  (`openspec/specs/agent-fleet-restore/spec.md:67`) gains the requirement that a complete result may
  auto-close while a partial one may not. `### Requirement: The surface offers restore per project
  and shows what happened` (`:83`) gains content-driven panel height and the shared chrome.

**Not modified, but constraining:** `module-install` governs what an install *does*; this change
touches only how its panel opens, so no delta. `project-status-contract:85` requires that an
unasked command is not rendered as a failure — which is why the declaration warning is amber and
why amber and red must stay distinct. **No spec currently covers waiters at all**, so the waiters
panel's behaviour lands in the new capability.

## Impact

**Code — new:** a panel component plus the shared open-state hook, under `web/src/components/`.

**Code — modified:**
- `web/src/pages/Fleet.tsx` — the header bar (`3693–3950`) and the declaration warning (`1064–1066`)
- `web/src/components/FleetWaiters.tsx` — trigger `167–193`, in-place body `195–205`
- `web/src/components/FleetInstall.tsx` — trigger `222–232`, `basis-full` body `233–246`
- `web/src/components/FleetRestore.tsx` — `Result` `139–162`, dialog `658`, `RestoreForProject` `889`
- `web/src/components/FleetTerminal.tsx:1186–1194`

**Wording is frozen, and that is what makes the existing tests a regression detector.** There is no
i18n layer; roughly 40 assertions read these strings directly, several by exact match
(`web/tests/unit/fleetRestoreSurface.test.tsx:233` — `getByText('All 1 restored.')`;
`web/tests/unit/fleetRoster.test.ts:92` — `toBe('All 2 restored.')`). A failing text assertion after
this change therefore means content was **lost**, not renamed.

**Two selector facts that decide whether tests survive:**
- `data-fleet-modules-open` is consumed by `web/tests/e2e/fleet-install.spec.ts:74` and **must not
  be dropped**. The shared mechanism should emit it for every opener.
- The waiters trigger has **no stable selector** — `web/tests/unit/fleetInstructSurface.test.tsx:319`
  finds it as "the only button" in an isolated render. Giving it a marker is safe and overdue.

Every other `data-fleet-*` marker on these panels and their rows must survive; moving one onto a new
wrapper is acceptable, dropping one is not.

**Binding rules:** *An overlay NEVER pushes* and *Compacting must never hide a failure*, both in
`ui-quality.md`. The same file requires a **visual check in the browser** as an implementation task;
if the browser cannot be reached, that task stays open and is reported as open rather than being
implied by a green suite.

**Out of scope, named so it is not mistaken for done:** the across-projects result, the triplicated
modal shell beyond what these openers need, `FollowPanel`, the 15 scattered `text-emerald-400`
literals, and any change to what the actions do.
