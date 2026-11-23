/**
 * A foreign agent inside tmux — the one foreign case that leads to an act.
 *
 * Asserted in both directions, per the file next to this one: the tmux offer
 * must appear ONLY where the producer measured a pane, the viewer terminal must
 * open ONLY under the label the producer reports held, and none of it may turn
 * the agent's ownership into "ours" — the viewer is ours, the agent is not.
 */
import { describe, expect, it } from 'vitest'

import { FOREIGN_REASON, terminalOffer } from '../../src/lib/fleetTerminal'
import { ownershipOf } from '../../src/lib/fleetCardStyle'

const foreign = { pid: 4242, population: 'foreign', terminal_label: null }

describe('terminalOffer — foreign inside tmux', () => {
  it('offers a tmux viewer when the producer measured a pane', () => {
    expect(terminalOffer({ ...foreign, tmux: { pane: '%0', viewer: null } }))
      .toEqual({ kind: 'tmux', pid: 4242, pane: '%0' })
  })

  it('stays plainly foreign without a measured pane', () => {
    expect(terminalOffer(foreign)).toEqual({ kind: 'foreign', reason: FOREIGN_REASON })
    expect(terminalOffer({ ...foreign, tmux: null })).toEqual({ kind: 'foreign', reason: FOREIGN_REASON })
  })

  it('opens the viewer under the held label, marked as a viewer', () => {
    expect(terminalOffer({
      ...foreign, terminal_label: 'tmux-desk', tmux: { pane: '%0', viewer: 'tmux-desk' },
    })).toEqual({ kind: 'available', label: 'tmux-desk', via: 'tmux' })
  })

  it('does not open a label the producer did not pair with the viewer', () => {
    // terminal_label and viewer disagree: a contradiction is not an attachable terminal.
    expect(terminalOffer({
      ...foreign, terminal_label: 'someone-else', tmux: { pane: '%0', viewer: 'tmux-desk' },
    }).kind).toBe('tmux')
  })

  it('never offers tmux for a population other than foreign', () => {
    expect(terminalOffer({ pid: 1, population: 'unknown', terminal_label: null,
      tmux: { pane: '%0', viewer: null } }).kind).toBe('unknown')
  })

  it('keeps the agent foreign on the card, viewer or not', () => {
    expect(ownershipOf({ ...foreign, tmux: { pane: '%0', viewer: null } })).toBe('foreign')
    expect(ownershipOf({
      ...foreign, terminal_label: 'tmux-desk', tmux: { pane: '%0', viewer: 'tmux-desk' },
    })).toBe('foreign')
    expect(ownershipOf({ pid: 2, population: 'started-here', terminal_label: 'a' })).toBe('ours')
  })
})
