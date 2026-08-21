import type { ReactNode } from 'react'
import { useEffect, useRef, useState } from 'react'
import { Pencil } from 'lucide-react'

import type { FleetAgent } from '../lib/fleetTypes'

/**
 * Giving a running agent a different name.
 *
 * ## Why this exists at all
 *
 * The name is the handle a person navigates eight identical-looking sessions
 * by, and until this change it could not be changed at all: a name typed once
 * was a name forever, and the only way to alter it was to stop the agent and
 * resume it — killing the in-flight turn and the terminal history to edit a
 * string. It is also the repair path for names a reboot lost, which no code can
 * derive: the framework cannot know which conversation somebody called
 * `bugfix`.
 *
 * ## Offered only where it can work
 *
 * `terminal_label` is present exactly when this framework holds the agent's
 * terminal. Without one there is nothing to rename — the name belongs to the
 * runtime, in a file the runtime owns and rewrites — so the control is ABSENT
 * rather than present-and-failing. A disabled pencil would invite the click
 * that teaches the reader the screen is lying.
 *
 * ## A refusal leaves the name alone
 *
 * The server refuses a name another agent holds, rather than deriving a variant
 * (restore does the opposite, and the asymmetry is deliberate: there the
 * alternative is losing an agent with nobody watching). So a refusal here is
 * information for the person looking at it, and it is shown next to the field
 * with the displayed name unchanged — never swallowed, and never applied
 * optimistically first.
 */
export default function FleetRename({ agent, onRenamed, children }: {
  agent: FleetAgent
  /** Called with the new name once the server has confirmed it. */
  onRenamed?: (from: string, to: string) => void
  /**
   * The name as the tile draws it. Rendered by THIS component so that editing
   * REPLACES it instead of sitting beside it.
   *
   * Found by looking, 2026-08-21: with the name outside, the header read
   * `set-core-memory [set-core-memory] rename cancel` — the same string twice,
   * a foot apart, one of them editable. No test would have called that wrong.
   */
  children?: ReactNode
}) {
  const label = agent.terminal_label
  const [editing, setEditing] = useState(false)
  const [text, setText] = useState(label ?? '')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const box = useRef<HTMLInputElement | null>(null)

  useEffect(() => { if (editing) box.current?.select() }, [editing])
  // The field starts from the CURRENT name, so the ordinary edit — change two
  // characters — is two characters of work rather than retyping the whole name.
  useEffect(() => { setText(label ?? '') }, [label])

  // Not renamable: render the name and no control at all. Returning nothing
  // would take the NAME away with the control, which is a worse screen than one
  // without a pencil.
  if (!label) return <>{children}</>

  const close = () => { setEditing(false); setError(null); setText(label) }

  const send = async () => {
    const wanted = text.trim()
    if (!wanted || wanted === label) { close(); return }
    setBusy(true)
    setError(null)
    try {
      const res = await fetch(`/api/fleet/agents/${encodeURIComponent(label)}/rename`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ new_label: wanted }),
      })
      if (!res || !res.ok) {
        const detail = res ? await res.json().catch(() => null) : null
        setError(detail?.detail || `rename failed (${res?.status ?? 'no answer'})`)
        return
      }
      onRenamed?.(label, wanted)
      setEditing(false)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'rename failed')
    } finally {
      setBusy(false)
    }
  }

  if (!editing) {
    return (
      <>
      {children}
      <button
        type="button"
        data-fleet-rename={label}
        aria-label={`rename ${label}`}
        title={`rename ${label}`}
        onClick={e => { e.stopPropagation(); setEditing(true) }}
        className="text-fg-ghost hover:text-fg-strong"
      >
        <Pencil size={11} strokeWidth={1.75} />
      </button>
      </>
    )
  }

  return (
    <span className="inline-flex items-baseline gap-1.5" onClick={e => e.stopPropagation()}>
      <input
        ref={box}
        value={text}
        disabled={busy}
        data-fleet-rename-input={label}
        aria-label={`new name for ${label}`}
        onChange={e => setText(e.target.value)}
        onKeyDown={e => {
          if (e.key === 'Enter') { e.preventDefault(); void send() }
          if (e.key === 'Escape') { e.preventDefault(); close() }
        }}
        className="bg-surface-page border border-surface-edge rounded px-1.5 py-0.5 text-sm text-fg-normal focus:outline-none focus:border-sky-400/60"
      />
      <button type="button" disabled={busy} onClick={() => void send()}
              data-fleet-rename-send={label}
              className="text-xs text-sky-300 disabled:text-fg-ghost">rename</button>
      <button type="button" onClick={close} className="text-xs text-fg-ghost">cancel</button>
      {/* Under the row, not in it. The owner's refusals are sentences — one of
          them lists every method it answers — and inline they push the state
          line and the rest of the header down the tile. A message that moves
          the furniture to be read is a message that gets read once. */}
      {error && (
        <span data-fleet-rename-error={label}
              className="block text-xs text-amber-400 max-w-md truncate" title={error}>{error}</span>
      )}
    </span>
  )
}
