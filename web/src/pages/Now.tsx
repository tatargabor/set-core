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
 * - **Three tabs, one window.** Now | Goals | Calls sit in the header row, which never changes size
 *   when the tab switches. A failure on the tab you are NOT looking at is marked on its
 *   label, so a hidden view can never look calm.
 * - **The card's own words follow `now.locale`** (nowI18n.ts, English by default). The
 *   publisher's text — sentences, why, options, outcomes, goals, advice — is shown as it
 *   arrives, never translated. The window title is never translated: bin/set-now finds it.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { ArrowUpRight, Check, CircleHelp, Clock, Flag, Hammer, Lightbulb, Loader2, Moon, Phone, Plus, RefreshCw, Send, ShieldCheck, Target, TriangleAlert, UserPlus, Volume2, VolumeX, X, Zap } from 'lucide-react'
import VoiceInput from '../components/VoiceInput'
import { useSonioxAvailable } from '../hooks/useSonioxAvailable'
import {
  callFeedbackText, callsCount, callsFailure, callsNotes, checkView, clockTime, dueLabel, fetchCalls, postCallAct, emptyMessage, evidenceTarget, feedbackText, timeLine, fetchGoals, fetchNow, gapMarkers, goalFeedbackText, goalsFailure, goalsNotes,
  laterChoices, matchProjects, needsReasons, progressChoices, postAct, postFocus, postGoalAct, postGroups, progressPercent,
} from '../lib/nowCard'
import type { ActBody, Call, CallActBody, CallsPayload, Goal, GoalActBody, GoalAdvice, GoalsPayload, NowItem, NowPayload } from '../lib/nowCard'
import { asLocale, makeT } from '../lib/nowI18n'
import type { Locale, MsgKey } from '../lib/nowI18n'
import { createAudio, playCue } from '../lib/nowSound'
import { age } from '../lib/fleetAge'
import './now.css'

export const POLL_MS = 15_000
export const FEEDBACK_MS = 10_000
/** Goals change about daily: read them with the card's poll, but never more often than once a minute. */
export const GOALS_POLL_MS = Math.max(POLL_MS, 60_000)

type Tab = 'now' | 'goals' | 'calls'

type Overlay = null | 'later' | 'reasons' | 'focus' | 'idea' | 'tomorrow' | 'help' | 'notneeded' | 'inprogress'
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

const btn = 'inline-flex items-center gap-1.5 rounded-lg border border-surface-strong bg-surface-panel px-3 py-1.5 text-base text-fg-strong shadow-sm hover:bg-surface-raised disabled:opacity-50'
const btnPrimary = 'inline-flex items-center gap-1.5 rounded-lg bg-status-done px-3.5 py-1.5 text-base font-semibold text-white shadow-sm hover:opacity-90 disabled:opacity-50'
/** Secondary actions: quiet until hovered, so the answer buttons carry the weight. */
const btnGhost = 'inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-sm text-fg-normal hover:bg-surface-raised hover:text-fg-strong disabled:opacity-50'
const chip = 'inline-flex items-center gap-1 rounded-md px-1.5 py-0.5'
/** Header chips: tighter, because the header row also carries the Now | Goals tabs. */
const hchip = 'inline-flex items-center gap-1 rounded-md px-1 py-0.5'
const btnSmall = 'inline-flex items-center gap-1 rounded-md border border-surface-strong bg-surface-panel px-2 py-0.5 text-sm text-fg-strong hover:bg-surface-raised disabled:opacity-50'
const btnSmallPrimary = 'inline-flex items-center gap-1 rounded-md bg-status-done px-2 py-0.5 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-50'
// A segmented control. Same padding, border and weight in both states: switching tabs must
// not resize the strip; only colour and the raised background change.
const tabBtn = (active: boolean) => 'inline-flex items-center gap-1 rounded-md px-2 py-0.5 sm:px-2.5 text-sm font-semibold ' +
  (active ? 'bg-surface-panel text-fg-loud shadow-sm' : 'text-fg-muted hover:text-fg-strong')
/** The advice kinds the contract names; an unknown kind is shown as the publisher wrote it. */
const KIND_LABEL: readonly string[] = ['add', 'drop', 'merge', 'reorder', 'neglected', 'other']
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
  const [progressNote, setProgressNote] = useState('')
  const [overlayText, setOverlayText] = useState('')
  const [soundOn, setSoundOn] = useState(false)
  const [showQueue, setShowQueue] = useState(false)
  // Now is the default on every load (spec): the tab is not remembered.
  const [tab, setTab] = useState<Tab>('now')
  const [goals, setGoals] = useState<GoalsPayload | null>(null)
  const [goalsError, setGoalsError] = useState<string | null>(null)
  const [calls, setCalls] = useState<CallsPayload | null>(null)
  const [callsError, setCallsError] = useState<string | null>(null)
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

  const loadCalls = useCallback(async (refresh = false) => {
    try {
      setCalls(await fetchCalls(refresh))
      setCallsError(null)
    } catch (e) {
      // As with goals: the last good list stays, the failure is marked over it and on the tab.
      setCallsError(e instanceof Error ? e.message : String(e))
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

  // Calls too are read on load: the tab label carries the count, the overdue tone and the failure marker.
  useEffect(() => {
    void loadCalls()
    const t = setInterval(() => { void loadCalls() }, GOALS_POLL_MS)
    return () => clearInterval(t)
  }, [loadCalls])

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
  // English until a payload says otherwise; either payload carries the same setting.
  const locale: Locale = asLocale(data?.locale ?? goals?.locale ?? calls?.locale)
  const t = useMemo(() => makeT(locale), [locale])
  const markers = useMemo(() => (data ? gapMarkers(data, locale) : []), [data, locale])

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
        ? t('feedback.closedToday', { n: res.closedToday }) : ''
      setFeedback({ ok: res.delivered, text: feedbackText(full.action, res, locale) + closed })
      if (res.delivered) { setText(''); await load() }
      return res
    } finally {
      setBusy(false)
    }
  }, [item, load, locale, t])

  /** A file is handed to the desktop (that route refuses what it must); anything else opens as a page. */
  const goThere = async (to: { kind: string; href: string }) => {
    if (to.kind !== 'file') { openHref(to.href); return }
    try {
      const res = await fetch('/api/desktop/open', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ path: to.href }),
      })
      if (!res.ok) {
        const body = await res.json().catch(() => null)
        setFeedback({ ok: false, text: t('feedback.openFailed', { path: to.href, detail: String(body?.detail ?? `HTTP ${res.status}`) }) })
      }
    } catch (e) {
      setFeedback({ ok: false, text: t('feedback.openFailed', { path: to.href, detail: String((e as Error)?.message ?? e) }) })
    }
  }

  const sendGoal = useCallback(async (body: GoalActBody) => {
    setBusy(true)
    try {
      const res = await postGoalAct(body)
      setFeedback({ ok: res.delivered, text: goalFeedbackText(body.action, res, locale) })
      if (res.delivered) await loadGoals(true)
      return res
    } finally {
      setBusy(false)
    }
  }, [loadGoals, locale])

  const sendCall = useCallback(async (body: CallActBody) => {
    setBusy(true)
    try {
      const res = await postCallAct(body)
      setFeedback({ ok: res.delivered, text: callFeedbackText(body.action, res, locale) })
      if (res.delivered) await loadCalls(true)
      return res
    } finally {
      setBusy(false)
    }
  }, [loadCalls, locale])

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
  const goalsFail = goalsFailure(goals, goalsError, locale)
  const nowFail = !!loadError || markers.some(m => m.tone === 'warn')
  const proposed = goals?.proposedCount ?? 0
  const callsFail = callsFailure(calls, callsError, locale)
  const callN = callsCount(calls)

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
      <header className="flex h-10 shrink-0 flex-nowrap items-center gap-1.5 overflow-hidden whitespace-nowrap border-b border-surface-line px-2 sm:px-3 text-sm text-fg-muted">
        <div role="tablist" aria-label={t('header.view')} className="mr-1 flex shrink-0 items-center gap-0.5 rounded-lg bg-surface-raised p-0.5" data-tabs>
          <button role="tab" aria-selected={tab === 'now'} className={tabBtn(tab === 'now')} onClick={() => setTab('now')} data-tab="now"
            title={nowFail ? t('tab.nowFailTitle') : t('tab.nowTitle')} aria-label={t('tab.now')}>
            {/* Below sm the three tabs are icons, so the one-line header still fits 440 px. */}
            <Zap size={14} className="sm:hidden" /><span className="hidden sm:inline">{t('tab.now')}</span>
            {nowFail && <span className="text-status-warn" data-now-fail aria-label={t('tab.nowFail')}><TriangleAlert size={12} /></span>}
          </button>
          <button role="tab" aria-selected={tab === 'goals'} className={tabBtn(tab === 'goals')} onClick={() => setTab('goals')} data-tab="goals"
            title={goalsFail ?? (proposed > 0 ? t('tab.goalsProposedTitle', { n: proposed }) : t('tab.goalsTitle'))} aria-label={t('tab.goals')}>
            <Flag size={14} className="sm:hidden" /><span className="hidden sm:inline">{t('tab.goals')}</span>
            {proposed > 0 && (
              <span className="rounded-full bg-status-done px-1.5 text-xs font-semibold leading-4 text-white" data-goals-count>{proposed}</span>
            )}
            {goalsFail && <span className="text-status-fail" data-goals-fail aria-label={t('tab.goalsFail')}><TriangleAlert size={12} /></span>}
          </button>
          <button role="tab" aria-selected={tab === 'calls'} className={tabBtn(tab === 'calls')} onClick={() => setTab('calls')} data-tab="calls"
            title={callsFail ?? (callN.overdue > 0 ? t('tab.callsOverdueTitle', { n: callN.open, overdue: callN.overdue })
              : callN.open > 0 ? t('tab.callsCountTitle', { n: callN.open }) : t('tab.callsTitle'))} aria-label={t('tab.calls')}>
            <Phone size={14} className="sm:hidden" /><span className="hidden sm:inline">{t('tab.calls')}</span>
            {callN.open > 0 && (
              <span className={'rounded-full px-1.5 text-xs font-semibold leading-4 text-white ' + (callN.overdue > 0 ? 'bg-status-fail' : 'bg-status-done')}
                data-calls-count data-overdue={callN.overdue > 0 ? 'yes' : 'no'}>{callN.open}</span>
            )}
            {callsFail && <span className="text-status-fail" data-calls-fail aria-label={t('tab.callsFail')}><TriangleAlert size={12} /></span>}
          </button>
        </div>
        <span className={hchip} title={t('header.closedTitle')} data-closed>
          <Check size={14} /> {data?.closedToday ?? 0}<span className="hidden sm:inline">{t('header.closed')}</span>
        </span>
        <span className={hchip} title={t('header.parkedTitle')} data-parked>
          <Lightbulb size={14} /> {data?.parkedIdeas ?? 0}<span className="hidden sm:inline">{t('header.parked')}</span>
        </span>
        <span className="ml-auto" />
        <button className={hchip + ' hover:text-fg-strong'} onClick={() => setOverlay('focus')} aria-label={t('header.focusLabel')} title={t('header.focusTitle')}>
          <Target size={14} /> {data ? `${data.focus.length}/${data.focusMax}` : ''}<span className="hidden sm:inline">{t('header.focus')}</span>
        </button>
        <button className={hchip + ' hover:text-fg-strong'} onClick={() => setOverlay('idea')} aria-label={t('header.parkLabel')} title={t('header.parkTitle')}>
          <Plus size={10} className="-mr-1" /><Lightbulb size={14} /><span className="hidden sm:inline">{t('header.park')}</span>
        </button>
        <span className={hchip} data-sound={soundOn ? 'on' : 'off'} title={soundOn ? t('header.soundOnTitle') : t('header.soundOffTitle')}>
          {soundOn ? <Volume2 size={14} /> : <VolumeX size={14} />}<span className="hidden sm:inline">{soundOn ? t('header.soundOn') : t('header.soundOff')}</span>
        </span>
        <button className={hchip + ' hover:text-fg-strong'} onClick={() => setOverlay('help')} title={t('header.helpTitle')} aria-label={t('header.help')} data-help-open>
          <CircleHelp size={14} />
        </button>
      </header>

      {tab === 'now' && (markers.length > 0 || loadError) && (
        <div className="flex flex-wrap gap-1.5 px-3 pt-2 text-xs" data-markers>
          {loadError && <span className={chip + ' bg-status-fail/15 text-status-fail'}>{t('marker.loadError', { error: loadError })}</span>}
          {markers.map(m => (
            <span key={m.text} className={chip + (m.tone === 'warn' ? ' bg-status-warn/15 text-status-warn' : ' bg-surface-raised text-fg-muted')}
              title={m.tone === 'warn' ? t('marker.warnTitle') : t('marker.infoTitle')}>
              {m.text}
            </span>
          ))}
        </div>
      )}

      {tab === 'now' && data && !windDownView && (data.groups?.length ?? 0) > 1 && (
        <TagStrip locale={locale} groups={data.groups!} onChange={async muted => {
          setData(d => (d ? { ...d, groups: d.groups!.map(g => ({ ...g, muted: muted.includes(g.name) })) } : d))
          try { await postGroups(muted) } finally { void load() }
        }} />
      )}

      <main className="flex-1 overflow-y-auto px-3 pb-3 pt-2">
        {tab === 'goals' && (
          <GoalsView locale={locale} goals={goals} failure={goalsFail} busy={busy} onAct={b => void sendGoal(b)}
            onOpen={link => void goThere(evidenceTarget(link))} />
        )}

        {tab === 'calls' && (
          <CallsView locale={locale} calls={calls} failure={callsFail} busy={busy} onAct={b => void sendCall(b)}
            onOpen={link => void goThere(evidenceTarget(link))} />
        )}

        {tab === 'now' && !data && !loadError && <p className="text-base text-fg-muted">{t('loading')}</p>}

        {tab === 'now' && data && windDownView && (
          <section className="flex flex-col gap-2" data-wind-down>
            <p className="flex items-center gap-2 text-lg text-fg-loud"><Moon size={18} /> {t('windDown.past', { hour: data.windDown.hour })}</p>
            <div className="flex flex-wrap gap-2">
              <button className={btn} onClick={() => setOverlay('tomorrow')}>{t('windDown.tomorrow')}</button>
              <button
                className={btn}
                disabled={busy || data.windDown.delegableIds.length === 0}
                onClick={async () => {
                  for (const id of data.windDown.delegableIds) {
                    await send({ id, source: 'owner-queue', action: 'wind-down-handoff' })
                  }
                }}
              >
                {t('windDown.handOff', { n: data.windDown.delegableIds.length })}
              </button>
              <button className={btn} onClick={() => setOverlay('focus')}>{t('windDown.park')}</button>
            </div>
            <button className="self-start text-sm text-fg-muted underline" onClick={() => setShowQueue(true)}>
              {t('windDown.showQueue')}
            </button>
          </section>
        )}

        {tab === 'now' && data && !windDownView && (
          <>
            {data.tomorrowNote && (
              <p className="mb-2 border-l-2 border-status-done pl-2 text-sm text-fg-normal" data-tomorrow>
                {t('card.fromLastNight', { note: data.tomorrowNote })}
              </p>
            )}
            {item ? (
              <article className="flex flex-col gap-2" data-now-item={item.id}>
                {item.project && (
                  <p className="self-start rounded-md bg-status-done/10 px-1.5 py-0.5 text-xs font-semibold uppercase tracking-wider text-status-done">
                    {item.project}
                  </p>
                )}
                <h1 className="text-[1.3rem] font-semibold leading-snug tracking-tight text-fg-loud">{item.sentence}</h1>
                {item.why && <p className="line-clamp-3 text-base leading-relaxed text-fg-normal" title={item.why}>{item.why}</p>}
                <ItemMeta item={item} locale={locale} />
                <ItemTimes item={item} rankedAt={data.rankedAt} busy={busy} locale={locale}
                  onRecheck={has('recheck') ? () => void send({ action: 'recheck' }) : undefined}
                  // What is SENT stays English in every locale: it is a message to the publisher
                  // (its ranker reads the "Not needed:" prefix), not a word on the card.
                  onClose={has('done') ? (why: string) => void send({ action: 'done', text: `Not needed: ${why}` }) : undefined} />
                {item.progressNote && (
                  <p className="border-l-2 border-status-warn pl-2 text-sm text-fg-normal" data-progress-note>{item.progressNote}</p>
                )}
                {item.resumeNote && (
                  <p className="border-l-2 border-status-done pl-2 text-sm text-fg-normal" data-resume-note>
                    {t('card.resume', { note: item.resumeNote })}
                  </p>
                )}

                {/* The answer is the card's point: pinned to the bottom so it is visible at the
                    launcher's window size however long the text above it is. */}
                <div className="sticky bottom-0 -mx-3 mt-1 flex flex-col gap-2 border-t border-surface-strong bg-surface-page px-3 pb-1 pt-2" data-answer-bar>
                {has('answer') && item.options.length > 0 && (
                  <div className="flex flex-wrap gap-2" data-options>
                    {item.options.map(o => (
                      <button key={o.id} className={btnPrimary} disabled={busy} title={t('card.optionTitle')}
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
                      placeholder={t('card.answerPlaceholder')}
                      aria-label={t('card.answerLabel')}
                      value={text}
                      onChange={e => setText(e.target.value)}
                      onKeyDown={e => { if (e.key === 'Enter' && text.trim()) keep({ action: 'answer', text: text.trim() }) }}
                    />
                    {voice && (
                      <span data-dictate>
                        <VoiceInput onTranscript={t => setText(prev => (prev ? `${prev} ${t}` : t))} onPartial={() => {}} disabled={busy} />
                      </span>
                    )}
                    <button className={btn} disabled={busy || !text.trim()} aria-label={t('card.sendLabel')} title={t('card.sendTitle')}
                      onClick={() => keep({ action: 'answer', text: text.trim() })}>
                      <Send size={16} />
                    </button>
                  </div>
                )}

                <div className="flex flex-wrap items-center gap-1" data-actions>
                  {has('done') && (
                    <button className={btn} disabled={busy} onClick={() => keep({ action: 'done' })} title={t('card.doneTitle')}>
                      <Check size={16} /> {t('card.done')}
                    </button>
                  )}
                  {has('goThere') && item.goThere && (
                    <button className={btnGhost} onClick={() => void goThere(item.goThere!)} title={t('card.goThereTitle')}>
                      <ArrowUpRight size={16} /> {t('card.goThere')}
                    </button>
                  )}
                  {has('done') && (
                    <button className={btnGhost} disabled={busy} onClick={() => setOverlay('notneeded')}
                      title={t('card.notNeededTitle')} data-not-needed>
                      <X size={16} /> {t('card.notNeeded')}
                    </button>
                  )}
                  {has('later') && (
                    <button className={btnGhost} disabled={busy} onClick={() => setOverlay('later')} title={t('card.laterTitle')}>
                      <Clock size={16} /> {t('card.later')}
                    </button>
                  )}
                  {has('inProgress') && (
                    <button className={btnGhost} disabled={busy} onClick={() => { setProgressNote(text.trim()); setOverlay('inprogress') }}
                      title={t('card.inProgressTitle')} data-in-progress>
                      <Hammer size={16} /> {t('card.inProgress')}
                    </button>
                  )}
                  {has('delegate') && (
                    <button className={btnGhost} disabled={busy} onClick={() => void send({ action: 'delegate' })} title={t('card.delegateTitle')}>
                      <UserPlus size={16} /> {t('card.delegate')}
                    </button>
                  )}
                </div>

                </div>

                <p className="text-xs text-fg-muted" data-following>
                  {data.following > 0 ? t('card.more', { n: data.following }) : t('card.nothingAfter')}
                  {data.heldBack > 0 && ` · ${t('card.heldBack', { n: data.heldBack })}`}
                  {(data.mutedHidden ?? 0) > 0 && ` · ${t('card.mutedHidden', { n: data.mutedHidden ?? 0 })}`}
                </p>
              </article>
            ) : (
              <div className="flex flex-col gap-1" data-empty>
                <p className="text-xl font-semibold text-fg-loud">{emptyMessage(data, locale)}</p>
                <p className="text-base text-fg-muted">{t('empty.closedToday', { n: data.closedToday })}</p>
                {data.heldBack > 0 && <p className="text-sm text-fg-muted">{t('card.heldBack', { n: data.heldBack })}</p>}
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
          <button aria-label={t('overlay.dismiss')} onClick={() => setFeedback(null)}><X size={16} /></button>
        </div>
      )}

      {overlay && (
        <div className="absolute inset-0 z-30 flex items-center justify-center bg-black/40 p-3" data-overlay={overlay}>
          <div className="relative w-full max-w-sm rounded-lg border border-surface-strong bg-surface-panel p-3 shadow-xl">
            <button className="absolute right-2 top-2 text-fg-muted" aria-label={t('overlay.close')} onClick={closeOverlay}><X size={16} /></button>

            {overlay === 'inprogress' && item && (
              // "I'm on it" is not an answer: nothing closes, the card comes back with the note.
              <div className="flex flex-col gap-2" data-in-progress-panel>
                <p className="text-base font-medium">{t('inProgress.prompt')}</p>
                <input autoFocus
                  className="rounded-md border border-surface-strong bg-surface-page px-2 py-1.5 text-base"
                  placeholder={t('inProgress.notePlaceholder')} aria-label={t('inProgress.noteLabel')}
                  value={progressNote} onChange={e => setProgressNote(e.target.value)} />
                <div className="flex flex-wrap gap-2">
                  {progressChoices(new Date(), locale).map(c => (
                    <button key={c.label} className={c.primary ? btnPrimary : btn} onClick={() => {
                      closeOverlay()
                      void send({ action: 'in-progress', text: progressNote.trim() || undefined, laterSeconds: c.seconds })
                      setText('')
                    }}>
                      {c.label}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {overlay === 'later' && item && (
              <div className="flex flex-col gap-2">
                <p className="text-base font-medium">{t('later.prompt')}</p>
                <div className="flex flex-wrap gap-2">
                  {laterChoices(new Date(), locale).map(c => (
                    <button key={c.label} className={btn} onClick={() => { closeOverlay(); void send({ action: 'later', laterSeconds: c.seconds }) }}>
                      {c.label}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {overlay === 'reasons' && pendingKeep && (
              <div className="flex flex-col gap-2">
                <p className="text-base font-medium">{t('reasons.prompt')}</p>
                {[0, 1].map(i => (
                  <input key={i}
                    className="rounded-md border border-surface-strong bg-surface-page px-2 py-1.5 text-base"
                    placeholder={i === 0 ? t('reasons.first') : t('reasons.second')}
                    aria-label={i === 0 ? t('reasons.first') : t('reasons.secondLabel')}
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
                    {t('reasons.keep')}
                  </button>
                  <button className={btn} disabled={busy} onClick={() => { closeOverlay(); void send({ action: 'delegate' }) }}>
                    {t('reasons.delegate')}
                  </button>
                </div>
              </div>
            )}

            {overlay === 'help' && <HelpLegend locale={locale} />}
            {overlay === 'notneeded' && (
              <div className="flex flex-col gap-2" data-not-needed-form>
                <p className="text-base font-medium">{t('notNeeded.prompt')}</p>
                <input autoFocus
                  className="rounded-md border border-surface-strong bg-surface-page px-2 py-1.5 text-base"
                  aria-label={t('notNeeded.label')} placeholder={t('notNeeded.placeholder')}
                  value={overlayText} onChange={e => setOverlayText(e.target.value)}
                  onKeyDown={e => { if (e.key === 'Enter' && overlayText.trim()) { const why = overlayText.trim(); closeOverlay(); void send({ action: 'done', text: `Not needed: ${why}` }) } }} />
                <button className={btnPrimary + ' self-start'} disabled={!overlayText.trim() || busy}
                  onClick={() => { const why = overlayText.trim(); closeOverlay(); void send({ action: 'done', text: `Not needed: ${why}` }) }}>
                  {t('notNeeded.close')}
                </button>
              </div>
            )}
            {(overlay === 'idea' || overlay === 'tomorrow') && (
              <div className="flex flex-col gap-2">
                <p className="text-base font-medium">{overlay === 'idea' ? t('idea.prompt') : t('tomorrow.prompt')}</p>
                <input
                  autoFocus
                  className="rounded-md border border-surface-strong bg-surface-page px-2 py-1.5 text-base"
                  aria-label={overlay === 'idea' ? t('idea.label') : t('tomorrow.prompt')}
                  value={overlayText}
                  onChange={e => setOverlayText(e.target.value)}
                />
                <button className={btnPrimary + ' self-start'} disabled={!overlayText.trim() || busy}
                  onClick={() => {
                    const typed = overlayText.trim()
                    const which = overlay
                    closeOverlay()
                    void send(which === 'idea'
                      ? { id: `idea-${Date.now()}`, source: 'owner-queue', action: 'park-idea', text: typed }
                      : { id: 'tomorrow', source: 'owner-queue', action: 'resume-note', text: typed })
                  }}>
                  {overlay === 'idea' ? t('idea.park') : t('tomorrow.save')}
                </button>
              </div>
            )}

            {overlay === 'focus' && data && (
              <FocusPicker data={data} locale={locale} onDone={async (fb) => { closeOverlay(); if (fb) setFeedback(fb); await load() }} />
            )}
          </div>
        </div>
      )}
    </div>
  )
}

function ItemMeta({ item, locale }: { item: NowItem; locale: Locale }) {
  const t = makeT(locale)
  const parts: string[] = []
  if (item.estimateMinutes != null) parts.push(t('meta.estimate', { n: item.estimateMinutes }))
  if (item.deadline) parts.push(t('meta.due', { date: item.deadline }))
  if (item.unblocks) parts.push(t('meta.unblocks', { what: item.unblocks }))
  const waited = sinceSeconds(item.since)
  if (waited != null) parts.push(t('meta.waiting', { age: age(waited) }))
  if (!parts.length) return null
  return <p className="truncate text-sm text-fg-muted" data-meta title={parts.join(' · ')}>{parts.join(' · ')}</p>
}

/**
 * When the card was recommended and ranked — exact clock times, the owner's "pontos idő" —
 * and the "Still current?" check: a tap asks the publisher to verify this one item in the
 * background; the publisher bounds the cost and may refuse. A check that finds the premise
 * gone does not close the card: it says why and offers a one-tap close.
 */
function ItemTimes({ item, rankedAt, busy, locale, onRecheck, onClose }: {
  item: NowItem
  rankedAt: string | null
  busy: boolean
  locale: Locale
  onRecheck?: () => void
  onClose?: (why: string) => void
}) {
  const t = makeT(locale)
  const times = timeLine(item, rankedAt, undefined, locale)
  const view = checkView(item.check, undefined, locale)
  const running = item.check?.state === 'running'
  if (!times && !view && !onRecheck) return null
  return (
    <div className="flex flex-col gap-1" data-times>
      <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-sm text-fg-muted">
        {times && <span title={t('times.title')} data-time-line>{times}</span>}
        {onRecheck && !running && (
          <button className="inline-flex items-center gap-1 rounded-md px-1 text-status-done hover:bg-surface-raised disabled:opacity-50"
            disabled={busy} onClick={onRecheck} data-recheck
            title={t('check.buttonTitle')}>
            <RefreshCw size={13} /> {t('check.button')}
          </button>
        )}
      </div>
      {view && (
        <div className={'flex flex-col gap-1 rounded-md text-sm ' + (view.tone === 'warn' ? 'bg-status-warn/10 px-2 py-1.5' : '')} data-check={item.check?.state}>
          <p className={'inline-flex items-center gap-1 font-medium ' + TONE[view.tone]}>
            {running ? <Loader2 size={13} className="now-spin" /> : view.tone === 'ok' ? <ShieldCheck size={13} /> : view.tone === 'warn' ? <TriangleAlert size={13} /> : <RefreshCw size={13} />}
            {view.label}
          </p>
          {view.evidence && <p className="line-clamp-3 text-fg-normal" title={view.evidence} data-check-evidence>{view.evidence}</p>}
          {item.check?.state === 'stale' && onClose && (
            <button className={btnSmall + ' self-start'} disabled={busy} data-check-close
              onClick={() => onClose(`no longer current (checked ${clockTime(item.check?.at) ?? 'just now'})`)}>
              <X size={13} /> {t('check.close')}
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
export function FocusPicker({ data, onDone, locale = 'en' }: { data: NowPayload; onDone: (feedback?: Feedback) => void | Promise<void>; locale?: Locale }) {
  const t = makeT(locale)
  const [draft, setDraft] = useState<string[]>(data.focus)
  const [query, setQuery] = useState('')
  const [swapFor, setSwapFor] = useState<string | null>(null)
  const [notesStep, setNotesStep] = useState(false)
  const [notes, setNotes] = useState<Record<string, string>>({})
  const [error, setError] = useState<string | null>(null)
  // The current focus, then a project just picked from the search (so it is in view, not at the
  // bottom of a scrolled list), then every project with a card.
  const names = useMemo(() => Array.from(new Set([...data.focus, ...draft, ...data.focusCandidates])), [data, draft])
  const others = useMemo(() => (data.focusOthers ?? []).filter(p => !names.includes(p)), [data, names])
  const found = matchProjects(query, others)
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
      if (!res.ok) { setError(res.reason ?? t('focus.notSaved')); return }
      const pub = res.publisher
      // The focus is saved either way; the toast says whether the publisher heard it too.
      await onDone(!pub ? undefined
        : pub.delivered ? { ok: true, text: pub.outcome || t('focus.saved') }
          : { ok: false, text: t('focus.notSent', { reason: pub.reason ?? '?' }) })
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }

  if (swapFor) {
    return (
      <div className="flex flex-col gap-2" data-swap>
        <p className="text-base font-medium">{t('focus.swap', { max: data.focusMax, project: swapFor })}</p>
        <div className="flex flex-wrap gap-2">
          {draft.map(p => (
            <button key={p} className={btn} onClick={() => { setDraft(draft.map(x => (x === p ? swapFor : x))); setSwapFor(null) }}>{p}</button>
          ))}
          <button className="text-sm text-fg-muted underline" onClick={() => setSwapFor(null)}>{t('focus.keepAsIs')}</button>
        </div>
      </div>
    )
  }

  if (notesStep) {
    return (
      <div className="flex flex-col gap-2" data-resume-notes>
        <p className="text-base font-medium">{t('focus.notesPrompt')}</p>
        {removed.map(p => (
          <input key={p}
            className="rounded-md border border-surface-strong bg-surface-page px-2 py-1.5 text-base"
            placeholder={t('focus.notePlaceholder', { project: p })}
            aria-label={t('focus.noteLabel', { project: p })}
            value={notes[p] ?? ''}
            onChange={e => setNotes({ ...notes, [p]: e.target.value })}
          />
        ))}
        {error && <p className="text-sm text-status-fail">{error}</p>}
        <button className={btnPrimary + ' self-start'} onClick={() => void save()}>{t('focus.save')}</button>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-2" data-focus-picker>
      <p className="text-base font-medium">{t('focus.title', { max: data.focusMax })}</p>
      <div className="flex max-h-40 flex-wrap gap-2 overflow-y-auto">
        {names.length === 0 && <p className="text-sm text-fg-muted">{t('focus.none')}</p>}
        {names.map(p => (
          <button key={p}
            className={draft.includes(p) ? btnPrimary : btn}
            aria-pressed={draft.includes(p)}
            onClick={() => toggle(p)}>
            {p}
          </button>
        ))}
      </div>
      {others.length > 0 && (
        <div className="flex flex-col gap-2" data-focus-search>
          <input
            className="rounded-md border border-surface-strong bg-surface-page px-2 py-1.5 text-base"
            placeholder={t('focus.searchPlaceholder')}
            aria-label={t('focus.searchLabel')}
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && found.length) { toggle(found[0]); setQuery('') } }}
          />
          {query.trim() !== '' && (
            <div className="flex flex-wrap gap-2">
              {found.length === 0 && <p className="text-sm text-fg-muted">{t('focus.noMatch', { query: query.trim() })}</p>}
              {found.map(p => (
                <button key={p} className={btn} onClick={() => { toggle(p); setQuery('') }}>+ {p}</button>
              ))}
            </div>
          )}
        </div>
      )}
      {error && <p className="text-sm text-status-fail">{error}</p>}
      <button className={btnPrimary + ' self-start'} onClick={() => void save()}>{t('focus.save')}</button>
    </div>
  )
}

/** The legend's rows, in order: each id names `help.<id>` (the term) and `help.<id>.text`. */
const HELP_ROWS = [
  'card', 'options', 'text', 'goThere', 'done', 'notNeeded', 'later', 'inProgress', 'delegate', 'times', 'check',
  'more', 'closed', 'parked', 'focus', 'sound', 'grey', 'yellow', 'tabs', 'unconfirmed', 'moon',
] as const

/** What every part of the card means — opened with "?", floats above the card. */
function HelpLegend({ locale }: { locale: Locale }) {
  const t = makeT(locale)
  return (
    <div className="flex max-h-[70vh] flex-col gap-2 overflow-y-auto pr-4" data-help>
      <p className="text-base font-medium">{t('help.title')}</p>
      <ul className="flex flex-col gap-1.5 text-sm text-fg-normal">
        {HELP_ROWS.map(id => (
          <li key={id}>
            <span className="font-medium text-fg-strong">{t(`help.${id}` as MsgKey)}</span> — {t(`help.${id}.text` as MsgKey)}
          </li>
        ))}
      </ul>
    </div>
  )
}

/**
 * Project tags above the card: click one to switch it off (its cards stop coming up) or back on.
 * The counts stay visible on switched-off tags, so the filter never hides how much is there.
 */
function TagStrip({ groups, onChange, locale }: {
  groups: { name: string; count: number; muted: boolean }[]
  onChange: (muted: string[]) => void
  locale: Locale
}) {
  const t = makeT(locale)
  const muted = groups.filter(g => g.muted).map(g => g.name)
  const toggle = (name: string) =>
    onChange(muted.includes(name) ? muted.filter(m => m !== name) : [...muted, name])
  return (
    // One row that scrolls sideways: two wrapped rows of tags took a third of the window's height.
    // The count of cards hidden by switched-off tags is stated under the card, so a tag
    // scrolled out of view never hides how much is there.
    <div className="now-tags flex shrink-0 flex-nowrap gap-1 overflow-x-auto whitespace-nowrap px-3 pb-0.5 pt-2 text-xs" data-tags>
      {muted.length > 0 && (
        <button onClick={() => onChange([])} className="shrink-0 rounded-full px-1.5 text-status-done hover:underline" title={t('tags.allOnTitle')} data-tags-all>
          {t('tags.allOn')}
        </button>
      )}
      {groups.map(g => (
        <button key={g.name} onClick={() => toggle(g.name)} aria-pressed={!g.muted} data-tag={g.name}
          title={g.muted ? t('tags.offTitle', { name: g.name })
                         : t('tags.onTitle', { name: g.name, n: g.count })}
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
function GoalsView({ goals, failure, busy, onAct, onOpen, locale }: {
  locale: Locale
  goals: GoalsPayload | null
  failure: string | null
  busy: boolean
  onAct: (body: GoalActBody) => void
  onOpen: (link: string) => void
}) {
  const [renaming, setRenaming] = useState<string | null>(null)
  const [draft, setDraft] = useState('')
  const t = makeT(locale)

  const failLine = failure && (
    <p className="flex items-start gap-1.5 rounded-lg bg-status-fail/10 px-2.5 py-1.5 text-sm text-status-fail" data-goals-error>
      <TriangleAlert size={14} className="mt-0.5 shrink-0" /> <span>{failure}</span>
    </p>
  )
  if (!goals) {
    // A failure with nothing to show yet fills the view, explained — not a red strip over white.
    return failLine
      ? <div className="flex h-full flex-col items-center justify-center gap-2 px-4 text-center" data-goals-empty>
          <TriangleAlert size={22} className="text-status-fail" />
          <p className="text-base font-semibold text-fg-loud">{t('goals.couldNotLoad')}</p>
          <p className="max-w-sm text-sm text-fg-muted" data-goals-error>{failure}</p>
        </div>
      : <p className="text-base text-fg-muted">{t('loading')}</p>
  }
  if (goals.publisher.state === 'none') {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-1.5 px-4 text-center" data-goals-none>
        {failLine}
        <Target size={22} className="text-fg-faint" />
        <p className="text-base font-semibold text-fg-loud">{t('goals.none')}</p>
        {goals.reason && <p className="max-w-sm text-sm text-fg-muted">{goals.reason}</p>}
      </div>
    )
  }

  const notes = goals.measured ? goalsNotes(goals, locale) : []
  const readOnly = goals.measured === true && !goals.acceptsVerdicts
  const startRename = (g: Goal) => { setRenaming(g.id); setDraft(g.title) }
  const submitRename = (g: Goal) => {
    const title = draft.trim()
    if (!title || title === g.title) return
    setRenaming(null)
    onAct({ id: g.id, action: 'rename', text: title })
  }
  const titleOf = (id?: string) => (id ? goals.goals.find(g => g.id === id)?.title : undefined)

  const synth = clockTime(goals.synthesizedAt, undefined, locale)
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
        {synth && <span title={t('goals.synthTitle')}>{t('goals.synth', { time: synth })}</span>}
        {t('goals.count', { n: goals.goals.length })}
        {goals.proposedCount > 0 ? t('goals.toConfirm', { n: goals.proposedCount }) : ''}
        {confirmed > 0 && goals.proposedCount > 0 ? t('goals.confirmed', { n: confirmed }) : ''}
      </p>
      {notes.length > 0 && <p className="text-xs text-status-warn" data-goals-notes>{notes.join(' · ')}</p>}
      {readOnly && (
        <p className="text-xs text-fg-muted" data-goals-readonly>
          {t('goals.readOnly')}
        </p>
      )}
      {goals.measured && goals.goals.length === 0 && <p className="text-base text-fg-muted">{t('goals.empty')}</p>}

      <ol className="flex flex-col gap-2">
        {goals.goals.map((g, i) => {
          const isProposed = g.status === 'proposed'
          const meta = [g.serves && t('goals.serves', { what: g.serves }), g.projects.length ? g.projects.join(', ') : null]
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
                    <span className="text-base font-semibold leading-snug text-fg-loud">{g.title}</span>
                    {isProposed && (
                      <span className="shrink-0 rounded-full border border-status-done/50 px-1.5 text-xs font-semibold uppercase tracking-wide text-status-done" data-unconfirmed
                        title={t('goals.unconfirmedTitle')}>{t('goals.unconfirmed')}</span>
                    )}
                    {g.deadline && (
                      <span className="shrink-0 rounded-full bg-surface-raised px-1.5 text-xs text-fg-normal" title={t('goals.deadline')}>{t('goals.due', { date: g.deadline })}</span>
                    )}
                  </div>
                  {meta && <p className="truncate text-xs text-fg-muted" title={meta} data-goal-meta>{meta}</p>}
                  {g.why && <p className="line-clamp-2 text-sm leading-relaxed text-fg-normal" title={g.why}>{g.why}</p>}
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
                        <span className="rounded-full bg-surface-raised px-1.5 text-fg-normal" title={t('goals.openCardsTitle')} data-open-items>
                          {t('goals.openCards', { n: g.openItems })}
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
                      <input autoFocus aria-label={t('goals.renameLabel')}
                        className="min-w-0 flex-1 rounded-md border border-surface-strong bg-surface-page px-2 py-0.5 text-sm text-fg-strong"
                        value={draft} onChange={e => setDraft(e.target.value)}
                        onKeyDown={e => {
                          if (e.key === 'Enter') submitRename(g)
                          if (e.key === 'Escape') setRenaming(null)
                        }} />
                      <button className={btnSmallPrimary} disabled={busy || !draft.trim() || draft.trim() === g.title}
                        onClick={() => submitRename(g)} title={t('goals.renameSaveTitle')}>{t('goals.renameSave')}</button>
                      <button className="text-fg-muted" aria-label={t('goals.renameCancel')} onClick={() => setRenaming(null)}><X size={14} /></button>
                    </div>
                  ) : isProposed ? (
                    <div className="mt-0.5 flex flex-wrap gap-1.5" data-goal-actions>
                      <button className={btnSmallPrimary} disabled={busy} onClick={() => onAct({ id: g.id, action: 'keep' })}
                        title={t('goals.keepTitle')}>{t('goals.keep')}</button>
                      <button className={btnSmall} disabled={busy} onClick={() => startRename(g)}
                        title={t('goals.renameTitle')}>{t('goals.rename')}</button>
                      <button className={btnSmall} disabled={busy} onClick={() => onAct({ id: g.id, action: 'drop' })}
                        title={t('goals.dropTitle')}>{t('goals.drop')}</button>
                    </div>
                  ) : (
                    <button className="self-start text-xs text-fg-faint hover:text-fg-strong hover:underline" disabled={busy}
                      onClick={() => onAct({ id: g.id, action: 'drop' })} title={t('goals.dropConfirmedTitle')}
                      data-goal-drop>
                      {t('goals.drop')}
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
          <h2 className="text-xs font-semibold uppercase tracking-wider text-fg-muted">{t('goals.suggestions')}</h2>
          <ul className="flex flex-col gap-2">
            {goals.advice.map((a: GoalAdvice) => {
              const about = titleOf(a.goalId)
              return (
                <li key={a.id} className="flex flex-col gap-1 rounded-lg border border-surface-line bg-surface-raised/50 px-2.5 py-2" data-advice={a.id}>
                  <p className="text-sm leading-snug text-fg-loud">
                    <span className={'mr-1.5 rounded-full px-1.5 py-px align-[1px] text-xs font-semibold uppercase tracking-wide ' + (KIND[a.kind] ?? 'bg-surface-raised text-fg-muted')} data-kind>{KIND_LABEL.includes(a.kind) ? t(`kind.${a.kind}` as MsgKey) : a.kind}</span>
                    {a.sentence}
                  </p>
                  <p className="text-xs leading-relaxed text-fg-muted">{about ? t('goals.about', { title: about }) : ''}{a.why}</p>
                  {goals.acceptsVerdicts && (
                    <div className="mt-0.5 flex gap-1.5">
                      <button className={btnSmallPrimary} disabled={busy} onClick={() => onAct({ id: a.id, action: 'accept' })}
                        title={t('goals.acceptTitle')}>{t('goals.accept')}</button>
                      <button className={btnSmall} disabled={busy} onClick={() => onAct({ id: a.id, action: 'decline' })}
                        title={t('goals.declineTitle')}>{t('goals.decline')}</button>
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

/**
 * The Calls tab: who to phone, in the publisher's order. Each call says who, why and what
 * kind (promised, again, missed, follow-up); an overdue due date is red. Called opens a
 * one-line note (optional, Enter sends); No answer brings it back later; Later hides it
 * until a chosen time; Not needed drops it.
 */
function CallsView({ calls, failure, busy, onAct, onOpen, locale }: {
  locale: Locale
  calls: CallsPayload | null
  failure: string | null
  busy: boolean
  onAct: (body: CallActBody) => void
  onOpen: (link: string) => void
}) {
  const [noting, setNoting] = useState<string | null>(null)
  const [note, setNote] = useState('')
  const [laterFor, setLaterFor] = useState<string | null>(null)
  const t = makeT(locale)

  const failLine = failure && (
    <p className="flex items-start gap-1.5 rounded-lg bg-status-fail/10 px-2.5 py-1.5 text-sm text-status-fail" data-calls-error>
      <TriangleAlert size={14} className="mt-0.5 shrink-0" /> <span>{failure}</span>
    </p>
  )
  if (!calls) {
    return failLine
      ? <div className="flex h-full flex-col items-center justify-center gap-2 px-4 text-center" data-calls-empty-fail>
          <TriangleAlert size={22} className="text-status-fail" />
          <p className="text-base font-semibold text-fg-loud">{t('calls.couldNotLoad')}</p>
          <p className="max-w-sm text-sm text-fg-muted" data-calls-error>{failure}</p>
        </div>
      : <p className="text-base text-fg-muted">{t('loading')}</p>
  }
  if (calls.publisher.state === 'none') {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-1.5 px-4 text-center" data-calls-none>
        {failLine}
        <Phone size={22} className="text-fg-faint" />
        <p className="text-base font-semibold text-fg-loud">{t('calls.none')}</p>
        {calls.reason && <p className="max-w-sm text-sm text-fg-muted">{calls.reason}</p>}
      </div>
    )
  }

  const notes = calls.measured ? callsNotes(calls, locale) : []
  const readOnly = calls.measured === true && !calls.acceptsActions
  const listed = clockTime(calls.rankedAt, undefined, locale)
  const sendNote = (c: Call) => {
    const text = note.trim()
    setNoting(null)
    setNote('')
    onAct(text ? { id: c.id, action: 'called', text } : { id: c.id, action: 'called' })
  }
  const KIND: Record<string, string> = {
    promised: 'bg-status-done/15 text-status-done',
    retry: 'bg-status-warn/15 text-status-warn',
    missed: 'bg-status-fail/10 text-status-fail',
    'follow-up': 'bg-surface-raised text-fg-normal',
  }

  return (
    <section className="flex flex-col gap-2.5" data-calls-view>
      {failLine}
      <p className="text-xs text-fg-muted" data-calls-summary>
        {listed && <span title={t('calls.listedTitle')}>{t('calls.listed', { time: listed })}</span>}
        {t('calls.count', { n: calls.calls.length })}
        {calls.overdueCount > 0 ? t('calls.overdueCount', { n: calls.overdueCount }) : ''}
      </p>
      {notes.length > 0 && <p className="text-xs text-status-warn" data-calls-notes>{notes.join(' · ')}</p>}
      {readOnly && <p className="text-xs text-fg-muted" data-calls-readonly>{t('calls.readOnly')}</p>}
      {calls.measured && calls.calls.length === 0 && (
        <div className="flex flex-col items-center gap-1.5 py-8 text-center" data-calls-empty>
          <Phone size={22} className="text-fg-faint" />
          <p className="text-base text-fg-muted">{t('calls.empty')}</p>
        </div>
      )}

      <ul className="flex flex-col gap-2">
        {calls.calls.map(c => {
          const kindKnown = (['promised', 'retry', 'missed', 'follow-up'] as string[]).includes(c.kind)
          const last = clockTime(c.lastAttempt, undefined, locale)
          return (
            <li key={c.id} data-call={c.id} data-kind={c.kind}
              className={'flex flex-col gap-1 rounded-lg border bg-surface-panel px-2.5 py-2 ' +
                (c.overdue ? 'border-status-fail/50' : 'border-surface-line')}>
              <div className="flex flex-wrap items-baseline gap-x-1.5 gap-y-0.5">
                <span className="text-base font-semibold leading-snug text-fg-loud" data-who>{c.who}</span>
                <span className={'shrink-0 rounded-full px-1.5 text-xs font-semibold uppercase tracking-wide ' + (KIND[c.kind] ?? 'bg-surface-raised text-fg-muted')}
                  title={kindKnown ? t(`calls.kindTitle.${c.kind}` as MsgKey) : undefined} data-call-kind>
                  {kindKnown ? t(`calls.kind.${c.kind}` as MsgKey) : c.kind}
                </span>
                {c.due && (
                  <span className={'shrink-0 rounded-full px-1.5 text-xs ' + (c.overdue ? 'bg-status-fail/15 font-semibold text-status-fail' : 'bg-surface-raised text-fg-normal')}
                    title={t('calls.dueTitle')} data-due data-overdue={c.overdue ? 'yes' : 'no'}>
                    {t(c.overdue ? 'calls.overdue' : 'calls.due', { date: dueLabel(c.due, undefined, locale) })}
                  </span>
                )}
              </div>
              <p className="text-sm leading-relaxed text-fg-normal" data-about>{c.about}</p>
              <div className="flex flex-wrap items-center gap-x-2.5 gap-y-0.5 text-xs">
                {c.phone && (
                  <a href={`tel:${c.phone.replace(/[^+\d]/g, '')}`} className="inline-flex items-center gap-1 font-semibold text-status-done hover:underline"
                    title={t('calls.phoneTitle')} data-phone><Phone size={12} />{c.phone}</a>
                )}
                {c.project && <span className="text-fg-muted">{c.project}</span>}
                {c.attempts != null && c.attempts > 0 && (
                  <span className="text-status-warn" data-attempts>{t('calls.attempts', { n: c.attempts })}{last ? t('calls.lastAttempt', { time: last }) : ''}</span>
                )}
                {c.evidence.map((ev, k) => ev.link ? (
                  <button key={k} className="inline-flex items-center gap-0.5 text-status-done hover:underline" title={ev.link}
                    onClick={() => onOpen(ev.link!)}><ArrowUpRight size={11} />{ev.label}</button>
                ) : (
                  <span key={k} className="text-fg-muted">{ev.label}</span>
                ))}
              </div>
              {calls.acceptsActions && (noting === c.id ? (
                <div className="mt-0.5 flex items-center gap-1.5" data-call-note>
                  <input autoFocus aria-label={t('calls.noteLabel')} placeholder={t('calls.notePlaceholder')}
                    className="min-w-0 flex-1 rounded-md border border-surface-strong bg-surface-page px-2 py-0.5 text-sm text-fg-strong"
                    value={note} onChange={e => setNote(e.target.value)}
                    onKeyDown={e => {
                      if (e.key === 'Enter') sendNote(c)
                      if (e.key === 'Escape') { setNoting(null); setNote('') }
                    }} />
                  <button className={btnSmallPrimary} disabled={busy} onClick={() => sendNote(c)}>{t('calls.noteSend')}</button>
                  <button className="text-fg-muted" aria-label={t('calls.noteCancel')} onClick={() => { setNoting(null); setNote('') }}><X size={14} /></button>
                </div>
              ) : laterFor === c.id ? (
                <div className="mt-0.5 flex flex-wrap items-center gap-1.5" data-call-later>
                  {laterChoices(new Date(), locale).map(ch => (
                    <button key={ch.label} className={btnSmall} disabled={busy}
                      onClick={() => { setLaterFor(null); onAct({ id: c.id, action: 'later', until: new Date(Date.now() + ch.seconds * 1000).toISOString() }) }}>
                      {ch.label}
                    </button>
                  ))}
                  <button className="text-fg-muted" aria-label={t('calls.noteCancel')} onClick={() => setLaterFor(null)}><X size={14} /></button>
                </div>
              ) : (
                <div className="mt-0.5 flex flex-wrap gap-1.5" data-call-actions>
                  <button className={btnSmallPrimary} disabled={busy} onClick={() => { setNoting(c.id); setNote('') }}
                    title={t('calls.calledTitle')}><Check size={12} />{t('calls.called')}</button>
                  <button className={btnSmall} disabled={busy} onClick={() => onAct({ id: c.id, action: 'no-answer' })}
                    title={t('calls.noAnswerTitle')}>{t('calls.noAnswer')}</button>
                  <button className={btnSmall} disabled={busy} onClick={() => setLaterFor(c.id)}
                    title={t('calls.laterTitle')}><Clock size={12} />{t('calls.later')}</button>
                  <button className={btnSmall} disabled={busy} onClick={() => onAct({ id: c.id, action: 'not-needed' })}
                    title={t('calls.notNeededTitle')}><X size={12} />{t('calls.notNeeded')}</button>
                </div>
              ))}
            </li>
          )
        })}
      </ul>
    </section>
  )
}
