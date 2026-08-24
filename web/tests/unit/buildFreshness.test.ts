/**
 * Telling "the build was replaced" apart from "something else broke" — B-77.
 *
 * The defect this guards is not the failure itself; it is what the reader was
 * told about it. A lazy chunk whose filename carries a build hash disappears on
 * every redeploy, and the rejected `import()` used to leave `loading the editor…`
 * on screen with the truth only in the console.
 *
 * The repair had to avoid the opposite error just as carefully: printing *"the
 * dashboard was updated — reload"* on ANY chunk failure would send an offline
 * reader to spend a reload that cannot help. So staleness is measured — the
 * served `index.html` is asked whether it still names this page's entry script —
 * and every path that cannot measure it reports the underlying error instead.
 * These tests hold both directions.
 */
import { describe, expect, it } from 'vitest'
import {
  classifyLoadFailure,
  entryScriptPath,
  isChunkLoadError,
  servedHtmlHasEntry,
  STALE_REASON,
} from '../../src/lib/buildFreshness'

const chromeErr = new Error(
  'Failed to fetch dynamically imported module: http://localhost:7400/assets/index-C41P94E2.js',
)

/** A document whose single module script is the given path. */
function docWith(src: string | null): Document {
  const doc = document.implementation.createHTMLDocument('t')
  const base = doc.createElement('base')
  base.href = 'http://localhost:7400/'
  doc.head.appendChild(base)
  if (src !== null) {
    const el = doc.createElement('script')
    el.type = 'module'
    el.setAttribute('src', src)
    doc.head.appendChild(el)
  }
  return doc
}

const served = (html: string) =>
  (async () => new Response(html, { status: 200 })) as unknown as typeof fetch

describe('recognising a chunk that is no longer on the server', () => {
  it('knows the wording of all three engines', () => {
    expect(isChunkLoadError(chromeErr)).toBe(true)
    expect(isChunkLoadError(new Error('error loading dynamically imported module: x'))).toBe(true)
    expect(isChunkLoadError(new Error('Importing a module script failed.'))).toBe(true)
  })

  /**
   * The one that keeps a check honest. A message-matching test that only ever
   * feeds it matching messages proves nothing about what it rejects.
   */
  it('does not claim every error is one', () => {
    expect(isChunkLoadError(new Error('NetworkError when attempting to fetch resource.'))).toBe(false)
    expect(isChunkLoadError(new TypeError('x is not a function'))).toBe(false)
    expect(isChunkLoadError(null)).toBe(false)
  })
})

describe('the entry script this page was loaded with', () => {
  it('is read from the document, as a path', () => {
    expect(entryScriptPath(docWith('/assets/index-DIYHZ1ow.js'))).toBe('/assets/index-DIYHZ1ow.js')
  })

  it('is null when there is none to read', () => {
    expect(entryScriptPath(docWith(null))).toBeNull()
  })

  /**
   * `null` is not "fresh". A page that cannot name its own entry cannot answer
   * the question, and answering it anyway in the reassuring direction is the
   * false-value class.
   */
  it('makes the comparison unanswerable rather than true', () => {
    expect(servedHtmlHasEntry('<script src="/assets/index-x.js">', null)).toBeNull()
  })
})

describe('what the reader is told', () => {
  it('says the build was replaced only when the served page no longer names it', async () => {
    const out = await classifyLoadFailure(
      chromeErr,
      served('<script type="module" src="/assets/index-NEWHASH.js"></script>'),
      docWith('/assets/index-DIYHZ1ow.js'),
    )
    expect(out).toEqual({ kind: 'stale', reason: STALE_REASON })
  })

  /**
   * The direction that matters more. The same rejection is what an offline tab
   * produces, and a reload cannot help there — so a served page that still names
   * this entry must NOT be reported as a redeploy.
   */
  it('does not blame a redeploy when this page is still the one being served', async () => {
    const out = await classifyLoadFailure(
      chromeErr,
      served('<script type="module" src="/assets/index-DIYHZ1ow.js"></script>'),
      docWith('/assets/index-DIYHZ1ow.js'),
    )
    expect(out.kind).toBe('unknown')
    expect(out.reason).toContain('Failed to fetch dynamically imported module')
  })

  it('reports the underlying error when the server cannot be asked at all', async () => {
    const dead = (async () => { throw new Error('offline') }) as unknown as typeof fetch
    const out = await classifyLoadFailure(chromeErr, dead, docWith('/assets/index-DIYHZ1ow.js'))
    expect(out.kind).toBe('unknown')
  })

  it('leaves an unrelated error alone, without a round trip', async () => {
    const never = (() => { throw new Error('the server must not be asked') }) as unknown as typeof fetch
    const out = await classifyLoadFailure(new TypeError('x is not a function'), never, docWith('/a.js'))
    expect(out).toEqual({ kind: 'unknown', reason: 'x is not a function' })
  })
})
