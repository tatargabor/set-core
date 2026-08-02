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

  it('counts ROWS, never "items", because the key above it names a domain', () => {
    // The count is the renderer's own, and the wording is what keeps it from being read
    // as the project's. Under a key like `openManualTasks`, "3 items" reads as "3 open
    // tasks" — and once the project publishes its own derived open-count, the screen
    // carries two numbers about one thing, disagreeing. The renderer counts rows; what
    // the rows MEAN is never its claim to make.
    const { container } = render(<StatusValue value={[{ k: 1 }, { k: 2 }, { k: 3 }]} />)

    expect(container.textContent).toContain('3 rows')
    expect(container.textContent).not.toContain('3 items')
  })

  it('says row, not rows, for one — a count that misreports itself is still a false value', () => {
    const { container } = render(<StatusValue value={[{ k: 1 }]} />)

    expect(container.textContent).toContain('1 row')
    expect(container.textContent).not.toContain('1 rows')
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

  it('offers a TEXT input for an argument the project cannot enumerate', () => {
    // `choose` is for values the project knows; `ask` is for the ones it cannot. A decision
    // written against an open question has no option list — nobody knows the sentence yet.
    withAction([{
      thing: 'x',
      actions: [{ command: 'answer', args: { task: '7.D1' }, ask: { answer: 'your decision' } }],
    }])

    const input = document.querySelector<HTMLInputElement>('input[type="text"]')
    expect(input).not.toBeNull()
    expect(input!.placeholder).toBe('your decision')
    expect(document.querySelector<HTMLButtonElement>('[data-action="answer"]')!.disabled).toBe(true)
  })

  it('stays disabled while the typed value is only whitespace', () => {
    // An empty answer recorded against an open question is worse than no answer: it closes
    // the question while saying nothing, and nothing on the other side can tell them apart.
    withAction([{
      thing: 'x',
      actions: [{ command: 'answer', ask: { answer: 'your decision' } }],
    }])
    const btn = () => document.querySelector<HTMLButtonElement>('[data-action="answer"]')!

    fireEvent.change(document.querySelector('input[type="text"]')!, { target: { value: '   ' } })
    expect(btn().disabled).toBe(true)

    fireEvent.change(document.querySelector('input[type="text"]')!, { target: { value: 'amber' } })
    expect(btn().disabled).toBe(false)
  })

  it('merges the typed value into the project’s arguments, trimmed', async () => {
    const calls: unknown[] = []
    withAction(
      [{ thing: 'x', actions: [{ command: 'answer', args: { task: '7.D1' }, ask: { answer: 'x' } }] }],
      async (c, a) => { calls.push(a); return { ok: true } },
    )
    vi.spyOn(window, 'confirm').mockReturnValue(true)

    fireEvent.change(document.querySelector('input[type="text"]')!, { target: { value: '  amber  ' } })
    fireEvent.click(document.querySelector('[data-action="answer"]')!)
    await waitFor(() => expect(calls).toHaveLength(1))

    expect(calls[0]).toEqual({ task: '7.D1', answer: 'amber' })
  })

  it('shows a refusal IN FULL rather than behind a hover', async () => {
    // The producer's own contract makes the error branch informative: it lists what could
    // have been asked instead. A tooltip on the word "failed" throws that away, and is not
    // reachable at all from a keyboard.
    const long = 'answer failed: no such open task: 9.ZZ\nCurrently open: 7.D1 — [confirm] …'
    withAction(
      [{ thing: 'x', actions: [{ command: 'answer', ask: { answer: 'x' } }] }],
      async () => ({ ok: false, error: long }),
    )
    vi.spyOn(window, 'confirm').mockReturnValue(true)

    fireEvent.change(document.querySelector('input[type="text"]')!, { target: { value: 'a' } })
    fireEvent.click(document.querySelector('[data-action="answer"]')!)

    await waitFor(() => expect(document.body.textContent).toContain('Currently open: 7.D1'))
    expect(document.body.textContent).not.toBe('failed')
  })

  it('a project declaring no ask gets no input, as every project does today', () => {
    withAction([ROW])
    expect(document.querySelector('input[type="text"]')).toBeNull()
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
    // Asserts the REASON, not the word "failed". It used to assert the label, which a
    // producer's own error text — theirs lists what could have been asked instead — was
    // hidden behind: the writing side had made its refusal informative and the reading
    // side threw it away into a tooltip.
    withAction([ROW], async () => ({ ok: false, error: 'nope' }))
    vi.spyOn(window, 'confirm').mockReturnValue(true)

    fireEvent.click(document.querySelector('[data-action="ack"]')!)

    await waitFor(() =>
      expect(document.body.textContent).toContain('nope'))
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

describe('a uniform nested object becomes columns, not a stack inside a cell', () => {
  // Measured on a real screen: two environments, each with a seven-field health object.
  // Rendered in-cell it is two tall blocks, and comparing them means reading both. Rows
  // are comparable by definition — that is what makes them rows — so the columns should
  // be comparable too.
  const rows = [
    { name: 'test', health: { up: true, ms: 223 } },
    { name: 'prod', health: { up: false, ms: 291 } },
  ]

  it('spreads the nested keys into their own columns, keeping the parent in the name', () => {
    const { container } = render(<StatusValue value={rows} />)
    const headers = Array.from(container.querySelectorAll('th')).map(th => th.textContent)

    expect(headers).toContain('health.up')
    expect(headers).toContain('health.ms')
    expect(headers).toContain('name')
  })

  it('does NOT flatten when the rows disagree on the nested shape', () => {
    // Flattening a ragged shape would invent columns most rows lack, and every gap would
    // render as unknown — absences manufactured by a rendering choice.
    const ragged = [
      { name: 'a', detail: { x: 1 } },
      { name: 'b', detail: { y: 2 } },
    ]
    const { container } = render(<StatusValue value={ragged} />)
    const headers = Array.from(container.querySelectorAll('th')).map(th => th.textContent)

    expect(headers).toContain('detail')
    expect(headers).not.toContain('detail.x')
  })

  it('leaves a wide nested object alone rather than exploding the table', () => {
    const wide = [{ k: Object.fromEntries(Array.from({ length: 9 }, (_, i) => [`f${i}`, i])) }]
    const { container } = render(<StatusValue value={wide} />)
    const headers = Array.from(container.querySelectorAll('th')).map(th => th.textContent)

    // One named column, plus the unnamed expander the row grew because its value is a
    // structure the cell will not hold. Nine fields do not become nine columns.
    expect(headers.filter(Boolean)).toEqual(['k'])
  })

  it('the header has exactly one cell per body cell — a table that displaces must not shift', () => {
    // The invariant, held here because losing it is invisible and expensive: the expander
    // column is driven by CONTENT while sorting and facets are driven by ROW COUNT, and for a
    // while the body grew that column from one signal while the header still keyed on the
    // other. Every header then sat one column left of the values it named — on precisely the
    // tables that displace, which are the ones whose columns most need naming. Nothing threw,
    // the suite stayed green, and the screen simply lied.
    // RAGGED on purpose. A uniform nested shape is flattened into columns, so nothing is
    // displaced and no expander appears — the first version of this test used one and passed
    // against the bug it was written to catch. The rows must disagree for the structure to
    // survive as a structure.
    const displacing = [{ id: 'a', detail: { x: 1 } }, { id: 'b', detail: { y: 2 } }]
    const { container } = render(<StatusValue value={displacing} />)

    const headerCells = container.querySelectorAll('thead tr th').length
    const firstBodyRow = container.querySelector('tbody tr')!
    const bodyCells = firstBodyRow.querySelectorAll('td').length

    expect(headerCells).toBe(bodyCells)
    expect(headerCells).toBeGreaterThan(1)
  })

  it('keeps the values intact — flattening must not change what is shown', () => {
    const { container } = render(<StatusValue value={rows} />)

    expect(container.textContent).toContain('223')
    expect(container.textContent).toContain('291')
    expect(container.textContent).toContain('yes')
    expect(container.textContent).toContain('no')
  })

  it('never spreads the actions machinery into columns', () => {
    const withActions = [
      { name: 'a', actions: [{ command: 'ack' }] },
      { name: 'b', actions: [{ command: 'ack' }] },
    ]
    const { container } = render(<StatusValue value={withActions} />)
    const headers = Array.from(container.querySelectorAll('th')).map(th => th.textContent)

    expect(headers.some(h => h?.startsWith('actions'))).toBe(false)
  })
})

describe('a long list is shortened, but never silently', () => {
  // Measured on the live screen: one blocker row carried three identifier lists and grew
  // to a dozen lines, pushing the other three blockers off the first screenful.
  const many = ['a', 'b', 'c', 'd', 'e', 'f', 'g']

  it('shows a bounded number of chips and states exactly how many are hidden', () => {
    const { container } = render(<StatusValue value={many} />)

    expect(container.textContent).toContain('+2 more')
    expect(container.textContent).toContain('a')
    expect(container.textContent).not.toContain('g')
  })

  it('is one click from complete — shortening is never a truncation', () => {
    const { container } = render(<StatusValue value={many} />)
    fireEvent.click(screen.getByText('+2 more'))

    expect(container.textContent).toContain('g')
    expect(container.textContent).toContain('show fewer')
  })

  it('leaves a short list entirely alone, with no control to click', () => {
    const { container } = render(<StatusValue value={['a', 'b']} />)

    expect(container.querySelector('button')).toBeNull()
    expect(container.textContent).not.toContain('more')
  })

  it('never claims to hide what it is already showing', () => {
    // Exactly at the limit: a "+0 more" would be a false absence, announcing a hidden
    // thing that is on screen.
    const { container } = render(<StatusValue value={['a', 'b', 'c', 'd', 'e']} />)

    expect(container.textContent).not.toContain('more')
    expect(container.textContent).toContain('e')
  })
})

/**
 * The project marking one of ITS fields as the one to act on.
 *
 * This is the mechanism that replaced a request to recognise a domain field name, so the
 * tests below use nonsense keys on purpose — if any of them started needing a real one,
 * the mechanism would have failed at the only thing it exists for.
 *
 * The dangerous direction is not "no emphasis drawn". It is emphasis drawn for something
 * that is not there: the marking is a declaration, and a declaration that outruns the data
 * is exactly the false absence this whole contract keeps having to defend against — now
 * arriving through the channel built to carry intent.
 */
describe('emphasis is declared by the project, never recognised by name', () => {
  const EMPH = '[data-emphasis="true"]'

  it('draws weight on a marked key that is present', () => {
    const { container } = render(
      <StatusValue value={[{ wibble: 'a', wobble: ['x', 'y'], _emphasis: ['wobble'] }]} />,
    )

    const marked = container.querySelector(EMPH)
    expect(marked).not.toBeNull()
    expect(marked!.textContent).toContain('x')
    expect(marked!.textContent).not.toContain('a')
  })

  it('draws NOTHING for a marked key that is absent — a declaration is not data', () => {
    const { container } = render(
      <StatusValue value={[{ wibble: 'a', _emphasis: ['nosuchfield'] }]} />,
    )

    expect(container.querySelector(EMPH)).toBeNull()
    // and no note announcing something that was never there
    expect(container.textContent).not.toMatch(/emphasis|marked|hidden/i)
  })

  it('never renders the marking itself as data', () => {
    const { container } = render(
      <StatusValue value={[{ wibble: 'a', _emphasis: ['wibble'] }]} />,
    )

    expect(container.textContent).not.toContain('_emphasis')
  })

  it('is per row, not per column — a sibling without the marking stays plain', () => {
    const { container } = render(
      <StatusValue
        value={[
          { wibble: 'first', _emphasis: ['wibble'] },
          { wibble: 'second' },
        ]}
      />,
    )

    const marked = container.querySelectorAll(EMPH)
    expect(marked).toHaveLength(1)
    expect(marked[0].textContent).toContain('first')
  })

  it('survives the renderer flattening a nested object into dotted columns', () => {
    // `flattenUniformObjects` renames `wobble` to `wobble.up`. Dropping the marking there
    // would be this side losing a declaration because of something this side did to it.
    const { container } = render(
      <StatusValue
        value={[
          { wibble: 'a', wobble: { up: true, ms: 3 }, _emphasis: ['wobble'] },
          { wibble: 'b', wobble: { up: false, ms: 9 }, _emphasis: ['wobble'] },
        ]}
      />,
    )

    expect(container.textContent).toContain('wobble.up')
    expect(container.querySelectorAll(EMPH).length).toBeGreaterThan(0)
  })

  it('marks the label in a key grid, where there is no column to mark', () => {
    const { container } = render(
      <StatusValue value={{ wibble: 'a', wobble: 'b', _emphasis: ['wobble'] }} />,
    )

    const marked = container.querySelector(EMPH)
    expect(marked).not.toBeNull()
    expect(marked!.textContent).toBe('wobble')
  })

  it('ignores a marking that names a framework key rather than a field', () => {
    const { container } = render(
      <StatusValue value={[{ wibble: 'a', _emphasis: ['_emphasis'] }]} />,
    )

    expect(container.querySelector(EMPH)).toBeNull()
  })

  it('ignores a malformed marking instead of failing the whole render', () => {
    const { container } = render(
      <StatusValue value={[{ wibble: 'a', _emphasis: 'wibble' }]} />,
    )

    expect(container.querySelector(EMPH)).toBeNull()
    expect(container.textContent).toContain('a')
  })
})

/**
 * `false` and "we could not find out" must never look the same.
 *
 * The renderer already keeps them apart; these are GUARDS, not measurements — nothing here
 * failed before they were written, and saying otherwise would be reporting a sentinel as
 * proof. They exist because the distinction stopped being cosmetic: a producer now sends
 * three-valued fields where `false` is a verdict, `true` is a different verdict, and `null`
 * means an input was unreadable. If this renderer collapsed the last two into the first, an
 * unreadable file would appear on screen as the project's own answer — and the reader has
 * no way to tell, because the verdict arrives already formed.
 */
describe('a false is a value, an unknown is not', () => {
  it('renders false as an answer, not as an absence', () => {
    const { container } = render(<StatusValue value={{ wibble: false }} />)

    expect(container.querySelector(UNKNOWN)).toBeNull()
    expect(container.textContent).toContain('no')
  })

  it('renders null as an absence, not as a false', () => {
    const { container } = render(<StatusValue value={{ wibble: null }} />)

    expect(container.querySelector(UNKNOWN)).not.toBeNull()
    expect(container.textContent).not.toContain('no')
  })

  it('keeps all three apart in one row, which is where they actually arrive', () => {
    const { container } = render(
      <StatusValue value={[{ a: true, b: false, c: null }]} />,
    )

    expect(container.querySelectorAll(UNKNOWN)).toHaveLength(1)
    expect(container.textContent).toContain('yes')
    expect(container.textContent).toContain('no')
  })
})

/**
 * The project ranking its own lists, and the renderer honouring a ranking it cannot read.
 *
 * The weight comes from ORDER, so these tests use nonsense severity words on purpose: if
 * any of them started needing `block` or `warn` to pass, the mechanism would have failed at
 * the only thing it exists for — working for the next project, which will use other words,
 * in another language.
 */
describe('sections: the project ranks, the renderer never interprets', () => {
  const HEAVIEST = '.border-l-4'

  it('orders the sections as declared, whatever the severity words are', () => {
    const { container } = render(
      <StatusValue value={{
        wobble: [{ a: 1 }],
        wibble: [{ a: 1 }, { a: 2 }],
        sections: [
          { key: 'wibble', severity: 'zzz', label: 'First' },
          { key: 'wobble', severity: 'aaa', label: 'Second' },
        ],
      }} />,
    )

    const text = container.textContent!
    expect(text.indexOf('First')).toBeLessThan(text.indexOf('Second'))
    // …and the heaviest rule sits on the first, not on the alphabetically-smallest word
    expect(container.querySelector(HEAVIEST)!.textContent).toContain('First')
  })

  it('never renders the declaration itself as data', () => {
    const { container } = render(
      <StatusValue value={{ wibble: [{ a: 1 }], sections: [{ key: 'wibble', label: 'L' }] }} />,
    )

    expect(container.textContent).not.toContain('sections')
  })

  it('draws NOTHING for a declared section that is absent', () => {
    const { container } = render(
      <StatusValue value={{
        wibble: [{ a: 1 }],
        sections: [{ key: 'wibble', label: 'Here' }, { key: 'nosuch', label: 'Gone' }],
      }} />,
    )

    expect(container.textContent).toContain('Here')
    expect(container.textContent).not.toContain('Gone')
  })

  it('still shows a list the declaration forgot to rank', () => {
    const { container } = render(
      <StatusValue value={{
        wibble: [{ a: 1 }],
        forgotten: [{ b: 2 }],
        sections: [{ key: 'wibble', label: 'Ranked' }],
      }} />,
    )

    expect(container.textContent).toContain('forgotten')
  })

  it('counts the rows itself and says so when the declaration disagrees', () => {
    const { container } = render(
      <StatusValue value={{
        wibble: [{ a: 1 }, { a: 2 }],
        sections: [{ key: 'wibble', label: 'L', count: 7 }],
      }} />,
    )

    expect(container.textContent).toContain('2 rows')
    expect(container.textContent).toContain('declared 7, 2 delivered')
    // …and exactly once: a heading that repeats the list's own count is one fact twice.
    expect(container.textContent!.match(/2 rows/g)).toHaveLength(1)
  })

  it('leaves a project\'s OWN sections alone when they are not a declaration', () => {
    // Same key name, real data: objects that do not name siblings.
    const { container } = render(
      <StatusValue value={{
        sections: [{ title: 'Intro', pages: 3 }, { title: 'Body', pages: 40 }],
      }} />,
    )

    expect(container.textContent).toContain('Intro')
    expect(container.textContent).toContain('sections')
  })

  it('is not fooled by a ragged array that merely looks like one', () => {
    const { container } = render(
      <StatusValue value={{
        wibble: [{ a: 1 }],
        sections: [{ key: 'wibble' }, 'not an object'],
      }} />,
    )

    // Falls back to plain rendering: the declaration is not trusted, and nothing vanishes.
    expect(container.textContent).toContain('sections')
    expect(container.textContent).toContain('wibble')
  })
})
