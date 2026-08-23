/**
 * Where a new agent starts — the project's checkout, or one of its worktrees.
 *
 * Until this change the start form sent `cwd: project.root` and offered nothing
 * else, so the one directory an agent is most often wanted in — a change/
 * worktree, which is what this framework's whole parallel-work discipline
 * creates — was the one place the screen could not start one.
 *
 * Three decisions live here as functions rather than inside the component, so
 * each can be asserted in both directions:
 *
 *  - **A prunable location is not offered.** git reports `prunable` for a
 *    worktree whose directory it can no longer find; nothing can run there, and
 *    the endpoint refuses it. Offering it would be a control that fails.
 *  - **The default is the main checkout**, not the first entry that happens to
 *    come back. They are the same today because git emits the main working tree
 *    first — which is exactly why it must not be re-derived from position here.
 *  - **A failed read is said, never rendered as an empty list.** No worktrees
 *    and *we could not ask* are different facts, and the second one silently
 *    wearing the first one's clothes is this repository's most-repeated defect.
 */

export interface StartLocation {
  path: string
  branch: string
  is_main: boolean
  prunable: boolean
}

export interface StartLocations {
  project: string
  root: string
  locations: StartLocation[]
}

/** What the selector may show: everything git can still run something in. */
export function offerable(locations: StartLocation[]): StartLocation[] {
  return locations.filter(loc => !loc.prunable)
}

/**
 * The location a freshly-opened form starts on.
 *
 * Falls back to the project root rather than to `locations[0]`: if no entry
 * claims to be the main checkout, picking the first one would present a
 * worktree as the default while looking exactly like a correct answer.
 */
export function defaultLocation(locations: StartLocation[], root: string): string {
  const main = offerable(locations).find(loc => loc.is_main)
  return main ? main.path : root
}

/**
 * How one location reads in the list.
 *
 * The branch is the name people actually use for a worktree ("change/add-auth").
 * A detached worktree has no branch, so the directory name stands in — never an
 * empty option, which is unclickable in the only sense that matters: the reader
 * cannot tell what they would be choosing.
 */
export function locationLabel(loc: StartLocation): string {
  if (loc.is_main) return loc.branch ? `main checkout (${loc.branch})` : 'main checkout'
  if (loc.branch) return loc.branch
  const name = loc.path.replace(/\/+$/, '').split('/').pop()
  return name && name.length > 0 ? name : loc.path
}

/**
 * Whether the selector is worth rendering at all.
 *
 * A project with a single checkout gains nothing from a one-option dropdown,
 * and the start control lives in a header row where every element competes for
 * width (see the UI-quality rule: compact before complete).
 */
export function selectorWorthShowing(locations: StartLocation[]): boolean {
  return offerable(locations).length > 1
}

/**
 * Ask for a project's startable locations.
 *
 * Resolves to `null` when the list could not be read — the caller keeps the
 * project root and says so. Deliberately not an empty array: that is the value
 * that reads as "this project has no worktrees".
 */
export async function fetchStartLocations(
  project: string,
  fetchImpl: typeof fetch = fetch,
): Promise<StartLocations | null> {
  try {
    const res = await fetchImpl(`/api/fleet/projects/${encodeURIComponent(project)}/worktrees`)
    if (!res.ok) return null
    const body = await res.json()
    if (!body || !Array.isArray(body.locations)) return null
    return body as StartLocations
  } catch {
    return null
  }
}
