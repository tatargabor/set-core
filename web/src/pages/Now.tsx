/**
 * The Now window — one item at a time (openspec/changes/fleet-now-card).
 *
 * Opened by `bin/set-now` as a compact app window kept above other windows. No nav
 * chrome: the route sits outside GlobalLayout. Large type for a ~440×300 window.
 *
 * The rules the page holds, in the order they would be broken by a "tidy-up":
 *
 * - **One item, never a list.** Only the count of what follows is shown, never a title.
 * - **A gap is a fact on the card.** Unreadable sources, a partial queue, a stale ranking
 *   and slowed cues are markers that stay visible; the empty state says "nothing is
 *   waiting" only when every source was read.
 * - **Overlays float.** Pickers, prompts and the feedback toast are absolutely positioned
 *   and never move the card. Delivered feedback closes after 10 s; a failure stays.
 * - **Feedback names the outcome.** No streaks, points, or loss framing anywhere.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { ArrowUpRight, Check, Clock, Lightbulb, Moon, Send, Target, UserPlus, Volume2, VolumeX, X } from 'lucide-react'
import VoiceInput from '../components/VoiceInput'
import { useSonioxAvailable } from '../hooks/useSonioxAvailable'
import {
  emptyMessage, feedbackText, fetchNow, gapMarkers, laterChoices, needsReasons, postAct, postFocus,
} from '../lib/nowCard'
import type { ActBody, NowItem, NowPayload } from '../lib/nowCard'
import { createAudio, playCue } from '../lib/nowSound'
import { age } from '../lib/fleetAge'
import './now.css'

export const POLL_MS = 15_000
export const FEEDBACK_MS = 10_000

type Overlay = null | 'later' | 'reasons' | 'focus' | 'idea' | 'tomorrow'
interface Feedback { ok: boolean; text: string }
interface PendingKeep { action: 'done' | 'answer'; option?: string; text?: string }

function sinceSeconds(since: NowItem['since']): number | null {
  if (since == null) return null
  const t = typeof since === 'number' ? since * 1000 : Date.parse(since)
  return Number.isFinite(t) ? Math.max(0, (Date.now() - t) / 1000) : null
}

function openHref(href: string) {
  if (href.startsWith('/')) {
    window.open(`${window.location.origin}${href}`, 'set-fleet')
  } else {
    window.open(href, '_blank', 'noopener')
  }
}

const btn = 'inline-flex items-center gap-1.5 rounded-md border border-surface-strong bg-surface-panel px-3 py-1.5 text-base text-fg-strong hover:bg-surface-raised disabled:opacity-50'
const btnPrimary = 'inline-flex items-center gap-1.5 rounded-md bg-status-done px-3 py-1.5 text-base font-medium text-white hover:opacity-90 disabled:opacity-50'
const chip = 'inline-flex items-center gap-1 rounded px-1.5 py-0.5'

export default function Now() {
  const [data, setData] = useState<NowPayload | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [feedback, setFeedback] = useState<Feedback | null>(null)
  const [busy, setBusy] = useState(false)
  const [overlay, setOverlay] = useState<Overlay>(null)
  const [pendingKeep, setPendingKeep] = useState<PendingKeep | null>(null)
  const [reasons, setReasons] = useState<[string, string]>(['', ''])
  const [text, setText] = useState('')
  const [overlayText, setOverlayText] = useState('')
  const [soundOn, setSoundOn] = useState(false)
  const [showQueue, setShowQueue] = useState(false)
  const audioRef = useRef<AudioContext | null>(null)
  const { checked: voiceChecked, hasKey, micSupported } = useSonioxAvailable()
  const voice = voiceChecked && hasKey && micSupported

  const load = useCallback(async () => {
    try {
      setData(await fetchNow())
      setLoadError(null)
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : String(e))
    }
  }, [])

  // A fixed title: bin/set-now finds the window by it, and a window title is read by
  // other tools — it must never carry item text.
  useEffect(() => {
    const before = document.title
    document.title = 'Now · SET'
    return () => { document.title = before }
  }, [])

  useEffect(() => {
    void load()
    const t = setInterval(() => { void load() }, POLL_MS)
    return () => clearInterval(t)
  }, [load])

  // A cue plays only when the server decided one AND the owner enabled sound.
  useEffect(() => {
    if (data?.cue.play && audioRef.current) playCue(audioRef.current, data.cue.variant)
  }, [data?.generatedAt, data?.cue.play, data?.cue.variant])

  // Delivered feedback closes itself; a failure waits for the reader.
  useEffect(() => {
    if (!feedback?.ok) return
    const t = setTimeout(() => setFeedback(null), FEEDBACK_MS)
    return () => clearTimeout(t)
  }, [feedback])

  const enableSound = useCallback(() => {
    if (audioRef.current) return
    const ctx = createAudio()
    if (ctx) { audioRef.current = ctx; setSoundOn(true) }
  }, [])

  const item = data?.item ?? null
  const markers = useMemo(() => (data ? gapMarkers(data) : []), [data])

  const send = useCallback(async (body: Omit<ActBody, 'id' | 'source'> & Partial<Pick<ActBody, 'id' | 'source'>>) => {
    const target = item
    const full: ActBody = {
      id: body.id ?? target?.id ?? '',
      source: body.source ?? target?.source ?? 'owner-queue',
      sessionId: target?.sessionId ?? null,
      project: target?.project ?? null,
      ...body,
    } as ActBody
    setBusy(true)
    try {
      const res = await postAct(full)
      const closed = res.delivered && res.closedToday >= 0 && ['answer', 'done', 'delegate', 'wind-down-handoff'].includes(full.action)
        ? ` · ${res.closedToday} closed today` : ''
      setFeedback({ ok: res.delivered, text: feedbackText(full.action, res) + closed })
      if (res.delivered) { setText(''); await load() }
      return res
    } finally {
      setBusy(false)
    }
  }, [item, load])

  const keep = (k: PendingKeep) => {
    if (item && needsReasons(item, k.action)) {
      setPendingKeep(k)
      setReasons(['', ''])
      setOverlay('reasons')
      return
    }
    void send({ action: k.action, option: k.option, text: k.text })
  }

  const closeOverlay = () => { setOverlay(null); setOverlayText('') }

  // ----------------------------------------------------------------------- render

  const has = (a: string) => !!item?.actions.includes(a)
  const windDownView = !!data?.windDown.active && !showQueue

  return (
    <div
      className="now-root relative flex h-screen flex-col overflow-hidden bg-surface-page text-fg-strong"
      onPointerDown={enableSound}
      data-now-root
    >
      <header className="flex items-center gap-3 px-3 pt-2 text-sm text-fg-muted">
        <span className={chip} title="Closed today" data-closed>
          <Check size={14} /> {data?.closedToday ?? 0}
        </span>
        <span className={chip} title="Parked ideas" data-parked>
          <Lightbulb size={14} /> {data?.parkedIdeas ?? 0}
        </span>
        <span className="ml-auto" />
        <button className={chip + ' hover:text-fg-strong'} onClick={() => setOverlay('focus')} title="Today's focus projects">
          <Target size={14} /> {data ? `${data.focus.length}/${data.focusMax}` : ''}
        </button>
        <button className={chip + ' hover:text-fg-strong'} onClick={() => setOverlay('idea')} title="Park an idea">
          <Lightbulb size={14} /> Park
        </button>
        <span className={chip} data-sound={soundOn ? 'on' : 'off'} title={soundOn ? 'Cues will play' : 'Click anywhere to enable cue sounds'}>
          {soundOn ? <Volume2 size={14} /> : <VolumeX size={14} />} {soundOn ? 'Sound on' : 'Sound off'}
        </span>
      </header>

      {(markers.length > 0 || loadError) && (
        <div className="flex flex-wrap gap-1.5 px-3 pt-1.5 text-sm" data-markers>
          {loadError && <span className={chip + ' bg-status-fail/15 text-status-fail'}>Card could not load: {loadError}</span>}
          {markers.map(m => (
            <span key={m.text} className={chip + (m.tone === 'warn' ? ' bg-status-warn/15 text-status-warn' : ' bg-surface-raised text-fg-muted')}>
              {m.text}
            </span>
          ))}
        </div>
      )}

      <main className="flex-1 overflow-y-auto px-3 pb-3 pt-2">
        {!data && !loadError && <p className="text-base text-fg-muted">Loading…</p>}

        {data && windDownView && (
          <section className="flex flex-col gap-2" data-wind-down>
            <p className="flex items-center gap-2 text-lg text-fg-loud"><Moon size={18} /> It is past {data.windDown.hour}:00.</p>
            <div className="flex flex-wrap gap-2">
              <button className={btn} onClick={() => setOverlay('tomorrow')}>Write tomorrow's first card</button>
              <button
                className={btn}
                disabled={busy || data.windDown.delegableIds.length === 0}
                onClick={async () => {
                  for (const id of data.windDown.delegableIds) {
                    await send({ id, source: 'owner-queue', action: 'wind-down-handoff' })
                  }
                }}
              >
                Hand off {data.windDown.delegableIds.length} delegable
              </button>
              <button className={btn} onClick={() => setOverlay('focus')}>Park projects with notes</button>
            </div>
            <button className="self-start text-sm text-fg-muted underline" onClick={() => setShowQueue(true)}>
              Show the queue
            </button>
          </section>
        )}

        {data && !windDownView && (
          <>
            {data.tomorrowNote && (
              <p className="mb-2 border-l-2 border-status-done pl-2 text-sm text-fg-normal" data-tomorrow>
                From last night: {data.tomorrowNote}
              </p>
            )}
            {item ? (
              <article className="flex flex-col gap-2" data-now-item={item.id}>
                {item.project && <p className="text-sm uppercase tracking-wide text-fg-muted">{item.project}</p>}
                <h1 className="text-xl font-semibold leading-snug text-fg-loud">{item.sentence}</h1>
                {item.why && <p className="line-clamp-3 text-base text-fg-normal" title={item.why}>{item.why}</p>}
                <ItemMeta item={item} />
                {item.resumeNote && (
                  <p className="border-l-2 border-status-done pl-2 text-sm text-fg-normal" data-resume-note>
                    Resume: {item.resumeNote}
                  </p>
                )}

                {/* The answer is the card's point: pinned to the bottom so it is visible at the
                    launcher's window size however long the text above it is. */}
                <div className="sticky bottom-0 -mx-3 mt-1 flex flex-col gap-2 border-t border-surface-strong bg-surface-page px-3 pb-1 pt-2" data-answer-bar>
                {has('answer') && item.options.length > 0 && (
                  <div className="flex flex-wrap gap-2" data-options>
                    {item.options.map(o => (
                      <button key={o.id} className={btnPrimary} disabled={busy}
                        onClick={() => keep({ action: 'answer', option: o.id })}>
                        {o.label}
                      </button>
                    ))}
                  </div>
                )}

                {has('text') && (
                  <div className="flex items-center gap-2" data-text-answer>
                    <input
                      className="min-w-0 flex-1 rounded-md border border-surface-strong bg-surface-panel px-2 py-1.5 text-base text-fg-strong"
                      placeholder="Type an answer"
                      aria-label="Answer"
                      value={text}
                      onChange={e => setText(e.target.value)}
                      onKeyDown={e => { if (e.key === 'Enter' && text.trim()) keep({ action: 'answer', text: text.trim() }) }}
                    />
                    {voice && (
                      <span data-dictate>
                        <VoiceInput onTranscript={t => setText(prev => (prev ? `${prev} ${t}` : t))} onPartial={() => {}} disabled={busy} />
                      </span>
                    )}
                    <button className={btn} disabled={busy || !text.trim()} aria-label="Send answer"
                      onClick={() => keep({ action: 'answer', text: text.trim() })}>
                      <Send size={16} />
                    </button>
                  </div>
                )}

                <div className="flex flex-wrap gap-2" data-actions>
                  {has('goThere') && item.goThere && (
                    <button className={btn} onClick={() => openHref(item.goThere!.href)}>
                      <ArrowUpRight size={16} /> Go there
                    </button>
                  )}
                  {has('done') && (
                    <button className={btn} disabled={busy} onClick={() => keep({ action: 'done' })}>
                      <Check size={16} /> Done
                    </button>
                  )}
                  {has('later') && (
                    <button className={btn} disabled={busy} onClick={() => setOverlay('later')}>
                      <Clock size={16} /> Later
                    </button>
                  )}
                  {has('delegate') && (
                    <button className={btn} disabled={busy} onClick={() => void send({ action: 'delegate' })}>
                      <UserPlus size={16} /> Delegate
                    </button>
                  )}
                </div>

                </div>

                <p className="text-sm text-fg-muted" data-following>
                  {data.following > 0 ? `${data.following} more` : 'Nothing else after this'}
                  {data.heldBack > 0 && ` · ${data.heldBack} held back outside today's focus`}
                </p>
              </article>
            ) : (
              <div className="flex flex-col gap-1" data-empty>
                <p className="text-xl font-semibold text-fg-loud">{emptyMessage(data)}</p>
                <p className="text-base text-fg-muted">{data.closedToday} closed today.</p>
                {data.heldBack > 0 && <p className="text-sm text-fg-muted">{data.heldBack} held back outside today's focus</p>}
              </div>
            )}
          </>
        )}
      </main>

      {feedback && (
        <div
          role="status"
          data-feedback={feedback.ok ? 'ok' : 'fail'}
          className={'absolute inset-x-3 bottom-3 z-20 flex items-start gap-2 rounded-md px-3 py-2 text-base shadow-lg ' +
            (feedback.ok ? 'bg-surface-raised text-fg-loud' : 'bg-status-fail text-white')}
        >
          <span className="flex-1">{feedback.text}</span>
          <button aria-label="Dismiss" onClick={() => setFeedback(null)}><X size={16} /></button>
        </div>
      )}

      {overlay && (
        <div className="absolute inset-0 z-30 flex items-center justify-center bg-black/40 p-3" data-overlay={overlay}>
          <div className="relative w-full max-w-sm rounded-lg border border-surface-strong bg-surface-panel p-3 shadow-xl">
            <button className="absolute right-2 top-2 text-fg-muted" aria-label="Close" onClick={closeOverlay}><X size={16} /></button>

            {overlay === 'later' && item && (
              <div className="flex flex-col gap-2">
                <p className="text-base font-medium">Bring it back in…</p>
                <div className="flex flex-wrap gap-2">
                  {laterChoices(new Date()).map(c => (
                    <button key={c.label} className={btn} onClick={() => { closeOverlay(); void send({ action: 'later', laterSeconds: c.seconds }) }}>
                      {c.label}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {overlay === 'reasons' && pendingKeep && (
              <div className="flex flex-col gap-2">
                <p className="text-base font-medium">Could a colleague take this? Why keep it — one or two reasons.</p>
                {[0, 1].map(i => (
                  <input key={i}
                    className="rounded-md border border-surface-strong bg-surface-page px-2 py-1.5 text-base"
                    placeholder={i === 0 ? 'Reason' : 'Second reason (optional)'}
                    aria-label={i === 0 ? 'Reason' : 'Second reason'}
                    value={reasons[i]}
                    onChange={e => setReasons(r => (i === 0 ? [e.target.value, r[1]] : [r[0], e.target.value]))}
                  />
                ))}
                <div className="flex gap-2">
                  <button className={btnPrimary} disabled={!reasons[0].trim() || busy}
                    onClick={() => {
                      const rs = reasons.map(r => r.trim()).filter(Boolean)
                      closeOverlay()
                      void send({ action: pendingKeep.action, option: pendingKeep.option, text: pendingKeep.text, reasons: rs })
                    }}>
                    Keep it
                  </button>
                  <button className={btn} disabled={busy} onClick={() => { closeOverlay(); void send({ action: 'delegate' }) }}>
                    Delegate instead
                  </button>
                </div>
              </div>
            )}

            {(overlay === 'idea' || overlay === 'tomorrow') && (
              <div className="flex flex-col gap-2">
                <p className="text-base font-medium">{overlay === 'idea' ? 'Park an idea — it will wait, not start.' : "Tomorrow's first card"}</p>
                <input
                  autoFocus
                  className="rounded-md border border-surface-strong bg-surface-page px-2 py-1.5 text-base"
                  aria-label={overlay === 'idea' ? 'Idea' : "Tomorrow's first card"}
                  value={overlayText}
                  onChange={e => setOverlayText(e.target.value)}
                />
                <button className={btnPrimary + ' self-start'} disabled={!overlayText.trim() || busy}
                  onClick={() => {
                    const t = overlayText.trim()
                    const which = overlay
                    closeOverlay()
                    void send(which === 'idea'
                      ? { id: `idea-${Date.now()}`, source: 'owner-queue', action: 'park-idea', text: t }
                      : { id: 'tomorrow', source: 'owner-queue', action: 'resume-note', text: t })
                  }}>
                  {overlay === 'idea' ? 'Park it' : 'Save'}
                </button>
              </div>
            )}

            {overlay === 'focus' && data && (
              <FocusPicker data={data} onDone={async () => { closeOverlay(); await load() }} />
            )}
          </div>
        </div>
      )}
    </div>
  )
}

function ItemMeta({ item }: { item: NowItem }) {
  const parts: string[] = []
  if (item.estimateMinutes != null) parts.push(`~${item.estimateMinutes} min`)
  if (item.deadline) parts.push(`due ${item.deadline}`)
  if (item.unblocks) parts.push(`unblocks ${item.unblocks}`)
  const waited = sinceSeconds(item.since)
  if (waited != null) parts.push(`waiting ${age(waited)}`)
  if (!parts.length) return null
  return <p className="truncate text-sm text-fg-muted" data-meta title={parts.join(' · ')}>{parts.join(' · ')}</p>
}

/**
 * Today's focus: at most three. A fourth asks which one to swap out; a project
 * leaving the focus asks for a one-line resume note (optional).
 */
export function FocusPicker({ data, onDone }: { data: NowPayload; onDone: () => void | Promise<void> }) {
  const [draft, setDraft] = useState<string[]>(data.focus)
  const [swapFor, setSwapFor] = useState<string | null>(null)
  const [notesStep, setNotesStep] = useState(false)
  const [notes, setNotes] = useState<Record<string, string>>({})
  const [error, setError] = useState<string | null>(null)
  const names = useMemo(() => Array.from(new Set([...data.focus, ...data.focusCandidates])), [data])
  const removed = data.focus.filter(p => !draft.includes(p))

  const toggle = (p: string) => {
    if (draft.includes(p)) { setDraft(draft.filter(x => x !== p)); return }
    if (draft.length >= data.focusMax) { setSwapFor(p); return }
    setDraft([...draft, p])
  }

  const save = async () => {
    if (removed.length && !notesStep) { setNotesStep(true); return }
    try {
      const res = await postFocus(draft, notes)
      if (!res.ok) { setError(res.reason ?? 'not saved'); return }
      await onDone()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }

  if (swapFor) {
    return (
      <div className="flex flex-col gap-2" data-swap>
        <p className="text-base font-medium">{data.focusMax} focus projects already — swap out which one for {swapFor}?</p>
        <div className="flex flex-wrap gap-2">
          {draft.map(p => (
            <button key={p} className={btn} onClick={() => { setDraft(draft.map(x => (x === p ? swapFor : x))); setSwapFor(null) }}>{p}</button>
          ))}
          <button className="text-sm text-fg-muted underline" onClick={() => setSwapFor(null)}>Keep as is</button>
        </div>
      </div>
    )
  }

  if (notesStep) {
    return (
      <div className="flex flex-col gap-2" data-resume-notes>
        <p className="text-base font-medium">Where to pick it up again? One line each.</p>
        {removed.map(p => (
          <input key={p}
            className="rounded-md border border-surface-strong bg-surface-page px-2 py-1.5 text-base"
            placeholder={`${p} — next step`}
            aria-label={`Resume note for ${p}`}
            value={notes[p] ?? ''}
            onChange={e => setNotes({ ...notes, [p]: e.target.value })}
          />
        ))}
        {error && <p className="text-sm text-status-fail">{error}</p>}
        <button className={btnPrimary + ' self-start'} onClick={() => void save()}>Save focus</button>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-2" data-focus-picker>
      <p className="text-base font-medium">Today's focus — up to {data.focusMax}</p>
      <div className="flex max-h-40 flex-wrap gap-2 overflow-y-auto">
        {names.length === 0 && <p className="text-sm text-fg-muted">No project has an item right now.</p>}
        {names.map(p => (
          <button key={p}
            className={draft.includes(p) ? btnPrimary : btn}
            aria-pressed={draft.includes(p)}
            onClick={() => toggle(p)}>
            {p}
          </button>
        ))}
      </div>
      {error && <p className="text-sm text-status-fail">{error}</p>}
      <button className={btnPrimary + ' self-start'} onClick={() => void save()}>Save focus</button>
    </div>
  )
}
