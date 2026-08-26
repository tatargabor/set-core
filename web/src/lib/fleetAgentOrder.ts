/**
 * The hand-made order of a project's agents — what it is stored by, and how a
 * stored list meets a live inventory.
 *
 * Kept out of the component for the ordinary reason (it can be measured without
 * a browser) and for one that is specific to this feature: every rule here is a
 * rule about the reader's arrangement rewriting itself, and each fails silently.
 * A test is the only place those become visible.
 */

import type { FleetAgent } from './fleetTypes'

/**
 * What an agent is called in a stored order.
 *
 * NOT the pid, which is the obvious choice and the wrong one: a pid dies with
 * the process, so an order stored by pid is forgotten exactly when the reader
 * would notice — after a restart. The terminal label is what the layout document
 * already keys agent panels by, and the rename path already carries dock ids, so
 * an ordered agent follows a rename for free by sharing that identity.
 *
 * The pid fallback is PREFIXED. Without `pid:` a bare number could collide with
 * a label that happens to be digits, and a collision here silently swaps two
 * agents' places.
 */
export function agentKey(agent: Pick<FleetAgent, 'terminal_label' | 'name' | 'pid'>): string {
  const label = agent.terminal_label?.trim()
  if (label) return label
  const name = agent.name?.trim()
  if (name) return name
  return `pid:${agent.pid}`
}

/**
 * The agents in the reader's order: named ones first, in the stored sequence,
 * then everything the order does not name in discovery's own order.
 *
 * The tail is the load-bearing half. A newly started agent placed FIRST would
 * move everything the reader arranged, on its own, for a reason they did not
 * ask for — so it goes last, where it changes nothing that was placed.
 *
 * A stored key naming an agent that is not running is simply skipped here. It is
 * NOT removed from the stored list; see `moveKey`.
 */
export function orderAgents<T extends Pick<FleetAgent, 'terminal_label' | 'name' | 'pid'>>(
  agents: readonly T[],
  order: readonly string[] | undefined,
): T[] {
  if (!order || order.length === 0) return [...agents]
  const byKey = new Map<string, T>()
  for (const agent of agents) {
    const key = agentKey(agent)
    // First wins: two agents cannot hold one key, and if they somehow do, the
    // second is not lost — it falls into the unnamed tail below.
    if (!byKey.has(key)) byKey.set(key, agent)
  }
  const placed: T[] = []
  const taken = new Set<T>()
  for (const key of order) {
    const agent = byKey.get(key)
    if (!agent || taken.has(agent)) continue
    placed.push(agent)
    taken.add(agent)
  }
  return [...placed, ...agents.filter(a => !taken.has(a))]
}

/**
 * The stored list after the reader moved the agent at `from` to `to`.
 *
 * The indices are positions in the RENDERED list — what the reader was actually
 * looking at — and the answer is a stored list, which is a different thing: it
 * also carries keys whose agents are not running.
 *
 * Those keys keep their places. Dropping them would be invisible and permanent:
 * a stopped agent that lost its slot comes back at the end of the strip, and the
 * arrangement the reader made quietly becomes one they did not. So the rendered
 * agents' keys are spliced back into the stored list at the positions the stored
 * list already gives them, and every other stored key stays exactly where it is.
 */
export function moveKey<T extends Pick<FleetAgent, 'terminal_label' | 'name' | 'pid'>>(
  rendered: readonly T[],
  order: readonly string[] | undefined,
  from: number,
  to: number,
): string[] {
  const keys = rendered.map(agentKey)
  if (from < 0 || to < 0 || from >= keys.length || to >= keys.length || from === to) {
    return mergedOrder(keys, order)
  }
  const moved = [...keys]
  moved.splice(to, 0, ...moved.splice(from, 1))
  return mergedOrder(moved, order)
}

/**
 * The rendered keys, in their new sequence, with every stored key that is not on
 * screen kept in place.
 *
 * "In place" means: relative to the stored list, an absent key stays between the
 * same two neighbours it had. Walking the stored list and substituting the next
 * rendered key at each rendered position does exactly that, and appends anything
 * rendered that the stored list never knew about — which is where a newly
 * started agent lands the first time it is dragged.
 */
function mergedOrder(keys: readonly string[], order: readonly string[] | undefined): string[] {
  const stored = order ?? []
  const onScreen = new Set(keys)
  const queue = [...keys]
  const out: string[] = []
  for (const key of stored) {
    if (onScreen.has(key)) {
      const next = queue.shift()
      if (next !== undefined) out.push(next)
      continue
    }
    out.push(key)
  }
  out.push(...queue)
  // A key can appear twice when the stored list held a duplicate; the store
  // drops those too, but doing it here means the screen and the file agree
  // before the write returns.
  return out.filter((key, i) => out.indexOf(key) === i)
}

/** Every project's stored order, keyed by project name. */
export type AgentOrderMap = Record<string, string[]>

/**
 * Read the stored orders. A failure is "no order", never an error state — the
 * same rule the docking and the divider positions follow: a screen that will
 * not render because a preference could not be read is a worse outcome than one
 * at its defaults.
 */
export async function loadAgentOrders(fetchImpl: typeof fetch = fetch): Promise<AgentOrderMap> {
  try {
    const res = await fetchImpl('/api/fleet/layout')
    if (!res.ok) return {}
    const body = await res.json()
    const raw = body?.agent_order
    if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return {}
    const out: AgentOrderMap = {}
    for (const [project, keys] of Object.entries(raw as Record<string, unknown>)) {
      if (!project || !Array.isArray(keys)) continue
      const list = keys.filter((k): k is string => typeof k === 'string' && k !== '')
      if (list.length) out[project] = list
    }
    return out
  } catch {
    return {}
  }
}

/**
 * Write ONE project's order. Says whether it landed; never throws at the caller.
 *
 * A write with no project is not sent at all, and the server refuses one too.
 * Both refusals are deliberate: an order without a project is the shape that
 * made docking screen-wide once, and a caller that could omit it is how such a
 * shape comes back.
 */
export async function saveAgentOrder(
  project: string | null, order: readonly string[], fetchImpl: typeof fetch = fetch,
): Promise<boolean> {
  if (!project) return false
  try {
    const res = await fetchImpl('/api/fleet/layout/agent-order', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ project, order }),
    })
    return res.ok
  } catch {
    return false
  }
}
