/**
 * The workspace state: several terminals at once, one agent alone, and the
 * ownership an agent tile has to show — all asserted as pure decisions.
 *
 * Three requests from 2026-08-19 sit under this file, and each one has a
 * failure direction that a happy-path test would miss:
 *
 *  - **several terminals**: a remembered label whose agent is gone must be
 *    DROPPED, not rendered as a dead pane — and the reader whose memory
 *    predates this shape must not lose the terminal they left open;
 *  - **full screen**: a remembered pid that is gone must NOT fall back to
 *    another agent, because a full screen is a claim about which agent you are
 *    looking at;
 *  - **ownership**: `unknown` is not a shade of `foreign`. While the owner
 *    service restarts, every agent arrives unknown, and rendering that as
 *    foreign states "the framework does not hold it" about agents it does.
 */
import { describe, expect, it } from 'vitest'

import { resolveFocus, resolveLogs, resolveTerminals } from '../../src/lib/fleetViewState'
import { cardClasses, ownershipOf } from '../../src/lib/fleetCardStyle'

describe('several terminals may be open at once', () => {
  it('keeps every remembered label that is still attachable', () => {
    expect(resolveTerminals({ terminals: ['a', 'b'] }, ['a', 'b', 'c'])).toEqual(['a', 'b'])
  })

  /** The memory says what to SHOW; it never says what exists. */
  it('drops a label whose agent is gone rather than rendering a dead pane', () => {
    expect(resolveTerminals({ terminals: ['a', 'gone'] }, ['a'])).toEqual(['a'])
  })

  it('reads a pre-upgrade single terminal as one open terminal', () => {
    expect(resolveTerminals({ terminal: 'a' }, ['a'])).toEqual(['a'])
  })

  /**
   * The load-bearing negative of the migration. An explicit empty list means
   * *I closed them all*; falling back to the legacy key there would reopen a
   * terminal the reader deliberately closed.
   */
  it('an explicit empty list outranks the legacy single label', () => {
    expect(resolveTerminals({ terminals: [], terminal: 'a' }, ['a'])).toEqual([])
  })

  it('treats a deliberate close in the old shape as nothing open', () => {
    expect(resolveTerminals({ terminal: null }, ['a'])).toEqual([])
  })

  it('does not open the same terminal twice from a duplicated memory', () => {
    expect(resolveTerminals({ terminals: ['a', 'a'] }, ['a'])).toEqual(['a'])
  })

  it('opens nothing when nothing is attachable, whatever is remembered', () => {
    expect(resolveTerminals({ terminals: ['a', 'b'] }, [])).toEqual([])
  })
})

describe('one agent alone on the panel', () => {
  it('shows the remembered agent when it is still there', () => {
    expect(resolveFocus({ focus: 7 }, [5, 7])).toBe(7)
  })

  /**
   * The refuted alternative: "fall back to the nearest live agent". It would
   * put a different session under a heading the reader trusts — the same class
   * as a binding guessed rather than recorded.
   */
  it('goes back to the grid when the remembered agent is gone — never substitutes another', () => {
    expect(resolveFocus({ focus: 7 }, [5, 9])).toBeNull()
    expect(resolveFocus({ focus: 7 }, [])).toBeNull()
  })

  it('is off until it is asked for', () => {
    expect(resolveFocus({}, [5])).toBeNull()
    expect(resolveFocus({ focus: null }, [5])).toBeNull()
  })
})

describe('which logs are open', () => {
  it('keeps every remembered log whose agent is still running', () => {
    expect(resolveLogs({ logs: [1, 2] }, [1, 2, 3], null)).toEqual([1, 2])
  })

  /**
   * Added after a mutation run that this file did NOT catch: dropping the
   * liveness filter changed nothing any test could see, because no fixture had
   * an agent disappear. A log left open for an agent that is gone would poll a
   * pid nobody holds and render its last answer as current.
   */
  it('drops a log whose agent is gone rather than leaving it on screen', () => {
    expect(resolveLogs({ logs: [1, 99] }, [1], null)).toEqual([1])
    expect(resolveLogs({ logs: [99] }, [1], null)).toEqual([])
  })

  it('opens the enlarged tile’s log while no choice has been made', () => {
    expect(resolveLogs({}, [1, 2], 1)).toEqual([1])
    expect(resolveLogs({}, [1, 2], null)).toEqual([])
  })

  /** An explicit empty list is a choice: closed stays closed. */
  it('an explicit empty list outranks the enlarged default', () => {
    expect(resolveLogs({ logs: [] }, [1, 2], 1)).toEqual([])
  })

  it('does not open one twice from a duplicated memory', () => {
    expect(resolveLogs({ logs: [1, 1] }, [1], null)).toEqual([1])
  })
})

describe('ownership is visible on the tile, and unknown is its own answer', () => {
  const ours = { population: 'started-here', terminal_label: 'set-core-1' }
  const foreign = { population: 'foreign', terminal_label: null }

  it('reads ownership from the same source the terminal offer uses', () => {
    expect(ownershipOf(ours, true)).toBe('ours')
    expect(ownershipOf(foreign, true)).toBe('foreign')
  })

  /**
   * Corrected while writing: an agent the producer MEASURED as `started-here`
   * stays ours even while the owner service is unreachable — the population is
   * the measurement and `owner_reachable` only explains an absent one. What
   * resolves to unknown is an agent whose population was never reported, and
   * the reason then names which of the two silences it was.
   */
  it('says unknown for an agent whose population was never reported', () => {
    expect(ownershipOf({ terminal_label: null }, false)).toBe('unknown')
    expect(ownershipOf({ terminal_label: null }, true)).toBe('unknown')
  })

  it('keeps a measured `started-here` ours even while the owner is unreachable', () => {
    expect(ownershipOf(ours, false)).toBe('ours')
  })

  it('calls a `started-here` with no address unknown, not ours — a contradiction is not a fact', () => {
    expect(ownershipOf({ population: 'started-here', terminal_label: null }, true)).toBe('unknown')
  })

  /**
   * The defect the tiles actually had, and it is measured rather than
   * aesthetic: `--color-surface-line` and `--color-surface-raised` are both
   * `neutral-800`, so a border painted with `surface-line` is invisible against
   * the surface it bounds. Task 7.17 found it in the project column; the agent
   * tiles kept it.
   */
  it('never bounds a tile with the token that aliases the fill', () => {
    for (const o of ['ours', 'foreign', 'unknown'] as const) {
      expect(cardClasses(o)).not.toMatch(/\bborder-surface-line\b/)
    }
  })

  /**
   * Rewritten after a mutation run, and the correction is the finding: the
   * first version compared the three whole class strings and passed on a build
   * where every tile had the SAME edge — because the FILL also differs, so the
   * strings differed for a reason that has nothing to do with the assertion.
   * The check verified that three strings are three strings; it was silent
   * about the edge, which is the thing the reader sees.
   */
  it('gives ours a solid edge and the two non-ours a dashed one', () => {
    expect(cardClasses('ours')).not.toMatch(/border-dashed/)
    expect(cardClasses('foreign')).toMatch(/border-dashed/)
    expect(cardClasses('unknown')).toMatch(/border-dashed/)
  })

  it('separates unknown from foreign by colour, not only by dashes', () => {
    expect(cardClasses('unknown')).toMatch(/amber/)
    expect(cardClasses('foreign')).not.toMatch(/amber/)
  })

  it('fills only the tiles the framework holds', () => {
    expect(cardClasses('ours')).toMatch(/bg-surface-raised/)
    expect(cardClasses('foreign')).toMatch(/bg-transparent/)
  })

  /**
   * `ui-quality.md`: one visual weight per meaning. Red is *broken* on this
   * screen and a foreign agent is not broken — it is the ordinary case.
   */
  it('spends no red on ownership', () => {
    for (const o of ['ours', 'foreign', 'unknown'] as const) {
      expect(cardClasses(o)).not.toMatch(/red/)
    }
  })

  it('marks where the keyboard is, and only there', () => {
    expect(cardClasses('ours', { typing: true })).toMatch(/ring/)
    expect(cardClasses('ours', {})).not.toMatch(/ring/)
    expect(cardClasses('foreign', { typing: true })).toMatch(/ring/)
  })
})
