/**
 * How full each live agent's context is, on the fleet header.
 *
 * The account bars beside this say how much quota is left to spend at all. This
 * says how close each agent is to compacting — a different measurement, drawn
 * with its own marks, in the same way cache heat keeps its own.
 *
 * ## Why it takes agents rather than fetching
 *
 * The fleet page already holds the agents and their `context` blocks. A second
 * fetch would be a second clock and a second failure mode for a figure the page
 * already has. `FleetUsageStrip` fetches because its measurement comes from a
 * different service; this one does not.
 *
 * ## Bars are per agent here, which the quota strip may not do
 *
 * Account quota has no per-seat identity to join on, so `fleet-usage-bars`
 * forbids a per-tab mark. Context is read from the agent's own transcript, so it
 * has no attribution gap — the prohibition does not transfer, and the two marks
 * stay visually distinct so nobody reads one as the other.
 */

import { Brain } from 'lucide-react'

import {
  contextStrip, overflowTitle, unmeasuredTitle,
  type ContextAgent, type ContextMark,
} from '../lib/fleetContextFill'

/** One agent's fill. A single stripe — the pair-of-stripes form belongs to the
 *  quota bars, and reusing it here would invite reading elapsed time into a
 *  measurement that has no time in it. */
function FillBar({ mark }: { mark: ContextMark }) {
  if (mark.kind === 'unmeasured') {
    return (
      <span className="inline-flex items-center gap-0.5 text-xs text-amber-400 shrink-0"
            data-fleet-context-agent={mark.name}
            data-fleet-context-state="unmeasured"
            title={mark.title}>
        ?
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-1 shrink-0"
          data-fleet-context-agent={mark.name}
          data-fleet-context-state="measured"
          data-fleet-context-fill={mark.fill.toFixed(3)}
          data-fleet-context-over={mark.over ? 'yes' : undefined}
          title={mark.title}>
      <span className="relative inline-block h-[7px] w-9 border border-surface-line align-middle">
        <span className={`absolute left-0 top-0 h-full ${mark.tone}`}
              style={{ width: `${mark.drawn * 100}%` }} />
      </span>
      {/* Over its window cannot be drawn — the bar is already full — so it is
          said. Silently clamping would hide a disagreement behind a tidy bar. */}
      {mark.over && <span className="text-xs text-red-400" aria-hidden>!</span>}
    </span>
  )
}

export default function FleetContextStrip({ agents }: { agents: ContextAgent[] | null | undefined }) {
  const state = contextStrip(agents)

  // Nothing live, and nothing unmeasured either: draw nothing at all. An empty
  // bar here would read as an agent holding no context, which is a claim about
  // an agent that is not there.
  if (state.marks.length === 0 && state.unmeasured === 0) return null

  return (
    <span className="inline-flex items-center gap-1.5 shrink-0"
          data-fleet-context="ready"
          data-fleet-context-total={state.total}
          data-fleet-context-drawn={state.marks.length}
          title="Context fill — how full each live agent's context window is, against its own model's window.">
      <Brain size={13} strokeWidth={1.75} className="text-fg-ghost shrink-0" aria-hidden />

      {/* Keyed by pid, not name: a name can be null or repeated, and colliding
          keys would silently draw a smaller fleet than there is. */}
      {state.marks.map(m => <FillBar key={m.pid} mark={m} />)}

      {/* The cap's remainder. Shown because a hidden agent that nobody counts is
          indistinguishable from an agent that does not exist — and safe to hide
          only because the drawn marks are the fullest ones. */}
      {state.overflow > 0 && (
        <span className="text-xs text-fg-muted tabular-nums shrink-0"
              data-fleet-context-overflow={state.overflow}
              aria-label={`${state.overflow} more agents with measured context fill`}
              title={overflowTitle(state.overflow)}>
          +{state.overflow}
        </span>
      )}

      {/* Agents with no measurable fill. Counted, never dropped. */}
      {state.unmeasured > 0 && (
        <span className="inline-flex items-center gap-0.5 text-xs text-amber-400 tabular-nums shrink-0"
              data-fleet-context-unmeasured={state.unmeasured}
              aria-label={`${state.unmeasured} agents with no measured context fill`}
              title={unmeasuredTitle(
                `${state.unmeasured} agent${state.unmeasured > 1 ? 's' : ''}`,
                null,
              )}>
          ?{state.unmeasured}
        </span>
      )}
    </span>
  )
}
