import type { LucideIcon } from 'lucide-react'
import { Expand, Maximize2, Minimize2, ScrollText, Shrink, SquareTerminal } from 'lucide-react'

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

function IconButton({ icon: Icon, label, active, tone, onClick, testId, mark }: {
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
      */}
      <span className="sr-only">{label}</span>
    </Tag>
  )
}

export default function TileControls({
  agent, ownerReachable, logOpen, onLog, enlarged, onEnlarge, focused, onFocus, terminalOpen, onTerminal,
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
}) {
  const offer = terminalOffer(agent, ownerReachable)
  return (
    <span className="ml-auto flex items-center gap-0.5 shrink-0" data-tile-controls={agent.pid}>
      <IconButton
        icon={ScrollText}
        testId="log"
        active={logOpen}
        label={logOpen ? 'close the log' : 'open the log — the conversation opens on this tile'}
        onClick={onLog}
      />
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
