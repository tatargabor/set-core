/**
 * The live view of a file the project pointed at.
 *
 * Two rules shape everything here, and both are the same rule one layer apart:
 *
 * **This panel recognises no key.** A line that parses as JSON is shown by the producer's own
 * keys in the producer's own order; nothing is promoted, coloured by name, or required to exist.
 * Knowing that `type` means the event type would be the same mistake as knowing that a field
 * called `log` holds a log, and the next producer's conventions differ.
 *
 * **Silence is never the report.** The stream says why it ended — the file vanished, was
 * replaced, hit a bound — and that reason is rendered where the lines were arriving. A dead
 * stream and a quiet file look identical otherwise, and a reader will take the first for the
 * second every time.
 */

import { useEffect, useRef, useState } from 'react'
import { followStreamURL } from '../lib/api'

/** How many lines the panel keeps. Older ones fall off the top — stated on screen, not silently. */
const KEEP_LINES = 500

/** How many times a stream that HAD opened is re-established before the panel gives up. */
const MAX_RECONNECTS = 4

/** Base backoff between reconnects; multiplied by the attempt number. */
const RECONNECT_MS = 1000

interface Line {
  n: number
  text: string
  truncated?: boolean
}

/** Why the stream stopped, in the producer-independent words the endpoint uses. */
const END_REASONS: Record<string, string> = {
  'file-gone': 'the file was deleted',
  'file-replaced': 'the file was replaced by a different one',
  'line-budget': 'the line budget for one stream was reached',
  'max-duration': 'the stream reached its maximum duration',
  unreadable: 'the file could not be read',
  refused: 'the project would not allow this file to be followed',
  'connection-lost': 'the connection dropped and could not be re-established',
}

/**
 * One console line. No structure, no disclosure, no click.
 *
 * The first version rendered a JSON line as its own key/value pairs and let each line expand.
 * The user's correction was direct: *a console, not per-line expandable things* — and it is the
 * right call. A reader watching a run wants to scan what happened; every affordance per line is
 * one more thing between them and the next event, and 500 of them is a page of controls.
 *
 * The formatting that makes a transcript readable happens on the SERVER (`_console_line`), using
 * the reader set-core already ships for this shape. This component deliberately holds none of it:
 * a second copy of "what a tool_use block looks like", written in TypeScript, would agree on the
 * day it was written and drift afterwards.
 */
function ConsoleLine({ line }: { line: Line }) {
  return (
    <div className="whitespace-pre-wrap break-all text-fg-normal">
      {line.text}
      {line.truncated && <span className="text-fg-ghost italic"> … line truncated</span>}
    </div>
  )
}

export function FollowPanel({
  project, command, path, field, onClose,
}: {
  project: string
  command: string
  path: string
  field: string
  onClose: () => void
}) {
  const [lines, setLines] = useState<Line[]>([])
  const [ended, setEnded] = useState<string | null>(null)
  const [detail, setDetail] = useState<string | null>(null)
  const [opened, setOpened] = useState(false)
  const [retrying, setRetrying] = useState(0)
  const [dropped, setDropped] = useState(0)
  const box = useRef<HTMLDivElement>(null)
  const counter = useRef(0)
  const attempt = useRef(0)
  /**
   * Whether this stream ever connected — in a REF, and the reason is a bug this had.
   *
   * The first version read the `opened` state inside the error handler. The effect does not
   * re-run when `opened` changes, so the closure captured `false` and kept it forever: a stream
   * that had been delivering lines for an hour still looked, at the moment it dropped, like one
   * that never connected. It therefore took the "ask the endpoint why it refused" path — and
   * during a service restart nothing answers, so it gave up instead of reconnecting.
   *
   * Measured, not reasoned: restarting the service under an open stream printed
   * "could not be re-established" immediately, with no reconnect attempted.
   */
  const everOpened = useRef(false)

  useEffect(() => {
    const url = followStreamURL(project, command, path)
    let src: EventSource
    let timer: ReturnType<typeof setTimeout> | undefined
    let live = true

    /**
     * Why the stream would not open — asked of the endpoint, because the browser cannot say.
     *
     * `EventSource` reports every failure as one bare `error` event and gives no access to the
     * response body, so a carefully worded 400 arrives indistinguishable from a pulled cable.
     * The user saw the consequence and reported it: `stream ended — connection-lost` for a path
     * the project had simply stopped naming. The refusal exists and says exactly what is wrong;
     * it was the reading side that threw it away.
     *
     * So a plain fetch of the same URL retrieves it. Cheap, because it only runs when the stream
     * has already failed to open.
     */
    const askWhy = async () => {
      try {
        const res = await fetch(url)
        if (res.ok) return null
        const body = await res.json().catch(() => null)
        const d = body?.detail ?? body
        return typeof d?.error === 'string' ? d.error : `HTTP ${res.status}`
      } catch {
        return null
      }
    }

    const connect = () => {
      src = new EventSource(url)
      src.addEventListener('open', () => {
        everOpened.current = true
        setOpened(true); attempt.current = 0; setRetrying(0)
      })

      src.addEventListener('line', (e: MessageEvent) => {
        let payload: { text?: string; truncated?: boolean }
        try {
          payload = JSON.parse(e.data)
        } catch {
          return
        }
        if (typeof payload.text !== 'string') return
        setLines(prev => {
          const next = [...prev, {
            n: counter.current++, text: payload.text as string, truncated: payload.truncated,
          }]
          if (next.length > KEEP_LINES) {
            setDropped(d => d + (next.length - KEEP_LINES))
            return next.slice(next.length - KEEP_LINES)
          }
          return next
        })
      })

      src.addEventListener('end', (e: MessageEvent) => {
        let reason = 'unknown'
        try {
          reason = JSON.parse(e.data).reason ?? 'unknown'
        } catch { /* the reason is the point; a malformed one still ends the stream */ }
        setEnded(reason)
        src.close()
      })

      /**
       * A transport failure is an ending too, and the one most likely to be mistaken for calm.
       *
       * Two different situations arrive here as the same event, and telling them apart is the
       * whole of this handler:
       *
       * **It never opened.** The endpoint refused — a path the answer no longer names, a command
       * that failed, a file outside the tree. The reason exists; the browser cannot read it. So
       * it is fetched and shown, instead of the word `connection-lost` standing in for a sentence
       * that was written precisely so nobody would have to guess.
       *
       * **It opened and then dropped.** A restarted server, a suspended laptop, a blip. This is
       * exactly what `EventSource` reconnects for, and closing the socket threw that away — so a
       * service restart ended the follow permanently while the file kept growing. It now
       * reconnects a bounded number of times AND SAYS SO: a silent reconnect would mean lines
       * missed during the gap look like a quiet file.
       */
      src.onerror = () => {
        src.close()
        if (!live) return
        const retry = () => {
          if (attempt.current >= MAX_RECONNECTS) {
            setEnded(prev => prev ?? 'connection-lost')
            return
          }
          attempt.current += 1
          setRetrying(attempt.current)
          timer = setTimeout(connect, RECONNECT_MS * attempt.current)
        }

        if (everOpened.current) { retry(); return }

        // It never connected. Ask the endpoint why — but only treat an ANSWER as final. A
        // fetch that fails too means nothing is listening, which is a restart, not a refusal,
        // and the difference decides between explaining and waiting.
        if (attempt.current === 0) {
          askWhy().then(why => {
            if (!live) return
            if (why) { setEnded('refused'); setDetail(why) }
            else retry()
          })
          return
        }
        retry()
      }

    }

    connect()
    return () => { live = false; if (timer) clearTimeout(timer); src?.close() }
  }, [project, command, path])

  // Follow the tail unless the reader has scrolled up to look at something.
  useEffect(() => {
    const el = box.current
    if (!el) return
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 60
    if (atBottom) el.scrollTop = el.scrollHeight
  }, [lines])

  // Escape closes it, because a layer that covers the page and can only be dismissed with the
  // mouse is a trap for anyone reading with the keyboard.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
    >
    <div
      className="w-[80vw] h-[80vh] flex flex-col rounded border border-surface-line bg-surface-page shadow-2xl"
      onClick={e => e.stopPropagation()}
    >
      <div className="flex items-center gap-2 px-2 py-1 border-b border-surface-line text-xs shrink-0">
        <span className={`inline-block w-1.5 h-1.5 rounded-full ${
          ended ? 'bg-fg-ghost' : opened ? 'bg-emerald-500' : 'bg-amber-500'
        }`} />
        <span className="text-fg-faint">{field}</span>
        <span className="text-fg-ghost truncate" title={path}>{path}</span>
        <span className="ml-auto text-fg-ghost">{lines.length} line{lines.length === 1 ? '' : 's'}</span>
        <button
          onClick={onClose}
          className="text-fg-muted hover:text-fg-strong px-1"
          aria-label="stop following"
        >×</button>
      </div>

      <div ref={box} className="flex-1 min-h-0 overflow-y-auto px-2 py-1 text-xs leading-relaxed">
        {lines.length === 0 && !ended && (
          // Not "nothing is happening" — this stream starts at the end of the file on purpose.
          <div className="text-fg-ghost py-1">
            waiting for new lines — this follows from now, and does not replay what came before
          </div>
        )}
        {dropped > 0 && (
          <div className="text-fg-muted italic py-0.5">
            {dropped} earlier line{dropped === 1 ? '' : 's'} scrolled out of this panel
          </div>
        )}
        {lines.map(l => <ConsoleLine key={l.n} line={l} />)}
        {retrying > 0 && !ended && (
          // Said out loud: a silent reconnect makes the lines missed during the gap look like
          // a file that had nothing to say.
          <div className="text-amber-500/90 py-1">
            connection dropped — reconnecting ({retrying}/{MAX_RECONNECTS}); lines written
            during the gap will not appear
          </div>
        )}
        {ended && (
          <div className="text-amber-500/90 py-1 whitespace-pre-wrap break-words">
            stream ended — {END_REASONS[ended] ?? ended}
            {detail && <span className="block text-fg-muted">{detail}</span>}
          </div>
        )}
      </div>
    </div>
    </div>
  )
}
