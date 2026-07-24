/**
 * The renderer's two honesty rules, held by tests rather than by care.
 *
 * A status screen fails in one direction that matters: it reports calm it has not
 * verified. Both rules below exist to make that failure impossible to reach by accident,
 * and both are easy to break later with a well-meant "cleaner" render.
 *
 * 1. **Unknown never looks like zero, and never looks like success.** In JSON, "we could
 *    not find out" and "there are none" are both falsy. On screen they must not be.
 * 2. **No field name is recognised.** The renderer works from shape. A test that asserted
 *    a specific key would be the first step toward coupling the framework to one
 *    project's vocabulary, so these tests deliberately use nonsense keys.
 */

import { describe, it, expect, afterEach, vi } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import StatusValue, {
  ActionProvider,
  DeprecationProvider,
  presentDeprecations,
} from '../../src/components/StatusValue'

afterEach(() => { cleanup(); vi.restoreAllMocks() })

const UNKNOWN = '[title^="no value"]'

describe('unknown is not zero', () => {
  it('renders null as an explicit unknown, not as a number', () => {
    const { container } = render(<StatusValue value={null} />)

    expect(container.querySelector(UNKNOWN)).not.toBeNull()
    expect(container.textContent).not.toContain('0')
  })

  it('distinguishes a real zero from a missing one', () => {
    const { container } = render(<StatusValue value={{ wibble: 0, wobble: null }} />)

    // The zero is a value the project reported and is shown as such.
    expect(container.textContent).toContain('0')
    // The null is not — exactly one unknown marker, for the field that has none.
    expect(container.querySelectorAll(UNKNOWN)).toHaveLength(1)
  })

  it('does not render an unknown as a success tick', () => {
    const { container } = render(<StatusValue value={{ flag: null }} />)

    expect(container.textContent).not.toContain('yes')
    expect(container.querySelector('.text-emerald-400')).toBeNull()
  })

  it('an empty list says none WITH its count, so it cannot be read as unknown', () => {
    const { container } = render(<StatusValue value={[]} />)

    expect(container.textContent).toContain('none')
    expect(container.querySelector(UNKNOWN)).toBeNull()
  })

  it('an empty string is marked, not rendered as blank space', () => {
    const { container } = render(<StatusValue value={{ note: '' }} />)

    expect(container.querySelector(UNKNOWN)).not.toBeNull()
  })
})

describe('shape, not vocabulary', () => {
  it('turns a list of objects into a table with the project’s own column names', () => {
    render(<StatusValue value={[{ zork: 'a', quux: 1 }, { zork: 'b', quux: 2 }]} />)

    expect(screen.getByText('zork')).toBeDefined()
    expect(screen.getByText('quux')).toBeDefined()
    expect(document.querySelectorAll('tbody tr')).toHaveLength(2)
  })

  it('keeps first-seen column order and fills gaps rather than shifting cells', () => {
    render(<StatusValue value={[{ a: 1 }, { b: 2 }]} />)

    const headers = [...document.querySelectorAll('th')].map(th => th.textContent)
    expect(headers).toEqual(['a', 'b'])
    // Row one has no `b`: that cell is an unknown, not an empty cell borrowed from row two.
    expect(document.querySelectorAll(UNKNOWN)).toHaveLength(2)
  })

  it('renders a scalar list as chips without inventing a table', () => {
    const { container } = render(<StatusValue value={['x', 'y']} />)

    expect(container.querySelector('table')).toBeNull()
    expect(container.textContent).toContain('x')
  })

  it('shows deep structure verbatim instead of pretending to understand it', () => {
    const deep = { a: { b: { c: { d: { e: 1 } } } } }
    const { container } = render(<StatusValue value={deep} />)

    expect(container.querySelector('pre')).not.toBeNull()
  })

  it('reports a count for a non-empty list so the reader is never guessing', () => {
    const { container } = render(<StatusValue value={[{ k: 1 }, { k: 2 }, { k: 3 }]} />)

    expect(container.textContent).toContain('3 items')
  })
})

describe('numbers are shown as given', () => {
  it('does not round or abbreviate', () => {
    const { container } = render(<StatusValue value={{ n: 1234567 }} />)

    expect(container.textContent).toMatch(/1[\s,. ]?234[\s,. ]?567/)
    expect(container.textContent).not.toContain('1.2M')
  })
})

describe('a field the project no longer stands behind', () => {
  const withDeprecation = (names: string[], show: boolean, value: unknown) =>
    render(
      <DeprecationProvider value={{ names: new Set(names), show }}>
        <StatusValue value={value} />
      </DeprecationProvider>,
    )

  it('is hidden by default, so it cannot contradict its replacement', () => {
    // The live failure this exists for: the old count rendered `1` directly beside the
    // new count's `2`, which is the ambiguity the new field was introduced to end.
    const { container } = withDeprecation(['oldCount'], false, { oldCount: 1, newCount: 2 })

    expect(container.textContent).not.toContain('oldCount')
    expect(container.textContent).toContain('newCount')
  })

  it('is never hidden silently — the count is always shown', () => {
    const { container } = withDeprecation(['oldCount'], false, { oldCount: 1, newCount: 2 })

    expect(container.textContent).toContain('1 deprecated field hidden')
  })

  it('is shown struck through when the reader asks for it', () => {
    const { container } = withDeprecation(['oldCount'], true, { oldCount: 1, newCount: 2 })

    expect(container.textContent).toContain('oldCount')
    expect(container.querySelector('.line-through')).not.toBeNull()
  })

  it('drops the column from a table, not just the label', () => {
    withDeprecation(['stale'], false, [{ stale: 1, fresh: 2 }])

    const headers = [...document.querySelectorAll('th')].map(th => th.textContent)
    expect(headers).toEqual(['fresh'])
  })

  it('does not reappear in the verbatim dump of deeply nested structure', () => {
    const deep = { a: { b: { c: { stale: 1, fresh: 2 } } } }
    const { container } = withDeprecation(['stale'], false, deep)

    expect(container.querySelector('pre')).not.toBeNull()
    expect(container.textContent).not.toContain('stale')
  })

  it('changes nothing when the project declares no deprecations', () => {
    const { container } = withDeprecation([], false, { a: 1, b: 2 })

    expect(container.textContent).toContain('a')
    expect(container.textContent).toContain('b')
    expect(container.textContent).not.toContain('hidden')
  })
})

describe('a declaration is a claim about the data, and can be wrong', () => {
  it('counts only the deprecated fields that are actually there', () => {
    // The mirror of the failure this mechanism prevents: not a false value, a false
    // absence. Announcing a hidden field that was never sent is its own lie.
    const found = presentDeprecations({ a: 1 }, new Set(['ghost']))

    expect(found.size).toBe(0)
  })

  it('finds one nested inside a list of rows', () => {
    const found = presentDeprecations({ rows: [{ stale: 1 }] }, new Set(['stale']))

    expect([...found]).toEqual(['stale'])
  })

  it('finds one nested arbitrarily deep', () => {
    const found = presentDeprecations({ a: { b: { c: { stale: 1 } } } }, new Set(['stale']))

    expect([...found]).toEqual(['stale'])
  })

  it('reports nothing when nothing was declared, without walking anything', () => {
    expect(presentDeprecations({ a: { b: 1 } }, new Set()).size).toBe(0)
  })

  it('does not mistake a VALUE equal to the name for a field of that name', () => {
    const found = presentDeprecations({ label: 'stale' }, new Set(['stale']))

    expect(found.size).toBe(0)
  })

  it('survives null and scalars in the tree without throwing', () => {
    expect(() => presentDeprecations({ a: null, b: 3, c: 'x' }, new Set(['a']))).not.toThrow()
    expect([...presentDeprecations({ a: null }, new Set(['a']))]).toEqual(['a'])
  })
})

describe('an action the project attached to a row', () => {
  const withAction = (value: unknown, run = async () => ({ ok: true })) =>
    render(
      <ActionProvider value={run}>
        <StatusValue value={value} />
      </ActionProvider>,
    )

  const ROW = {
    thing: 'x',
    actions: [{ command: 'ack', label: 'Record', args: { id: 7 } }],
  }

  it('renders as a control, never as a JSON column', () => {
    withAction([ROW])

    const headers = [...document.querySelectorAll('th')].map(h => h.textContent)
    expect(headers).not.toContain('actions')
    expect(document.querySelector('[data-action="ack"]')).not.toBeNull()
  })

  it('is not offered at all when nothing can run it', () => {
    // Without a runner there is no write path, so a button would be a lie about
    // what this page can do.
    render(<StatusValue value={[ROW]} />)

    expect(document.querySelector('[data-action="ack"]')).toBeNull()
  })

  it('sends the project’s own arguments, not arguments derived here', async () => {
    const calls: unknown[] = []
    withAction([ROW], async (c, a) => { calls.push([c, a]); return { ok: true } })
    vi.spyOn(window, 'confirm').mockReturnValue(true)

    fireEvent.click(document.querySelector('[data-action="ack"]')!)
    await waitFor(() => expect(calls).toHaveLength(1))

    expect(calls[0]).toEqual(['ack', { id: 7 }])
  })

  it('asks first, and does nothing if the confirmation is declined', async () => {
    const calls: unknown[] = []
    withAction([ROW], async (c, a) => { calls.push([c, a]); return { ok: true } })
    vi.spyOn(window, 'confirm').mockReturnValue(false)

    fireEvent.click(document.querySelector('[data-action="ack"]')!)

    expect(calls).toHaveLength(0)
  })

  it('says out loud that the record is a human statement, not a measurement', async () => {
    // The consumer produced a stray record for a check nobody had performed. The
    // confirmation is the one place a person can be told that before they assert it.
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
    withAction([ROW])

    fireEvent.click(document.querySelector('[data-action="ack"]')!)

    expect(confirm.mock.calls[0][0]).toMatch(/not a measurement/i)
  })

  it('will not run until every choice the project demands has been made', () => {
    withAction([{
      thing: 'x',
      actions: [{ command: 'ack', args: { id: 1 }, choose: { env: ['test', 'prod'] } }],
    }])

    expect(document.querySelector<HTMLButtonElement>('[data-action="ack"]')!.disabled).toBe(true)
    expect(document.querySelector('select')).not.toBeNull()
  })

  it('merges the choice into the project’s arguments', async () => {
    const calls: unknown[] = []
    withAction(
      [{ thing: 'x', actions: [{ command: 'ack', args: { id: 1 }, choose: { env: ['test'] } }] }],
      async (c, a) => { calls.push(a); return { ok: true } },
    )
    vi.spyOn(window, 'confirm').mockReturnValue(true)

    fireEvent.change(document.querySelector('select')!, { target: { value: 'test' } })
    fireEvent.click(document.querySelector('[data-action="ack"]')!)
    await waitFor(() => expect(calls).toHaveLength(1))

    expect(calls[0]).toEqual({ id: 1, env: 'test' })
  })

  it('reports a refused write instead of looking like it worked', async () => {
    withAction([ROW], async () => ({ ok: false, error: 'nope' }))
    vi.spyOn(window, 'confirm').mockReturnValue(true)

    fireEvent.click(document.querySelector('[data-action="ack"]')!)

    await waitFor(() =>
      expect(document.body.textContent).toContain('failed'))
    expect(document.body.textContent).not.toContain('recorded')
  })

  it('ignores a malformed action rather than rendering a button that cannot work', () => {
    withAction([{ thing: 'x', actions: [{ label: 'no command here' }] }])

    expect(document.querySelector('button')).toBeNull()
  })

  it('does not leak the machinery into the verbatim deep dump', () => {
    const deep = { a: { b: { c: { keep: 1, actions: [{ command: 'ack' }] } } } }
    const { container } = withAction(deep)

    expect(container.querySelector('pre')).not.toBeNull()
    expect(container.querySelector('pre')!.textContent).not.toContain('actions')
  })
})
