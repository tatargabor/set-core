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
