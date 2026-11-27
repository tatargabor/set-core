/**
 * The question relay's Details and Teach — the pure half (fleet-relay-teach).
 *
 * Asked for by the owner (2026-11-24): a details control that shows what a waiting question
 * asks and what it waits for, and a teach control that answers it and records a project rule
 * — with a short explanation or condition — committed in the project so a teammate's agents
 * behave the same way. Kept pure so the prefill rule and the result wording are tested
 * without a screen.
 */

export interface DetailReference {
  kind: string | null
  quote: string | null
  path: string | null
}

export interface DetailQuestion {
  key: string | null
  question: string
  options: string[]
  outcome: string | null
  reason: string
  choice: string | null
  tier: string | null
  confidence: number | null
  references: DetailReference[]
}

export interface RelayDetail {
  id: string
  project: string | null
  kind: string
  questions: number | null
  seconds: number | null
  release_requested: boolean
  waits_for: 'answer' | 'countdown' | 'release' | string
  decider: { state: string | null; method: string | null; seconds_left: number | null; questions: DetailQuestion[] } | null
  teach: { allowed: boolean; reason: string; prefill: string }
}

export interface TeachResult {
  answered: boolean
  answer_reason: string
  written: boolean
  rules_file: string
  project: string
  commit: { sha: string; branch: string; reason: string }
}

const str = (v: unknown): string => (typeof v === 'string' ? v : '')
const strOrNull = (v: unknown): string | null => (typeof v === 'string' ? v : null)
const num = (v: unknown): number | null => (typeof v === 'number' && Number.isFinite(v) ? v : null)

export function parseDetail(d: unknown): RelayDetail | null {
  if (!d || typeof d !== 'object') return null
  const o = d as Record<string, unknown>
  if (typeof o.id !== 'string' || !o.teach || typeof o.teach !== 'object') return null
  const t = o.teach as Record<string, unknown>
  const dec = o.decider && typeof o.decider === 'object' ? (o.decider as Record<string, unknown>) : null
  return {
    id: o.id,
    project: strOrNull(o.project),
    kind: str(o.kind) || 'question',
    questions: num(o.questions),
    seconds: num(o.seconds),
    release_requested: o.release_requested === true,
    waits_for: str(o.waits_for) || 'answer',
    decider: dec ? {
      state: strOrNull(dec.state),
      method: strOrNull(dec.method),
      seconds_left: num(dec.seconds_left),
      questions: (Array.isArray(dec.questions) ? dec.questions : []).map((q: Record<string, unknown>) => ({
        key: strOrNull(q.key),
        question: str(q.question),
        options: Array.isArray(q.options) ? q.options.filter((x): x is string => typeof x === 'string') : [],
        outcome: strOrNull(q.outcome),
        reason: str(q.reason),
        choice: strOrNull(q.choice),
        tier: strOrNull(q.tier),
        confidence: num(q.confidence),
        references: (Array.isArray(q.references) ? q.references : []).map((r: Record<string, unknown>) => ({
          kind: strOrNull(r.kind), quote: strOrNull(r.quote), path: strOrNull(r.path),
        })),
      })),
    } : null,
    teach: { allowed: t.allowed === true, reason: str(t.reason), prefill: str(t.prefill) },
  }
}

/** The answer field starts with the decider's proposal, else the agent's recommended option. */
export function prefillAnswer(d: RelayDetail): string {
  if (d.teach.prefill.trim()) return d.teach.prefill.replace(/^\s*(?:→|->)\s*/, '')
  const opts = d.decider?.questions[0]?.options ?? []
  return opts.find(o => /\(recommended\)/i.test(o)) ?? ''
}

/** What the call is waiting for, in one sentence. */
export function waitsForText(d: RelayDetail): string {
  if (d.waits_for === 'release') return 'Handed back to the terminal — it waits for an answer typed there.'
  if (d.waits_for === 'countdown') {
    const s = d.decider?.seconds_left
    return `The decider writes its proposal in ${s === null || s === undefined ? '?' : Math.round(s)}s unless you answer first.`
  }
  if (d.kind === 'permission') return 'Waits for your Allow or Deny — on the relay board, the channel or the terminal; a permission prompt is answered only by a person.'
  return 'Waits for your answer on the channel (or in the agent\'s terminal after "to terminal ↩").'
}

/** Each step of a save, as the overlay reports it; `ok` is false when anything failed. */
export function teachResultLines(r: TeachResult): { lines: string[]; ok: boolean } {
  const lines: string[] = []
  lines.push(r.answered ? 'Answered — the agent has it.' : `Not answered: ${r.answer_reason || 'unknown reason'}`)
  if (!r.written) lines.push(`Rule not written: ${r.commit.reason || 'unknown reason'}`)
  else if (r.commit.sha) lines.push(`Rule committed in ${r.project} (${r.commit.branch}) as ${r.commit.sha} — ${r.rules_file}. Not pushed.`)
  else lines.push(`Rule written to ${r.project}/${r.rules_file}, not committed: ${r.commit.reason || 'unknown reason'}`)
  const answeredOrGone = r.answered || /no longer waiting/.test(r.answer_reason)
  return { lines, ok: answeredOrGone && r.written && !!r.commit.sha }
}

// --------------------------------------------------------------------------- own answer (fleet-relay-answer-own)

/** How many answer fields the call needs: the decider's question list, else the relay's count. */
export function answerFieldCount(d: RelayDetail): number {
  const fromDecider = d.decider?.questions.length ?? 0
  if (fromDecider > 0) return fromDecider
  return d.questions !== null && d.questions > 0 ? d.questions : 1
}

/** Whether the own-answer overlay is offered at all, and why not. */
export function ownAnswerBlocked(d: RelayDetail): string | null {
  if (d.kind === 'permission') return 'A permission prompt is answered with Allow or Deny — on the relay board, the channel or the terminal.'
  if (d.release_requested) return 'It was handed back to the terminal; answer it there.'
  return null
}

/** Send is offered only when every field holds something. */
export function canSendOwn(fields: string[], count: number): boolean {
  return fields.length === count && fields.every(f => f.trim().length > 0)
}

/** "Also teach it" needs one question and the teach route's own permission. */
export function canAlsoTeach(d: RelayDetail): boolean {
  return d.teach.allowed && answerFieldCount(d) === 1
}
