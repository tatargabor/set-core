/**
 * What the panel says when the stream does NOT deliver lines.
 *
 * This is the whole risk surface of a live view: a stream that refuses, a stream that drops, and
 * a stream that is simply quiet all look identical from the outside. The user reported the
 * consequence in one sentence — `stream ended — connection-lost` for a file the project had
 * merely stopped naming — and every test here is about telling those three apart.
 */

import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { render, waitFor } from '@testing-library/react'
import { FollowPanel } from '../../src/components/FollowPanel'

class FakeSource {
  static made: FakeSource[] = []
  listeners: Record<string, ((e: unknown) => void)[]> = {}
  onerror: (() => void) | null = null
  closed = false
  constructor(public url: string) { FakeSource.made.push(this) }
  addEventListener(k: string, fn: (e: unknown) => void) {
    (this.listeners[k] ??= []).push(fn)
  }
  close() { this.closed = true }
  emit(k: string, data: unknown) {
    for (const fn of this.listeners[k] ?? []) fn({ data: JSON.stringify(data) })
  }
  fail() { this.onerror?.() }
}

beforeEach(() => {
  FakeSource.made = []
  vi.stubGlobal('EventSource', FakeSource as unknown as typeof EventSource)
})
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks() })

const panel = () => render(
  <FollowPanel project="p" command="current" path="a.jsonl" field="log" onClose={() => {}} />,
)

describe('a stream that never opened', () => {
  it('shows the endpoint’s OWN reason instead of “connection-lost”', async () => {
    // The defect the user hit. `EventSource` reports every failure as one bare error event and
    // gives no access to the body, so a carefully worded 400 arrived indistinguishable from a
    // pulled cable — and the panel printed the cable.
    vi.stubGlobal('fetch', vi.fn(async () => ({
      ok: false, status: 400,
      json: async () => ({ detail: {
        error: 'the requested path is not what any followable field holds in the current answer',
        errorClass: 'not-followable',
      } }),
    })))
    const { container } = panel()

    FakeSource.made[0].fail()

    await waitFor(() =>
      expect(container.textContent).toContain('is not what any followable field holds'))
    expect(container.textContent).not.toContain('connection dropped')
  })

  it('retries instead of explaining when NOTHING answers — a restart is not a refusal', async () => {
    // The distinction that decides between waiting and giving up: an answer is final, an
    // unreachable server is a service coming back.
    vi.stubGlobal('fetch', vi.fn(async () => { throw new Error('ECONNREFUSED') }))
    const { container } = panel()

    FakeSource.made[0].fail()

    await waitFor(() => expect(container.textContent).toContain('reconnecting'))
  })
})

describe('a stream that opened and then dropped', () => {
  it('reconnects, and SAYS it is reconnecting', async () => {
    // A silent reconnect makes the lines written during the gap look like a quiet file. It was
    // measured against the real service: restarting it under an open stream must not end the
    // follow, because the file keeps growing either way.
    const asked = vi.fn(async () => ({ ok: false, status: 400, json: async () => ({}) }))
    vi.stubGlobal('fetch', asked)
    const { container } = panel()
    const src = FakeSource.made[0]
    src.listeners['open']?.[0]?.({})
    src.emit('line', { text: 'one' })

    src.fail()

    await waitFor(() => expect(container.textContent).toContain('reconnecting'))
    expect(container.textContent).toContain('will not appear')

    // The load-bearing assertion, and it exists because the first version of this test did
    // NOT have it: a mutation restoring the exact bug the user reported — reading `opened`
    // from state, which the effect's closure freezes at `false` — left this test green. The
    // broken path reaches "reconnecting" too; it just asks the endpoint why it was refused
    // first, on a stream that had been delivering lines. So the discriminator is not the
    // outcome, it is whether anything was ASKED.
    expect(asked).not.toHaveBeenCalled()
  })

  it('gives up only after a bounded number of attempts, and says why', async () => {
    vi.useFakeTimers()
    const { container } = panel()
    const open = () => {
      const s = FakeSource.made[FakeSource.made.length - 1]
      s.listeners['open']?.[0]?.({})
      return s
    }
    open()
    for (let i = 0; i < 6; i++) {
      FakeSource.made[FakeSource.made.length - 1].fail()
      await vi.advanceTimersByTimeAsync(6000)
    }
    vi.useRealTimers()

    expect(container.textContent).toContain('could not be re-established')
  })
})

describe('a stream the server ended on purpose', () => {
  it('reports the server’s reason and does not reconnect', async () => {
    const { container } = panel()
    const src = FakeSource.made[0]
    src.listeners['open']?.[0]?.({})

    src.emit('end', { reason: 'file-replaced' })

    await waitFor(() => expect(container.textContent).toContain('replaced by a different one'))
    expect(FakeSource.made).toHaveLength(1)
  })
})
