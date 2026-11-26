/**
 * The relay board (fleet-relay-board): every waiting question in full, answered in place.
 *
 * Asked for by the owner (2026-11-26): „vszeg egyből kellene mutatni egy nagy ablakban
 * táblázatban hogy ne kelljen kattintani tudjak dönteni és jól olvasható legyen". One row
 * per question: who asks, the question with its line breaks, the options as controls, and
 * the decider's verdict with its reason.
 *
 * Per question, three things the owner asked for the same evening:
 *  - an option pick;
 *  - a note written BESIDE the pick („a választás mellé … de csak felülírni tudom") — sent as
 *    "<option> — <note>", or alone as an own answer;
 *  - "teach" with an optional condition, on any question of the call, not only on a
 *    single-question one („itt első kérdésre akarnék teach-et", „teach is a táblázatos
 *    formátumban kellene nem külön képernyő").
 * A single-question call is sent by the option click itself (type the note and tick teach
 * first); a several-question call by "send all" once every question has an answer. Both go
 * through `…/answer`, which delivers the operator's answers and commits the ticked rules.
 *
 * The question text lives only in the decider's record (the relay record holds none, by
 * design), so the board reads each call's detail on the panel's own cadence.
 */

import { useCallback, useEffect, useRef, useState } from 'react'

import { age } from '../lib/fleetAge'
import { agentName, kindLabel } from '../lib/fleetAutoAnswer'
import {
  answerable, boardChoices, composeAnswer, oneClick, readyToSend, taughtLine, verdictSentence, type TaughtResult,
} from '../lib/fleetRelayBoard'
import type { WaitingQuestion } from '../lib/fleetRelay'
import { parseDetail, type RelayDetail } from '../lib/fleetRelayTeach'

const READ_INTERVAL_MS = 5_000

type Sent = { ok: boolean; lines: string[] }
/** Per call, per question index. */
type PerQ<T> = Record<string, Record<number, T>>

export default function FleetRelayBoard({ waiting, busy, onRelease, onAnswered }: {
  waiting: WaitingQuestion[]
  busy: boolean
  onRelease: (sessionId: string) => void
  onAnswered: () => void
}) {
  const [details, setDetails] = useState<Record<string, RelayDetail | string>>({})
  const [picks, setPicks] = useState<PerQ<string>>({})
  const [notes, setNotes] = useState<PerQ<string>>({})
  const [teach, setTeach] = useState<PerQ<boolean>>({})
  const [when, setWhen] = useState<PerQ<string>>({})
  const [sent, setSent] = useState<Record<string, Sent>>({})
  const [sending, setSending] = useState<string | null>(null)
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

  const setIn = <T,>(set: (f: (m: PerQ<T>) => PerQ<T>) => void, id: string, i: number, v: T) =>
    set(m => ({ ...m, [id]: { ...(m[id] ?? {}), [i]: v } }))

  /** Send every answer of one call, with the rules for the questions ticked "teach". */
  const send = (id: string, answers: string[], d: RelayDetail) => {
    const taught = d.teach.allowed
      ? answers.map((_, i) => i).filter(i => teach[id]?.[i]).map(i => ({ index: i, explanation: (when[id]?.[i] ?? '').trim() }))
      : []
    setSending(id)
    fetch(`/api/fleet/question-relay/${encodeURIComponent(id)}/answer`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ answers, teach: taught }),
    })
      .then(async r => {
        const res = await r.json().catch(() => null)
        if (!r.ok) throw new Error(res?.detail ?? `HTTP ${r.status}`)
        const lines = [`Sent: ${answers.map(a => `«${a}»`).join(', ')}`]
        const t = taughtLine(res?.teach as TaughtResult | null, taught.length)
        if (t) lines.push(t.text)
        setSent(m => ({ ...m, [id]: { ok: t ? t.ok : true, lines } }))
        onAnswered()
      })
      .catch(e => setSent(m => ({ ...m, [id]: { ok: false, lines: [`Not sent: ${String(e?.message ?? e)}`] } })))
      .finally(() => setSending(null))
  }

  if (waiting.length === 0) return <p className="mt-2 text-sm text-fg-muted">No question is waiting on the channel.</p>

  return (
    <table className="mt-2 w-full table-fixed border-collapse text-sm" data-fleet-relay-board>
      <colgroup>
        <col className="w-[13rem]" /><col /><col className="w-[32%]" /><col className="w-[21%]" />
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
          const id = w.id ?? ''
          const raw = id ? details[id] : undefined
          const d = typeof raw === 'object' ? raw : null
          const qs = d?.decider?.questions ?? []
          const done = id ? sent[id] : undefined
          const canAnswer = !!d && answerable(d) && !done?.ok && !!id
          const single = !!d && oneClick(d)
          const composed = qs.map((_, i) => composeAnswer(picks[id]?.[i], notes[id]?.[i]))
          const agentCell = (
            <td rowSpan={Math.max(1, qs.length)} className="py-2 pr-2 align-top" data-fleet-relay-board-agent={w.session_id}>
              <div className="break-words">
                {n.project && <span className="text-fg-muted">{n.project} · </span>}
                <span className={n.live ? 'text-fg-loud font-semibold' : 'text-fg-strong'}>{n.label ?? 'unknown agent'}</span>
              </div>
              <div className="text-xs text-fg-muted">
                {kindLabel(w.kind === 'question' ? 'ask' : w.kind ?? 'ask')} · {age(w.seconds)}
              </div>
              <div className="mt-1 text-xs">
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
                    : !id
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
            const pick = picks[id]?.[i]
            const note = notes[id]?.[i] ?? ''
            const teachOn = !!teach[id]?.[i]
            const last = i === qs.length - 1
            const choose = (value: string) => {
              if (single) send(id, [composeAnswer(value, note)], d)
              else setIn(setPicks, id, i, pick === value ? '' : value)
            }
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
                            <button key={c.value} type="button" disabled={sending === id}
                                    onClick={() => choose(c.value)}
                                    className={`rounded border px-2 py-0.5 text-left ${
                                      pick === c.value ? 'border-amber-400 bg-amber-400/15 text-amber-200'
                                        : c.proposed ? 'border-sky-400/70 text-sky-200 hover:bg-sky-400/10'
                                          : 'border-surface-line text-fg-strong hover:bg-surface-panel'}`}
                                    title={single
                                      ? `Answer with «${composeAnswer(c.value, note)}» now${teachOn ? ', and teach it' : ''} — the agent gets it at once`
                                      : 'Pick this answer (click again to unpick)'}
                                    data-fleet-relay-board-choice={c.proposed ? 'proposed' : 'option'}>
                              {c.label}{c.proposed && <span className="ml-1 text-xs text-sky-300/80">· proposed</span>}
                            </button>
                          ))}
                        </div>
                      )}
                      <input type="text" value={note}
                             onChange={e => setIn(setNotes, id, i, e.target.value)}
                             onKeyDown={e => {
                               if (e.key === 'Enter' && single && composeAnswer(pick, note)) send(id, [composeAnswer(pick, note)], d)
                             }}
                             placeholder={single
                               ? 'a note sent with the option you click — or your own answer, Enter sends'
                               : 'a note beside your pick — or your own answer'}
                             className="w-full rounded border border-surface-line bg-surface-panel px-2 py-1 text-fg-strong placeholder:text-fg-ghost"
                             data-fleet-relay-board-text={i + 1} />
                      {d.teach.allowed && (
                        <div className="space-y-1" data-fleet-relay-board-teach={`${id}#${i}`}>
                          <label className="flex items-center gap-1.5 text-xs text-sky-300/90"
                                 title="Also appends this answer as a rule to the project's .claude/rules/auto-answer-taught.md, committed there (not pushed). Every agent and the decider follow it next time — an outward step too; never a permission prompt.">
                            <input type="checkbox" checked={teachOn} onChange={e => setIn(setTeach, id, i, e.target.checked)}
                                   data-fleet-relay-board-teach-toggle={`${id}#${i}`} />
                            teach it too — answer like this next time
                          </label>
                          {teachOn && (
                            <input type="text" value={when[id]?.[i] ?? ''} onChange={e => setIn(setWhen, id, i, e.target.value)}
                                   placeholder="when / why (optional) — e.g. as long as there is no test user"
                                   className="w-full rounded border border-sky-400/40 bg-surface-panel px-2 py-1 text-fg-strong placeholder:text-fg-ghost"
                                   data-fleet-relay-board-teach-when={`${id}#${i}`} />
                          )}
                        </div>
                      )}
                      {!single && last && (
                        <button type="button" disabled={sending === id || !readyToSend(composed, qs.length)}
                                onClick={() => send(id, composed, d)}
                                className="rounded border border-amber-400/60 px-2 py-0.5 text-amber-300 hover:bg-amber-400/10 disabled:opacity-40"
                                data-fleet-relay-board-send={id}>
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
                    <ul className={`mt-1 ${done.ok ? 'text-emerald-300' : 'text-amber-400'}`} data-fleet-relay-board-sent={done.ok ? 'ok' : 'failed'}>
                      {done.lines.map(l => <li key={l}>{l}</li>)}
                    </ul>
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
