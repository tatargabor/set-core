/**
 * The per-agent stage strip, on screen — NUMBERED CIRCLES since 2026-08-30.
 *
 * The user asked for *"little circles like 1-2-3-4-5-6-7 where 1 is the start
 * and the last is the final — more representative than just the name"*. So the
 * DOM contract is: one numbered circle per flow stage, in declared order,
 * connected; the current stage's name rendered AFTER the circles (nothing
 * load-bearing on hover); every circle carrying its stage name on title.
 * Every assertion here reads the DOM: numbers, states, connectors, the
 * current name, the empty state NOT reading like a failure, the stray carried.
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

const circles = () =>
  Array.from(screen.getByTestId('fleet-stage-strip').querySelectorAll('[data-stage-chip]'))
    .map(el => ({
      name: el.getAttribute('data-stage-chip'),
      index: Number(el.getAttribute('data-stage-index')),
      state: el.getAttribute('data-stage-state'),
    }))

describe('the mid-flow agent reads at a glance', () => {
  it('numbers the circles from 1, in declared order', () => {
    render(<AgentStageStrip stage={stage({ position: 'apply' })} />)
    expect(circles().map(c => c.index)).toEqual([1, 2, 3, 4, 5])
    expect(circles().map(c => c.name)).toEqual(FLOW)
  })

  it('marks done / running / pending per position', () => {
    render(<AgentStageStrip stage={stage({ position: 'apply' })} />)
    expect(circles().map(c => c.state)).toEqual(
      ['done', 'done', 'running', 'pending', 'pending'])
  })

  it('renders the CURRENT stage name after the circles — no hover needed', () => {
    render(<AgentStageStrip stage={stage({ position: 'apply' })} />)
    expect(screen.getByTestId('fleet-stage-current').textContent).toBe('apply')
  })

  it('every circle carries its stage name', () => {
    render(<AgentStageStrip stage={stage({ position: 'proposal' })} />)
    for (const el of screen.getByTestId('fleet-stage-strip').querySelectorAll('[data-stage-chip]')) {
      expect(el.getAttribute('title')).toContain(el.getAttribute('data-stage-chip'))
    }
  })

  it('connects the circles, so it reads as a pipeline', () => {
    render(<AgentStageStrip stage={stage({ position: 'apply' })} />)
    const strip = screen.getByTestId('fleet-stage-strip')
    expect(strip.querySelectorAll('span[aria-hidden]').length).toBe(FLOW.length - 1)
  })

  it('renders a declared flow that is not the OpenSpec one, in the declared order', () => {
    render(<AgentStageStrip stage={stage({
      flow: ['triage', 'fixing', 'shipping'], position: 'shipping', source: 'declared',
    })} />)
    expect(circles().map(c => c.name)).toEqual(['triage', 'fixing', 'shipping'])
    expect(circles().map(c => c.state)).toEqual(['done', 'done', 'running'])
    expect(screen.getByTestId('fleet-stage-strip').getAttribute('data-fleet-stage-source')).toBe('declared')
    expect(screen.getByTestId('fleet-stage-current').textContent).toBe('shipping')
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
    const states = circles()
    // No declared stage is "running" — the agent is not IN the declared flow —
    // and the stray is spelled out after the circles.
    expect(states.every(c => c.state !== 'running')).toBe(true)
    expect(screen.getByTestId('fleet-stage-current').textContent).toContain('weird')
    expect(states.map(c => c.name)).toEqual(FLOW)
  })
})

describe('nothing rendered when there is nothing to say', () => {
  it('renders nothing for an agent whose payload predates the field', () => {
    const { container } = render(<AgentStageStrip stage={undefined} />)
    expect(container.querySelector('[data-testid="fleet-stage-strip"]')).toBeNull()
  })
})
