/**
 * Per-project view state — task 7.5.
 *
 * What is remembered here is how the reader was LOOKING at a project: which
 * tile they had enlarged, and anything they had typed and not sent. It is not
 * remembered anywhere else and it is deliberately not on the server:
 *
 *  - the ARRANGEMENT (order, groups, parked) is work the user does once and
 *    relies on, so it lives on the server and survives a different browser —
 *    see `fleetLayout.ts`;
 *  - a view preference can be lost to a cleared cache without anyone minding,
 *    and it is per-person-per-browser by nature.
 *
 * ## The two rules the task states, and both of them are about direction
 *
 * **A remembered view never determines state.** The memory says what to *show*,
 * never what *is*. So a remembered pid that no longer exists in the answer must
 * not produce an enlarged tile for an agent that is gone — the caller resolves
 * it against the live list and falls back. Nothing here asserts that a
 * remembered agent is alive.
 *
 * **A remembered choice outranks the single-agent default.** Which is why
 * "collapsed" is stored as an explicit `null` rather than as an absent key: a
 * project with exactly one agent enlarges it by default, and a reader who
 * closed it must not have it reopened on their next visit. `undefined` (no
 * choice yet) and `null` (chose to close) are different states, and collapsing
 * them into one is the same absent-key-is-not-an-empty-value defect this screen
 * refuses everywhere else.
 */

const KEY = 'set-fleet-view'

/**
 * The storage key, for tests that need to SEED a memory rather than build one
 * through the UI.
 *
 * Exported instead of duplicated in the test file: a copied literal is a second
 * definition, and it drifts silently — the test would then seed a key nothing
 * reads and assert against a screen that saw no memory at all, which passes for
 * the wrong reason on the negative cases and fails inexplicably on the rest.
 */
export const VIEW_KEY_FOR_TESTS = KEY

export interface ProjectView {
  /** `undefined` — no choice yet. `null` — deliberately collapsed. A number — that pid. */
  enlarged?: number | null
  /** An unsent message. Kept so switching projects does not throw away typing. */
  draft?: string
  /**
   * The terminal that was open, by LABEL — task 8.3's reattach half.
   *
   * A label rather than a pid, because the pid is what the scope currently holds
   * and a pid is reused, while the label is what the framework named. Same
   * `undefined` / `null` distinction as `enlarged`: no choice yet versus closed
   * on purpose. And the same rule — a remembered view never determines state, so
   * a remembered label that no longer belongs to a `started-here` agent opens
   * nothing.
   */
  terminal?: string | null
  /**
   * Every terminal the reader has open in this project, by label.
   *
   * Replaces the single `terminal` above, which held exactly one — asked for on
   * 2026-08-19: *"ezt az egy terminalt meg at kell gondolnunk"*. Two terminals
   * open at once is not a new capability on the server: attaching is a
   * reattach, the buffered screen is replayed on connect, and a second viewer
   * is the same code path as the first (task 8.3). So the ONE was a shape of
   * this memory, not a limit of the thing.
   *
   * The alternative the request also named — keeping a picture of a terminal
   * while looking at another — is refused on purpose: a frozen screen is wrong
   * exactly while something is happening on it, and it looks like data. The
   * replay gives the real screen back instead of a photograph of an old one.
   *
   * `terminal` is still read for a reader whose memory predates this; see
   * {@link resolveTerminals}.
   */
  terminals?: string[]
  /**
   * The agent shown ALONE, filling the panel — asked for on 2026-08-19: a full
   * screen that shows one agent and not the column grid.
   *
   * Same `undefined` / `null` distinction as `enlarged`, and the same rule: a
   * remembered pid is resolved against the live answer before anything is
   * rendered. What it may NOT do is hide a state — a focused agent covers its
   * siblings, so the surface counts what it is covering and says so. That is
   * `ui-quality.md`'s rule about compaction, applied to a layout that hides the
   * most.
   */
  focus?: number | null
  /**
   * Which agents have their log open, by pid.
   *
   * Before this, opening a log MEANT enlarging the tile — one log at a time,
   * and never in the grid. Raised 2026-08-19: *"túl kicsi így is, ami nincs
   * nyitva … ott is látni kellene az utolsó üzeneteket, naplót is"*. Reading a
   * log and choosing a layout are two different acts, and tying them together
   * made the commonest one (read what this agent is saying) cost the most
   * expensive one (hide every other agent).
   *
   * `undefined` — no choice yet, and the enlarged tile's log is open, which is
   * what the single-agent default (task 7.5) relied on. An array is a
   * deliberate choice and outranks it, including the empty one.
   */
  logs?: number[]
  /**
   * How many columns the agent grid uses for THIS project — task 7.5's
   * "density", asked for on 2026-08-19: *"elég nagy a képernyő hozzá, hogy
   * csináljunk legalább két oszlopot"*.
   *
   * Per project rather than global, because the right number follows the
   * project's own shape: two agents want one column each, eight want four.
   * `undefined` means no choice yet — the default applies; a stored number is
   * a deliberate choice and outranks it, the same rule as `enlarged`.
   */
  columns?: number
  /**
   * Panels of ANY kind this reader has open in this project, each declaring its
   * kind — see `fleetPanels.ts`.
   *
   * `terminals` above is the older, kind-less shape and still means agents; it
   * is read, never rewritten. Both are resolved together by `resolvePanels`, so
   * there is one ordered list on screen and not two lanes that can disagree
   * about order.
   *
   * A stored entry naming a kind THIS BUILD does not have is reported as
   * unrecognised rather than dropped — the same rule the arrangement applies to
   * a project it can no longer find. Dropping it would tell the reader they had
   * closed something they never closed.
   */
  panels?: { kind: string; id: string }[]
}

/** Column counts a reader may choose. Two is the default the user asked for. */
export const COLUMN_CHOICES = [1, 2, 3, 4] as const
export const DEFAULT_COLUMNS = 2

/**
 * The column count to render with — clamped to what the UI can actually lay
 * out, so a hand-edited or stale stored value cannot produce an unreadable
 * grid. A remembered choice wins; anything outside the range is not honoured
 * as "the closest thing they meant", it falls back to the default, because a
 * value that was never offered is corruption rather than preference.
 */
export function resolveColumns(view: ProjectView): number {
  const c = view.columns
  if (typeof c !== 'number' || !Number.isInteger(c)) return DEFAULT_COLUMNS
  return (COLUMN_CHOICES as readonly number[]).includes(c) ? c : DEFAULT_COLUMNS
}

type Store = Record<string, ProjectView>

function read(): Store {
  try {
    const raw = localStorage.getItem(KEY)
    if (!raw) return {}
    const parsed: unknown = JSON.parse(raw)
    return parsed && typeof parsed === 'object' ? (parsed as Store) : {}
  } catch {
    // localStorage can be unavailable (private mode, disabled storage) and the
    // stored value can be anything. Neither is a reason for the landing screen
    // to fail — it just means nothing is remembered.
    return {}
  }
}

export function readView(project: string | null): ProjectView {
  if (!project) return {}
  return read()[project] ?? {}
}

export function writeView(project: string | null, patch: ProjectView): void {
  if (!project) return
  try {
    const all = read()
    all[project] = { ...all[project], ...patch }
    localStorage.setItem(KEY, JSON.stringify(all))
  } catch {
    /* nothing remembered; the screen still works */
  }
}

/**
 * Which tile should be enlarged, given what is remembered and what is alive.
 *
 * The whole rule in one place so the two halves cannot drift apart:
 * a remembered choice wins, including the choice to have nothing enlarged; a
 * remembered pid that is not in `alive` is discarded rather than rendered; and
 * only with no choice at all does the single-agent default apply.
 */
export function resolveEnlarged(view: ProjectView, alive: readonly number[]): number | null {
  if (view.enlarged === null) return null
  if (typeof view.enlarged === 'number') {
    return alive.includes(view.enlarged) ? view.enlarged : (alive.length === 1 ? alive[0] : null)
  }
  return alive.length === 1 ? alive[0] : null
}

/**
 * Which terminals to show, given what is remembered and what exists.
 *
 * The memory says what to SHOW; `alive` says what exists — a label that no
 * longer belongs to an agent the framework holds opens nothing, and is dropped
 * here rather than rendered as a dead pane.
 *
 * A reader whose memory predates the multi-terminal shape has a single
 * `terminal` label. It is read as a one-element list, so the first render after
 * an upgrade shows what they left open rather than an empty panel. An explicit
 * `terminals` — including the empty array, which means *I closed them all* —
 * always outranks it.
 */
export function resolveTerminals(view: ProjectView, alive: readonly string[]): string[] {
  const remembered = Array.isArray(view.terminals)
    ? view.terminals
    : typeof view.terminal === 'string' ? [view.terminal] : []
  const seen = new Set<string>()
  return remembered.filter(l => {
    if (typeof l !== 'string' || seen.has(l) || !alive.includes(l)) return false
    seen.add(l)
    return true
  })
}

/**
 * The agent to show alone, or `null`.
 *
 * Deliberately NOT falling back to "the nearest live agent" when the remembered
 * one is gone: a full screen is a claim about which agent you are looking at,
 * and silently substituting another one would put a different session under a
 * heading the reader trusts. Gone means back to the grid.
 */
export function resolveFocus(view: ProjectView, alive: readonly number[]): number | null {
  return typeof view.focus === 'number' && alive.includes(view.focus) ? view.focus : null
}

/**
 * Whose log is open.
 *
 * With no choice recorded, the enlarged tile's log is open — that is the
 * pre-existing behaviour (task 7.5's single-agent default lands on it), and
 * changing it silently would make a reader's first visit differ from every
 * later one. Once anything has been opened or closed by hand, the list is the
 * answer, and a pid that is no longer running is dropped rather than rendered.
 */
export function resolveLogs(
  view: ProjectView,
  alive: readonly number[],
  enlarged: number | null,
): number[] {
  if (!Array.isArray(view.logs)) {
    return enlarged !== null && alive.includes(enlarged) ? [enlarged] : []
  }
  const seen = new Set<number>()
  return view.logs.filter(p => {
    if (typeof p !== 'number' || seen.has(p) || !alive.includes(p)) return false
    seen.add(p)
    return true
  })
}
