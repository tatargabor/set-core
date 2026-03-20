import type { ChangeInfo } from './api'

export interface ChangeTransition {
  name: string
  from: string
  to: string
  change: ChangeInfo
}

/** Non-status events: session count changes, token milestones, etc. */
export interface ChangeEvent {
  name: string
  type: 'new_session' | 'session_closed' | 'tokens_milestone' | 'iteration'
  detail: string
  change: ChangeInfo
}

export function detectTransitions(prev: ChangeInfo[], next: ChangeInfo[]): ChangeTransition[] {
  const transitions: ChangeTransition[] = []
  const prevMap = new Map(prev.map(c => [c.name, c.status]))

  for (const c of next) {
    const prevStatus = prevMap.get(c.name) ?? 'unknown'
    if (prevStatus !== c.status) {
      transitions.push({ name: c.name, from: prevStatus, to: c.status, change: c })
    }
  }

  return transitions
}

export function detectEvents(prev: ChangeInfo[], next: ChangeInfo[]): ChangeEvent[] {
  const events: ChangeEvent[] = []
  const prevMap = new Map(prev.map(c => [c.name, c]))

  for (const c of next) {
    const p = prevMap.get(c.name)
    if (!p) continue

    // Session count changed
    const prevSessions = p.session_count ?? 0
    const nextSessions = c.session_count ?? 0
    if (nextSessions > prevSessions) {
      const diff = nextSessions - prevSessions
      for (let i = 0; i < diff; i++) {
        events.push({
          name: c.name,
          type: 'new_session',
          detail: `Session #${prevSessions + i + 1} opened`,
          change: c,
        })
      }
    }

    // Token milestones (every 100k)
    const prevTok = (p.input_tokens ?? 0) + (p.output_tokens ?? 0)
    const nextTok = (c.input_tokens ?? 0) + (c.output_tokens ?? 0)
    const prevMilestone = Math.floor(prevTok / 100_000)
    const nextMilestone = Math.floor(nextTok / 100_000)
    if (nextMilestone > prevMilestone && nextTok > 0) {
      events.push({
        name: c.name,
        type: 'tokens_milestone',
        detail: `${nextMilestone * 100}k tokens used`,
        change: c,
      })
    }

    // Iteration / retry count
    const prevIter = p.iteration ?? 0
    const nextIter = c.iteration ?? 0
    if (nextIter > prevIter && nextIter > 1) {
      events.push({
        name: c.name,
        type: 'iteration',
        detail: `Iteration #${nextIter}`,
        change: c,
      })
    }
  }

  return events
}
