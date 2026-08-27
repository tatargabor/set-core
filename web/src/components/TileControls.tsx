import type { LucideIcon } from 'lucide-react'
import {
  Expand, Maximize2, Minimize2, MessageSquare, PanelBottom, PanelLeft, PanelRight, PanelTop,
  ScrollText, Shrink, SquareTerminal,
} from 'lucide-react'
import type { DockEdge } from '../lib/fleetDocks'
import SrOnly from './SrOnly'

/**
 * The four docking controls, in reading order.
 *
 * A table rather than four hand-written buttons: four copies of one control is
 * where the accessible name, the active state or the undock branch gets left
 * out of exactly one of them, and it is always the one nobody clicks while
 * testing.
 */
/**
 * The four edges, as one list.
 *
 * Exported because the file view draws the same four controls: two lists would
 * be two answers to *where can a panel go*, and the second one drifts the day an
 * edge is added or a wording is fixed.
 */
export const DOCK_CONTROLS: { edge: DockEdge; icon: LucideIcon; where: string }[] = [
  { edge: 'left', icon: PanelLeft, where: 'on the left' },
  { edge: 'right', icon: PanelRight, where: 'on the right' },
  { edge: 'top', icon: PanelTop, where: 'along the top' },
  { edge: 'bottom', icon: PanelBottom, where: 'along the bottom' },
]

import type { FleetAgent } from '../lib/fleetTypes'
import { terminalOffer } from '../lib/fleetTerminal'

/**
 * A tile's controls, as window controls — asked for on 2026-08-19:
 * *"ikonok kellenek, kevesebb szöveg a fejlécbe, vezérlőknek legalábbis,
 * mintha ablakok lennének (azok is)"*.
 *
 * They were four sentences in a row under the excerpt — `open the log`,
 * `⤢ enlarge`, `⤢ full screen`, `open the terminal` — which is a paragraph
 * where a title bar belongs. With two to four tiles across, that paragraph
 * appeared four times on one screen and competed with the thing a reader came
 * to read.
 *
 * ## The wording is not deleted, it MOVES
 *
 * Every control keeps its sentence in `title` and in `aria-label`. That matters
 * twice over: a screen reader still hears "open the log", and the two negative
 * terminal cases still SAY why there is nothing to open — a requirement (task
 * 8.2) that an icon alone would quietly drop.
 *
 * ## What may not become an icon
 *
 * A state that needs acting on must be visible WITHOUT hovering, so the
 * terminal control carries its meaning in colour as well as in shape: amber for
 * *orphaned* (ours, terminal lost) and for *we could not ask*, dim for
 * *foreign*. A tooltip is where the reason lives; it is never where the alarm
 * lives — `ui-quality.md`'s rule about compaction applied to a title bar.
 */

export function IconButton({ icon: Icon, label, active, tone, onClick, testId, mark }: {
  icon: LucideIcon
  /** The sentence this control used to be. It is rendered, not just hinted. */
  label: string
  active?: boolean
  tone?: 'default' | 'amber' | 'ghost'
  onClick?: () => void
  testId?: string
  /** Extra data attributes that must sit on the SAME element as the reason. */
  mark?: Record<string, string>
}) {
  const colour = tone === 'amber' ? 'text-amber-400'
    : tone === 'ghost' ? 'text-fg-ghost'
      : active ? 'text-sky-300' : 'text-fg-muted hover:text-fg-strong'
  const Tag = onClick ? 'button' : 'span'
  return (
    <Tag
      onClick={onClick}
      title={label}
      aria-pressed={onClick && active !== undefined ? active : undefined}
      data-tile-control={testId}
      data-tile-control-active={active ? 'on' : undefined}
      {...mark}
      className={`shrink-0 rounded p-1 leading-none ${colour} ${
        onClick ? 'hover:bg-surface-raised/60 cursor-pointer' : 'cursor-default'
      } ${active ? 'bg-surface-raised/60' : ''}`}
    >
      <Icon size={14} strokeWidth={active ? 2.25 : 1.75} aria-hidden />
      {/*
        RENDERED, not merely hinted — visually hidden, present in the accessible
        name and in the DOM. An `aria-label` would satisfy a screen reader and
        leave the text nowhere else: task 8.2 requires the reason a terminal
        cannot be offered to be STATED, and a tooltip is not a statement — it is
        a thing you have to already suspect in order to find.

        `SrOnly` rather than a bare `sr-only` span because rendered-but-hidden
        text is still SELECTABLE: copying the screen used to drag every one of
        these sentences into the clipboard. See the component — B-90.
      */}
      <SrOnly>{label}</SrOnly>
    </Tag>
  )
}

export default function TileControls({
  agent, ownerReachable, logOpen, onLog, enlarged, onEnlarge, focused, onFocus, terminalOpen, onTerminal,
  onDock, dockedEdge, instructOpen, onInstruct,
}: {
  agent: FleetAgent
  ownerReachable?: boolean
  logOpen: boolean
  onLog: () => void
  enlarged?: boolean
  onEnlarge?: () => void
  focused?: boolean
  onFocus?: () => void
  terminalOpen: boolean
  onTerminal: (label: string | null) => void
  /**
   * Send this panel to an edge, or `null` to bring it back into the grid.
   *
   * Offered only where the panel HAS an identity a docking can be stored
   * against — the terminal label, here. A control that looked available and did
   * nothing would be worse than an absent one: the reader would conclude that
   * docking is broken rather than that this panel cannot be docked.
   */
  onDock?: (edge: DockEdge | null) => void
  /** Which edge it is on now, if any — so the control can say where it went. */
  dockedEdge?: DockEdge | null
  /**
   * Whether the instruction box is open — B-61.
   *
   * It used to be open on every tile, always, costing a row per agent before a
   * word had been typed into it. Reported 2026-08-22: *"send mesage tök
   * feleslegesen van ott kinyitva, majd kuldko üzenetet akkor nyiljon le"*. So
   * it became a control, and the control lives HERE rather than as a row of its
   * own — a row that exists to open a row is the thing being removed.
   */
  instructOpen?: boolean
  onInstruct?: () => void
}) {
  const offer = terminalOffer(agent, ownerReachable)
  const dockable = onDock && agent.terminal_label
  return (
    <span className="ml-auto flex items-center gap-0.5 shrink-0" data-tile-controls={agent.pid}>
      {onInstruct && (
        <IconButton
          icon={MessageSquare}
          testId="instruct"
          active={instructOpen}
          mark={{ 'data-tile-instruct-open': instructOpen ? 'yes' : 'no' }}
          label={instructOpen
            ? 'close the instruction box — nothing typed into it is sent by closing'
            : 'send an instruction to this agent'}
          onClick={onInstruct}
        />
      )}
      <IconButton
        icon={ScrollText}
        testId="log"
        active={logOpen}
        label={logOpen ? 'close the log' : 'open the log — the conversation opens on this tile'}
        onClick={onLog}
      />
      {dockable && (
        /* Four edges, one control each. A single "dock" button would have to
           pick an edge for the reader, and the point of the feature is that
           they pick. The one it is already on becomes the way back — pressing
           it again undocks, so the control never becomes a dead end. */
        <span className="flex items-center" data-tile-dock={agent.terminal_label}>
          {DOCK_CONTROLS.map(({ edge, icon, where }) => (
            <IconButton
              key={edge}
              icon={icon}
              testId={`dock-${edge}`}
              active={dockedEdge === edge}
              label={dockedEdge === edge
                ? `bring this panel back into the grid from the ${where}`
                : `put this panel ${where} — it takes its space out of the grid`}
              onClick={() => onDock?.(dockedEdge === edge ? null : edge)}
            />
          ))}
        </span>
      )}
      {onEnlarge && !focused && (
        <IconButton
          icon={enlarged ? Minimize2 : Maximize2}
          testId="enlarge"
          active={enlarged}
          label={enlarged
            ? 'back to the grid — every tile the same size again'
            : 'this tile big, the others as rows — nothing is hidden, a row still carries its state'}
          onClick={onEnlarge}
        />
      )}
      {onFocus && (
        <IconButton
          icon={focused ? Shrink : Expand}
          testId="focus"
          active={focused}
          label={focused
            ? 'back to the grid — the other agents come back into view'
            : 'show this agent alone, filling the panel — what it covers is counted in the header'}
          onClick={onFocus}
        />
      )}
      {/* Task 8.2, four outcomes. Only the first is a control; the other three
          are statements, and their tone carries the difference without a hover.
          The reason itself is in the label, so nothing that used to be said is
          now unsaid. */}
      {offer.kind === 'available' ? (
        <IconButton
          icon={SquareTerminal}
          testId="terminal"
          active={terminalOpen}
          mark={{ 'data-fleet-terminal-open': offer.label }}
          label={terminalOpen
            ? 'close the terminal — the agent keeps running'
            : 'open the terminal — the framework holds this one'}
          onClick={() => onTerminal(terminalOpen ? null : offer.label)}
        />
      ) : (
        /* The absent cases carry `data-fleet-terminal-absent` and their REASON on
           the SAME element — that is what the 8.2 checks read, and separating the
           two would let a marker say "no terminal here" with the explanation
           somewhere else. */
        <IconButton
          icon={SquareTerminal}
          testId={`terminal-${offer.kind}`}
          tone={offer.kind === 'foreign' ? 'ghost' : 'amber'}
          mark={{ 'data-fleet-terminal-absent': offer.kind }}
          label={offer.kind === 'orphaned'
            ? `terminal lost — ours, scope ${offer.scope} still running. ${offer.reason}`
            : offer.reason}
        />
      )}
    </span>
  )
}
