/**
 * Is this page still the build the server is serving? — B-77.
 *
 * ## The failure this exists for
 *
 * The dashboard is a Vite SPA whose heavy parts arrive as LAZY chunks: the
 * editor, the terminal emulator, the graph panel. Their filenames carry a
 * content hash, so a redeploy replaces every one of them. A tab that was opened
 * before the redeploy is still running the old entry script, and the moment the
 * reader does something that needs a chunk, the browser asks for a filename that
 * no longer exists and gets a 404.
 *
 * What the reader sees is not an error. It is `loading the editor…`, for ever,
 * because the rejected `import()` leaves the "ready" flag where it was. The
 * console has the truth — *Failed to fetch dynamically imported module* — and
 * nothing on screen does. Measured 2026-08-24, reported by the user with the
 * devtools open beside it, which is the only way it was legible at all.
 *
 * ## Why this is a MEASUREMENT and not a message
 *
 * The obvious repair is to print *"the dashboard was updated — reload"* on any
 * chunk failure. That claim would be a guess: the same rejection is what an
 * offline tab, a dead server or a disk error produces, and telling a reader to
 * reload when reloading cannot help sends them somewhere empty.
 *
 * So the page ASKS. `index.html` names the current entry script; this page knows
 * the entry script it was loaded with. If the served page no longer mentions
 * this one, the build was replaced — that is a fact, not an inference, and it is
 * what licenses the word "updated".
 */

/**
 * The chunk-load rejection, across engines.
 *
 * Each browser words it differently and none of them exposes a code, so the
 * message is all there is. Kept in one place with all three wordings: a check
 * written against Chrome's phrasing alone passes every test on a developer's
 * machine and recognises nothing in Firefox or Safari.
 */
export function isChunkLoadError(err: unknown): boolean {
  const message = err instanceof Error ? err.message : String(err ?? '')
  return (
    // Chrome / Edge
    message.includes('Failed to fetch dynamically imported module') ||
    // Firefox
    message.includes('error loading dynamically imported module') ||
    // Safari
    message.includes('Importing a module script failed')
  )
}

/**
 * The entry script THIS page was loaded with, as a path, or `null`.
 *
 * Vite puts exactly one module script in `index.html`, and its `src` carries the
 * build's hash. The path — not the absolute URL — because that is what the
 * served HTML contains.
 */
export function entryScriptPath(doc: Document = document): string | null {
  const el = doc.querySelector('script[type="module"][src]') as HTMLScriptElement | null
  if (!el) return null
  const src = el.getAttribute('src')
  if (!src) return null
  try {
    return new URL(src, doc.baseURI).pathname
  } catch {
    return src
  }
}

/**
 * Does the freshly served `index.html` still reference this page's entry script?
 *
 * Pure, so the decision is testable without a network: the caller does the
 * fetching. `null` means *not answerable* — no entry script to compare, which is
 * a jsdom test or a page assembled some other way. A `null` must never be shown
 * as "up to date"; that is the false-value class, in the reassuring direction.
 */
export function servedHtmlHasEntry(html: string, entry: string | null): boolean | null {
  if (!entry) return null
  return html.includes(entry)
}

/** What went wrong, in the reader's terms. */
export type LoadFailure =
  | { kind: 'stale'; reason: string }
  | { kind: 'unknown'; reason: string }

export const STALE_REASON =
  'the dashboard was updated while this page was open, so the part it just asked ' +
  'for is no longer on the server — reload the page'

/**
 * Classify a failed lazy import, asking the server before blaming the build.
 *
 * Fails towards `unknown`: every path that cannot MEASURE staleness reports the
 * underlying error instead of guessing. A wrong "reload" is worse than a plain
 * error, because the reader spends the reload before learning nothing changed.
 */
export async function classifyLoadFailure(
  err: unknown,
  fetchFn: typeof fetch = fetch,
  doc: Document = document,
): Promise<LoadFailure> {
  const plain = err instanceof Error ? err.message : String(err ?? 'unknown error')
  if (!isChunkLoadError(err)) return { kind: 'unknown', reason: plain }
  try {
    const res = await fetchFn('/index.html', { cache: 'no-store' })
    if (!res.ok) return { kind: 'unknown', reason: plain }
    const fresh = servedHtmlHasEntry(await res.text(), entryScriptPath(doc))
    if (fresh === false) return { kind: 'stale', reason: STALE_REASON }
    return { kind: 'unknown', reason: plain }
  } catch {
    return { kind: 'unknown', reason: plain }
  }
}
