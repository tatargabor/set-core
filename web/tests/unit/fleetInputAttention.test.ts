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
  EMPTY_TALLY, INPUT_WAIT_AMBER_SECONDS, INPUT_WAIT_PARKED_SECONDS, INPUT_WAIT_RED_SECONDS,
  escalationTone, inputWaitTone, tally, waitsForAPerson, worstInputWait,
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
  it('counts all three waiting classes, and only working is not one', () => {
    expect(waitsForAPerson(agent({ attention: ATT_INPUT }))).toBe(true)
    expect(waitsForAPerson(agent({ attention: ATT_PROMPT }))).toBe(true)
    // ⚠ This line asserted `false` for an hour on 2026-08-28, on the reasoning
    // that "a turn that ended while a command runs in the background is waiting
    // for nobody". The runtime disagrees and always did: its status is computed
    // as `base === "idle" && hasBackgroundBash ? "shell" : base`, and its idle
    // notification fires for `idle || shell`. A dev server is not the agent
    // working. The wrong expectation is kept here because the direction is the
    // lesson: it made a screen calm about a session waiting 20 minutes.
    expect(waitsForAPerson(agent({ attention: ATT_BACKGROUND }))).toBe(true)
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
    // `working` only. A parked background wait is excluded for being parked,
    // not for being background — the 9000 s here is past the parked threshold.
    expect(worstInputWait([
      agent({ attention: ATT_BACKGROUND, input_wait_seconds: 9000 }),
      agent({ attention: ATT_WORKING, input_wait_seconds: 9000 }),
    ])).toBeNull()
    expect(worstInputWait([
      agent({ attention: ATT_BACKGROUND, input_wait_seconds: 200 }),
    ])).toBe(200)
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
    // The background agent is counted BOTH ways: as a waiter (what the reader
    // acts on) and as a background marker (why it may look busy).
    expect(t.input).toBe(3)
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

describe('escalationTone — the strongest colour present, and never silence', () => {
  const set = (input: number, prompt: number, worst: number | null) =>
    ({ input, prompt, worstInputWaitSeconds: worst })

  it('takes the strongest: red beats amber beats plain', () => {
    expect(escalationTone(set(2, 0, 400))).toBe('red')
    expect(escalationTone(set(2, 0, 45))).toBe('amber')
    expect(escalationTone(set(2, 0, 5))).toBe('plain')
  })

  it('colours a project where ONE agent waits and the others are busy', () => {
    // The user's report, 2026-08-28: the colour vanished from a project whose
    // second agent was still waiting. One waiter is enough.
    expect(escalationTone(set(1, 0, 300))).toBe('red')
  })

  it('is amber, never nothing, when the wait has no measured age', () => {
    // The record said the prompt is free but carried no stamp. Somebody is
    // waiting either way, and silence is the one answer that is certainly wrong.
    expect(escalationTone(set(1, 0, null))).toBe('amber')
  })

  it('is null only when nobody is waiting', () => {
    expect(escalationTone(set(0, 0, null))).toBeNull()
    expect(escalationTone(set(0, 0, 9999))).toBeNull()
  })

  it('counts a permission prompt as a waiter too', () => {
    expect(escalationTone(set(0, 1, 200))).toBe('red')
  })
})

describe('working is counted from the record, not only from an open tool call', () => {
  it('counts a busy session whose log shows no open call', () => {
    // Measured 2026-08-28: two live sessions were `busy` in the record and
    // `quiet` in the log at the same instant — a turn's entries are flushed in
    // batches. Counted by state alone, that project rendered with no counter
    // at all, which reads as "nothing is happening here".
    const t = tally([{ name: 'p', agents: [
      agent({ state: 'quiet', attention: ATT_WORKING }),
      agent({ state: 'quiet', attention: ATT_WORKING }),
    ] }])
    expect(t.working).toBe(0)        // the log's answer, unchanged
    expect(t.attWorking).toBe(2)     // the record's answer
    expect(t.attentionReported).toBe(true)
  })

  it('says the axis was not reported when no agent carries a class', () => {
    const t = tally([{ name: 'p', agents: [agent({ state: 'working' })] }])
    expect(t.attentionReported).toBe(false)
    expect(t.attWorking).toBe(0)
  })
})

describe('the escalation goes cold, not louder', () => {
  it('is parked past 45 minutes, and red just before it', () => {
    expect(inputWaitTone(2699)).toBe('red')
    expect(inputWaitTone(2700)).toBe('parked')
    expect(inputWaitTone(7200)).toBe('parked')
    // 20 minutes is LIVE. The threshold shipped at 15 minutes and hid a session
    // the user had been waiting on for exactly that long.
    expect(inputWaitTone(20 * 60)).toBe('red')
  })

  it('leaves a parked wait out of the worst, so it cannot own the row', () => {
    // The user's report, 2026-08-28: a project whose oldest agent had waited
    // two hours rendered red forever, and the 40-second wait they were working
    // with never surfaced.
    expect(worstInputWait([
      agent({ attention: ATT_INPUT, input_wait_seconds: 7200 }),
      agent({ attention: ATT_INPUT, input_wait_seconds: 40 }),
    ])).toBe(40)
  })

  it('counts parked apart and never sums it into the live waiters', () => {
    const t = tally([{ name: 'p', agents: [
      agent({ attention: ATT_INPUT, input_wait_seconds: 7200 }),
      agent({ attention: ATT_INPUT, input_wait_seconds: 40 }),
    ] }])
    expect(t.parked).toBe(1)
    expect(t.input).toBe(1)
    expect(t.worstInputWaitSeconds).toBe(40)
    expect(escalationTone(t)).toBe('amber')
  })

  it('a project holding ONLY parked waits gets no tone at all', () => {
    const t = tally([{ name: 'p', agents: [
      agent({ attention: ATT_INPUT, input_wait_seconds: 7200 }),
    ] }])
    expect(t.parked).toBe(1)
    expect(t.input).toBe(0)
    expect(escalationTone(t)).toBeNull()
  })

  it('honours a parked threshold sent by the server', () => {
    expect(inputWaitTone(400, { parked_seconds: 300 })).toBe('parked')
  })

  it('agrees with the Python source on the parked threshold', async () => {
    const fs = await import('node:fs')
    const path = await import('node:path')
    const src = fs.readFileSync(
      path.resolve(process.cwd(), '..', 'lib/set_orch/fleet/state.py'), 'utf8',
    )
    const parked = src.match(/^INPUT_WAIT_PARKED_SECONDS = ([\d.]+)$/m)
    expect(parked).not.toBeNull()
    expect(Number(parked![1])).toBe(INPUT_WAIT_PARKED_SECONDS)
  })
})
