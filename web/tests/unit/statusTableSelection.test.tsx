/**
 * A reader can name a set of rows — and the set must never disagree with what the reader sees.
 *
 * Two failure directions are guarded here, and only one of them is obvious:
 *
 * - A selection keyed by ROW INDEX silently points at different rows after a sort. Nothing looks
 *   wrong; the wrong rows are simply selected.
 * - A selection whose hidden part is not counted reads as smaller than it is. Every later action
 *   would then act on more rows than the reader believes — the reassuring direction, on the one
 *   number that decides an action's blast radius.
 *
 * The tests drive the table the way a reader reaches it: clicking checkboxes and typing in the
 * search box. Calling the selection helper directly would test a system where every control
 * already works.
 */
import { describe, it, expect, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, within } from '@testing-library/react'
import StatusValue from '../../src/components/StatusValue'
import { identityColumn, CONTROL_MIN_ROWS, ROW_CAP } from '../../src/components/StatusTable'
import { ActionProvider } from '../../src/components/statusShape'

afterEach(cleanup)

/** Rows with a unique identifying column whose NAME says nothing — the point of the exercise. */
function rows(n: number, prefix = 'ZQ') {
  return Array.from({ length: n }, (_, i) => ({
    kód: `${prefix}-${String(i).padStart(4, '0')}`,
    állapot: i % 2 === 0 ? 'nyitott' : 'lezárt',
    súly: i % 3,
  }))
}

const checkboxes = () => screen.getAllByRole('checkbox')
/** The per-row boxes, i.e. everything after the header's select-all. */
const rowBoxes = () => screen.getAllByLabelText('select this row')

describe('identityColumn — chosen from the values, never from a name', () => {
  it('takes the first column that is scalar, present everywhere and unique', () => {
    const r = rows(10)
    expect(identityColumn(r, ['kód', 'állapot', 'súly'])).toBe('kód')
  })

  it('is indifferent to what the column is called, in any language', () => {
    const r = Array.from({ length: 5 }, (_, i) => ({ 識別子: `x${i}`, other: 'same' }))
    expect(identityColumn(r, ['識別子', 'other'])).toBe('識別子')
  })

  it('refuses a column with a repeat, even when it is nearly unique', () => {
    const r = [{ a: '1' }, { a: '2' }, { a: '2' }]
    expect(identityColumn(r, ['a'])).toBeNull()
  })

  it('refuses a column with a gap — an absent value identifies nothing', () => {
    const r = [{ a: '1' }, { a: null }, { a: '3' }]
    expect(identityColumn(r, ['a'])).toBeNull()
  })

  it('refuses a structured column, because a row is identified by a value it can carry', () => {
    const r = [{ a: { deep: 1 } }, { a: { deep: 2 } }]
    expect(identityColumn(r, ['a'])).toBeNull()
  })

  it('returns null for no rows at all', () => {
    expect(identityColumn([], ['a'])).toBeNull()
  })
})

describe('the selection survives what narrows the table', () => {
  it('keeps a row selected when a filter hides it, and says how many are hidden', () => {
    render(<StatusValue value={rows(12)} />)
    // Select one row that the search below will hide.
    fireEvent.click(rowBoxes()[1])
    expect(screen.getByTestId('selection-count').textContent).toContain('1 selected')

    fireEvent.change(screen.getByLabelText('search rows'), { target: { value: 'ZQ-0000' } })

    // Still selected — and the count of what is NOT on screen is stated, not implied.
    expect(screen.getByTestId('selection-count').textContent).toContain('1 selected')
    expect(screen.getByTestId('selection-hidden').textContent).toContain('1')
  })

  it('brings the selection back intact when the narrowing is removed', () => {
    render(<StatusValue value={rows(12)} />)
    fireEvent.click(rowBoxes()[1])
    const box = screen.getByLabelText('search rows')
    fireEvent.change(box, { target: { value: 'ZQ-0000' } })
    fireEvent.change(box, { target: { value: '' } })

    expect(screen.getByTestId('selection-count').textContent).toContain('1 selected')
    expect(screen.queryByTestId('selection-hidden')).toBeNull()
    expect((rowBoxes()[1] as HTMLInputElement).checked).toBe(true)
  })

  it('a selection of N with M hidden never displays as N−M', () => {
    // The false-absence direction: 3 selected, 2 hidden, and the visible truth is "1". If the
    // summary counted only what shows, an action would act on three while the reader read one.
    render(<StatusValue value={rows(12)} />)
    fireEvent.click(rowBoxes()[0])
    fireEvent.click(rowBoxes()[1])
    fireEvent.click(rowBoxes()[2])
    fireEvent.change(screen.getByLabelText('search rows'), { target: { value: 'ZQ-0000' } })

    const count = screen.getByTestId('selection-count')
    expect(count.textContent).toContain('3 selected')
    expect(count.textContent).not.toContain('1 selected')
    expect(screen.getByTestId('selection-hidden').textContent).toContain('2')
  })
})

describe('the identity key earns its existence', () => {
  it('a refreshed answer in a different order keeps the SAME row selected', () => {
    // The test that separates an identity key from a row index. Filtering and sorting do not
    // renumber `rows`, so a selection keyed by index passes every other test in this file — it
    // only breaks when the answer itself is refreshed and arrives in another order, which is
    // exactly what the page's refresh does. Without this test the whole of identityColumn could
    // be deleted and the suite would stay green.
    const forward = rows(12)
    const { rerender } = render(<StatusValue value={forward} />)

    const target = 'ZQ-0003'
    const trOf = (code: string) => screen.getByText(code).closest('tr') as HTMLElement
    fireEvent.click(within(trOf(target)).getByLabelText('select this row'))
    expect(screen.getByTestId('selection-count').textContent).toContain('1 selected')

    rerender(<StatusValue value={[...forward].reverse()} />)

    // Still exactly one selected, and it is still the row that was clicked — not whatever now
    // sits where it used to be.
    expect(screen.getByTestId('selection-count').textContent).toContain('1 selected')
    const box = within(trOf(target)).getByLabelText('select this row') as HTMLInputElement
    expect(box.checked).toBe(true)
    const moved = within(trOf('ZQ-0008')).getByLabelText('select this row') as HTMLInputElement
    expect(moved.checked).toBe(false)
  })

  it('drops a key the refreshed answer no longer contains, rather than counting a ghost', () => {
    const full = rows(12)
    const { rerender } = render(<StatusValue value={full} />)
    fireEvent.click(within(screen.getByText('ZQ-0003').closest('tr') as HTMLElement)
      .getByLabelText('select this row'))
    fireEvent.click(within(screen.getByText('ZQ-0004').closest('tr') as HTMLElement)
      .getByLabelText('select this row'))
    expect(screen.getByTestId('selection-count').textContent).toContain('2 selected')

    // One selected row is gone from the new answer. Counting it would overstate what any
    // action could reach — the direction that looks calm and acts wide.
    rerender(<StatusValue value={full.filter(r => r.kód !== 'ZQ-0003')} />)
    expect(screen.getByTestId('selection-count').textContent).toContain('1 selected')
  })
})

describe('select-all means what is showing, and names that limit', () => {
  it('adds only the rows currently showing', () => {
    render(<StatusValue value={rows(12)} />)
    fireEvent.change(screen.getByLabelText('search rows'), { target: { value: 'nyitott' } })
    const showing = rowBoxes().length
    expect(showing).toBeLessThan(12)

    fireEvent.click(screen.getByLabelText(`select the ${showing} rows showing`))
    expect(screen.getByTestId('selection-count').textContent).toContain(`${showing} selected`)
  })

  it('states the limit on the control rather than leaving it to be guessed', () => {
    render(<StatusValue value={rows(12)} />)
    expect(screen.queryByLabelText('select the 12 rows showing')).not.toBeNull()
  })

  it('counts rows beyond the row cap as hidden, not as unselected', () => {
    const n = ROW_CAP + 6
    render(<StatusValue value={rows(n)} />)
    // Select everything showing (the cap), then expand: nothing about the selection changed,
    // but before expanding, the rows past the cap were never selected in the first place.
    fireEvent.click(screen.getByLabelText(`select the ${ROW_CAP} rows showing`))
    expect(screen.getByTestId('selection-count').textContent).toContain(`${ROW_CAP} selected`)
    expect(screen.queryByTestId('selection-hidden')).toBeNull()
  })
})

describe('a batch action is offered only where the project declares one', () => {
  it('says in words that no action is offered, rather than showing nothing', () => {
    render(<StatusValue value={rows(12)} />)
    fireEvent.click(rowBoxes()[0])
    expect(screen.queryByTestId('no-batch-action')).not.toBeNull()
  })

  it('renders no disabled control whose reason for being disabled is unstated', () => {
    render(<StatusValue value={rows(12)} />)
    fireEvent.click(rowBoxes()[0])
    const disabled = screen.queryAllByRole('button').filter(b => (b as HTMLButtonElement).disabled)
    expect(disabled).toHaveLength(0)
  })

  it('THE REFUTED APPROACH: a row-level action does not become a batch control', () => {
    // Deriving a batch from `actions` is the obvious later "improvement", and it turns one
    // assertion about a set into N independent assertions. Held here so it cannot be added
    // and still look correct.
    const withActions = rows(12).map(r => ({
      ...r,
      actions: [{ command: 'acknowledge', label: 'acknowledge' }],
    }))
    // The provider is load-bearing for this test, not scaffolding: without it `ActionButton`
    // returns null (`statusShape.tsx:209`), so the assertion "no batch control appeared" would
    // pass while NO action rendered at all — proving nothing about the derivation it guards.
    render(
      <ActionProvider value={async () => ({ ok: true })}>
        <StatusValue value={withActions} />
      </ActionProvider>,
    )
    fireEvent.click(rowBoxes()[0])
    fireEvent.click(rowBoxes()[1])

    // The row buttons exist…
    expect(screen.getAllByText('acknowledge').length).toBeGreaterThan(1)
    // …and no control claims to act on the selection.
    expect(screen.queryByTestId('no-batch-action')).not.toBeNull()
    expect(screen.queryByTestId('batch-action')).toBeNull()
    // The refuted MATCHER, kept as a note: `/2 rows/i` was the obvious way to write the line
    // above and it matched the table's own count line — "12 rows" contains "2 rows". An
    // unanchored pattern over a corpus that includes the page's other numbers fails toward
    // "found something", which here would have read as a batch control that does not exist.
    expect(screen.queryByText(/\bacts on 2 rows\b/i)).toBeNull()
  })
})

describe('what selection must not do to the table', () => {
  it('offers no selection control on a table too small for controls', () => {
    render(<StatusValue value={rows(CONTROL_MIN_ROWS - 1)} />)
    expect(screen.queryAllByLabelText('select this row')).toHaveLength(0)
  })

  it('shows the selection line only once something is selected', () => {
    render(<StatusValue value={rows(12)} />)
    expect(screen.queryByTestId('selection-count')).toBeNull()
    fireEvent.click(rowBoxes()[0])
    expect(screen.queryByTestId('selection-count')).not.toBeNull()
  })

  it('clears the whole selection while part of it is hidden', () => {
    render(<StatusValue value={rows(12)} />)
    fireEvent.click(rowBoxes()[0])
    fireEvent.click(rowBoxes()[1])
    fireEvent.change(screen.getByLabelText('search rows'), { target: { value: 'ZQ-0000' } })

    fireEvent.click(screen.getByText('clear selection'))
    expect(screen.queryByTestId('selection-count')).toBeNull()
  })

  it('warns when rows are keyed by position, because a sort would then reselect', () => {
    // No column is unique here, so identity falls back to row position — and the reader is told
    // BEFORE sorting, not after the selection has quietly moved.
    const noIdentity = Array.from({ length: 12 }, (_, i) => ({
      állapot: i % 2 === 0 ? 'nyitott' : 'lezárt',
      súly: i % 3,
    }))
    render(<StatusValue value={noIdentity} />)
    fireEvent.click(rowBoxes()[0])
    expect(screen.queryByTestId('selection-positional')).not.toBeNull()
  })

  it('does not warn when a column identifies the rows', () => {
    render(<StatusValue value={rows(12)} />)
    fireEvent.click(rowBoxes()[0])
    expect(screen.queryByTestId('selection-positional')).toBeNull()
  })

  it('adds exactly one selection box per row, plus the one in the header', () => {
    // Counted by role, this would be 18 — the facet popovers hold checkboxes too, and they are
    // in the DOM whether or not the popover is open. So the assertion is on the labelled boxes,
    // not on the role: a count that includes another control's checkboxes measures the wrong set
    // and would drift the moment a facet is added.
    render(<StatusValue value={rows(12)} />)
    expect(rowBoxes()).toHaveLength(12)
    expect(screen.queryByLabelText('select the 12 rows showing')).not.toBeNull()
    expect(checkboxes().length).toBeGreaterThan(13) // facets included — measured, not assumed
  })
})
