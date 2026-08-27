import type { ReactNode } from 'react'

/**
 * Text that is RENDERED for a screen reader and for the DOM, and must not come
 * along when a person copies the screen — B-90.
 *
 * The `sr-only` half is a deliberate decision this repo already made: an
 * `aria-label` satisfies an assistive technology and leaves the sentence
 * nowhere else, while `ui-quality.md` asks for the reason a control exists to
 * be STATED rather than hinted. So the sentence lives in the DOM.
 *
 * What that decision did not account for is that `sr-only` only *hides* the
 * text — it clips it to a 1px box. It stays selectable, so a plain Ctrl+C over
 * the fleet screen drags every hidden sentence into the clipboard beside the
 * three words the reader could actually see. Measured 2026-08-27 in Chromium
 * against the running dashboard: selecting the terminal header alone yielded
 * **668 characters**, of which 4 were visible (`live`). With `user-select:
 * none` on these spans the same selection yields those 4 and nothing else.
 *
 * `user-select: none` is the right half to add because it is invisible to the
 * accessibility tree — the accessible name, the DOM presence and every test
 * that reads `textContent` are unchanged. Only the copy path narrows.
 */
export default function SrOnly({ children }: { children: ReactNode }) {
  return <span className="sr-only select-none">{children}</span>
}
