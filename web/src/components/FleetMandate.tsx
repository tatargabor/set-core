import { useEffect, useState } from 'react'

import {
  EMPTY_DRAFT, GOAL_NOTE, NO_GOAL_NOTE,
  declareOutcome, mandateFields, mandateStanding,
  type MandateDraft,
} from '../lib/fleetMandate'
import type { FleetAgent } from '../lib/fleetTypes'

/**
 * The mandate — why this agent was started — on the tile and in the start form.
 *
 * Every decision about what may be SAID lives in `lib/fleetMandate.ts`; this
 * file only draws it. Two layout rules it keeps:
 *
 *  - the tile's line is ONE line. The scope, the closing condition, who asked
 *    and whether the agent has been told ride in the title;
 *  - everything that opens — the scope fields in the start form, the declare
 *    dialog — floats above the layout and has its own way out. Nothing here
 *    adds height to the row it was opened from.
 */

const INPUT =
  'bg-surface-panel border border-surface-line rounded px-1.5 py-0.5 text-xs text-fg-strong w-full'

/** The goal fields, shared by the start form and the declare dialog. */
export function MandateFieldset({ draft, onChange, autoFocus = false }: {
  draft: MandateDraft
  onChange: (next: MandateDraft) => void
  autoFocus?: boolean
}) {
  const [more, setMore] = useState(false)
  const extras = [draft.paths, draft.change, draft.doneWhen].filter(v => v.trim()).length
  return (
    /* `relative` so the scope fields can float from here: they cover what is
       below them and move none of it. */
    <div className="relative flex flex-col gap-1" data-fleet-mandate-fields>
      <textarea
        autoFocus={autoFocus}
        value={draft.goal}
        onChange={e => onChange({ ...draft, goal: e.target.value })}
        rows={2}
        aria-label="goal: what this agent is for"
        placeholder="goal — what this agent is for"
        data-fleet-mandate-goal
        className={`${INPUT} resize-none`}
      />
      <button
        type="button"
        onClick={() => setMore(o => !o)}
        aria-expanded={more}
        data-fleet-mandate-more={more ? 'open' : 'closed'}
        className="self-start text-xs text-fg-muted hover:text-fg-strong"
        title="Optional: the paths or the change this agent is confined to, and what counts as done."
      >
        scope and closing condition{extras > 0 ? ` (${extras} set)` : ''} {more ? '▴' : '▾'}
      </button>
      {more && (
        <div
          data-fleet-mandate-extras
          className="absolute left-0 right-0 top-full z-20 mt-0.5 flex flex-col gap-1.5 p-2 rounded border
                     border-surface-line bg-surface-raised shadow-xl"
        >
          <div className="flex items-center">
            <span className="text-xs text-fg-muted">scope and closing condition</span>
            <button
              type="button"
              onClick={() => setMore(false)}
              aria-label="close scope and closing condition"
              data-fleet-mandate-extras-close
              className="ml-auto px-1 text-base leading-none text-fg-muted hover:text-fg-strong"
            >×</button>
          </div>
          <textarea
            value={draft.paths}
            onChange={e => onChange({ ...draft, paths: e.target.value })}
            rows={2}
            aria-label="paths this agent is confined to"
            placeholder="paths — one per line (optional)"
            className={`${INPUT} resize-none`}
          />
          <input
            value={draft.change}
            onChange={e => onChange({ ...draft, change: e.target.value })}
            aria-label="the change this agent works on"
            placeholder="change name (optional)"
            className={INPUT}
          />
          <input
            value={draft.doneWhen}
            onChange={e => onChange({ ...draft, doneWhen: e.target.value })}
            aria-label="what counts as done"
            placeholder="done when… (optional)"
            className={INPUT}
          />
        </div>
      )}
    </div>
  )
}

/**
 * The one sentence under the goal fields of the start form.
 *
 * It ALWAYS renders, at a fixed two-line height. The first build showed it only
 * while the goal was empty, and on the screen the whole dialog jumped twenty
 * pixels at the first keystroke — the fields moved out from under the cursor
 * because a sentence left. The space is reserved; only the sentence changes.
 */
export function StartMandateNote({ draft }: { draft: MandateDraft }) {
  const fields = mandateFields(draft)
  const reserve = 'block min-h-8 text-xs'
  if (fields.kind === 'problem') {
    return <span data-fleet-start="mandate-problem" className={`${reserve} text-red-400`}>{fields.message}</span>
  }
  return fields.kind === 'mandate'
    ? <span data-fleet-start="mandate-set" className={`${reserve} text-fg-ghost`}>{GOAL_NOTE}</span>
    : <span data-fleet-start="no-mandate" className={`${reserve} text-fg-ghost`}>{NO_GOAL_NOTE}</span>
}

function DeclareDialog({ agent, onClose }: { agent: FleetAgent; onClose: () => void }) {
  const [draft, setDraft] = useState<MandateDraft>(EMPTY_DRAFT)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [outcome, setOutcome] = useState<{ told: boolean; text: string } | null>(null)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const fields = mandateFields(draft)
  const who = agent.terminal_label ?? agent.name ?? `pid ${agent.pid}`

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-surface-page/60"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      data-fleet-mandate-dialog={agent.pid}
    >
      <div
        className="w-96 max-w-[92vw] flex flex-col rounded border border-surface-line bg-surface-page shadow-2xl"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center gap-2 px-3 py-2 border-b border-surface-line shrink-0">
          <span className="text-sm text-fg-strong truncate">Declare a mandate for {who}</span>
          <button
            onClick={onClose}
            aria-label="close"
            data-fleet-mandate-dialog-close
            className="ml-auto px-1 text-base leading-none text-fg-muted hover:text-fg-strong"
          >×</button>
        </div>
        {outcome ? (
          /* A result the reader has to act on or not — it stays until closed. */
          <div className="flex flex-col gap-2 px-3 py-2.5">
            <span data-fleet-mandate-outcome={outcome.told ? 'told-later' : 'screen-only'}
                  className={`text-xs ${outcome.told ? 'text-fg-normal' : 'text-amber-400'}`}>
              {outcome.text}
            </span>
            <button onClick={onClose} className="self-start text-xs text-fg-muted hover:text-fg-strong">close</button>
          </div>
        ) : (
          <form
            className="flex flex-col gap-2 px-3 py-2.5"
            onSubmit={e => {
              e.preventDefault()
              if (fields.kind !== 'mandate' || busy) return
              setBusy(true)
              setError(null)
              fetch('/api/fleet/mandates', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                  ...fields.mandate,
                  // The label when the framework holds the agent, else the session:
                  // whichever the inventory can find it by.
                  ...(agent.terminal_label ? { label: agent.terminal_label } : { session_id: agent.session_id }),
                }),
              })
                .then(async r => {
                  const body = await r.json().catch(() => null)
                  if (!r.ok) throw new Error(String(body?.detail ?? `HTTP ${r.status}`))
                  setOutcome(declareOutcome(body))
                })
                .catch(err => setError(String(err?.message ?? err)))
                .finally(() => setBusy(false))
            }}
          >
            <MandateFieldset draft={draft} onChange={setDraft} autoFocus />
            {fields.kind === 'problem' && <span className="text-xs text-red-400">{fields.message}</span>}
            {error && <span className="text-xs text-red-400" title={error}>not recorded: {error}</span>}
            <div className="flex items-center gap-2 pt-0.5">
              <button
                type="submit"
                disabled={busy || fields.kind !== 'mandate'}
                className="px-2 py-0.5 rounded border border-sky-500/50 text-xs text-sky-300
                           hover:bg-sky-500/10 disabled:opacity-50"
              >
                {busy ? 'recording…' : 'declare'}
              </button>
              <button type="button" onClick={onClose} className="text-xs text-fg-muted hover:text-fg-strong">cancel</button>
            </div>
          </form>
        )}
      </div>
    </div>
  )
}

/**
 * The tile's mandate line: the kind and the goal, or "no mandate" with its
 * reason and a control to declare one.
 *
 * "No mandate" is drawn quietly on the tile. It is true of every agent on a
 * machine that has only just gained mandates, and amber on every tile is amber
 * that means nothing; the marker that must not be missed is the count on the
 * map's opener, where one glance covers the whole fleet.
 */
export default function FleetMandateLine({ agent }: { agent: FleetAgent }) {
  const [declaring, setDeclaring] = useState(false)
  const s = mandateStanding(agent)
  if (s.kind === 'unreported') return null
  if (s.kind === 'unmeasured') {
    return (
      <div className="flex items-baseline gap-2 text-xs mt-1" data-fleet-mandate="unmeasured">
        <span className="text-amber-400 shrink-0" title={s.title}>mandate ?</span>
        <span className="text-fg-ghost truncate">the mandate store could not be read</span>
      </div>
    )
  }
  if (s.kind === 'held') {
    return (
      <div className="flex items-baseline gap-2 text-xs mt-1 min-w-0" data-fleet-mandate={s.badge} title={s.title}>
        <span className={`shrink-0 px-1 rounded border ${
          s.badge === 'desk' ? 'border-violet-400/50 text-violet-300' : 'border-sky-400/40 text-sky-300'
        }`}>{s.badge}</span>
        <span className="text-fg-normal truncate min-w-0" data-fleet-mandate-goal>{s.goal}</span>
        {!s.told && (
          <span className="text-fg-ghost shrink-0 italic" data-fleet-mandate-told="no">not told yet</span>
        )}
      </div>
    )
  }
  return (
    <div className="flex items-baseline gap-2 text-xs mt-1" data-fleet-mandate="none" data-fleet-mandate-reason={s.reason}>
      <span className="text-fg-muted shrink-0" title={s.title}>no mandate</span>
      <span className="text-fg-ghost shrink-0">· {s.why}</span>
      {s.canDeclare && (
        <button
          onClick={() => setDeclaring(true)}
          data-fleet-mandate-declare={agent.pid}
          className="shrink-0 text-sky-300 hover:text-sky-200 underline-offset-2 hover:underline"
          title="Record why this agent exists."
        >declare</button>
      )}
      {declaring && <DeclareDialog agent={agent} onClose={() => setDeclaring(false)} />}
    </div>
  )
}
