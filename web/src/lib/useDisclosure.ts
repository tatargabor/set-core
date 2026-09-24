/**
 * Open state for the things the project header opens.
 *
 * Four chips in the header open something — restore's recorded list, the
 * waiters, the set-core modules — and every one of them carried its own
 * `useState(false)` plus its own idea of what "open" looks like. Two of them
 * opened INSIDE the header row, which is a `flex-wrap` row, so opening them
 * grew the row and pushed the page down. Measured: expanding the waiters list
 * shoved the modules chip and the whole window-control cluster into the middle
 * of its own list.
 *
 * The user's rule, stated 2026-09-23 after a mock-up that made the header taller
 * on open: *"never push on the elements, or sizes. I think that's a common
 * request on UIs"*. It is now `.claude/rules/ui-quality.md` § *An overlay NEVER
 * pushes*, and this hook plus `Panel` is how the header obeys it.
 *
 * ## Why a hook and not a prop on `Chip`
 *
 * `Chip` renders every trigger, so it looks like the natural home. But `Chip` is
 * also used for facts that open nothing — counts, labels, a path. Giving every
 * chip an open state would make "is this clickable?" ambiguous at the call site,
 * which is the question the reader is really asking. So the state lives here and
 * the chip stays a chip.
 *
 * ## The marker is not decoration
 *
 * `triggerData` emits `data-fleet-<name>-open`. One consumer already exists and
 * must keep working: `tests/e2e/fleet-install.spec.ts:93` polls
 * `data-fleet-modules-open` to decide whether to click. The waiters trigger, by
 * contrast, has NO stable selector at all — its unit test finds it as "the only
 * button" in an isolated render — so giving every opener the same marker is a
 * repair, not just consistency.
 */

import { useCallback, useEffect, useState } from 'react'

export interface Disclosure {
  open: boolean
  toggle: () => void
  close: () => void
  /** Spread onto the trigger: `data-fleet-<name>-open="on"|"off"`. */
  triggerData: Record<string, string>
}

export function useDisclosure(name: string): Disclosure {
  const [open, setOpen] = useState(false)

  // Escape closes it. A layer that covers the page and can only be dismissed
  // with the mouse is a trap for anyone reading with the keyboard — the rule the
  // recorded-list dialog already followed, now shared so a fifth opener cannot
  // forget it.
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false) }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open])

  const toggle = useCallback(() => setOpen(v => !v), [])
  const close = useCallback(() => setOpen(false), [])

  return {
    open,
    toggle,
    close,
    triggerData: { [`data-fleet-${name}-open`]: open ? 'on' : 'off' },
  }
}
