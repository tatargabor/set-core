import type { FleetAgent } from '../lib/fleetTypes'

/**
 * One agent's stage, as a compact strip — the fleet column's rendering of the
 * stage axis the payload resolves (`agent-stage-derivation`).
 *
 * ## One visual weight per meaning, and the hues are chosen LAST
 *
 * The fleet screen already assigns meaning to colour: emerald is *working*,
 * sky is *waiting for an answer*, amber is *waiting for you / a contradiction*,
 * rose is an *urgent wait*, violet is *work with nobody on it*. The strip is a
 * different lane — chips with text, beside the agent's name, not a dot in the
 * row's counter line — but a hue collision is still a hue collision, so the
 * three stage states draw on hues this screen has NOT claimed:
 *
 * - **done** — teal: the work behind the agent;
 * - **running** — indigo, the strongest of the three: it is the one stage the
 *   reader opened the row for, and the only one with a ring;
 * - **pending** — no colour at all: ghost text. Not-done-yet is not a state
 *   worth ink, and colouring it would put three hues on every row.
 *
 * The two marked states reuse marks this screen already teaches:
 * `⚑` for a value outside a declared order (the same convention the project
 * status table's strip established), and a dashed amber chip for a gap —
 * dashed being the screen's mark for *unknown/unmeasured*, which is what a
 * resolution failure is.
 *
 * ## The empty state is NOT a gap chip
 *
 * `nothing-started` and a resolution failure both arrive as `state: 'gap'`,
 * and rendering them alike is exactly the collapse the spec forbids: one says
 * "this agent has nothing going, like most rows", the other says "we looked
 * and could not tell". So nothing-started renders as the EMPTY state — a bare
 * dash, quiet, no amber — and only a real failure draws attention.
 *
 * Legibility rule for this component: the current stage must be readable at
 * sub-row height, with no hover and no expansion. The strip never truncates
 * its chips; a flow that does not fit wraps, once.
 */
export function AgentStageStrip({ stage }: { stage: FleetAgent['stage'] }) {
  if (!stage) return null
  if (stage.state === 'gap') {
    if (stage.reason === 'nothing-started') {
      return (
        <span data-fleet-stage="empty" data-testid="fleet-stage-empty"
              title="nothing started — no change is in flight here"
              className="inline-flex shrink-0 items-center px-1 text-xs text-fg-muted" aria-label="nothing started">
          —
        </span>
      )
    }
    const why: Record<string, string> = {
      'join-failed': 'work is in flight here, but this agent could not be matched to its own change',
      'no-flow': 'this project publishes no flow to read — no openspec tree and no declared stage order',
      'no-position': 'the agent’s change was found, but its artifacts back no stage',
    }
    return (
      <span data-fleet-stage="gap" data-testid="fleet-stage-gap" data-fleet-stage-reason={stage.reason ?? 'unknown'}
            title={why[stage.reason ?? ''] ?? 'the stage could not be resolved'}
            className="inline-flex shrink-0 items-center rounded border border-dashed border-amber-400/70 px-1 text-xs text-amber-400">
        ⚠ stage?
      </span>
    )
  }

  const flow = stage.flow ?? []
  const currentIndex = stage.outside ? -1 : flow.indexOf(stage.position ?? '')
  return (
    // Full sub-row width, left-aligned — the strip IS the second line of the
    // sub-row, and a pipeline reads left to right. Measured in the browser at
    // the column's own width: a right-aligned wrapped variant broke the flow
    // into a ragged stack, which is the opposite of at-a-glance. Done and
    // pending are plain COLOURED TEXT rather than chips for the same reason —
    // five boxed chips do not fit the column, five words do; only the running
    // stage keeps a box, because it is the one worth a second look.
    <span data-fleet-stage="strip" data-testid="fleet-stage-strip" data-fleet-stage-source={stage.source ?? undefined}
          className="inline-flex -mr-1 items-center gap-x-[3px] gap-y-0.5 flex-wrap min-w-0">
      {flow.map((name, i) => {
        const state = i < currentIndex ? 'done' : i === currentIndex ? 'running' : 'pending'
        return (
          <span key={name}
                data-stage-chip={name} data-stage-state={state}
                title={state === 'done' ? `${name} — done`
                  : state === 'running' ? `${name} — where this agent is now`
                    : `${name} — not reached yet`}
                className={`text-xs leading-4 whitespace-nowrap ${
                  state === 'done' ? 'text-teal-300'
                    : state === 'running' ? 'rounded bg-indigo-400/25 px-0.5 text-indigo-100 ring-1 ring-indigo-300/60 font-medium'
                      : 'text-fg-ghost'
                }`}>
            {name}
          </span>
        )
      })}
      {stage.outside && stage.position && (
        <span data-stage-chip={stage.position} data-stage-state="outside"
              title={`“${stage.position}” is not a stage the flow declares — carried and marked, never dropped`}
              className="rounded bg-amber-400/10 px-1 text-xs leading-4 whitespace-nowrap text-amber-400">
          ⚑ {stage.position}
        </span>
      )}
    </span>
  )
}
