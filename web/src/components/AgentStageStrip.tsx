import { Fragment } from 'react'

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
    // NUMBERED CIRCLES, at the user's request (2026-08-30): *"adj numbers to
    // the states … draw little circles like 1-2-3-4-5-6-7 where 1 is the start
    // and the last is the final — more representative than just the name"*.
    // Circle N is stage N of the flow — position is the number, so the shape
    // of the flow survives even where the names would not fit; each circle
    // carries its stage name on title, and the CURRENT stage's name is
    // rendered after the circles, because nothing load-bearing may depend on
    // hover. The connector dash is what makes it read as a pipeline rather
    // than a row of badges.
    <span data-fleet-stage="strip" data-testid="fleet-stage-strip" data-fleet-stage-source={stage.source ?? undefined}
          className="inline-flex -mr-1 items-center gap-x-1 gap-y-0.5 flex-wrap min-w-0">
      {flow.map((name, i) => {
        const state = i < currentIndex ? 'done' : i === currentIndex ? 'running' : 'pending'
        return (
          <Fragment key={name}>
            {i > 0 && <span aria-hidden className="h-px w-1.5 shrink-0 bg-fg-ghost/60" />}
            <span data-stage-chip={name} data-stage-state={state} data-stage-index={i + 1}
                  title={`${i + 1}/${flow.length} · ${name} — ${
                    state === 'done' ? 'done'
                      : state === 'running' ? 'where this agent is now'
                        : 'not reached yet'}`}
                  className={`inline-flex w-4 h-4 items-center justify-center rounded-full text-xs leading-none ${
                    state === 'done' ? 'bg-teal-300/80 text-surface-panel'
                      : state === 'running' ? 'bg-indigo-400/30 text-indigo-100 ring-2 ring-indigo-300/70 font-semibold'
                        : 'border border-fg-ghost/70 text-fg-ghost'
                  }`}>
              {i + 1}
            </span>
          </Fragment>
        )
      })}
      {stage.outside && stage.position ? (
        <span data-stage-current={stage.position} data-testid="fleet-stage-current"
              title={`“${stage.position}” is not a stage the flow declares — carried and marked, never dropped`}
              className="rounded bg-amber-400/10 px-1 text-xs leading-4 whitespace-nowrap text-amber-400">
          ⚑ {stage.position}
        </span>
      ) : (
        <span data-stage-current={stage.position ?? ''} data-testid="fleet-stage-current"
              className="text-xs leading-4 whitespace-nowrap text-indigo-200">
          {stage.position}
        </span>
      )}
    </span>
  )
}
