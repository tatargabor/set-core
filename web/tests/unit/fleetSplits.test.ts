/**
 * Divider positions — the pure half: what a stored number means, and what an
 * ABSENT one means.
 *
 * The whole hazard in this module is one distinction. A divider nobody dragged
 * has no stored position, and that is not the same as a stored zero: a pane at
 * zero renders as no pane at all, and the edge needed to drag it back is exactly
 * what is no longer on screen. So every one of these tests is really the same
 * question asked from a different side — does an absence stay an absence, or does
 * it quietly become a value?
 */
import { describe, expect, it, vi } from 'vitest'
import {
  MAX_PANE, MIN_PANE, SPLIT_PROJECTS, clampPane, loadSplits, positionOf, saveSplits,
} from '../../src/lib/fleetSplits'

describe('a stored divider position', () => {
  it('is used when it exists', () => {
    expect(positionOf({ [SPLIT_PROJECTS]: 340 }, SPLIT_PROJECTS, 288)).toBe(340)
  })

  it('falls back to the caller default when the key is absent — NOT to zero', () => {
    expect(positionOf({}, SPLIT_PROJECTS, 288)).toBe(288)
    expect(positionOf(null, SPLIT_PROJECTS, 288)).toBe(288)
    expect(positionOf(undefined, SPLIT_PROJECTS, 288)).toBe(288)
  })

  it('treats a non-number as absent rather than coercing it', () => {
    // A hand-edited file or an older store can carry anything. Coercing "300px"
    // to 300 would be a guess that happens to be right; coercing it to NaN and
    // rendering that is a pane with no width. Both are worse than the default.
    expect(positionOf({ a: '300' } as never, 'a', 288)).toBe(288)
    expect(positionOf({ a: Number.NaN }, 'a', 288)).toBe(288)
  })

  it('clamps a stored value that is outside what the surface can render', () => {
    expect(positionOf({ a: 5 }, 'a', 288)).toBe(MIN_PANE)
    expect(positionOf({ a: 99999 }, 'a', 288)).toBe(MAX_PANE)
  })
})

describe('clampPane', () => {
  it('never returns something the user cannot grab again', () => {
    expect(clampPane(0)).toBe(MIN_PANE)
    expect(clampPane(-40)).toBe(MIN_PANE)
    expect(clampPane(Number.NaN)).toBe(MIN_PANE)
  })

  it('honours a caller-supplied maximum, because the window is not a constant', () => {
    // The static MAX_PANE is about sanity; the shell's own width is about fit.
    expect(clampPane(800, 500)).toBe(500)
  })
})

describe('reading and writing the store', () => {
  it('reads the positions out of the layout document', async () => {
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true, json: async () => ({ version: 3, groups: [], splits: { projects: 320 } }),
    }) as unknown as typeof fetch
    expect(await loadSplits(fetchImpl)).toEqual({ projects: 320 })
  })

  it('reports NO positions rather than failing when the store cannot be read', async () => {
    // A screen that refuses to render because a preference is unreadable is a
    // worse outcome than one rendering at its defaults.
    const boom = vi.fn().mockRejectedValue(new Error('offline')) as unknown as typeof fetch
    expect(await loadSplits(boom)).toEqual({})
    const http500 = vi.fn().mockResolvedValue({ ok: false, status: 500 }) as unknown as typeof fetch
    expect(await loadSplits(http500)).toEqual({})
  })

  it('drops a non-numeric entry on the way in', async () => {
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true, json: async () => ({ splits: { projects: 320, broken: 'wide' } }),
    }) as unknown as typeof fetch
    expect(await loadSplits(fetchImpl)).toEqual({ projects: 320 })
  })

  it('writes to the divider route, not to the version-guarded layout PUT', async () => {
    // The distinction is the point: the layout PUT carries `base_version` and
    // protects a hand-made arrangement. Dragging an edge through it would make
    // the next group edit conflict with the user's own dragging.
    const fetchImpl = vi.fn().mockResolvedValue({ ok: true }) as unknown as typeof fetch
    await saveSplits({ projects: 320 }, fetchImpl)
    const [url, init] = (fetchImpl as unknown as ReturnType<typeof vi.fn>).mock.calls[0]
    expect(url).toBe('/api/fleet/layout/splits')
    expect(init.method).toBe('PUT')
    expect(JSON.parse(init.body)).toEqual({ splits: { projects: 320 } })
  })

  it('says whether the write landed instead of throwing at the caller', async () => {
    const ok = vi.fn().mockResolvedValue({ ok: true }) as unknown as typeof fetch
    expect(await saveSplits({}, ok)).toBe(true)
    const boom = vi.fn().mockRejectedValue(new Error('offline')) as unknown as typeof fetch
    expect(await saveSplits({}, boom)).toBe(false)
  })
})
