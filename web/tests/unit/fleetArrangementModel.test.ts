/**
 * The arrangement, as a model — D-2's two-level manual ordering.
 *
 * These are here rather than in the component test because a drag cannot be
 * asserted without a layout engine, but the RESULT of one can, and the result is
 * where the damage would be. Three of the tests below guard against silent data
 * loss rather than against a wrong pixel; the fourth guards against a rule
 * re-evaluating itself, which is the failure the user explicitly asked to be
 * designed out.
 */
import { describe, expect, it } from 'vitest'

import {
  type FleetArrangement,
  arrangedNames,
  assign,
  createGroup,
  forgetMissing,
  fromResponse,
  moveProject,
  moveWithin,
  orphans,
  removeGroup,
  seedCandidates,
  toPutBody,
} from '../../src/lib/fleetLayout'

const RESPONSE = {
  version: 7,
  groups: [
    { id: 'g-set', name: 'set-*', collapsed: false, projects: ['set-core', 'set-designer'], missing: ['set-gone'] },
    { id: 'g-work', name: 'munka', collapsed: true, projects: ['itline-web'], missing: [] },
  ],
  parked: ['blackbelt-web'],
  ungrouped: ['deckforge', 'veleje'],
  // Group missings first, then the parked ones — the shape `apply_to` produces.
  missing: ['set-gone', 'parked-gone'],
}

const base = (): FleetArrangement => fromResponse(RESPONSE)

describe('reading the API answer', () => {
  it('separates a parked project that is gone from a grouped one that is gone', () => {
    const a = base()
    expect(a.groups[0].missing).toEqual(['set-gone'])
    // Derived by subtraction, because the API reports the parked remainder only
    // inside the flat `missing` list. Getting this wrong would file a vanished
    // parked project under no section at all, which is the silence the whole
    // `missing` mechanism exists to prevent.
    expect(a.parkedMissing).toEqual(['parked-gone'])
    expect(a.version).toBe(7)
  })

  it('survives an answer that is missing every optional field', () => {
    const a = fromResponse({})
    expect(a.groups).toEqual([])
    expect(a.version).toBe(0)
    expect(fromResponse(null).ungrouped).toEqual([])
  })
})

describe('a save must not forget what discovery could not find', () => {
  it('sends missing members back, so replacing the document does not erase them', () => {
    const body = toPutBody(base())
    expect(body.groups[0].projects).toContain('set-gone')
    expect(body.parked).toContain('parked-gone')
  })

  /**
   * The wrong implementation, held in a test.
   *
   * Sending `group.projects` straight back is the obvious code, it type-checks,
   * and every screen it produces looks tidier than the correct one — the missing
   * row simply stops appearing. Recording the refuted version is worth more than
   * the corrected number: without this, a later simplification back to
   * `projects: g.projects` reads as a cleanup and quietly deletes user data.
   */
  it('a body built from the joined `projects` alone would have dropped the name', () => {
    const a = base()
    const naive = a.groups.map(g => ({ ...g, projects: g.projects }))
    expect(naive[0].projects).not.toContain('set-gone')
    expect(toPutBody(a).groups[0].projects).toContain('set-gone')
  })

  it('carries the version that was read, which is what makes a stale write refusable', () => {
    expect(toPutBody(base()).base_version).toBe(7)
  })

  it('forgetting a missing project is what removes it — and only that', () => {
    const a = forgetMissing(base(), 'set-gone')
    expect(toPutBody(a).groups[0].projects).not.toContain('set-gone')
    expect(toPutBody(a).groups[0].projects).toEqual(['set-core', 'set-designer'])
  })
})

describe('ordering', () => {
  it('moves an element and leaves the rest in order', () => {
    expect(moveWithin(['a', 'b', 'c'], 0, 2)).toEqual(['b', 'c', 'a'])
    expect(moveWithin(['a', 'b', 'c'], 2, 0)).toEqual(['c', 'a', 'b'])
  })

  it('is a no-op outside the list, because a drag can end anywhere', () => {
    expect(moveWithin(['a', 'b'], 0, 5)).toEqual(['a', 'b'])
    expect(moveWithin(['a', 'b'], -1, 0)).toEqual(['a', 'b'])
    expect(moveWithin(['a', 'b'], 1, 1)).toEqual(['a', 'b'])
  })

  it('reorders inside one group and touches no other group', () => {
    const a = moveProject(base(), 'g-set', 1, 0)
    expect(a.groups[0].projects).toEqual(['set-designer', 'set-core'])
    expect(a.groups[1].projects).toEqual(['itline-web'])
    expect(a.ungrouped).toEqual(['deckforge', 'veleje'])
  })
})

describe('membership is an explicit act, and a project has exactly one home', () => {
  it('moving a project into another group removes it from the first', () => {
    const a = assign(base(), 'set-core', { kind: 'group', id: 'g-work' })
    expect(a.groups[0].projects).toEqual(['set-designer'])
    expect(a.groups[1].projects).toEqual(['itline-web', 'set-core'])
    // The invariant, asserted as a count rather than by reading two lists: a
    // project in two places renders twice and its position then depends on
    // iteration order.
    expect(arrangedNames(a).filter(n => n === 'set-core')).toHaveLength(1)
  })

  it('parking removes it from its group, and unparking returns it to the ungrouped tail', () => {
    const parked = assign(base(), 'set-core', { kind: 'parked' })
    expect(parked.parked).toContain('set-core')
    expect(parked.groups[0].projects).toEqual(['set-designer'])

    const back = assign(parked, 'set-core', { kind: 'ungrouped' })
    expect(back.parked).not.toContain('set-core')
    expect(back.ungrouped).toContain('set-core')
    expect(arrangedNames(back).filter(n => n === 'set-core')).toHaveLength(1)
  })

  it('a target group that does not exist leaves the project ungrouped, never nowhere', () => {
    const a = assign(base(), 'deckforge', { kind: 'group', id: 'g-nope' })
    expect(a.ungrouped).toContain('deckforge')
    expect(arrangedNames(a)).toContain('deckforge')
  })

  it('deleting a group moves its members out instead of deleting them', () => {
    const a = removeGroup(base(), 'g-set')
    expect(a.groups.map(g => g.id)).toEqual(['g-work'])
    expect(a.ungrouped).toContain('set-core')
    expect(a.ungrouped).toContain('set-designer')
    // Including the one discovery could not find: a deletion must not be a back
    // door to the loss `toPutBody` exists to prevent.
    expect(toPutBody(a).parked).toContain('set-gone')
  })
})

describe('a prefix seeds a group once; it is never a rule', () => {
  it('shows what it would take before it takes it', () => {
    expect(seedCandidates(base(), 'set-')).toEqual(['set-core', 'set-designer'])
    expect(seedCandidates(base(), '')).toEqual([])
  })

  /**
   * The whole point of the decision, and the assertion that proves the wrong
   * implementation was not shipped. A prefix RULE would re-evaluate: a project
   * discovered later whose name happens to start with `set-` would land in a
   * group nobody put it in, and renaming a project would move it silently.
   */
  it('a project discovered afterwards does not join, because nothing re-evaluates', () => {
    const seeded = createGroup(base(), 'set-csoport', seedCandidates(base(), 'set-'))
    const group = seeded.groups.find(g => g.name === 'set-csoport')!
    expect(group.projects).toEqual(['set-core', 'set-designer'])

    // The next answer from discovery holds a new `set-` project.
    const later = { ...seeded, ungrouped: [...seeded.ungrouped, 'set-uj'] }
    const stillTheSame = later.groups.find(g => g.name === 'set-csoport')!
    expect(stillTheSame.projects).not.toContain('set-uj')
    // And what persists carries no prefix at all — there is nothing to re-run.
    // Asserted as the WHOLE key set rather than as "has no `prefix` key": a
    // stored rule could arrive under any name, and an absence check names only
    // the one name somebody thought of.
    // `order` joined this list on 2026-08-19 and is not a rule: it is the stored
    // membership sequence, which is the very thing "membership is a stored fact"
    // means. The assertion stays a WHOLE key set rather than a per-name absence
    // check, because a stored rule could arrive under any name and an absence
    // check names only the one name somebody thought of.
    expect(Object.keys(stillTheSame).sort()).toEqual(['collapsed', 'id', 'missing', 'name', 'order', 'projects'])
    expect(Object.keys(toPutBody(later).groups[0]).sort()).toEqual(['collapsed', 'id', 'name', 'projects'])
  })
})

describe('a discovered project the arrangement places nowhere', () => {
  it('is reported rather than rendered nowhere', () => {
    expect(orphans(base(), ['set-core', 'deckforge', 'brand-new'])).toEqual(['brand-new'])
  })

  it('is empty when every discovered project has a home, including a parked one', () => {
    expect(orphans(base(), ['set-core', 'set-designer', 'itline-web', 'blackbelt-web', 'deckforge', 'veleje']))
      .toEqual([])
  })
})
