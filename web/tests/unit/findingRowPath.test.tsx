/**
 * A finding names a file the reader must be able to OPEN.
 *
 * The stored `file` is relative to the repository root and the base is not written next to
 * it, so pasting it into a terminal or an editor resolves nowhere — silently, because an
 * unopenable path looks exactly like an openable one until somebody clicks it. The server
 * resolves it into `file_abs`; this row must show that, and must still show something when
 * the server could not resolve it.
 */
import { describe, expect, it } from 'vitest'
import { fireEvent, render } from '@testing-library/react'

import { FindingRow } from '../../src/components/LearningsPanel'

const base = { severity: 'CRITICAL', summary: 'IDOR on order lookup', change: 'add-orders', attempt: 1 }

function expand(container: HTMLElement) {
  fireEvent.click(container.querySelector('button')!)
}

describe('FindingRow — the path it shows', () => {
  it('shows the resolved absolute path, not the stored relative one', () => {
    const { container } = render(
      <FindingRow issue={{ ...base, file: 'src/api/orders.ts', file_abs: '/home/u/p/src/api/orders.ts' }} />,
    )
    expand(container)
    expect(container.textContent).toContain('/home/u/p/src/api/orders.ts')
  })

  it('falls back to the stored path when the server resolved nothing', () => {
    // An empty field would read as "this finding has no file", which is a different and
    // wrong statement — the fail direction that hides information.
    const { container } = render(
      <FindingRow issue={{ ...base, file: 'src/api/orders.ts', file_abs: '' }} />,
    )
    expand(container)
    expect(container.textContent).toContain('src/api/orders.ts')
  })

  it('shows no File row at all when there is no path either way', () => {
    const { container } = render(<FindingRow issue={{ ...base }} />)
    expand(container)
    expect(container.textContent).not.toContain('File:')
  })

  it('keeps the line number beside the resolved path', () => {
    const { container } = render(
      <FindingRow issue={{ ...base, file: 'a.ts', file_abs: '/home/u/p/a.ts', line: '142' }} />,
    )
    expand(container)
    expect(container.textContent).toContain('/home/u/p/a.ts')
    expect(container.textContent).toContain('L142')
  })

  it('lets a long absolute path wrap instead of overflowing its column', () => {
    const { container } = render(
      <FindingRow issue={{ ...base, file_abs: '/home/u/very/deep/nested/project/src/api/orders.ts' }} />,
    )
    expand(container)
    const span = Array.from(container.querySelectorAll('span')).find(
      (el) => el.textContent === '/home/u/very/deep/nested/project/src/api/orders.ts',
    )
    expect(span?.className).toContain('break-all')
  })
})
