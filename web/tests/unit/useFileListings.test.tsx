/**
 * B-180: one `/api/fleet/files` request per checkout, not one per re-render.
 *
 * The defect was a cancellation: each arriving listing re-ran the effect, whose
 * cleanup discarded every reply still in flight, so those roots were requested
 * again — and a root set re-created on every fleet poll did the same. These
 * tests hold both triggers: a new array identity with the same roots, and a
 * listing arriving while another is still pending.
 */
import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { useFileListings } from '../../src/hooks/useFileListings'

type Pending = { root: string; resolve: (files: string[]) => void }

function deferredFetch() {
  const pending: Pending[] = []
  const fetchMock = vi.fn((url: string) => {
    const root = decodeURIComponent(url.split('root=')[1])
    return new Promise<Response>(res => {
      pending.push({
        root,
        resolve: files => res({ ok: true, json: async () => ({ files }) } as Response),
      })
    })
  })
  vi.stubGlobal('fetch', fetchMock)
  return { fetchMock, pending }
}

afterEach(() => { vi.unstubAllGlobals() })

describe('useFileListings', () => {
  it('fetches each root exactly once while re-rendered with fresh arrays and staggered replies', async () => {
    const { fetchMock, pending } = deferredFetch()
    const { result, rerender } = renderHook(
      ({ roots, on }) => useFileListings(roots, on),
      { initialProps: { roots: ['/a', '/b', '/c'], on: true } },
    )
    expect(fetchMock).toHaveBeenCalledTimes(3)

    // A fleet poll: same roots, new array.
    rerender({ roots: ['/a', '/b', '/c'], on: true })
    rerender({ roots: ['/a', '/b', '/c'], on: true })
    expect(fetchMock).toHaveBeenCalledTimes(3)

    // One reply lands while the other two are still in flight.
    await act(async () => { pending.find(p => p.root === '/a')!.resolve(['x.ts']) })
    await waitFor(() => expect(result.current['/a']).toBeDefined())
    rerender({ roots: ['/a', '/b', '/c'], on: true })
    expect(fetchMock).toHaveBeenCalledTimes(3)

    // The replies that were in flight across those re-renders are kept, not discarded.
    await act(async () => {
      pending.find(p => p.root === '/b')!.resolve(['y.ts'])
      pending.find(p => p.root === '/c')!.resolve(['z.ts'])
    })
    await waitFor(() => expect(Object.keys(result.current).sort()).toEqual(['/a', '/b', '/c']))
    expect([...result.current['/b']]).toEqual(['y.ts'])
    expect(fetchMock).toHaveBeenCalledTimes(3)
  })

  it('asks for nothing while disabled, and only for the new root when one is added', async () => {
    const { fetchMock, pending } = deferredFetch()
    const { rerender } = renderHook(
      ({ roots, on }) => useFileListings(roots, on),
      { initialProps: { roots: ['/a'], on: false } },
    )
    expect(fetchMock).not.toHaveBeenCalled()
    rerender({ roots: ['/a'], on: true })
    expect(fetchMock).toHaveBeenCalledTimes(1)
    await act(async () => { pending[0].resolve([]) })
    rerender({ roots: ['/a', '/d'], on: true })
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(decodeURIComponent(fetchMock.mock.calls[1][0] as string)).toContain('/d')
  })

  it('retries a root whose request failed, on the next change of the root set', async () => {
    const fetchMock = vi.fn(async () => ({ ok: false, json: async () => null }) as Response)
    vi.stubGlobal('fetch', fetchMock)
    const { rerender } = renderHook(
      ({ roots }) => useFileListings(roots, true),
      { initialProps: { roots: ['/a'] } },
    )
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
    // Let the failed request leave the in-flight set.
    await act(async () => { await Promise.resolve() })
    rerender({ roots: ['/a'] })
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
  })
})
