/**
 * The per-project view memory — the decisions behind AC-110, AC-113 and AC-114.
 *
 * `resolveEnlarged` carries a docstring saying *"the whole rule in one place so
 * the two halves cannot drift apart"*, and until now nothing tested it. The
 * rule it holds has three parts that pull against each other, which is exactly
 * the shape that rots quietly:
 *
 *  - a remembered choice WINS, including the choice to have nothing enlarged;
 *  - a remembered pid that is not alive is discarded, never rendered;
 *  - only with no choice at all does the single-agent default apply.
 *
 * The second and third interact: a remembered pid that died falls back to the
 * default rather than to `null`, which is deliberate and is the part a reader
 * would most likely "simplify" away.
 *
 * The round trip through `localStorage` is here too, because *per project* is
 * half the requirement and a resolver cannot see it: a memory that resolved
 * perfectly and was stored under one shared key would satisfy every test about
 * the rule and none about the requirement.
 */
import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import {
  VIEW_KEY_FOR_TESTS,
  readView,
  resolveEnlarged,
  writeView,
} from '../../src/lib/fleetViewState'

beforeEach(() => { localStorage.clear() })
afterEach(() => { localStorage.clear() })

describe('AC-113 — a project holding one agent opens enlarged', () => {
  it('enlarges the only agent when no choice has been made', () => {
    expect(resolveEnlarged({}, [7])).toBe(7)
  })

  /** With more than one there is a grid, and a grid needs no default. */
  it('enlarges nothing when there is more than one', () => {
    expect(resolveEnlarged({}, [7, 8])).toBeNull()
  })

  it('enlarges nothing when there is nobody', () => {
    expect(resolveEnlarged({}, [])).toBeNull()
  })
})

describe('AC-114 — a remembered choice outranks the default', () => {
  /**
   * The load-bearing one, and the reason `null` is stored explicitly instead of
   * the key being deleted. A reader who closed the only tile must not have it
   * reopened on their next visit — `undefined` (no choice yet) and `null`
   * (chose to close) are different states, and collapsing them is the
   * absent-key-is-not-an-empty-value defect this screen refuses everywhere.
   */
  it('stays collapsed when the single tile was deliberately closed', () => {
    expect(resolveEnlarged({ enlarged: null }, [7])).toBeNull()
  })

  it('keeps a remembered tile that is still there', () => {
    expect(resolveEnlarged({ enlarged: 8 }, [7, 8])).toBe(8)
  })

  /**
   * A remembered pid that died does NOT become an empty enlarged tile — AC-111
   * from the resolver's side. It falls back to the single-agent default rather
   * than to nothing, which is the part most likely to be "simplified" into
   * `null` by someone reading only the first clause.
   */
  it('discards a remembered agent that is gone, and falls back rather than blanking', () => {
    expect(resolveEnlarged({ enlarged: 99 }, [7, 8])).toBeNull()
    expect(resolveEnlarged({ enlarged: 99 }, [7])).toBe(7)
  })
})

describe('AC-110 — the memory is PER PROJECT, and it survives leaving', () => {
  it('gives each project back its own view', () => {
    writeView('alpha', { enlarged: 1 })
    writeView('beta', { enlarged: 2 })
    expect(readView('alpha').enlarged).toBe(1)
    expect(readView('beta').enlarged).toBe(2)
  })

  /**
   * The requirement's own sentence, performed: select, enlarge, go away, come
   * back. "Going away" is reading another project's view — the act that would
   * clobber a shared key.
   */
  it('restores the enlarged tile after visiting another project', () => {
    writeView('alpha', { enlarged: 5 })
    writeView('beta', { enlarged: 6 })
    readView('beta')
    expect(resolveEnlarged(readView('alpha'), [5, 9])).toBe(5)
  })

  /**
   * ⚠ Holds the WRONG shape, so a later "simplification" to one shared key
   * fails instead of looking identical. Without this, every test above passes
   * on a build that remembers exactly one project at a time — the resolver
   * would be right and the requirement broken.
   */
  it('does not keep one shared view for every project', () => {
    writeView('alpha', { enlarged: 1 })
    writeView('beta', { enlarged: 2 })
    const stored = JSON.parse(localStorage.getItem(VIEW_KEY_FOR_TESTS) ?? '{}')
    expect(Object.keys(stored).sort()).toEqual(['alpha', 'beta'])
  })

  /** Writing one field leaves the rest of that project's view alone. */
  it('merges into a project’s view rather than replacing it', () => {
    writeView('alpha', { enlarged: 1 })
    writeView('alpha', { columns: 3 })
    expect(readView('alpha')).toMatchObject({ enlarged: 1, columns: 3 })
  })

  /**
   * A project nobody has looked at yet has no view — and that must read as *no
   * choice*, not as *closed*, or the single-agent default would never fire on a
   * first visit.
   */
  it('reports no choice for a project never visited', () => {
    expect(readView('never-seen').enlarged).toBeUndefined()
    expect(resolveEnlarged(readView('never-seen'), [4])).toBe(4)
  })
})
