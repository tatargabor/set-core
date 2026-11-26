/**
 * The relay board (fleet-relay-board): every waiting question in full, answered in place.
 *
 * Asked for by the owner (2026-11-26): „vszeg egyből kellene mutatni egy nagy ablakban
 * táblázatban hogy ne kelljen kattintani tudjak dönteni és jól olvasható legyen". One row
 * per question: who asks, the question with its line breaks, the options as controls, and
 * the decider's verdict with its reason. One click on an option of a single-question call
 * answers it as the operator's own answer — the same route the `answer…` overlay posts to.
 *
 * Teach is on the row too (owner, 2026-11-26: „teach is a táblázatos formátumban kellene nem
 * külön képernyő"): a checkbox and an optional condition beside the answer, and the same click
 * that answers also appends the rule to the project's `.claude/rules/auto-answer-taught.md`.
 *
 * The question text lives only in the decider's record (the relay record holds none, by
 * design), so the board reads each call's detail on the panel's own cadence.
 */

import { useCallback, useEffect, useRef, useState } from 'react'

import { age } from '../lib/fleetAge'
import { agentName, kindLabel } from '../lib/fleetAutoAnswer'
import { answerable, boardChoices, oneClick, readyToSend, verdictSentence } from '../lib/fleetRelayBoard'
import type { WaitingQuestion } from '../lib/fleetRelay'
import { canAlsoTeach, parseDetail, teachResultLines, type RelayDetail, type TeachResult } from '../lib/fleetRelayTeach'

const READ_INTERVAL_MS = 5_000

type Sent = { ok: boolean; text: string }

export default function FleetRelayBoard({ waiting, busy, onRelease, onAnswered }: {
  waiting: WaitingQuestion[]
  busy: boolean
  onRelease: (sessionId: string) => void
  onAnswered: () => void
}) {
  const [details, setDetails] = useState<Record<string, RelayDetail | string>>({})
  /** Per call: the pick or the typed text for each question, by index. */
  const [picks, setPicks] = useState<Record<string, string[]>>({})
  const [sent, setSent] = useState<Record<string, Sent>>({})
  const [sending, setSending] = useState<string | null>(null)
  /** Per call: teach the answer too, and the optional condition. */
  const [teach, setTeach] = useState<Record<string, boolean>>({})
  const [when, setWhen] = useState<Record<string, string>>({})
  const ids = waiting.map(w => w.id).filter((x): x is string => !!x)
  const idsKey = ids.join(' ')
  const live = useRef(true)

  const readAll = useCallback(() => {
    for (const id of idsKey ? idsKey.split(' ') : []) {
      fetch(`/api/fleet/question-relay/${encodeURIComponent(id)}/detail`)
        .then(async r => {
          const d = await r.json().catch(() => null)
          if (!r.ok) throw new Error(d?.detail ?? `HTTP ${r.status}`)
          const parsed = parseDetail(d)
          if (!parsed) throw new Error('unexpected answer shape')
          if (live.current) setDetails(m => ({ ...m, [id]: parsed }))
        })
        .catch(e => { if (live.current) setDetails(m => ({ ...m, [id]: String(e?.message ?? e) })) })
    }
  }, [idsKey])

  useEffect(() => {
    live.current = true
    readAll()
    const t = setInterval(readAll, READ_INTERVAL_MS)
    return () => { live.current = false; clearInterval(t) }
  }, [readAll])

  const send = (id: string, answers: string[], d: RelayDetail) => {
    setSending(id)
    const taught = !!teach[id] && canAlsoTeach(d) && answers.length === 1
    const url = `/api/fleet/question-relay/${encodeURIComponent(id)}/${taught ? 'teach' : 'answer'}`
    const body = taught ? { answer: answers[0], explanation: (when[id] ?? '').trim() } : { answers }
    fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
      .then(async r => {
        const res = await r.json().catch(() => null)
        if (!r.ok) throw new Error(res?.detail ?? `HTTP ${r.status}`)
        if (taught) {
          const t = teachResultLines(res as TeachResult)
          setSent(m => ({ ...m, [id]: { ok: t.ok, text: t.lines.join(' ') } }))
        } else {
          setSent(m => ({ ...m, [id]: { ok: true, text: `Sent: ${answers.map(a => `«${a}»`).join(', ')}` } }))
        }
        onAnswered()
      })
      .catch(e => setSent(m => ({ ...m, [id]: { ok: false, text: `Not sent: ${String(e?.message ?? e)}` } })))
      .finally(() => setSending(null))
  }

  const setPick = (id: string, i: number, v: string) =>
    setPicks(m => { const cur = [...(m[id] ?? [])]; cur[i] = v; return { ...m, [id]: cur } })

  if (waiting.length === 0) return <p className="mt-2 text-sm text-fg-muted">No question is waiting on the channel.</p>

  return (
    <table className="mt-2 w-full table-fixed border-collapse text-sm" data-fleet-relay-board>
      <colgroup>
        <col className="w-[13rem]" /><col /><col className="w-[30%]" /><col className="w-[22%]" />
      </colgroup>
      <thead className="sticky top-0 bg-surface-raised text-left text-xs text-fg-muted">
        <tr className="border-b border-surface-line">
          <th className="py-1 pr-2 font-normal">Agent</th>
          <th className="py-1 pr-2 font-normal">Question</th>
          <th className="py-1 pr-2 font-normal">Your answer</th>
          <th className="py-1 font-normal">Decider</th>
        </tr>
      </thead>
      <tbody>
        {waiting.map(w => {
          const n = agentName(w.session_id, w.project ? `${w.project} · ${w.session_id.slice(0, 8)}` : null, w.project)
          const raw = w.id ? details[w.id] : undefined
          const d = typeof raw === 'object' ? raw : null
          const qs = d?.decider?.questions ?? []
          const done = w.id ? sent[w.id] : undefined
          const canAnswer = !!d && answerable(d) && !done?.ok && !!w.id
          const single = !!d && oneClick(d)
          const rowPicks = (w.id && picks[w.id]) || []
          const agentCell = (
            <td rowSpan={Math.max(1, qs.length)} className="py-2 pr-2 align-top" data-fleet-relay-board-agent={w.session_id}>
              <div className="break-words">
                {n.project && <span className="text-fg-muted">{n.project} · </span>}
                <span className={n.live ? 'text-fg-loud font-semibold' : 'text-fg-strong'}>{n.label ?? 'unknown agent'}</span>
              </div>
              <div className="text-xs text-fg-muted">
                {kindLabel(w.kind === 'question' ? 'ask' : w.kind ?? 'ask')} · {age(w.seconds)}
              </div>
              <div className="mt-1 flex flex-wrap gap-x-2 text-xs">
                {w.release_requested
                  ? <span className="text-fg-muted">releasing…</span>
                  : (
                    <button type="button" disabled={busy} onClick={() => onRelease(w.session_id)}
                            className="underline decoration-dotted text-fg-muted hover:text-fg-strong"
                            title="Takes the question OFF the channel: it then waits at the agent's terminal. It answers nothing."
                            data-fleet-relay-release={w.session_id}>to terminal ↩</button>
                  )}
              </div>
            </td>
          )

          if (!d || qs.length === 0) {
            return (
              <tr key={w.session_id} className="border-b border-surface-line/60" data-fleet-relay-row={w.session_id}>
                {agentCell}
                <td colSpan={3} className="py-2 text-fg-muted">
                  {typeof raw === 'string'
                    ? <span className="text-red-400">Detail unreadable: {raw}</span>
                    : !w.id
                      ? 'This call has no relay id; read it on the channel or in the terminal.'
                      : !d
                        ? 'Reading…'
                        : w.kind === 'permission'
                          ? 'A permission prompt — Allow or Deny on the channel or in the terminal.'
                          : `The decider has no record of this call (${d.questions ?? '?'} question(s)), so its text is only on the channel or in the terminal.`}
                </td>
              </tr>
            )
          }

          return qs.map((q, i) => {
            const choices = boardChoices(q)
            const verdict = verdictSentence(q, d.decider?.seconds_left ?? null)
            const value = rowPicks[i] ?? ''
            const last = i === qs.length - 1
            return (
              <tr key={`${w.session_id}-${i}`} className={last ? 'border-b border-surface-line/60' : ''}
                  data-fleet-relay-row={i === 0 ? w.session_id : undefined} data-fleet-relay-board-question={q.key ?? i}>
                {i === 0 && agentCell}
                <td className="py-2 pr-3 align-top">
                  <div className="max-h-64 overflow-auto whitespace-pre-wrap break-words text-fg-loud leading-snug">{q.question}</div>
                </td>
                <td className="py-2 pr-3 align-top">
                  {canAnswer ? (
                    <div className="space-y-1.5">
                      {choices.length > 0 && (
                        <div className="flex flex-wrap gap-1.5">
                          {choices.map(c => (
                            <button key={c.value} type="button" disabled={sending === w.id}
                                    onClick={() => (single ? send(w.id as string, [c.value], d) : setPick(w.id as string, i, c.value))}
                                    className={`rounded border px-2 py-0.5 text-left ${
                                      value === c.value ? 'border-amber-400 bg-amber-400/15 text-amber-200'
                                        : c.proposed ? 'border-sky-400/70 text-sky-200 hover:bg-sky-400/10'
                                          : 'border-surface-line text-fg-strong hover:bg-surface-panel'}`}
                                    title={single ? `Answer with «${c.value}» now — the agent gets it at once` : 'Pick this answer'}
                                    data-fleet-relay-board-choice={c.proposed ? 'proposed' : 'option'}>
                              {c.label}{c.proposed && <span className="ml-1 text-xs text-sky-300/80">· proposed</span>}
                            </button>
                          ))}
                        </div>
                      )}
                      <input type="text" value={choices.some(c => c.value === value) ? '' : value}
                             onChange={e => setPick(w.id as string, i, e.target.value)}
                             onKeyDown={e => {
                               if (e.key === 'Enter' && single && e.currentTarget.value.trim()) send(w.id as string, [e.currentTarget.value.trim()], d)
                             }}
                             placeholder={single ? 'or type your own answer, Enter sends' : 'or type your own answer'}
                             className="w-full rounded border border-surface-line bg-surface-panel px-2 py-1 text-fg-strong placeholder:text-fg-ghost"
                             data-fleet-relay-board-text={i + 1} />
                      {single && (d.teach.allowed ? (
                        <div className="space-y-1" data-fleet-relay-board-teach={w.id}>
                          <label className="flex items-center gap-1.5 text-xs text-sky-300/90"
                                 title="The same click also appends the answer as a rule to the project's .claude/rules/auto-answer-taught.md, committed there (not pushed). Every agent and the decider follow it next time — an outward step too; never a permission prompt.">
                            <input type="checkbox" checked={!!teach[w.id as string]}
                                   onChange={e => setTeach(m => ({ ...m, [w.id as string]: e.target.checked }))}
                                   data-fleet-relay-board-teach-toggle={w.id} />
                            teach it too — answer like this next time
                          </label>
                          {teach[w.id as string] && (
                            <input type="text" value={when[w.id as string] ?? ''}
                                   onChange={e => setWhen(m => ({ ...m, [w.id as string]: e.target.value }))}
                                   placeholder="when / why (optional) — e.g. whenever the scan cleanup is done"
                                   className="w-full rounded border border-sky-400/40 bg-surface-panel px-2 py-1 text-fg-strong placeholder:text-fg-ghost"
                                   data-fleet-relay-board-teach-when={w.id} />
                          )}
                          {teach[w.id as string] && (
                            <p className="text-xs text-fg-muted">
                              Your click answers now and writes the rule to {d.project ?? 'the project'}/.claude/rules/auto-answer-taught.md.
                            </p>
                          )}
                        </div>
                      ) : d.teach.reason ? (
                        <p className="text-xs text-fg-ghost" data-fleet-relay-board-no-teach>teach: {d.teach.reason}</p>
                      ) : null)}
                      {!single && last && (
                        <button type="button" disabled={sending === w.id || !readyToSend(rowPicks, qs.length)}
                                onClick={() => send(w.id as string, rowPicks.slice(0, qs.length).map(p => p.trim()), d)}
                                className="rounded border border-amber-400/60 px-2 py-0.5 text-amber-300 hover:bg-amber-400/10 disabled:opacity-40"
                                data-fleet-relay-board-send={w.id}>
                          send all {qs.length} answers
                        </button>
                      )}
                    </div>
                  ) : last && done ? null : (
                    <span className="text-fg-muted">
                      {d.kind === 'permission' ? 'Allow or Deny on the channel or in the terminal.'
                        : d.release_requested ? 'Handed back to the terminal; answer it there.' : ''}
                    </span>
                  )}
                  {last && done && (
                    <p className={`mt-1 ${done.ok ? 'text-emerald-300' : 'text-amber-400'}`} data-fleet-relay-board-sent={done.ok ? 'ok' : 'failed'}>
                      {done.text}
                    </p>
                  )}
                </td>
                <td className={`py-2 align-top ${verdict.tone === 'due' ? 'text-amber-300' : verdict.tone === 'held' ? 'text-amber-200/80' : 'text-fg-muted'}`}
                    data-fleet-relay-auto={q.outcome ?? 'none'}>
                  {verdict.text}
                </td>
              </tr>
            )
          })
        })}
      </tbody>
    </table>
  )
}
