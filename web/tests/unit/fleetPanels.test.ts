/**
 * Panel kinds — declared, and what happens when this build does not have one.
 *
 * The whole file is about one asymmetry. A panel kind this build KNOWS is
 * uninteresting: it renders. A panel kind it does NOT know has three possible
 * outcomes, and two of them are defects that look like working software:
 *
 *  - drop it            → false absence. The reader concludes they closed
 *                         something they never closed, and stops looking.
 *  - render it as agent → false value. An empty tile that claims to be an agent.
 *  - report it          → the only honest one, and the one this asserts.
 */
import { describe, expect, it } from 'vitest'
import {
  KNOWN_PANEL_KINDS, PANEL_AGENT, isPanelRef, renderablePanels, resolvePanel,
  resolvePanels, unrenderablePanels,
} from '../../src/lib/fleetPanels'

describe('a panel kind', () => {
  it('resolves when this build has it', () => {
    const r = resolvePanel({ kind: PANEL_AGENT, id: 'a-label' })
    expect(r.known).toBe(true)
  })

  it('is reported — with the kind NAMED — when this build does not', () => {
    // "Something is missing" is not a report. The kind is what makes it
    // actionable: it says which build, or which feature, is absent.
    const r = resolvePanel({ kind: 'changes', id: 'x' })
    expect(r.known).toBe(false)
    if (!r.known) expect(r.reason).toContain('changes')
  })

  it('the agent terminal is one kind among several, not the implicit whole', () => {
    // The registry existing at all is the assertion here: before this, "panel"
    // and "agent terminal" were the same word, and a second kind could not be
    // expressed.
    expect(KNOWN_PANEL_KINDS).toContain(PANEL_AGENT)
  })
})

describe('what counts as a panel reference', () => {
  it('rejects entries that are not usable, rather than filling in a guess', () => {
    expect(isPanelRef(null)).toBe(false)
    expect(isPanelRef('agent')).toBe(false)
    expect(isPanelRef({ kind: 'agent' })).toBe(false)
    expect(isPanelRef({ id: 'x' })).toBe(false)
    expect(isPanelRef({ kind: '', id: 'x' })).toBe(false)
    expect(isPanelRef({ kind: 'agent', id: '' })).toBe(false)
    expect(isPanelRef({ kind: 'agent', id: 'x' })).toBe(true)
  })
})

describe('resolving a stored view', () => {
  it('reads the older kind-less shape as agent panels', () => {
    // A memory written before panels had kinds holds bare labels, and those
    // meant agents. Refusing to read them would empty every existing reader's
    // screen on upgrade.
    const out = resolvePanels({ terminals: ['one', 'two'] })
    expect(out.map(r => r.ref)).toEqual([
      { kind: PANEL_AGENT, id: 'one' },
      { kind: PANEL_AGENT, id: 'two' },
    ])
    expect(out.every(r => r.known)).toBe(true)
  })

  it('keeps ONE ordered list, old shape first, rather than two lanes', () => {
    // Two lists rendered separately can disagree about order, and the
    // disagreement changes with whichever happens to be read first.
    const out = resolvePanels({
      terminals: ['old'],
      panels: [{ kind: PANEL_AGENT, id: 'new' }],
    })
    expect(out.map(r => r.ref.id)).toEqual(['old', 'new'])
  })

  it('does not list the same panel twice when both shapes name it', () => {
    const out = resolvePanels({
      terminals: ['same'],
      panels: [{ kind: PANEL_AGENT, id: 'same' }],
    })
    expect(out).toHaveLength(1)
  })

  it('keeps an unknown kind in the list instead of dropping it', () => {
    // The defect this whole module exists to prevent. `resolvePanels` returning
    // only what it can render would be indistinguishable from a clean screen.
    const out = resolvePanels({ panels: [{ kind: 'not-built-yet', id: 'x' }] })
    expect(out).toHaveLength(1)
    expect(out[0].known).toBe(false)
  })

  it('drops entries that are not panel references at all', () => {
    // Corruption, not preference: a hand-edited or truncated store. Unlike an
    // unknown KIND, there is nothing here to report — no kind, no id, nothing a
    // reader could act on.
    const out = resolvePanels({ panels: [null, 42, { kind: 'agent' }, 'agent'] })
    expect(out).toEqual([])
  })

  it('treats an absent view as no panels rather than throwing', () => {
    expect(resolvePanels(null)).toEqual([])
    expect(resolvePanels(undefined)).toEqual([])
    expect(resolvePanels({})).toEqual([])
  })
})

describe('splitting the resolved list', () => {
  const resolved = resolvePanels({
    terminals: ['agent-one'],
    panels: [{ kind: 'future-view', id: 'v1' }, { kind: PANEL_AGENT, id: 'agent-two' }],
  })

  it('hands the renderable ones over unwrapped', () => {
    expect(renderablePanels(resolved).map(r => r.id)).toEqual(['agent-one', 'agent-two'])
  })

  it('names the unrenderable ones as their own list, not by subtraction', () => {
    // Stated rather than derived, for the same reason `parked_missing` is on the
    // server: an inference standing in for data is where a wrong answer looks
    // like a computed one.
    const unknown = unrenderablePanels(resolved)
    expect(unknown).toHaveLength(1)
    expect(unknown[0].ref.kind).toBe('future-view')
  })

  it('the two lists together account for every stored panel', () => {
    expect(renderablePanels(resolved).length + unrenderablePanels(resolved).length)
      .toBe(resolved.length)
  })
})

describe('the registry stays domain-free — task 4.4', () => {
  it('is exactly this list, so adding a kind is a decision and not a drift', () => {
    // A change-detector on purpose, and this is the case where one earns its
    // keep: the constraint it protects cannot be expressed as a pattern. The
    // framework layer may know that a view EXISTS; it may never know what the
    // view lists, because that is the consumer's domain and the abstraction is
    // the whole point. No string test can tell "changes" (a framework word from
    // the consumer contract) from an order number or a partner name — a person
    // has to look. Failing here is the prompt to look.
    expect([...KNOWN_PANEL_KINDS]).toEqual(['agent'])
  })

  it('an unknown kind is carried as data, never executed or interpolated anywhere but a message', () => {
    // A stored kind is attacker-adjacent input in the mildest sense: it comes
    // from a file a person can edit. It reaches exactly one place — the text of
    // a report — and this asserts the shape of that, so a future change that
    // starts keying behaviour off an arbitrary stored string has to say so.
    const r = resolvePanel({ kind: '<script>', id: 'x' })
    expect(r.known).toBe(false)
    if (!r.known) expect(r.reason).toContain('<script>')
  })
})
