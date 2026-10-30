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
 * - **Two tabs, one window.** Now | Goals sit in the header row, which never changes size
 *   when the tab switches. A failure on the tab you are NOT looking at is marked on its
 *   label, so a hidden view can never look calm.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { ArrowUpRight, Check, CircleHelp, Clock, Lightbulb, Loader2, Moon, Plus, RefreshCw, Send, ShieldCheck, Target, TriangleAlert, UserPlus, Volume2, VolumeX, X } from 'lucide-react'
import VoiceInput from '../components/VoiceInput'
import { useSonioxAvailable } from '../hooks/useSonioxAvailable'
import {
  checkView, clockTime, emptyMessage, evidenceTarget, feedbackText, timeLine, fetchGoals, fetchNow, gapMarkers, goalFeedbackText, goalsFailure, goalsNotes,
  laterChoices, needsReasons, postAct, postFocus, postGoalAct, postGroups, progressPercent,
} from '../lib/nowCard'
import type { ActBody, Goal, GoalActBody, GoalAdvice, GoalsPayload, NowItem, NowPayload } from '../lib/nowCard'
import { createAudio, playCue } from '../lib/nowSound'
import { age } from '../lib/fleetAge'
import './now.css'

export const POLL_MS = 15_000
export const FEEDBACK_MS = 10_000
/** Goals change about daily: read them with the card's poll, but never more often than once a minute. */
export const GOALS_POLL_MS = Math.max(POLL_MS, 60_000)

type Tab = 'now' | 'goals'

type Overlay = null | 'later' | 'reasons' | 'focus' | 'idea' | 'tomorrow' | 'help' | 'notneeded'
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

const btn = 'inline-flex items-center gap-1.5 rounded-lg border border-surface-strong bg-surface-panel px-3 py-1.5 text-[15px] text-fg-strong shadow-sm hover:bg-surface-raised disabled:opacity-50'
const btnPrimary = 'inline-flex items-center gap-1.5 rounded-lg bg-status-done px-3.5 py-1.5 text-[15px] font-semibold text-white shadow-sm hover:opacity-90 disabled:opacity-50'
/** Secondary actions: quiet until hovered, so the answer buttons carry the weight. */
const btnGhost = 'inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-sm text-fg-normal hover:bg-surface-raised hover:text-fg-strong disabled:opacity-50'
const chip = 'inline-flex items-center gap-1 rounded-md px-1.5 py-0.5'
/** Header chips: tighter, because the header row also carries the Now | Goals tabs. */
const hchip = 'inline-flex items-center gap-1 rounded-md px-1 py-0.5'
const btnSmall = 'inline-flex items-center gap-1 rounded-md border border-surface-strong bg-surface-panel px-2 py-0.5 text-[13px] text-fg-strong hover:bg-surface-raised disabled:opacity-50'
const btnSmallPrimary = 'inline-flex items-center gap-1 rounded-md bg-status-done px-2 py-0.5 text-[13px] font-semibold text-white hover:opacity-90 disabled:opacity-50'
// A segmented control. Same padding, border and weight in both states: switching tabs must
// not resize the strip; only colour and the raised background change.
const tabBtn = (active: boolean) => 'inline-flex items-center gap-1 rounded-md px-2.5 py-0.5 text-[13px] font-semibold ' +
  (active ? 'bg-surface-panel text-fg-loud shadow-sm' : 'text-fg-muted hover:text-fg-strong')
const TONE: Record<'ok' | 'info' | 'warn', string> = {
  ok: 'text-status-active',
  info: 'text-fg-muted',
  warn: 'text-status-warn',
}

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
  // Now is the default on every load (spec): the tab is not remembered.
  const [tab, setTab] = useState<Tab>('now')
  const [goals, setGoals] = useState<GoalsPayload | null>(null)
  const [goalsError, setGoalsError] = useState<string | null>(null)
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

  const loadGoals = useCallback(async (refresh = false) => {
    try {
      setGoals(await fetchGoals(refresh))
      setGoalsError(null)
    } catch (e) {
      // The last good answer stays on screen; the failure is marked over it and on the tab.
      setGoalsError(e instanceof Error ? e.message : String(e))
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

  // Read on load, not on first opening the tab: the tab label carries the proposed count
  // and the failure marker, and both must be true while the Now tab is the one open.
  useEffect(() => {
    void loadGoals()
    const t = setInterval(() => { void loadGoals() }, GOALS_POLL_MS)
    return () => clearInterval(t)
  }, [loadGoals])

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

  /** A file is handed to the desktop (that route refuses what it must); anything else opens as a page. */
  const goThere = async (to: { kind: string; href: string }) => {
    if (to.kind !== 'file') { openHref(to.href); return }
    try {
      const res = await fetch('/api/desktop/open', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ path: to.href }),
      })
      if (!res.ok) {
        const body = await res.json().catch(() => null)
        setFeedback({ ok: false, text: `Could not open ${to.href}: ${String(body?.detail ?? `HTTP ${res.status}`)}` })
      }
    } catch (e) {
      setFeedback({ ok: false, text: `Could not open ${to.href}: ${String((e as Error)?.message ?? e)}` })
    }
  }

  const sendGoal = useCallback(async (body: GoalActBody) => {
    setBusy(true)
    try {
      const res = await postGoalAct(body)
      setFeedback({ ok: res.delivered, text: goalFeedbackText(body.action, res) })
      if (res.delivered) await loadGoals(true)
      return res
    } finally {
      setBusy(false)
    }
  }, [loadGoals])

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
  const goalsFail = goalsFailure(goals, goalsError)
  const nowFail = !!loadError || markers.some(m => m.tone === 'warn')
  const proposed = goals?.proposedCount ?? 0

  return (
    <div
      className="now-root relative flex h-screen flex-col overflow-hidden bg-surface-page text-fg-strong"
      // After the click, never at the press: anything enabling sound changes might move the
      // element under the cursor between press and release, and then the click is lost
      // (measured: a header that changed height swallowed every first click).
      onClickCapture={enableSound}
      data-now-root
    >
      {/* One line, always: a header that wraps changes height when a label changes, which
          moves everything below it under the reader's cursor. */}
      {/* The Now | Goals tabs share this row with the counters: at the launcher's 440 px the
          row is full, so the controls on the right are icon-only below `sm` (measured: with
          text labels the help button was clipped off the right edge). */}
      <header className="flex h-10 shrink-0 flex-nowrap items-center gap-1.5 overflow-hidden whitespace-nowrap border-b border-surface-line px-3 text-[13px] text-fg-muted">
        <div role="tablist" aria-label="View" className="mr-1 flex shrink-0 items-center gap-0.5 rounded-lg bg-surface-raised p-0.5" data-tabs>
          <button role="tab" aria-selected={tab === 'now'} className={tabBtn(tab === 'now')} onClick={() => setTab('now')} data-tab="now"
            title={nowFail ? 'The next card — something on it could not be read' : 'The next card: one thing to do now'}>
            Now
            {nowFail && <span className="text-status-warn" data-now-fail aria-label="Something on the card could not be read"><TriangleAlert size={12} /></span>}
          </button>
          <button role="tab" aria-selected={tab === 'goals'} className={tabBtn(tab === 'goals')} onClick={() => setTab('goals')} data-tab="goals"
            title={goalsFail ?? (proposed > 0 ? `${proposed} proposed goal${proposed > 1 ? 's' : ''} await your verdict` : 'The goals the work serves')}>
            Goals
            {proposed > 0 && (
              <span className="rounded-full bg-status-done px-1.5 text-[11px] font-semibold leading-4 text-white" data-goals-count>{proposed}</span>
            )}
            {goalsFail && <span className="text-status-fail" data-goals-fail aria-label="The goals could not be read"><TriangleAlert size={12} /></span>}
          </button>
        </div>
        <span className={hchip} title="Cards you closed today (Done, an answer, or Delegate)" data-closed>
          <Check size={14} /> {data?.closedToday ?? 0}<span className="hidden sm:inline"> closed</span>
        </span>
        <span className={hchip} title="Ideas you parked instead of starting them" data-parked>
          <Lightbulb size={14} /> {data?.parkedIdeas ?? 0}<span className="hidden sm:inline"> parked</span>
        </span>
        <span className="ml-auto" />
        <button className={hchip + ' hover:text-fg-strong'} onClick={() => setOverlay('focus')} aria-label="Today's focus projects" title="Today's focus projects — pick up to three; cards from other projects wait unless a deadline is near">
          <Target size={14} /> {data ? `${data.focus.length}/${data.focusMax}` : ''}<span className="hidden sm:inline"> focus</span>
        </button>
        <button className={hchip + ' hover:text-fg-strong'} onClick={() => setOverlay('idea')} aria-label="Park an idea" title="Park a new idea: it is written down and waits, instead of starting work now">
          <Plus size={10} className="-mr-1" /><Lightbulb size={14} /><span className="hidden sm:inline"> Park</span>
        </button>
        <span className={hchip} data-sound={soundOn ? 'on' : 'off'} title={soundOn ? 'Cues will play' : 'Click anywhere to enable cue sounds'}>
          {soundOn ? <Volume2 size={14} /> : <VolumeX size={14} />}<span className="hidden sm:inline">{soundOn ? ' Sound on' : ' Sound off'}</span>
        </span>
        <button className={hchip + ' hover:text-fg-strong'} onClick={() => setOverlay('help')} title="What is what on this card" aria-label="Help" data-help-open>
          <CircleHelp size={14} />
        </button>
      </header>

      {tab === 'now' && (markers.length > 0 || loadError) && (
        <div className="flex flex-wrap gap-1.5 px-3 pt-2 text-xs" data-markers>
          {loadError && <span className={chip + ' bg-status-fail/15 text-status-fail'}>Card could not load: {loadError}</span>}
          {markers.map(m => (
            <span key={m.text} className={chip + (m.tone === 'warn' ? ' bg-status-warn/15 text-status-warn' : ' bg-surface-raised text-fg-muted')}
              title={m.tone === 'warn' ? 'Something the card could not read or trust — what you see may be incomplete' : 'A known gap, not an error: this source is not set up yet'}>
              {m.text}
            </span>
          ))}
        </div>
      )}

      {tab === 'now' && data && !windDownView && (data.groups?.length ?? 0) > 1 && (
        <TagStrip groups={data.groups!} onChange={async muted => {
          setData(d => (d ? { ...d, groups: d.groups!.map(g => ({ ...g, muted: muted.includes(g.name) })) } : d))
          try { await postGroups(muted) } finally { void load() }
        }} />
      )}

      <main className="flex-1 overflow-y-auto px-3 pb-3 pt-2">
        {tab === 'goals' && (
          <GoalsView goals={goals} failure={goalsFail} busy={busy} onAct={b => void sendGoal(b)}
            onOpen={link => void goThere(evidenceTarget(link))} />
        )}

        {tab === 'now' && !data && !loadError && <p className="text-base text-fg-muted">Loading…</p>}

        {tab === 'now' && data && windDownView && (
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

        {tab === 'now' && data && !windDownView && (
          <>
            {data.tomorrowNote && (
              <p className="mb-2 border-l-2 border-status-done pl-2 text-sm text-fg-normal" data-tomorrow>
                From last night: {data.tomorrowNote}
              </p>
            )}
            {item ? (
              <article className="flex flex-col gap-2" data-now-item={item.id}>
                {item.project && (
                  <p className="self-start rounded-md bg-status-done/10 px-1.5 py-0.5 text-[11px] font-semibold uppercase tracking-wider text-status-done">
                    {item.project}
                  </p>
                )}
                <h1 className="text-[1.3rem] font-semibold leading-snug tracking-tight text-fg-loud">{item.sentence}</h1>
                {item.why && <p className="line-clamp-3 text-[15px] leading-relaxed text-fg-normal" title={item.why}>{item.why}</p>}
                <ItemMeta item={item} />
                <ItemTimes item={item} rankedAt={data.rankedAt} busy={busy}
                  onRecheck={has('recheck') ? () => void send({ action: 'recheck' }) : undefined}
                  onClose={has('done') ? (why: string) => void send({ action: 'done', text: `Not needed: ${why}` }) : undefined} />
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
                      <button key={o.id} className={btnPrimary} disabled={busy} title="Answer with this — it goes back to where the question came from"
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
                      placeholder="…or type your own answer (Enter sends)"
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
                    <button className={btn} disabled={busy || !text.trim()} aria-label="Send answer" title="Send your own answer to this card"
                      onClick={() => keep({ action: 'answer', text: text.trim() })}>
                      <Send size={16} />
                    </button>
                  </div>
                )}

                <div className="flex flex-wrap items-center gap-1" data-actions>
                  {has('done') && (
                    <button className={btn} disabled={busy} onClick={() => keep({ action: 'done' })} title="It is done — close the card; it will not come back">
                      <Check size={16} /> Done
                    </button>
                  )}
                  {has('goThere') && item.goThere && (
                    <button className={btnGhost} onClick={() => void goThere(item.goThere!)} title="Open where this came from — the agent, the project or the message">
                      <ArrowUpRight size={16} /> Go there
                    </button>
                  )}
                  {has('done') && (
                    <button className={btnGhost} disabled={busy} onClick={() => setOverlay('notneeded')}
                      title="Not needed (any more) — say why in one line; the card closes and the ranker learns from the reason" data-not-needed>
                      <X size={16} /> Not needed…
                    </button>
                  )}
                  {has('later') && (
                    <button className={btnGhost} disabled={busy} onClick={() => setOverlay('later')} title="Not now — bring it back later; nothing is sent">
                      <Clock size={16} /> Later
                    </button>
                  )}
                  {has('delegate') && (
                    <button className={btnGhost} disabled={busy} onClick={() => void send({ action: 'delegate' })} title="Hand it to a colleague">
                      <UserPlus size={16} /> Delegate
                    </button>
                  )}
                </div>

                </div>

                <p className="text-xs text-fg-muted" data-following>
                  {data.following > 0 ? `${data.following} more` : 'Nothing else after this'}
                  {data.heldBack > 0 && ` · ${data.heldBack} held back outside today's focus`}
                  {(data.mutedHidden ?? 0) > 0 && ` · ${data.mutedHidden} hidden by switched-off tags`}
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

            {overlay === 'help' && <HelpLegend />}
            {overlay === 'notneeded' && (
              <div className="flex flex-col gap-2" data-not-needed-form>
                <p className="text-base font-medium">Why is it not needed? One line — the ranker reads it.</p>
                <input autoFocus
                  className="rounded-md border border-surface-strong bg-surface-page px-2 py-1.5 text-base"
                  aria-label="Why not needed" placeholder="e.g. we moved the domain elsewhere"
                  value={overlayText} onChange={e => setOverlayText(e.target.value)}
                  onKeyDown={e => { if (e.key === 'Enter' && overlayText.trim()) { const t = overlayText.trim(); closeOverlay(); void send({ action: 'done', text: `Not needed: ${t}` }) } }} />
                <button className={btnPrimary + ' self-start'} disabled={!overlayText.trim() || busy}
                  onClick={() => { const t = overlayText.trim(); closeOverlay(); void send({ action: 'done', text: `Not needed: ${t}` }) }}>
                  Close it
                </button>
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
  return <p className="truncate text-[13px] text-fg-muted" data-meta title={parts.join(' · ')}>{parts.join(' · ')}</p>
}

/**
 * When the card was recommended and ranked — exact clock times, the owner's "pontos idő" —
 * and the "Still current?" check: a tap asks the publisher to verify this one item in the
 * background; the publisher bounds the cost and may refuse. A check that finds the premise
 * gone does not close the card: it says why and offers a one-tap close.
 */
function ItemTimes({ item, rankedAt, busy, onRecheck, onClose }: {
  item: NowItem
  rankedAt: string | null
  busy: boolean
  onRecheck?: () => void
  onClose?: (why: string) => void
}) {
  const times = timeLine(item, rankedAt)
  const view = checkView(item.check)
  const running = item.check?.state === 'running'
  if (!times && !view && !onRecheck) return null
  return (
    <div className="flex flex-col gap-1" data-times>
      <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[13px] text-fg-muted">
        {times && <span title="When this was first recommended, and when the list was last ranked (and every item re-checked)" data-time-line>{times}</span>}
        {onRecheck && !running && (
          <button className="inline-flex items-center gap-1 rounded-md px-1 text-status-done hover:bg-surface-raised disabled:opacity-50"
            disabled={busy} onClick={onRecheck} data-recheck
            title="Check in the background whether this is still current — sent mail, inbox, commits, the project's notes. Reused for 2 hours; a daily limit applies.">
            <RefreshCw size={13} /> Still current?
          </button>
        )}
      </div>
      {view && (
        <div className={'flex flex-col gap-1 rounded-md text-[13px] ' + (view.tone === 'warn' ? 'bg-status-warn/10 px-2 py-1.5' : '')} data-check={item.check?.state}>
          <p className={'inline-flex items-center gap-1 font-medium ' + TONE[view.tone]}>
            {running ? <Loader2 size={13} className="now-spin" /> : view.tone === 'ok' ? <ShieldCheck size={13} /> : view.tone === 'warn' ? <TriangleAlert size={13} /> : <RefreshCw size={13} />}
            {view.label}
          </p>
          {view.evidence && <p className="line-clamp-3 text-fg-normal" title={view.evidence} data-check-evidence>{view.evidence}</p>}
          {item.check?.state === 'stale' && onClose && (
            <button className={btnSmall + ' self-start'} disabled={busy} data-check-close
              onClick={() => onClose(`no longer current (checked ${clockTime(item.check?.at) ?? 'just now'})`)}>
              <X size={13} /> Close it — not needed
            </button>
          )}
        </div>
      )}
    </div>
  )
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

/** What every part of the card means — opened with "?", floats above the card. */
function HelpLegend() {
  const row = (term: string, text: string) => (
    <li key={term}><span className="font-medium text-fg-strong">{term}</span> — {text}</li>
  )
  return (
    <div className="flex max-h-[70vh] flex-col gap-2 overflow-y-auto pr-4" data-help>
      <p className="text-base font-medium">What is what</p>
      <ul className="flex flex-col gap-1.5 text-sm text-fg-normal">
        {row('The card', 'one thing to do next: the project, what to do, and why it is first.')}
        {row('Blue buttons', 'ready answers. One tap sends it back to where the question came from.')}
        {row('Text field', 'your own answer when no button fits. Enter or the arrow sends it the same way.')}
        {row('Go there', 'opens where the work is done: the agent in Fleet, or a link the card carries. Absent when there is no such place.')}
        {row('Done', 'it is finished; the card closes and will not come back.')}
        {row('Not needed…', 'it is moot (e.g. already handled, cancelled, moved) — write why in one line; it closes and the ranker learns from it.')}
        {row('Later', 'not now; pick when it should return. Nothing is sent anywhere.')}
        {row('Delegate', 'hand it to a colleague (shown only when someone else could do it).')}
        {row('recommended · ranked', 'exact times: when this card was first recommended, and when the list was last ranked (every ranking also re-checks each card).')}
        {row('Still current?', 'checks this one card in the background — sent mail, inbox, commits, the project\'s notes — and rewords it or says it is no longer current. A result is reused for 2 hours; a daily limit applies.')}
        {row('N more', 'how many cards follow; you only ever see one.')}
        {row('✓ closed', 'cards you closed today.')}
        {row('💡 parked / +💡 Park', 'write down a new idea so it waits instead of starting work now.')}
        {row('◎ focus', 'up to three projects for today; other cards wait unless a deadline is near.')}
        {row('Sound', 'a short tone when you switch projects and a new card is first. Click once to enable.')}
        {row('Grey note', 'a known gap, not an error (e.g. a source that is not set up yet).')}
        {row('Yellow note', 'something could not be read — the card may be incomplete.')}
        {row('Now | Goals', 'the two tabs: the next card, and the goals the work serves. A number on Goals counts proposed goals awaiting your verdict; a triangle on a tab means that view could not be read.')}
        {row('Unconfirmed', 'a goal the publisher proposed. Keep it, say it is not a goal, or rename it; Suggestions below are its advice on what the goals should be.')}
        {row('Moon view', 'after the evening hour: write tomorrow\'s first card, hand things to night agents, park projects.')}
      </ul>
    </div>
  )
}

/**
 * Project tags above the card: click one to switch it off (its cards stop coming up) or back on.
 * The counts stay visible on switched-off tags, so the filter never hides how much is there.
 */
function TagStrip({ groups, onChange }: {
  groups: { name: string; count: number; muted: boolean }[]
  onChange: (muted: string[]) => void
}) {
  const muted = groups.filter(g => g.muted).map(g => g.name)
  const toggle = (name: string) =>
    onChange(muted.includes(name) ? muted.filter(m => m !== name) : [...muted, name])
  return (
    // One row that scrolls sideways: two wrapped rows of tags took a third of the window's height.
    // The count of cards hidden by switched-off tags is stated under the card, so a tag
    // scrolled out of view never hides how much is there.
    <div className="now-tags flex shrink-0 flex-nowrap gap-1 overflow-x-auto whitespace-nowrap px-3 pb-0.5 pt-2 text-[11px]" data-tags>
      {muted.length > 0 && (
        <button onClick={() => onChange([])} className="shrink-0 rounded-full px-1.5 text-status-done hover:underline" title="Switch every tag back on" data-tags-all>
          all on
        </button>
      )}
      {groups.map(g => (
        <button key={g.name} onClick={() => toggle(g.name)} aria-pressed={!g.muted} data-tag={g.name}
          title={g.muted ? `${g.name}: switched off — its cards do not come up. Click to switch on.`
                         : `${g.name}: ${g.count} card(s). Click to switch off.`}
          className={'shrink-0 rounded-full border px-2 py-px ' + (g.muted
            ? 'border-surface-line text-fg-faint line-through'
            : 'border-surface-strong bg-surface-panel text-fg-strong hover:border-status-done/60')}>
          {g.name} <span className="font-semibold text-fg-muted">{g.count}</span>
        </button>
      ))}
    </div>
  )
}

/**
 * The Goals tab: the publisher's goals in its order, then its suggestions. Proposed goals
 * carry Keep / Not a goal / Rename; a confirmed goal only a small Not a goal. Every
 * incomplete-answer marker is a muted line at the top — never a reason to hide a goal.
 */
function GoalsView({ goals, failure, busy, onAct, onOpen }: {
  goals: GoalsPayload | null
  failure: string | null
  busy: boolean
  onAct: (body: GoalActBody) => void
  onOpen: (link: string) => void
}) {
  const [renaming, setRenaming] = useState<string | null>(null)
  const [draft, setDraft] = useState('')

  const failLine = failure && (
    <p className="flex items-start gap-1.5 rounded-lg bg-status-fail/10 px-2.5 py-1.5 text-[13px] text-status-fail" data-goals-error>
      <TriangleAlert size={14} className="mt-0.5 shrink-0" /> <span>{failure}</span>
    </p>
  )
  if (!goals) {
    // A failure with nothing to show yet fills the view, explained — not a red strip over white.
    return failLine
      ? <div className="flex h-full flex-col items-center justify-center gap-2 px-4 text-center" data-goals-empty>
          <TriangleAlert size={22} className="text-status-fail" />
          <p className="text-base font-semibold text-fg-loud">The goals could not be loaded</p>
          <p className="max-w-sm text-[13px] text-fg-muted" data-goals-error>{failure}</p>
        </div>
      : <p className="text-base text-fg-muted">Loading…</p>
  }
  if (goals.publisher.state === 'none') {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-1.5 px-4 text-center" data-goals-none>
        {failLine}
        <Target size={22} className="text-fg-faint" />
        <p className="text-base font-semibold text-fg-loud">No goals are published</p>
        {goals.reason && <p className="max-w-sm text-[13px] text-fg-muted">{goals.reason}</p>}
      </div>
    )
  }

  const notes = goals.measured ? goalsNotes(goals) : []
  const readOnly = goals.measured === true && !goals.acceptsVerdicts
  const startRename = (g: Goal) => { setRenaming(g.id); setDraft(g.title) }
  const submitRename = (g: Goal) => {
    const t = draft.trim()
    if (!t || t === g.title) return
    setRenaming(null)
    onAct({ id: g.id, action: 'rename', text: t })
  }
  const titleOf = (id?: string) => (id ? goals.goals.find(g => g.id === id)?.title : undefined)

  const synth = clockTime(goals.synthesizedAt)
  const confirmed = goals.goals.length - goals.proposedCount
  const KIND: Record<string, string> = {
    neglected: 'bg-status-warn/15 text-status-warn',
    reorder: 'bg-status-done/15 text-status-done',
    add: 'bg-status-active/15 text-status-active',
    drop: 'bg-status-fail/10 text-status-fail',
  }

  return (
    <section className="flex flex-col gap-2.5" data-goals-view>
      {failLine}
      <p className="text-xs text-fg-muted" data-goals-summary>
        {synth && <span title="When the publisher last synthesised the goals">synthesised {synth} · </span>}
        {goals.goals.length} goal{goals.goals.length === 1 ? '' : 's'}
        {goals.proposedCount > 0 ? ` · ${goals.proposedCount} to confirm` : ''}
        {confirmed > 0 && goals.proposedCount > 0 ? ` · ${confirmed} confirmed` : ''}
      </p>
      {notes.length > 0 && <p className="text-xs text-status-warn" data-goals-notes>{notes.join(' · ')}</p>}
      {readOnly && (
        <p className="text-xs text-fg-muted" data-goals-readonly>
          Read-only — the publisher declares no owner-goals-act command, so it accepts no verdicts.
        </p>
      )}
      {goals.measured && goals.goals.length === 0 && <p className="text-base text-fg-muted">The answer lists no goals.</p>}

      <ol className="flex flex-col gap-2">
        {goals.goals.map((g, i) => {
          const isProposed = g.status === 'proposed'
          const meta = [g.serves && `serves: ${g.serves}`, g.projects.length ? g.projects.join(', ') : null]
            .filter(Boolean).join(' · ')
          const pct = progressPercent(g.progress)
          return (
            <li key={g.id} data-goal={g.id} data-status={g.status}
              className={'flex flex-col gap-1 rounded-lg border bg-surface-panel px-2.5 py-2 ' +
                (isProposed ? 'border-dashed border-surface-strong' : 'border-surface-line')}>
              <div className="flex items-start gap-2">
                <span className="mt-0.5 w-4 shrink-0 text-right text-xs font-semibold text-fg-faint">{i + 1}</span>
                <div className="flex min-w-0 flex-1 flex-col gap-1">
                  <div className="flex flex-wrap items-baseline gap-x-1.5 gap-y-0.5">
                    <span className="text-[15px] font-semibold leading-snug text-fg-loud">{g.title}</span>
                    {isProposed && (
                      <span className="shrink-0 rounded-full border border-status-done/50 px-1.5 text-[10px] font-semibold uppercase tracking-wide text-status-done" data-unconfirmed
                        title="Proposed by the publisher — not confirmed by you yet">unconfirmed</span>
                    )}
                    {g.deadline && (
                      <span className="shrink-0 rounded-full bg-surface-raised px-1.5 text-[11px] text-fg-normal" title="Deadline">due {g.deadline}</span>
                    )}
                  </div>
                  {meta && <p className="truncate text-xs text-fg-muted" title={meta} data-goal-meta>{meta}</p>}
                  {g.why && <p className="line-clamp-2 text-[13px] leading-relaxed text-fg-normal" title={g.why}>{g.why}</p>}
                  {g.progress && (
                    <div className="flex flex-col gap-1" data-progress>
                      {pct != null && (
                        <div className="h-1.5 w-full overflow-hidden rounded-full bg-surface-raised" aria-hidden>
                          <div className="h-1.5 rounded-full bg-status-active" style={{ width: `${pct}%` }} />
                        </div>
                      )}
                      <p className="text-xs text-fg-normal">{g.progress.text}</p>
                    </div>
                  )}
                  {(g.evidence.length > 0 || g.openItems != null) && (
                    <div className="flex flex-wrap items-center gap-x-2.5 gap-y-0.5 text-xs" data-evidence>
                      {g.openItems != null && g.openItems > 0 && (
                        <span className="rounded-full bg-surface-raised px-1.5 text-fg-normal" title="Open cards on the Now tab that serve this goal" data-open-items>
                          {g.openItems} open card{g.openItems === 1 ? '' : 's'}
                        </span>
                      )}
                      {g.evidence.map((ev, k) => ev.link ? (
                        <button key={k} className="inline-flex items-center gap-0.5 text-status-done hover:underline" title={ev.link}
                          onClick={() => onOpen(ev.link!)}><ArrowUpRight size={11} />{ev.label}</button>
                      ) : (
                        <span key={k} className="text-fg-muted">{ev.label}</span>
                      ))}
                    </div>
                  )}
                  {goals.acceptsVerdicts && (renaming === g.id ? (
                    <div className="mt-0.5 flex items-center gap-1.5" data-rename>
                      <input autoFocus aria-label="New goal title"
                        className="min-w-0 flex-1 rounded-md border border-surface-strong bg-surface-page px-2 py-0.5 text-[13px] text-fg-strong"
                        value={draft} onChange={e => setDraft(e.target.value)}
                        onKeyDown={e => {
                          if (e.key === 'Enter') submitRename(g)
                          if (e.key === 'Escape') setRenaming(null)
                        }} />
                      <button className={btnSmallPrimary} disabled={busy || !draft.trim() || draft.trim() === g.title}
                        onClick={() => submitRename(g)} title="Send the new title (Enter)">Save</button>
                      <button className="text-fg-muted" aria-label="Cancel rename" onClick={() => setRenaming(null)}><X size={14} /></button>
                    </div>
                  ) : isProposed ? (
                    <div className="mt-0.5 flex flex-wrap gap-1.5" data-goal-actions>
                      <button className={btnSmallPrimary} disabled={busy} onClick={() => onAct({ id: g.id, action: 'keep' })}
                        title="Yes, this is a goal — confirm it">Keep</button>
                      <button className={btnSmall} disabled={busy} onClick={() => startRename(g)}
                        title="Keep it under a better title (Enter sends)">Rename</button>
                      <button className={btnSmall} disabled={busy} onClick={() => onAct({ id: g.id, action: 'drop' })}
                        title="This is not a goal — the publisher drops it">Not a goal</button>
                    </div>
                  ) : (
                    <button className="self-start text-[11px] text-fg-faint hover:text-fg-strong hover:underline" disabled={busy}
                      onClick={() => onAct({ id: g.id, action: 'drop' })} title="This is no longer a goal — the publisher drops it"
                      data-goal-drop>
                      Not a goal
                    </button>
                  ))}
                </div>
              </div>
            </li>
          )
        })}
      </ol>

      {goals.advice.length > 0 && (
        <section className="mt-1 flex flex-col gap-2" data-suggestions>
          <h2 className="text-xs font-semibold uppercase tracking-wider text-fg-muted">Suggestions — what the goals should be</h2>
          <ul className="flex flex-col gap-2">
            {goals.advice.map((a: GoalAdvice) => {
              const about = titleOf(a.goalId)
              return (
                <li key={a.id} className="flex flex-col gap-1 rounded-lg border border-surface-line bg-surface-raised/50 px-2.5 py-2" data-advice={a.id}>
                  <p className="text-[14px] leading-snug text-fg-loud">
                    <span className={'mr-1.5 rounded-full px-1.5 py-px align-[1px] text-[10px] font-semibold uppercase tracking-wide ' + (KIND[a.kind] ?? 'bg-surface-raised text-fg-muted')} data-kind>{a.kind}</span>
                    {a.sentence}
                  </p>
                  <p className="text-xs leading-relaxed text-fg-muted">{about ? `on "${about}" — ` : ''}{a.why}</p>
                  {goals.acceptsVerdicts && (
                    <div className="mt-0.5 flex gap-1.5">
                      <button className={btnSmallPrimary} disabled={busy} onClick={() => onAct({ id: a.id, action: 'accept' })}
                        title="Agree — the publisher applies this suggestion">Accept</button>
                      <button className={btnSmall} disabled={busy} onClick={() => onAct({ id: a.id, action: 'decline' })}
                        title="Disagree — the publisher keeps the goals as they are">Decline</button>
                    </div>
                  )}
                </li>
              )
            })}
          </ul>
        </section>
      )}
    </section>
  )
}
