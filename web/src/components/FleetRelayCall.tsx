/**
 * One waiting relay call, opened: Details and Teach (fleet-relay-teach).
 *
 * Asked for by the owner (2026-11-24), from a screenshot of four questions waiting 29–52 min
 * with nothing on the panel saying what they asked: *„kellene egy részletek gomb ami
 * megmutatja mi a kérdés mire várunk, meg egy gomb ami megtanítja a rendszernek hogy ne
 * várjon legközelebb"*. Teach answers the call now and appends a rule to the project's
 * `.claude/rules/auto-answer-taught.md`, committed there (not pushed), so every agent of the
 * project — a teammate's too — and the decider know it next time.
 *
 * Floats over the relay panel (absolutely positioned, own close control) and moves nothing
 * under it. A finished save closes itself after 10 s; one that failed anywhere stays.
 */

import { useEffect, useRef, useState } from 'react'
import { X } from 'lucide-react'

import { age } from '../lib/fleetAge'
import { kindLabel } from '../lib/fleetAutoAnswer'
import {
  parseDetail, prefillAnswer, teachResultLines, waitsForText, type RelayDetail, type TeachResult,
} from '../lib/fleetRelayTeach'

const DONE_CLOSE_MS = 10_000

export default function FleetRelayCall({ id, mode, onMode, onClose, onSaved }: {
  id: string
  mode: 'details' | 'teach'
  onMode: (m: 'details' | 'teach') => void
  onClose: () => void
  onSaved: () => void
}) {
  const [detail, setDetail] = useState<RelayDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [answer, setAnswer] = useState('')
  const [explanation, setExplanation] = useState('')
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<{ lines: string[]; ok: boolean } | null>(null)
  const prefilled = useRef(false)

  useEffect(() => {
    let live = true
    fetch(`/api/fleet/question-relay/${encodeURIComponent(id)}/detail`)
      .then(async r => {
        const d = await r.json().catch(() => null)
        if (!r.ok) throw new Error(d?.detail ?? `HTTP ${r.status}`)
        const parsed = parseDetail(d)
        if (!parsed) throw new Error('unexpected answer shape')
        if (!live) return
        setDetail(parsed)
        if (!prefilled.current) { setAnswer(prefillAnswer(parsed)); prefilled.current = true }
      })
      .catch(e => { if (live) setError(String(e?.message ?? e)) })
    return () => { live = false }
  }, [id])

  useEffect(() => {
    if (!result?.ok) return
    const t = setTimeout(onClose, DONE_CLOSE_MS)
    return () => clearTimeout(t)
  }, [result, onClose])

  const save = () => {
    setBusy(true)
    fetch(`/api/fleet/question-relay/${encodeURIComponent(id)}/teach`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ answer, explanation }),
    })
      .then(async r => {
        const d = await r.json().catch(() => null)
        if (!r.ok) throw new Error(d?.detail ?? `HTTP ${r.status}`)
        setResult(teachResultLines(d as TeachResult))
        onSaved()
      })
      .catch(e => setResult({ lines: [`Not saved: ${String(e?.message ?? e)}`], ok: false }))
      .finally(() => setBusy(false))
  }

  const q0 = detail?.decider?.questions[0]
  return (
    <div className="absolute left-2 right-2 top-8 z-40 max-h-[70vh] overflow-auto rounded border border-surface-line
                    bg-surface-raised px-3 py-2 shadow-xl text-xs"
         role="dialog" aria-label={mode === 'teach' ? 'Teach an answer' : 'Question details'}
         data-fleet-relay-call={mode}>
      <div className="flex items-center gap-2 pb-1 border-b border-surface-line">
        <span className="font-semibold text-fg-loud">{mode === 'teach' ? 'Teach' : 'Details'}</span>
        {detail && (
          <span className="text-fg-muted truncate">
            {detail.project ?? 'unknown project'} · {kindLabel(detail.kind === 'question' ? 'ask' : detail.kind)}
            {detail.seconds !== null ? ` · ${age(detail.seconds)}` : ''}
          </span>
        )}
        <button type="button" onClick={onClose} aria-label="Close" data-fleet-relay-call-close
                className="ml-auto text-fg-muted hover:text-fg-strong">
          <X size={14} strokeWidth={1.75} aria-hidden />
        </button>
      </div>

      {error && <p className="mt-1.5 text-red-400" data-fleet-relay-call-error>{error}</p>}
      {!detail && !error && <p className="mt-1.5 text-fg-muted">Reading…</p>}

      {detail && mode === 'details' && (
        <div className="mt-1.5 space-y-2">
          <p className="text-fg-strong" data-fleet-relay-waits={detail.waits_for}>{waitsForText(detail)}</p>
          {!detail.decider && (
            <p className="text-fg-muted" data-fleet-relay-no-record>
              The decider has no record of this call ({detail.questions ?? '?'} question(s)). Its text is kept only
              in the decider's record, so read it on the channel or in the agent's terminal.
            </p>
          )}
          {detail.decider?.questions.map((q, i) => (
            <div key={q.key ?? i} className="space-y-1" data-fleet-relay-question={q.key ?? i}>
              <p className="whitespace-pre-wrap break-words text-fg-loud max-h-48 overflow-auto">{q.question}</p>
              {q.options.length > 0 && (
                <ul className="flex flex-wrap gap-1">
                  {q.options.map(o => (
                    <li key={o} className={`rounded border px-1.5 ${o === q.choice ? 'border-sky-400/60 text-sky-300' : 'border-surface-line text-fg-muted'}`}>{o}</li>
                  ))}
                </ul>
              )}
              <p className="text-fg-muted" data-fleet-relay-outcome={q.outcome ?? 'none'}>
                decider: <span className="text-fg-strong">{q.outcome ?? 'deciding'}</span>
                {q.choice ? <> — proposed «{q.choice}»{q.tier ? ` (${q.tier}${q.confidence !== null ? ` ${q.confidence.toFixed(2)}` : ''})` : ''}</> : null}
                {q.reason ? <> — {q.reason}</> : null}
              </p>
              {q.references.length > 0 && (
                <ul className="pl-2 border-l border-surface-line space-y-0.5">
                  {q.references.map((r, j) => (
                    <li key={j} className="text-fg-muted break-words">
                      {r.path ? <span className="text-fg-strong">{r.path}: </span> : <span className="text-fg-strong">{r.kind}: </span>}
                      “{r.quote}”
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ))}
          <div className="pt-1 border-t border-surface-line flex items-center gap-2">
            {detail.teach.allowed
              ? <button type="button" onClick={() => onMode('teach')} data-fleet-relay-to-teach
                        className="rounded border border-sky-400/50 px-1.5 text-sky-300 hover:bg-sky-400/10">teach…</button>
              : <span className="text-fg-muted" data-fleet-relay-no-teach>Teach is not available: {detail.teach.reason}</span>}
          </div>
        </div>
      )}

      {detail && mode === 'teach' && (
        <div className="mt-1.5 space-y-1.5">
          {!detail.teach.allowed && <p className="text-amber-400">Teach is not available: {detail.teach.reason}</p>}
          {q0 && <p className="whitespace-pre-wrap break-words text-fg-loud max-h-32 overflow-auto">{q0.question}</p>}
          {q0 && q0.options.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {q0.options.map(o => (
                <button key={o} type="button" onClick={() => setAnswer(o)}
                        className={`rounded border px-1.5 ${answer === o ? 'border-sky-400/60 text-sky-300' : 'border-surface-line text-fg-muted hover:text-fg-strong'}`}>
                  {o}
                </button>
              ))}
            </div>
          )}
          <label className="block">
            <span className="text-fg-muted">Answer — sent to the agent now, and the answer next time</span>
            <textarea value={answer} onChange={e => setAnswer(e.target.value)} rows={2}
                      className="mt-0.5 w-full rounded border border-surface-line bg-surface-panel px-1.5 py-1 text-fg-strong"
                      data-fleet-relay-teach-answer />
          </label>
          <label className="block">
            <span className="text-fg-muted">When / why (optional) — the condition the agents and the decider check</span>
            <textarea value={explanation} onChange={e => setExplanation(e.target.value)} rows={2}
                      placeholder="e.g. whenever the design change is verified, it may go live"
                      className="mt-0.5 w-full rounded border border-surface-line bg-surface-panel px-1.5 py-1 text-fg-strong"
                      data-fleet-relay-teach-explanation />
          </label>
          <p className="text-fg-muted">
            Saving answers the agent now and appends this rule to{' '}
            <span className="text-fg-strong">{detail.project ?? 'the project'}/.claude/rules/auto-answer-taught.md</span>,
            committed there and not pushed. Every agent of the project loads it, and the decider answers by it next
            time — an outward step too. A permission prompt is never answered by a rule.
          </p>
          <div className="flex items-center gap-2">
            <button type="button" onClick={save} disabled={busy || !answer.trim() || !detail.teach.allowed || !!result}
                    className="rounded border border-sky-400/50 px-2 text-sky-300 hover:bg-sky-400/10 disabled:opacity-40"
                    data-fleet-relay-teach-save>
              {busy ? 'saving…' : 'answer + teach'}
            </button>
            <button type="button" onClick={() => onMode('details')} className="text-fg-muted hover:text-fg-strong underline decoration-dotted">
              details
            </button>
          </div>
          {result && (
            <ul className={result.ok ? 'text-emerald-300' : 'text-amber-400'} data-fleet-relay-teach-result={result.ok ? 'ok' : 'partial'}>
              {result.lines.map(l => <li key={l}>{l}</li>)}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
