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

import { describe, it, expect, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import StatusValue, { DeprecationProvider } from '../../src/components/StatusValue'

afterEach(cleanup)

const UNKNOWN = '[title="not provided by the project"]'

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
