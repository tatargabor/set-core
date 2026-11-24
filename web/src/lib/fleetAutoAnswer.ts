/**
 * Automatic answers on the fleet header — the pure half (fleet-auto-answer, D13).
 *
 * The decider (`set-auto-answer`) sits in front of the relay's outbound; the fleet shows
 * its switch, the proposals that will be written unless a person answers first, and the
 * newest decision-log records. Kept pure so the wording, the closed control's count and
 * the shape checks are tested without a screen.
 *
 * Two rules of the screen live here:
 * - **A pending proposal is counted where the reader stands** (ui-quality): it is a thing
 *   that will ACT, so its count rides on the closed control, and it is marked on the
 *   asking agent's tile.
 * - **Unread is not zero.** A route that failed shows as unread, never as "off, nothing
 *   pending", which is what calm looks like.
 */

import { useSyncExternalStore } from 'react'

export interface AutoReference {
  kind: 'operator' | 'file' | string
  quote: string
  path?: string
  decision?: boolean
  checked?: boolean | null
  reason?: string
}

export interface PendingProposal {
  id: string
  key: string
  session_id: string
  agent: string | null
  project: string | null
  kind: string | null
  question: string
  choice: string
  tier: string
  confidence: number | null
  references: AutoReference[]
  seconds_left: number | null
}

export interface AutoAnswerState {
  enabled: boolean
  wired: boolean
  forward: boolean
  window_s: number
  likely_min: number
  pending: PendingProposal[]
}

export interface DecisionRecord {
  ts: number
  id: string
  key: string
  session: string | null
  agent: string | null
  kind: string | null
  question: string
  choice: string | null
  tier: string | null
  confidence: number | null
  outcome: string | null
  reason: string
  human_answer: string | null
  references: AutoReference[]
}

const str = (v: unknown): string | null => (typeof v === 'string' ? v : null)
const num = (v: unknown): number | null => (typeof v === 'number' && Number.isFinite(v) ? v : null)

function refs(v: unknown): AutoReference[] {
  if (!Array.isArray(v)) return []
  return v.filter((r): r is AutoReference => !!r && typeof r === 'object' && typeof (r as AutoReference).quote === 'string')
}

/** The route's answer, or null when it is not the shape this control renders. */
export function parseAutoAnswerState(d: unknown): AutoAnswerState | null {
  if (!d || typeof d !== 'object') return null
  const o = d as Record<string, unknown>
  if (typeof o.enabled !== 'boolean' || !Array.isArray(o.pending)) return null
  const pending = (o.pending as unknown[]).flatMap(p => {
    if (!p || typeof p !== 'object') return []
    const r = p as Record<string, unknown>
    const id = str(r.id), session = str(r.session_id), choice = str(r.choice)
    if (!id || !session || choice === null) return []
    return [{
      id, key: str(r.key) ?? 'Q1', session_id: session, agent: str(r.agent), project: str(r.project),
      kind: str(r.kind), question: str(r.question) ?? '', choice, tier: str(r.tier) ?? '?',
      confidence: num(r.confidence), references: refs(r.references), seconds_left: num(r.seconds_left),
    }]
  })
  return {
    enabled: o.enabled,
    wired: o.wired === true,
    forward: o.forward === true,
    window_s: num(o.window_s) ?? 60,
    likely_min: num(o.likely_min) ?? 0.8,
    pending,
  }
}

export function parseDecisions(d: unknown): DecisionRecord[] | null {
  if (!d || typeof d !== 'object' || !Array.isArray((d as { decisions?: unknown }).decisions)) return null
  return ((d as { decisions: unknown[] }).decisions).flatMap(x => {
    if (!x || typeof x !== 'object') return []
    const r = x as Record<string, unknown>
    if (typeof r.id !== 'string') return []
    return [{
      ts: num(r.ts) ?? 0, id: r.id, key: str(r.key) ?? 'Q1', session: str(r.session), agent: str(r.agent),
      kind: str(r.kind),
      question: str(r.question) ?? '', choice: str(r.choice), tier: str(r.tier), confidence: num(r.confidence),
      outcome: str(r.outcome), reason: str(r.reason) ?? '', human_answer: str(r.human_answer),
      references: refs(r.references),
    }]
  })
}

export type AutoMode = 'unread' | 'off' | 'on' | 'on-not-wired'

/** `on-not-wired` is real: the switch is on but the relay's outbound is not the decider. */
export function autoMode(state: AutoAnswerState | null): AutoMode {
  if (!state) return 'unread'
  if (!state.enabled) return 'off'
  return state.wired ? 'on' : 'on-not-wired'
}

export function autoTitle(state: AutoAnswerState | null, error: string | null = null): string {
  const n = state?.pending.length ?? 0
  switch (autoMode(state)) {
    case 'unread':
      return error ? `Automatic answers unreadable: ${error}` : 'Automatic answers: reading…'
    case 'off':
      return 'Automatic answers off — every relayed question waits for you. Click for the panel.'
    case 'on-not-wired':
      return 'Automatic answers ON, but the question relay does not run set-auto-answer — nothing is decided. Click for how to wire it.'
    case 'on':
      return n > 0
        ? `Automatic answers ON — ${n} proposal(s) will be written unless you answer or cancel. Click for the panel.`
        : 'Automatic answers ON — proposals are written after the window unless you answer first. Click for the panel.'
  }
}

/** A tier as a reader sees it: `likely` carries its confidence, the others their meaning. */
export function tierLabel(tier: string | null, confidence: number | null): string {
  if (tier === 'likely') return confidence === null ? 'likely' : `likely ${confidence.toFixed(2)}`
  return tier ?? 'no decision'
}

/** The outcome in words, and its tone: what was WRITTEN is the loud one. */
export function outcomeLabel(outcome: string | null): { text: string; tone: 'loud' | 'warn' | 'muted' } {
  switch (outcome) {
    case 'written': return { text: 'written', tone: 'loud' }
    case 'overtaken': return { text: 'you answered', tone: 'muted' }
    case 'cancelled': return { text: 'cancelled', tone: 'muted' }
    case 'excluded': return { text: 'excluded — outward step', tone: 'warn' }
    case 'below-bar': return { text: 'below the bar', tone: 'muted' }
    case 'no-decision': return { text: 'no decision', tone: 'muted' }
    case 'forward-failed': return { text: 'forward failed — released', tone: 'warn' }
    case 'released': return { text: 'ended elsewhere', tone: 'muted' }
    default: return { text: outcome ?? '?', tone: 'muted' }
  }
}

/** Whether the proposal matched what the person actually answered (D14's live accuracy). */
export function matched(r: DecisionRecord): boolean | null {
  if (r.human_answer === null || r.choice === null) return null
  return r.human_answer.trim() === r.choice.trim()
}

export function countdown(seconds: number | null): string {
  if (seconds === null) return '?'
  const s = Math.max(0, Math.round(seconds))
  return s >= 60 ? `${Math.floor(s / 60)}m${String(s % 60).padStart(2, '0')}s` : `${s}s`
}

// --------------------------------------------------------------------------- //
// The pending proposals, shared with the agent tiles
// --------------------------------------------------------------------------- //

let pendingBySession: Record<string, PendingProposal> = {}
const listeners = new Set<() => void>()

/** Called by the header control after every read; the tiles subscribe. */
export function publishPending(pending: PendingProposal[]): void {
  const next: Record<string, PendingProposal> = {}
  for (const p of pending) if (!next[p.session_id]) next[p.session_id] = p
  const same = Object.keys(next).length === Object.keys(pendingBySession).length
    && Object.entries(next).every(([k, v]) => {
      const o = pendingBySession[k]
      return o && o.id === v.id && o.choice === v.choice && o.seconds_left === v.seconds_left
    })
  if (same) return
  pendingBySession = next
  listeners.forEach(l => l())
}

export function pendingFor(sessionId: string | null | undefined): PendingProposal | null {
  return sessionId ? pendingBySession[sessionId] ?? null : null
}

function subscribe(cb: () => void): () => void {
  listeners.add(cb)
  return () => { listeners.delete(cb) }
}

export function usePendingFor(sessionId: string | null | undefined): PendingProposal | null {
  return useSyncExternalStore(subscribe, () => pendingFor(sessionId), () => null)
}

// --------------------------------------------------------------------------- //
// The agents' names as the fleet shows them on their tiles
// --------------------------------------------------------------------------- //

/**
 * Asked for by the user (2026-11-24): the panel said `set-core · f7306bb0` — the project and
 * a session-id prefix — while the tile says `set-core-autop2` or `video-orulet`, so a row
 * could not be matched to a tile. The fleet publishes the name it renders on each tile; the
 * panel shows that, and falls back to the logged label only for a session that is gone.
 */
export interface AgentName {
  project: string | null
  label: string | null
  /** False when the session is no longer on the fleet and the name is the logged one. */
  live: boolean
}

let namesBySession: Record<string, { project: string | null; label: string | null }> = {}
const nameListeners = new Set<() => void>()

export function publishAgentNames(names: Record<string, { project: string | null; label: string | null }>): void {
  const keys = Object.keys(names)
  const same = keys.length === Object.keys(namesBySession).length
    && keys.every(k => namesBySession[k]?.project === names[k].project && namesBySession[k]?.label === names[k].label)
  if (same) return
  namesBySession = { ...names }
  nameListeners.forEach(l => l())
}

/** The tile's name for a session; else the logged `project · id` split, marked not live. */
export function agentName(sessionId: string | null | undefined, logged: string | null,
                          project: string | null = null): AgentName {
  const known = sessionId ? namesBySession[sessionId] : undefined
  if (known && known.label) return { project: known.project ?? project, label: known.label, live: true }
  const parts = (logged ?? '').split(' · ')
  if (parts.length >= 2) return { project: parts[0] || project, label: parts.slice(1).join(' · '), live: false }
  return { project, label: logged || null, live: false }
}

function subscribeNames(cb: () => void): () => void {
  nameListeners.add(cb)
  return () => { nameListeners.delete(cb) }
}

/** Re-renders the caller when any tile name changes. */
export function useAgentNames(): Record<string, { project: string | null; label: string | null }> {
  return useSyncExternalStore(subscribeNames, () => namesBySession, () => namesBySession)
}

/**
 * The question as a reader wants it. A continuation's text starts with the relay's own
 * header line (`✅ Finished, waiting for the next instruction — <agent>`), which repeats the
 * agent and says nothing about THIS question; the summary under it is the content.
 */
export function questionBody(kind: string | null, question: string): string {
  if (kind !== 'continuation') return question
  const lines = question.split('\n')
  const rest = lines[0].startsWith('✅') ? lines.slice(1) : lines
  return rest.filter(l => !/^Pick a suggestion or write what it should do next/.test(l)).join(' ').trim() || question
}

export function kindLabel(kind: string | null): string {
  switch (kind) {
    case 'continuation': return 'next step'
    case 'permission': return 'permission'
    case 'ask': return 'question'
    default: return kind ?? 'question'
  }
}

/** A continuation's suggestions already start with an arrow; the row draws its own. */
export function shownChoice(choice: string): string {
  return choice.replace(/^\s*(?:→|->)\s*/, '')
}
