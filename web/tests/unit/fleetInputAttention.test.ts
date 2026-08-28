/**
 * The input-wait escalation, decided in one place.
 *
 * These are the numbers the user asked for on 2026-08-28 — notice at 15 s,
 * shout at 3 min — and they exist twice by necessity: the server owns them, the
 * client re-resolves the tone every render because the wait grows between polls.
 * Twice is why the last test in this file exists.
 */
import { describe, expect, it } from 'vitest'
import {
  ATT_BACKGROUND, ATT_INPUT, ATT_PROMPT, ATT_UNMEASURED, ATT_WORKING,
  EMPTY_TALLY, INPUT_WAIT_AMBER_SECONDS, INPUT_WAIT_RED_SECONDS,
  inputWaitTone, tally, waitsForAPerson, worstInputWait,
  type AttentionAgent,
} from '../../src/lib/fleetAttention'

const agent = (over: Partial<AttentionAgent> = {}): AttentionAgent => ({
  pid: 1, state: 'quiet', ...over,
})

describe('inputWaitTone', () => {
  it('marks nothing below the first threshold', () => {
    expect(inputWaitTone(0)).toBe('plain')
    expect(inputWaitTone(9)).toBe('plain')
  })

  it('is amber from 15 seconds and red from 3 minutes', () => {
    // LITERAL seconds, not the constants. A boundary test phrased in terms of
    // the constant it checks asserts the mechanism and is silent about the
    // result — moving the thresholds would leave it green.
    expect(inputWaitTone(14.9)).toBe('plain')
    expect(inputWaitTone(15)).toBe('amber')
    expect(inputWaitTone(45)).toBe('amber')
    expect(inputWaitTone(179.9)).toBe('amber')
    expect(inputWaitTone(180)).toBe('red')
    expect(inputWaitTone(400)).toBe('red')
  })

  it('has no tone for an unmeasured wait, rather than the calmest one', () => {
    expect(inputWaitTone(null)).toBeNull()
    expect(inputWaitTone(undefined)).toBeNull()
    expect(inputWaitTone(Number.NaN)).toBeNull()
  })

  it('prefers the thresholds the server sent over its own fallbacks', () => {
    const server = { amber_seconds: 30, red_seconds: 300 }
    expect(inputWaitTone(20, server)).toBe('plain')
    expect(inputWaitTone(40, server)).toBe('amber')
    expect(inputWaitTone(310, server)).toBe('red')
  })

  it('falls back cleanly when the envelope carries a partial or absent table', () => {
    expect(inputWaitTone(20, null)).toBe('amber')
    expect(inputWaitTone(20, {})).toBe('amber')
    expect(inputWaitTone(20, { amber_seconds: null, red_seconds: null })).toBe('amber')
  })
})

describe('who is actually waiting', () => {
  it('counts input and prompt, and never background', () => {
    expect(waitsForAPerson(agent({ attention: ATT_INPUT }))).toBe(true)
    expect(waitsForAPerson(agent({ attention: ATT_PROMPT }))).toBe(true)
    // The whole point of the axis: a turn that ended while a command runs in
    // the background is waiting for nobody, and looks identical from the log.
    expect(waitsForAPerson(agent({ attention: ATT_BACKGROUND }))).toBe(false)
    expect(waitsForAPerson(agent({ attention: ATT_WORKING }))).toBe(false)
    expect(waitsForAPerson(agent({ attention: ATT_UNMEASURED }))).toBe(false)
    expect(waitsForAPerson(agent())).toBe(false)
  })
})

describe('worstInputWait', () => {
  it('takes the maximum, so one fresh agent cannot vouch for a stopped one', () => {
    expect(worstInputWait([
      agent({ attention: ATT_INPUT, input_wait_seconds: 5 }),
      agent({ attention: ATT_INPUT, input_wait_seconds: 240 }),
    ])).toBe(240)
  })

  it('ignores agents nobody is waiting on, whatever their duration says', () => {
    expect(worstInputWait([
      agent({ attention: ATT_BACKGROUND, input_wait_seconds: 9000 }),
      agent({ attention: ATT_WORKING, input_wait_seconds: 9000 }),
    ])).toBeNull()
  })

  it('is null for an empty set and for a waiting agent with no duration', () => {
    expect(worstInputWait([])).toBeNull()
    expect(worstInputWait([agent({ attention: ATT_INPUT })])).toBeNull()
  })
})

describe('the tally carries the axis without disturbing the states', () => {
  it('counts each class and keeps an unbucketed guard', () => {
    const t = tally([{ name: 'p', agents: [
      agent({ attention: ATT_INPUT, input_wait_seconds: 20 }),
      agent({ attention: ATT_INPUT, input_wait_seconds: 400 }),
      agent({ attention: ATT_PROMPT, input_wait_seconds: 3 }),
      agent({ attention: ATT_BACKGROUND }),
      agent({ attention: 'hibernating' }),
    ] }])
    expect(t.input).toBe(2)
    expect(t.prompt).toBe(1)
    expect(t.background).toBe(1)
    expect(t.attentionUnbucketed).toBe(1)
    expect(t.worstInputWaitSeconds).toBe(400)
  })

  it('treats a server that sends no class as silence, not as a measurement', () => {
    const t = tally([{ name: 'p', agents: [agent(), agent()] }])
    expect(t.attentionUnbucketed).toBe(0)
    expect(t.input).toBe(0)
    expect(t.worstInputWaitSeconds).toBeNull()
    expect(t.agents).toBe(2)
  })

  it('starts from an empty tally that names every counter', () => {
    expect(EMPTY_TALLY.worstInputWaitSeconds).toBeNull()
    expect(EMPTY_TALLY.input + EMPTY_TALLY.prompt + EMPTY_TALLY.background).toBe(0)
  })
})

describe('the two sides carry the same thresholds', () => {
  it('matches the numbers declared in set_orch/fleet/state.py', async () => {
    // Read from the Python source rather than restated here. A second copy of a
    // number is what this test exists to catch, so writing the expected value
    // out would be the defect wearing the test's clothes.
    const fs = await import('node:fs')
    const path = await import('node:path')
    // `import.meta.url` is not a file URL under this runner's transform, so the
    // path is resolved from the working directory (`web/`) instead.
    const src = fs.readFileSync(
      path.resolve(process.cwd(), '..', 'lib/set_orch/fleet/state.py'), 'utf8',
    )
    const amber = src.match(/^INPUT_WAIT_AMBER_SECONDS = ([\d.]+)$/m)
    const red = src.match(/^INPUT_WAIT_RED_SECONDS = ([\d.]+)$/m)
    expect(amber).not.toBeNull()
    expect(red).not.toBeNull()
    expect(Number(amber![1])).toBe(INPUT_WAIT_AMBER_SECONDS)
    expect(Number(red![1])).toBe(INPUT_WAIT_RED_SECONDS)
  })
})
