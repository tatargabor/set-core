/**
 * The table's controls, tested from the HIDING side.
 *
 * Every mechanism here shows fewer rows, or less of a row, than arrived. So the assertions
 * are deliberately about what is NOT on screen and what the surface says about it — a test
 * that only checks the visible rows would pass just as happily while a filter silently
 * swallowed a failing one.
 *
 * The other reason these tests exist is the coupling they forbid. A column becomes
 * filterable because of the SHAPE of its values; the easy implementation is a list of known
 * names, and it would work on the project in front of us. So one test uses a column named
 * with one of set-core's own words and asserts it is treated exactly like a nonsense one.
 */

import { describe, it, expect, afterEach, vi } from 'vitest'
import { render, screen, cleanup, fireEvent, within } from '@testing-library/react'
import StatusValue from '../../src/components/StatusValue'
import {
  CONTROL_MIN_ROWS,
  compareValues,
  facetColumns,
  isMissing,
} from '../../src/components/StatusTable'

afterEach(() => { cleanup(); vi.restoreAllMocks() })

/** Enough rows for the controls to appear, with one categorical column and one free-text. */
const rows = (n = 12) =>
  Array.from({ length: n }, (_, i) => ({
    zonk: i % 3 === 0 ? 'alpha' : 'beta',
    blip: `unique-value-${i}`,
  }))

describe('a control appears only when it could change what you see', () => {
  it('leaves a small table exactly as it was — no search box over five rows', () => {
    render(<StatusValue value={rows(5)} />)

    expect(screen.queryByLabelText('search rows')).toBeNull()
  })

  it('offers the controls once a table is long enough to need them', () => {
    render(<StatusValue value={rows(CONTROL_MIN_ROWS)} />)

    expect(screen.queryByLabelText('search rows')).not.toBeNull()
  })
})

describe('a filter is derived from the shape of the values, never from a name', () => {
  it('offers a facet for a categorical column', () => {
    const facets = facetColumns(rows(12), ['zonk', 'blip'])

    expect([...facets.keys()]).toEqual(['zonk'])
    expect(facets.get('zonk')).toEqual(new Map([['alpha', 4], ['beta', 8]]))
  })

  it('offers none for a column whose values are nearly all distinct', () => {
    const facets = facetColumns(rows(12), ['blip'])

    expect(facets.size).toBe(0)
  })

  it('offers none for a column with a single value — a choice of one is not a choice', () => {
    const same = Array.from({ length: 12 }, () => ({ zonk: 'alpha' }))

    expect(facetColumns(same, ['zonk']).size).toBe(0)
  })

  it('treats a column named with one of set-core’s own words like any other', () => {
    // The cheap implementation is a list of known filterable names, and `status` would be
    // on it. Two identically-shaped columns, one named after a set-core concept and one
    // nonsense, must be indistinguishable to this mechanism.
    const both = Array.from({ length: 12 }, (_, i) => ({
      status: i % 2 ? 'failed' : 'done',
      wibble: i % 2 ? 'failed' : 'done',
    }))
    const facets = facetColumns(both, ['status', 'wibble'])

    expect(facets.get('status')).toEqual(facets.get('wibble'))
  })

  it('counts facet values from the data, not from how many rows exist', () => {
    const facets = facetColumns(rows(12), ['zonk'])

    // 12 rows, but the counts are 4 and 8 — a count that came from the row total would be
    // a number about the wrong thing, which is how a false value gets on screen.
    expect([...facets.get('zonk')!.values()].reduce((a, b) => a + b)).toBe(12)
  })
})

describe('hiding rows is never silent', () => {
  const filtered = () => {
    render(<StatusValue value={rows(12)} />)
    fireEvent.change(screen.getByLabelText('search rows'), { target: { value: 'alpha' } })
  }

  it('says how many rows it is showing OF how many arrived', () => {
    filtered()

    expect(document.body.textContent).toContain('4 of 12 rows shown')
  })

  it('states the number withheld, where the count is', () => {
    filtered()

    expect(document.body.textContent).toContain('8 hidden by filters')
  })

  it('makes no claim about hidden rows when nothing is filtered', () => {
    render(<StatusValue value={rows(12)} />)

    expect(document.body.textContent).toContain('12 rows')
    expect(document.body.textContent).not.toContain('hidden by filters')
  })

  it('clears every filter with one control', () => {
    filtered()
    fireEvent.click(screen.getByText('clear'))

    expect(document.body.textContent).toContain('12 rows')
    expect(document.body.textContent).not.toContain('hidden by filters')
  })

  it('says an empty result is hidden, not absent', () => {
    render(<StatusValue value={rows(12)} />)
    fireEvent.change(screen.getByLabelText('search rows'), { target: { value: 'nothing-matches' } })

    expect(document.body.textContent).toContain('No row matches these filters')
    expect(document.body.textContent).toContain('hidden, not absent')
    expect(screen.queryByText('clear')).not.toBeNull()
  })

  it('really removes the rows it says it removed', () => {
    // The count could be right while the table still rendered everything. Assert the rows.
    render(<StatusValue value={rows(12)} />)
    fireEvent.change(screen.getByLabelText('search rows'), { target: { value: 'alpha' } })
    const body = document.querySelector('tbody')!

    expect(within(body).queryAllByText('beta')).toHaveLength(0)
    expect(within(body).queryAllByText('alpha')).toHaveLength(4)
  })
})

describe('sorting can be undone back to the project’s order', () => {
  const values = () =>
    [...document.querySelectorAll('tbody tr td:nth-child(2)')].map(td => td.textContent)

  const table = () => {
    render(<StatusValue value={[
      { n: 3, t: 'c' }, { n: 1, t: 'a' }, { n: 2, t: 'b' },
      { n: 9, t: 'i' }, { n: 8, t: 'h' }, { n: 7, t: 'g' },
      { n: 6, t: 'f' }, { n: 5, t: 'e' }, { n: 4, t: 'd' },
    ]} />)
    return screen.getByText('n')
  }

  it('cycles delivered → ascending → descending → delivered', () => {
    const header = table()
    const delivered = values()

    fireEvent.click(header)
    expect(values()[0]).toBe('1')

    fireEvent.click(header)
    expect(values()[0]).toBe('9')

    fireEvent.click(header)
    expect(values()).toEqual(delivered)
  })

  it('says out loud when the rows are not in the project’s order', () => {
    fireEvent.click(table())

    expect(document.body.textContent).toContain("not the project's order")
  })

  it('stops saying it once the delivered order is restored', () => {
    const header = table()
    fireEvent.click(header); fireEvent.click(header); fireEvent.click(header)

    expect(document.body.textContent).not.toContain("not the project's order")
  })

  it('sorts numbers numerically, not as text', () => {
    expect(compareValues(9, 10)).toBeLessThan(0)
    expect(compareValues('9', '10')).toBeLessThan(0)
  })

  it('sorts an absent value last in BOTH directions', () => {
    // Ascending puts it last by the comparator; descending must not float it to the top,
    // where "we don't know" would occupy the position a reader scans first.
    expect(compareValues(null, 5)).toBe(1)
    expect(compareValues(5, null)).toBe(-1)
    expect(isMissing('')).toBe(true)
  })

  it('keeps an absent value at the bottom when the column is sorted either way', () => {
    render(<StatusValue value={[
      { n: 3 }, { n: null }, { n: 2 }, { n: 9 }, { n: 8 },
      { n: 7 }, { n: 6 }, { n: 5 }, { n: 4 },
    ]} />)
    const header = screen.getByText('n')

    fireEvent.click(header)
    expect(values()[values().length - 1]).toBe('—')

    fireEvent.click(header)
    expect(values()[values().length - 1]).toBe('—')
  })
})

describe('density costs nothing that was delivered', () => {
  it('still renders every column', () => {
    render(<StatusValue value={rows(12)} />)
    const headers = [...document.querySelectorAll('th')].map(h => h.textContent)

    expect(headers).toContain('zonk')
    expect(headers).toContain('blip')
  })

  it('keeps the whole record one interaction away from a clipped row', () => {
    render(<StatusValue value={rows(12)} />)
    const expand = screen.getAllByLabelText('show the whole record')[0]
    fireEvent.click(expand)

    // The detail renders the row AS DELIVERED, so both fields appear as a key grid below.
    expect(screen.queryAllByLabelText('hide the whole record')).toHaveLength(1)
    expect(document.body.textContent).toContain('unique-value-0')
  })
})

describe('nothing about the view is persisted', () => {
  // The first version of this test asserted `localStorage.length === 0`. It read
  // `undefined` in this environment — which is not zero and is not proof, and it would
  // have gone green forever the moment the property stopped existing. So the assertion is
  // on the ACT of writing, through a recorder installed in place of the store, and the
  // last test proves the recorder can actually catch one.
  interface Recorder { keys: string[]; store: Storage }
  function recorder(): Recorder {
    const keys: string[] = []
    const store = {
      length: 0,
      key: () => null,
      getItem: () => null,
      removeItem: () => {},
      clear: () => {},
      setItem: (k: string) => { keys.push(k) },
    } as unknown as Storage
    return { keys, store }
  }

  function watched(): { local: Recorder; session: Recorder; restore: () => void } {
    const local = recorder()
    const session = recorder()
    Object.defineProperty(window, 'localStorage', { value: local.store, configurable: true })
    Object.defineProperty(window, 'sessionStorage', { value: session.store, configurable: true })
    return {
      local,
      session,
      restore: () => {
        delete (window as unknown as Record<string, unknown>).localStorage
        delete (window as unknown as Record<string, unknown>).sessionStorage
      },
    }
  }

  it('writes no filter value to storage and does not touch the URL', () => {
    const w = watched()
    const push = vi.spyOn(window.history, 'pushState')
    const replace = vi.spyOn(window.history, 'replaceState')
    const before = window.location.href
    try {
      render(<StatusValue value={rows(12)} />)
      fireEvent.change(screen.getByLabelText('search rows'), { target: { value: 'alpha' } })
      fireEvent.click(screen.getByText('zonk'))

      // A facet value is the project's data. localStorage is disk; so is browser history.
      expect(w.local.keys).toEqual([])
      expect(w.session.keys).toEqual([])
      expect(push).not.toHaveBeenCalled()
      expect(replace).not.toHaveBeenCalled()
      expect(window.location.href).toBe(before)
      expect(document.cookie).toBe('')
    } finally {
      w.restore()
    }
  })

  it('the check above is capable of failing', () => {
    // A guard that cannot fire is indistinguishable from one that found nothing.
    const w = watched()
    const replace = vi.spyOn(window.history, 'replaceState')
    try {
      window.localStorage.setItem('probe', '1')
      window.history.replaceState({}, '', window.location.href)

      expect(w.local.keys).toEqual(['probe'])
      expect(replace).toHaveBeenCalled()
    } finally {
      w.restore()
    }
  })
})

describe('a reload starts clean, because there is nothing to restore from', () => {
  it('shows every row again after the component is mounted afresh', () => {
    const { unmount } = render(<StatusValue value={rows(12)} />)
    fireEvent.change(screen.getByLabelText('search rows'), { target: { value: 'alpha' } })
    expect(document.body.textContent).toContain('4 of 12 rows shown')

    unmount()
    render(<StatusValue value={rows(12)} />)

    expect(document.body.textContent).toContain('12 rows')
    expect(document.body.textContent).not.toContain('hidden by filters')
  })
})

describe('set-core’s own vocabulary is never applied to a project’s values', () => {
  it('renders a value that collides with a set-core run state like any other string', () => {
    // `failed`, `done` and `running` mean something to set-core about set-core's runs.
    // A project's cell holding one of those words means whatever the project means, and a
    // colour keyed on it would be this side asserting it knows which.
    render(<StatusValue value={Array.from({ length: 12 }, (_, i) => ({
      zonk: i % 2 ? 'failed' : 'quux',
    }))} />)
    const cells = [...document.querySelectorAll('tbody tr td:nth-child(2) span')]
    const classes = new Set(cells.map(c => c.className))

    expect(cells.length).toBeGreaterThan(0)
    expect(classes.size).toBe(1)
  })
})
