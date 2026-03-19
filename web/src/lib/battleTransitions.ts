import type { ChangeInfo } from './api'

export interface ChangeTransition {
  name: string
  from: string
  to: string
  change: ChangeInfo
}

const statusMap = new Map<string, string>()

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

export function initStatusMap(changes: ChangeInfo[]) {
  statusMap.clear()
  for (const c of changes) {
    statusMap.set(c.name, c.status)
  }
}
