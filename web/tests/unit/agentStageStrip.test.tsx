/**
 * The per-agent stage strip, on screen.
 *
 * Every assertion here is about something PRESENT and distinguishable, read
 * from the DOM: done / running / pending as three classes on real chips, the
 * empty state NOT reading like a failure, a failure NOT reading like calm,
 * the stray carried and marked. An assertion that nothing threw would pass
 * against a strip that renders nothing at all.
 */

import { describe, it, expect, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'

import { AgentStageStrip } from '../../src/components/AgentStageStrip'
import type { FleetAgent } from '../../src/lib/fleetTypes'

afterEach(() => { cleanup() })

const FLOW = ['proposal', 'design', 'apply', 'verify', 'archive']

const stage = (over: Partial<NonNullable<FleetAgent['stage']>>): NonNullable<FleetAgent['stage']> => ({
  state: 'resolved', flow: FLOW, position: 'apply', reason: null, source: 'derived', outside: false,
  ...over,
})

const chipStates = () =>
  Array.from(screen.getByTestId('fleet-stage-strip').querySelectorAll('[data-stage-chip]'))
    .map(el => [el.getAttribute('data-stage-chip'), el.getAttribute('data-stage-state')])

describe('the mid-flow agent reads at a glance', () => {
  it('renders done / running / pending per position, in flow order', () => {
    render(<AgentStageStrip stage={stage({ position: 'apply' })} />)
    expect(chipStates()).toEqual([
      ['proposal', 'done'], ['design', 'done'], ['apply', 'running'],
      ['verify', 'pending'], ['archive', 'pending'],
    ])
  })

  it('renders every stage of the flow, including the ones not reached', () => {
    render(<AgentStageStrip stage={stage({ position: 'proposal' })} />)
    expect(chipStates().map(c => c[0])).toEqual(FLOW)
    expect(chipStates()[0]).toEqual(['proposal', 'running'])
  })

  it('renders a declared flow that is not the OpenSpec one, in the declared order', () => {
    render(<AgentStageStrip stage={stage({
      flow: ['triage', 'fixing', 'shipping'], position: 'shipping', source: 'declared',
    })} />)
    expect(chipStates()).toEqual([
      ['triage', 'done'], ['fixing', 'done'], ['shipping', 'running'],
    ])
    expect(screen.getByTestId('fleet-stage-strip').getAttribute('data-fleet-stage-source')).toBe('declared')
  })
})

describe('the empty state and the gap are different sentences', () => {
  it('renders nothing-started as the EMPTY state — quiet, not amber', () => {
    render(<AgentStageStrip stage={stage({
      state: 'gap', position: null, reason: 'nothing-started',
    })} />)
    expect(screen.getByTestId('fleet-stage-empty')).toBeTruthy()
    expect(screen.queryByTestId('fleet-stage-gap')).toBeNull()
  })

  it('renders a resolution failure as a marked gap, with its reason', () => {
    render(<AgentStageStrip stage={stage({
      state: 'gap', position: null, reason: 'join-failed',
    })} />)
    expect(screen.getByTestId('fleet-stage-gap').getAttribute('data-fleet-stage-reason')).toBe('join-failed')
    expect(screen.queryByTestId('fleet-stage-empty')).toBeNull()
  })

  it('renders no-flow as a gap too, and never as calm', () => {
    render(<AgentStageStrip stage={stage({
      state: 'gap', flow: null, position: null, reason: 'no-flow', source: null,
    })} />)
    expect(screen.getByTestId('fleet-stage-gap').getAttribute('data-fleet-stage-reason')).toBe('no-flow')
  })
})

describe('the stray is carried and marked', () => {
  it('shows a value outside the flow beside the full flow, dropping neither', () => {
    render(<AgentStageStrip stage={stage({
      position: 'weird', outside: true,
    })} />)
    const states = chipStates()
    expect(states.filter(c => c[1] === 'outside')).toEqual([['weird', 'outside']])
    // The full declared flow is still there — five declared chips plus the stray.
    expect(states.filter(c => c[0] !== 'weird').map(c => c[0])).toEqual(FLOW)
  })
})

describe('nothing rendered when there is nothing to say', () => {
  it('renders nothing for an agent whose payload predates the field', () => {
    const { container } = render(<AgentStageStrip stage={undefined} />)
    expect(container.querySelector('[data-fleet-stage-strip]')).toBeNull()
  })
})
