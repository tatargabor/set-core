/**
 * One fact on a header strip: a mark, a number, and the sentence in the tooltip.
 *
 * The fleet's two header strips — the project column's attention row and the
 * project's own row above the grid — used to spell each fact out: `1 waiting for
 * an answer → first one`, `49 projects not measured`, `3 waiter(s), none
 * orphaned`, `2 not connected · 2 partial`. Asked for by the user with a picture
 * of each: *"felesleges szövegek vannak felül a menüben és a méretük is
 * változik. minden ikon-ra és számra menjen át"*, then *"csak ott legyen szöveg
 * ahol tényleg kell"*.
 *
 * The size complaint is the measurable half, and it is the reason this exists
 * rather than a matter of taste: a strip of phrases WRAPS, so its height moved
 * every time a count changed or a state appeared, and what sat below it jumped.
 * Measured on the column's strip: 117 px of header became 29 px, one row.
 *
 * Nothing is lost, because on these strips the MARK was always the meaning and
 * the prose only restated it. What the prose carried that a mark cannot — why
 * this is worth looking at — is on `title` for a pointer and on `aria-label` for
 * a reader who has none. Where a fact has no mark that distinguishes it, it
 * keeps its words; that is what "text only where it is really needed" means,
 * and a path is the clearest example: it is the only thing that says WHICH
 * checkout.
 *
 * Shared rather than copied. A second implementation of this drifts, and then
 * two strips that should read alike stop reading alike.
 */

import type { ReactNode } from 'react'

export interface ChipProps {
  /** The glyph or dot. It carries the meaning; keep the shapes distinct. */
  mark: ReactNode
  /** The number, or `?` where the fact was not measured at all. */
  count: ReactNode
  /** Colour and weight classes — one visual weight per meaning. */
  tone?: string
  /** The sentence the words used to say. Shown on hover. */
  title: string
  /** The same sentence for a reader without a pointer. */
  label: string
  onClick?: () => void
  /** `data-fleet-jump` on a chip that scrolls somewhere; `data-fleet-chip` otherwise. */
  jump?: string
  /** Extra markers this chip must keep carrying — `data-fleet-waiting`, say. */
  data?: Record<string, string>
  /** Rendered after the count, for the rare chip that also opens something. */
  trailing?: ReactNode
  'aria-pressed'?: boolean
  className?: string
}

export function Chip({
  mark, count, tone = 'text-fg-muted', title, label, onClick, jump, data, trailing,
  className, ...rest
}: ChipProps) {
  const cls = `inline-flex items-center gap-1 text-xs tabular-nums shrink-0 ${tone}${
    onClick ? ' hover:underline underline-offset-2' : ''}${className ? ` ${className}` : ''}`
  const body = <>{mark}{count}{trailing}</>
  return onClick
    ? (
      <button type="button" data-fleet-jump={jump} {...data} {...rest}
              onClick={onClick} title={title} aria-label={label} className={cls}>
        {body}
      </button>
    )
    : (
      <span data-fleet-chip={jump} {...data} {...rest} title={title} aria-label={label} className={cls}>
        {body}
      </span>
    )
}

/**
 * A filled dot — every agent-state mark on these surfaces is one.
 *
 * The shapes are load-bearing now that the words are gone: a circle is an agent
 * state, a square is work waiting on a person, and a glyph is an anomaly. Two
 * facts drawn with the same shape in the same colour are two facts a reader
 * cannot tell apart at all.
 */
export function Dot({ cls }: { cls: string }) {
  return <span className={`w-2 h-2 rounded-full shrink-0 ${cls}`} aria-hidden />
}
