/**
 * `/?agent=<session id>` — open the fleet with one agent's tile focused.
 *
 * The Now card's "Go there" (fleet-now-card 4.4) lands here. A session id rather
 * than a pid, because the card's items carry the session the source named, and a
 * pid is reused across restarts while a session id is not.
 */

const PARAM = 'agent'

/** The session id the URL asks to focus, or null. */
export function agentParam(search: string): string | null {
  const value = new URLSearchParams(search).get(PARAM)
  return value && value.trim() ? value.trim() : null
}

/** The same URL without the focus parameter — consumed once, so a reload does not re-jump. */
export function stripAgentParam(href: string): string {
  const url = new URL(href)
  url.searchParams.delete(PARAM)
  return url.pathname + (url.search ? url.search : '') + url.hash
}

/** The fleet URL that focuses one agent. */
export function agentHref(sessionId: string): string {
  return `/?${PARAM}=${encodeURIComponent(sessionId)}`
}
