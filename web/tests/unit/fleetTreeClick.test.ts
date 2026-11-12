/**
 * `treeClickAct` — a tree click changes the layout only when the agent is not
 * already on screen in it. Reported 2026-10-09: the click always enlarged, and
 * so overwrote a side-by-side layout the reader had built.
 */
import { describe, expect, it } from 'vitest'

import { treeClickAct } from '../../src/lib/fleetViewState'

describe('treeClickAct', () => {
  it('keeps a side-by-side grid — both agents are already visible', () => {
    expect(treeClickAct({ enlarged: null }, [1, 2], 2, false)).toBe('keep')
    expect(treeClickAct({}, [1, 2], 2, false)).toBe('keep')
  })

  it('keeps the layout when the agent is the enlarged one', () => {
    expect(treeClickAct({ enlarged: 2 }, [1, 2], 2, false)).toBe('keep')
  })

  it('enlarges an agent that sits behind a tab', () => {
    expect(treeClickAct({ enlarged: 1 }, [1, 2], 2, false)).toBe('enlarge')
  })

  it('enlarges when a maximised file view or board covers the agents', () => {
    expect(treeClickAct({ enlarged: null }, [1, 2], 2, true)).toBe('enlarge')
  })

  it('switches WHICH agent is shown alone, keeping the full-screen layout', () => {
    expect(treeClickAct({ focus: 1 }, [1, 2], 2, false)).toBe('focus')
    expect(treeClickAct({ focus: 2 }, [1, 2], 2, false)).toBe('keep')
  })

  it('keeps the layout for a docked agent — it is on its edge, not in the grid', () => {
    expect(treeClickAct({ enlarged: 1 }, [1], 2, false)).toBe('keep')
  })
})
