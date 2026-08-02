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
  const [opened, setOpened] = useState(false)
  const [dropped, setDropped] = useState(0)
  const box = useRef<HTMLDivElement>(null)
  const counter = useRef(0)

  useEffect(() => {
    const url = followStreamURL(project, command, path)
    const src = new EventSource(url)

    src.addEventListener('open', () => setOpened(true))

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

    // A transport failure is an ending too, and the one most likely to be mistaken for calm.
    src.onerror = () => {
      setEnded(prev => prev ?? 'connection-lost')
      src.close()
    }

    return () => src.close()
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
        {ended && (
          <div className="text-amber-500/90 py-1">
            stream ended — {END_REASONS[ended] ?? ended}
          </div>
        )}
      </div>
    </div>
    </div>
  )
}
