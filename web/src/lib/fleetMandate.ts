/**
 * The mandate on the tile and in the start form — as decisions, not as JSX.
 *
 * A mandate is the recorded reason an agent was started: a goal, optionally a
 * scope and a closing condition, and who asked. This file decides what a
 * surface may SAY about it, and three of those decisions are the content:
 *
 *  - **No mandate is three different facts.** Nobody declared one; the agent
 *    was opened by hand and the framework never had the chance to record one;
 *    or the store could not be read. The third is not an absence at all, and a
 *    tile that drew it as "no mandate" would report an outage as an agent with
 *    no purpose.
 *  - **A label is never read as a goal.** `fix-the-login-bug` is a name
 *    somebody typed. Nothing here looks at it.
 *  - **Scope protection is an instruction.** The agent is TOLD to decline
 *    requests outside its mandate. Nothing enforces that, so no sentence on the
 *    screen may say "blocked", "cannot" or "prevented".
 */

import type { FleetAgent, FleetMandate } from './fleetTypes'

export type MandateStanding =
  /** The payload carries neither field — a build that predates mandates. */
  | { kind: 'unreported' }
  | {
      kind: 'held'
      /** `work` or `desk`, verbatim. */
      badge: string
      goal: string
      /** Whether the agent's own session-start hook has read the record. */
      told: boolean
      title: string
    }
  | {
      kind: 'none'
      reason: 'not-declared' | 'not-started-here'
      /** A few words for the tile. */
      why: string
      title: string
      /** A declaration needs a key to name the agent by. */
      canDeclare: boolean
    }
  | { kind: 'unmeasured'; title: string }

/** Said wherever the screen describes how an agent treats outside requests. */
export const WORK_RULE_NOTE =
  'Instructed to decline requests outside this goal and to send them to the project’s desk. '
  + 'That is an instruction the agent was given — nothing enforces it.'
export const DESK_RULE_NOTE =
  'Instructed to answer requests addressed to its project and to decline work outside them. '
  + 'That is an instruction the agent was given — nothing enforces it.'

export const NOT_DECLARED_TITLE =
  'The framework started this agent and nobody gave it a goal. One can be declared now; '
  + 'the agent is told at its next session start, clear or compaction.'
export const NOT_STARTED_HERE_TITLE =
  'This agent was opened by hand, so the framework never recorded why. A mandate can be declared '
  + 'for this screen — nothing will tell the agent, because it carries no hook of ours.'
export const UNMEASURED_TITLE =
  'The mandate store could not be read. This is not the same as an agent with no mandate.'

export const NO_GOAL_NOTE =
  'no goal — this agent will have no mandate. One can be declared later from its tile.'
export const GOAL_NOTE =
  'recorded with the start. The agent is told this at every session start, clear and compaction.'

/** The mandate as lines a detail can list: goal, scope, closing condition,
    who asked (as the claim it is), whether the agent was told, and the rule. */
export function mandateDescription(m: FleetMandate): string[] {
  const lines = [`${m.kind}: ${m.goal}`]
  const paths = (m.scope?.paths ?? []).filter(Boolean)
  if (paths.length) lines.push(`scope: ${paths.join(', ')}`)
  if (m.scope?.change) lines.push(`change: ${m.scope.change}`)
  if (m.done_when) lines.push(`done when: ${m.done_when}`)
  if (m.requested_by) lines.push(`asked by: ${m.requested_by} (a claim — nothing verified who asked)`)
  lines.push(m.delivered
    ? 'The agent has been told: its session-start hook read this record.'
    : m.source === 'declared'
      ? 'Declared after the start. The agent has NOT been told yet — it reads this at its next session start, clear or compaction, if the framework started it.'
      : 'The agent has not been told yet — its session-start hook has not read this record.')
  lines.push(m.kind === 'desk' ? DESK_RULE_NOTE : WORK_RULE_NOTE)
  return lines
}

const describe = (m: FleetMandate): string => mandateDescription(m).join('\n')

export function mandateStanding(
  agent: Pick<FleetAgent, 'mandate' | 'mandate_absent' | 'terminal_label' | 'session_id'>,
): MandateStanding {
  const m = agent.mandate
  if (m) return { kind: 'held', badge: String(m.kind), goal: m.goal, told: m.delivered === true, title: describe(m) }
  const reason = agent.mandate_absent?.reason
  if (reason === undefined || reason === null) return { kind: 'unreported' }
  if (reason === 'not-declared' || reason === 'not-started-here') {
    const hand = reason === 'not-started-here'
    return {
      kind: 'none',
      reason,
      why: hand ? 'opened by hand' : 'none declared',
      title: hand ? NOT_STARTED_HERE_TITLE : NOT_DECLARED_TITLE,
      canDeclare: Boolean(agent.terminal_label || agent.session_id),
    }
  }
  // `unmeasured`, and any reason this build does not know: neither is "none".
  return { kind: 'unmeasured', title: UNMEASURED_TITLE }
}

/** One path per line or comma; blanks dropped, order kept, duplicates removed. */
export function parsePaths(text: string): string[] {
  const seen = new Set<string>()
  for (const part of text.split(/[\n,]/)) {
    const path = part.trim()
    if (path) seen.add(path)
  }
  return [...seen]
}

export interface MandateDraft {
  goal: string
  paths: string
  change: string
  doneWhen: string
}

export const EMPTY_DRAFT: MandateDraft = { goal: '', paths: '', change: '', doneWhen: '' }

export type MandateFields =
  /** Nothing typed: the start goes out with no mandate at all. */
  | { kind: 'none' }
  /** A scope or a closing condition with no goal — refused here, because the
      server would start the agent and silently drop both. */
  | { kind: 'problem'; message: string }
  | { kind: 'mandate'; mandate: { goal: string; paths?: string[]; change?: string; done_when?: string } }

export function mandateFields(draft: MandateDraft): MandateFields {
  const goal = draft.goal.trim()
  const paths = parsePaths(draft.paths)
  const change = draft.change.trim()
  const doneWhen = draft.doneWhen.trim()
  if (!goal) {
    return paths.length || change || doneWhen
      ? { kind: 'problem', message: 'a scope or a closing condition needs a goal — add one, or clear them' }
      : { kind: 'none' }
  }
  return {
    kind: 'mandate',
    mandate: {
      goal,
      ...(paths.length ? { paths } : {}),
      ...(change ? { change } : {}),
      ...(doneWhen ? { done_when: doneWhen } : {}),
    },
  }
}

/** What the declare route answered, as the sentence the reader needs. */
export function declareOutcome(answer: { carrier?: boolean } | null): { told: boolean; text: string } {
  if (answer?.carrier === true) {
    return {
      told: true,
      text: 'Recorded. The agent is told at its next session start, clear or compaction — not before.',
    }
  }
  return {
    told: false,
    text: 'Recorded for this screen only. Nothing tells this agent: the framework did not start it, so it carries no hook of ours.',
  }
}
