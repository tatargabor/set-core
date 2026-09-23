/**
 * The one panel every header opener uses.
 *
 * ## Why it is `fixed`, and why that is the whole point
 *
 * The project header is a `flex-wrap` row (`pages/Fleet.tsx`), so anything that
 * lives IN it participates in sizing: it grows the row, or wraps onto a new
 * line and grows it further. Two openers did exactly that — the waiters list
 * inline, and the modules panel with `basis-full`, which deliberately claims a
 * whole new wrapped line.
 *
 * `position: fixed` takes the panel out of normal flow entirely, so the row that
 * contains the trigger cannot see it. That is not a styling preference, it is
 * the mechanism by which opening a panel cannot move anything: there is nothing
 * for the flex container to lay out.
 *
 * The cost being avoided is not ugliness. A layout that reflows on open moves
 * the control the reader was about to click, and it does so EVERY time the
 * control is used.
 *
 * ## `max-h`, not `h`
 *
 * The recorded-list dialog was `h-[76vh]` whatever it held, so one recorded
 * session sat above roughly 380 px of nothing with the footer stranded at the
 * bottom — a panel covering most of the screen to say one sentence. Height now
 * follows content up to a cap; past the cap the body scrolls while the chrome
 * stays put.
 *
 * ## Chrome is uniform, bodies are not
 *
 * Every panel gets an icon, a title, its counts and a close control. A `footer`
 * is rendered only when one is passed, because only restore has panel-WIDE
 * actions. Waiters and modules have actions too — one stops a process, the other
 * writes files into the project's repo — but those belong to individual rows and
 * stay in the body. A panel that looked tidier by losing a guarded destructive
 * action would be a regression wearing a cleanup's clothes.
 */

import type { ReactNode } from 'react'
import type { CSSProperties } from 'react'

export interface PanelProps {
  /** The opener's own glyph, so the panel and its trigger read as one thing. */
  icon?: ReactNode
  title: string
  /** The counts that describe the contents — never invented when unmeasured. */
  counts?: ReactNode
  /** Rendered at the right of the header strip, before the close control. */
  headerExtra?: ReactNode
  onClose: () => void
  /** Panel-WIDE actions. Omit it and no footer is rendered at all. */
  footer?: ReactNode
  children: ReactNode
  /** Markers this panel must carry — `data-fleet-install-panel`, say. */
  data?: Record<string, string>
  /**
   * Markers for the close control.
   *
   * A caller that already had its own close marker keeps it: a test addressing
   * `data-fleet-restore-dialog-close` is asserting THAT panel's way out, and a
   * generic marker would make every panel's close look alike to a selector that
   * needs to tell them apart.
   */
  closeData?: Record<string, string>
  /** Markers for the footer row, where a caller's own marker must sit. */
  footerData?: Record<string, string>
  /** Accessible name for the dialog, when the title is not enough. */
  label?: string
}

export function Panel({
  icon, title, counts, headerExtra, onClose, footer, children, data, closeData, footerData, label,
}: PanelProps) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center pt-20 bg-surface-page/60"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label={label ?? title}
      {...data}
    >
      <div
        className="w-[70vw] max-w-4xl max-h-[76vh] flex flex-col rounded border border-surface-line
                   bg-surface-page shadow-2xl"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center gap-2 px-3 py-2 border-b border-surface-line shrink-0">
          {icon}
          <span className="text-sm text-fg-strong">{title}</span>
          {counts != null && <span className="text-xs text-fg-ghost">{counts}</span>}
          <span className="ml-auto flex items-center gap-2">
            {headerExtra}
            <button
              type="button"
              onClick={onClose}
              className="text-fg-muted hover:text-fg-strong px-1 text-base leading-none"
              aria-label="close"
              data-fleet-panel-close
              {...closeData}
            >×</button>
          </span>
        </div>

        <div className="flex-1 min-h-0 overflow-y-auto px-3 py-2">{children}</div>

        {footer != null && (
          <div className="flex items-center gap-3 px-3 py-2 border-t border-surface-line shrink-0"
               data-fleet-panel-footer {...footerData}>
            {footer}
          </div>
        )}
      </div>
    </div>
  )
}

export interface PanelColumn {
  key: string
  /** The column head. Empty string for a column that needs no heading. */
  label: string
  /** A CSS grid track — `7rem`, `minmax(0,1fr)`. */
  width: string
  align?: 'start' | 'end'
}

/**
 * Repeated records as aligned columns.
 *
 * The waiters list read `105989 live /a/project/checkout not
 * offered` — four fields run together in one row, so nothing could be compared
 * down a column and the eye had no edge to follow. The grid template is declared
 * once here and inherited by every row through a custom property, which is what
 * stops a row from drifting out of alignment with its own heading.
 */
export function PanelTable({ columns, children, data }: {
  columns: PanelColumn[]
  children: ReactNode
  data?: Record<string, string>
}) {
  const template = columns.map(c => c.width).join(' ')
  return (
    <div style={{ '--panel-cols': template } as CSSProperties} {...data}>
      <div className="grid gap-3 px-1 pb-1 text-xs uppercase tracking-wide text-fg-dim"
           style={{ gridTemplateColumns: 'var(--panel-cols)' }}
           data-fleet-panel-head>
        {columns.map(c => (
          <span key={c.key} className={c.align === 'end' ? 'text-right' : undefined}>{c.label}</span>
        ))}
      </div>
      <div className="border-t border-surface-line">{children}</div>
    </div>
  )
}

/** One record. Its children must be in the same order as the table's columns. */
export function PanelRow({ children, data, className }: {
  children: ReactNode
  data?: Record<string, string>
  className?: string
}) {
  return (
    <div
      className={`grid gap-3 items-center px-1 py-1 border-b border-surface-line/50 text-xs${
        className ? ` ${className}` : ''}`}
      style={{ gridTemplateColumns: 'var(--panel-cols)' }}
      {...data}
    >
      {children}
    </div>
  )
}
