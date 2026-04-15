import { useEffect, useState, useMemo } from 'react'

interface Artifact {
  path: string
  name: string
  type: string  // "image" | "trace" | "report" | "log" | "video"
  test?: string
  result?: string  // "pass" | "fail" — from profile plugin
  label?: string   // human-readable test name
  meta?: string    // HTML snippet with extra details (populated by profile plugin)
  attempt?: number // 1..N — which verify-gate attempt produced this file
}

interface Props {
  project: string
  changeName: string
  onClose: () => void
}

export default function ScreenshotGallery({ project, changeName, onClose }: Props) {
  const [artifacts, setArtifacts] = useState<Artifact[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedIndex, setSelectedIndex] = useState(0)
  // null = show all attempts, number = show only that attempt. Defaults to
  // the latest attempt once data arrives — that's the most useful entry
  // point when triaging a run.
  const [attemptFilter, setAttemptFilter] = useState<number | null>(null)
  const [otherFilesOpen, setOtherFilesOpen] = useState(false)

  const loadArtifacts = () => {
    setLoading(true)
    fetch(`/api/${project}/changes/${changeName}/screenshots`)
      .then(r => r.json())
      .then((data) => {
        const items: Artifact[] = data.artifacts ?? data.e2e ?? []
        setArtifacts(items)
      })
      .catch(() => setArtifacts([]))
      .finally(() => setLoading(false))
  }

  useEffect(() => { loadArtifacts() }, [project, changeName])

  const attempts = useMemo(() => {
    const s = new Set<number>()
    for (const a of artifacts) if (typeof a.attempt === 'number') s.add(a.attempt)
    return [...s].sort((a, b) => a - b)
  }, [artifacts])

  // Once data loads, default to the latest attempt. This makes the common
  // case (triage the most recent failure) a single click instead of wading
  // through 80+ files from every prior attempt mixed together.
  useEffect(() => {
    if (attempts.length > 0 && attemptFilter === null) {
      setAttemptFilter(attempts[attempts.length - 1])
    }
  }, [attempts.length])  // eslint-disable-line react-hooks/exhaustive-deps

  const filtered = useMemo(() => {
    if (attemptFilter === null) return artifacts
    return artifacts.filter(a => a.attempt === attemptFilter)
  }, [artifacts, attemptFilter])

  // Reset selection when filter changes so we don't point at a hidden image.
  useEffect(() => { setSelectedIndex(0) }, [attemptFilter])

  const images = useMemo(() => filtered.filter(a => a.type === 'image'), [filtered])
  const nonImages = useMemo(() => filtered.filter(a => a.type !== 'image'), [filtered])

  // Counts per attempt for the tab labels.
  const attemptCounts = useMemo(() => {
    const m = new Map<number, { images: number; others: number }>()
    for (const n of attempts) m.set(n, { images: 0, others: 0 })
    for (const a of artifacts) {
      if (typeof a.attempt !== 'number') continue
      const c = m.get(a.attempt)
      if (!c) continue
      if (a.type === 'image') c.images += 1
      else c.others += 1
    }
    return m
  }, [artifacts, attempts])

  const serveUrl = (a: Artifact) => {
    const parts = a.path.split('/').map(p => encodeURIComponent(p))
    return `/api/${project}/screenshots/${parts.join('/')}`
  }

  // Keyboard navigation
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
        e.preventDefault()
        setSelectedIndex(i => Math.min(i + 1, images.length - 1))
      } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
        e.preventDefault()
        setSelectedIndex(i => Math.max(i - 1, 0))
      } else if (e.key === 'Escape') {
        onClose()
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [images.length, onClose])

  if (loading) {
    return <div className="px-4 py-6 text-sm text-neutral-500">Loading artifacts...</div>
  }

  if (artifacts.length === 0) {
    return (
      <div className="px-4 py-6 text-sm text-neutral-500 space-y-1">
        <div>No test artifacts found.</div>
        <div className="text-xs text-neutral-600">
          Playwright runs with <code>screenshot: only-on-failure</code> —
          nothing is written when every test passes. Previous failing
          attempts would be archived under{' '}
          <code>runtime/{changeName}/screenshots/e2e/.../attempt-N/</code>{' '}
          but none exist for this change.
        </div>
      </div>
    )
  }

  const selected = images[selectedIndex]
  const testLabel = selected?.label
    || selected?.test
      ?.replace(/-chromium$/, '')
      ?.replace(/^[a-z]+-/, '')
      ?.replace(/-{2,}/g, ' — ')
      ?.replace(/-/g, ' ')
    || selected?.name || ''

  const TabBtn = ({
    active, onClick, children, title,
  }: {
    active: boolean
    onClick: () => void
    children: React.ReactNode
    title?: string
  }) => (
    <button
      onClick={onClick}
      title={title}
      className={`px-3 py-1.5 text-xs transition-colors border-b-2 -mb-px whitespace-nowrap ${
        active
          ? 'border-blue-500 text-neutral-100 bg-neutral-900/40'
          : 'border-transparent text-neutral-500 hover:text-neutral-300 hover:bg-neutral-900/30'
      }`}
    >
      {children}
    </button>
  )

  return (
    <div className="flex flex-col" style={{ height: 'min(85vh, 800px)' }}>
      {/* Row 1: title + close */}
      <div className="flex items-center justify-between px-4 pt-2 pb-1">
        <div className="text-sm text-neutral-300 font-medium truncate">
          Test Artifacts: <span className="text-neutral-500">{changeName}</span>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={loadArtifacts}
            className="text-xs text-neutral-600 hover:text-neutral-300 px-1.5 py-0.5 rounded hover:bg-neutral-800 transition-colors"
            title="Re-scan worktree for artifacts"
          >
            Refresh
          </button>
          <button
            onClick={onClose}
            className="text-lg leading-none text-neutral-500 hover:text-neutral-300"
            title="Close (Esc)"
          >
            ×
          </button>
        </div>
      </div>

      {/* Row 2: attempt TABS (an actual tab bar, not pill filters). */}
      {attempts.length > 0 && (
        <div className="flex items-center gap-0 px-3 border-b border-neutral-800 overflow-x-auto">
          {attempts.length > 1 && (
            <TabBtn
              active={attemptFilter === null}
              onClick={() => setAttemptFilter(null)}
              title="Show artifacts from every attempt"
            >
              all
              <span className="ml-1 text-[10px] text-neutral-500">
                {artifacts.length}
              </span>
            </TabBtn>
          )}
          {attempts.map(n => {
            const c = attemptCounts.get(n) ?? { images: 0, others: 0 }
            return (
              <TabBtn
                key={n}
                active={attemptFilter === n}
                onClick={() => setAttemptFilter(n)}
                title={`attempt #${n}: ${c.images} screenshots, ${c.others} other files`}
              >
                attempt #{n}
                <span className="ml-1 text-[10px] text-neutral-500">
                  {c.images}📷{c.others > 0 ? ` +${c.others}` : ''}
                </span>
              </TabBtn>
            )
          })}
        </div>
      )}

      {/* Row 3: summary strip (counts + image counter for the active tab) */}
      <div className="flex items-center justify-between px-4 py-1 bg-neutral-900/40 border-b border-neutral-800 text-[11px] text-neutral-500">
        <span>
          {images.length} {images.length === 1 ? 'screenshot' : 'screenshots'}
          {nonImages.length > 0 && ` · ${nonImages.length} other files`}
        </span>
        {images.length > 0 && (
          <span>{selectedIndex + 1} / {images.length}</span>
        )}
      </div>

      {/* Main body: split between image viewer (top, flex-1) and other
          files (bottom, fixed-height collapsible). */}
      <div className="flex flex-col flex-1 min-h-0">
        {images.length > 0 ? (
          <>
            {/* Main preview */}
            <div className="flex-1 min-h-[280px] relative bg-neutral-950 flex items-center justify-center px-2 py-2">
              {selectedIndex > 0 && (
                <button
                  onClick={() => setSelectedIndex(i => i - 1)}
                  className="absolute left-2 top-1/2 -translate-y-1/2 w-8 h-8 bg-neutral-800/80 hover:bg-neutral-700 rounded-full flex items-center justify-center text-neutral-300 z-10"
                >
                  &lt;
                </button>
              )}
              {selectedIndex < images.length - 1 && (
                <button
                  onClick={() => setSelectedIndex(i => i + 1)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 w-8 h-8 bg-neutral-800/80 hover:bg-neutral-700 rounded-full flex items-center justify-center text-neutral-300 z-10"
                >
                  &gt;
                </button>
              )}
              <img
                src={serveUrl(selected)}
                alt={testLabel}
                className="max-w-full max-h-full object-contain rounded"
              />
            </div>

            {/* Caption row */}
            <div className="px-4 py-1.5 border-t border-neutral-800 bg-neutral-900/50 flex items-center gap-2 flex-shrink-0">
              {typeof selected?.attempt === 'number' && (
                <span className="text-[10px] font-bold px-1.5 py-0.5 rounded uppercase bg-neutral-700 text-neutral-200">
                  #{selected.attempt}
                </span>
              )}
              {selected?.result && (
                <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded uppercase ${
                  selected.result === 'fail'
                    ? 'bg-red-500/20 text-red-400'
                    : 'bg-green-500/15 text-green-500/80'
                }`}>
                  {selected.result === 'fail' ? 'FAIL' : 'PASS'}
                </span>
              )}
              <span className="text-xs text-neutral-400 truncate flex-1" title={selected?.test || ''}>
                {testLabel}
              </span>
              {selected?.meta && (
                <span
                  className="text-[11px] text-neutral-500 flex-shrink-0"
                  dangerouslySetInnerHTML={{ __html: selected.meta }}
                />
              )}
            </div>

            {/* Thumbnail strip — horizontal scroll, fixed height so it never
                eats the viewer area. */}
            <div className="flex gap-1 px-3 py-2 overflow-x-auto bg-neutral-900/30 flex-shrink-0" style={{ height: 68 }}>
              {images.map((img, i) => (
                <button
                  key={img.path}
                  onClick={() => setSelectedIndex(i)}
                  className={`flex-shrink-0 w-16 h-11 rounded overflow-hidden border-2 transition-all relative ${
                    i === selectedIndex
                      ? 'border-blue-500 opacity-100 scale-105'
                      : img.result === 'fail'
                        ? 'border-red-500/60 opacity-80 hover:opacity-100'
                        : 'border-transparent opacity-60 hover:opacity-90 hover:border-neutral-600'
                  }`}
                  title={img.label || img.test?.replace(/-chromium$/, '').replace(/-/g, ' ')}
                >
                  <img
                    src={serveUrl(img)}
                    alt=""
                    className="w-full h-full object-cover"
                    loading="lazy"
                  />
                  {img.result === 'fail' && (
                    <div className="absolute top-0 right-0 w-2 h-2 bg-red-500 rounded-bl" />
                  )}
                </button>
              ))}
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center text-sm text-neutral-500 min-h-[200px]">
            No screenshots in this attempt
            {nonImages.length > 0 && ' — see other files below'}
            .
          </div>
        )}

        {/* Non-image artifacts: collapsible drawer so 121 items don't flood
            the dialog. Header is always visible with the count. */}
        {nonImages.length > 0 && (
          <div className="border-t border-neutral-800 flex-shrink-0">
            <button
              onClick={() => setOtherFilesOpen(v => !v)}
              className="w-full flex items-center justify-between px-4 py-2 text-xs text-neutral-400 hover:bg-neutral-900/30 transition-colors"
            >
              <span>
                Other files <span className="text-neutral-600">({nonImages.length})</span>
              </span>
              <span className="text-neutral-500">{otherFilesOpen ? '▼ hide' : '▶ show'}</span>
            </button>
            {otherFilesOpen && (
              <div
                className="flex flex-wrap gap-1.5 px-4 pb-3 pt-1 overflow-y-auto"
                style={{ maxHeight: 180 }}
              >
                {nonImages.map(a => {
                  // Text formats open inline in a new tab; binary formats download.
                  const inlineTextTypes = new Set(['report', 'log'])
                  const openInline = inlineTextTypes.has(a.type)
                  return (
                    <a
                      key={a.path}
                      href={serveUrl(a)}
                      {...(openInline
                        ? { target: '_blank', rel: 'noopener noreferrer' }
                        : { download: a.name })}
                      className="flex items-center gap-1.5 px-2 py-1 rounded border border-neutral-800 text-xs text-neutral-400 hover:border-neutral-600 hover:text-neutral-200 transition-colors"
                      title={
                        (typeof a.attempt === 'number' ? `attempt #${a.attempt} · ` : '') +
                        (a.test ?? '') + ' · ' +
                        (openInline ? 'open inline' : 'download')
                      }
                    >
                      {typeof a.attempt === 'number' && (
                        <span className="text-[10px] font-semibold text-neutral-500">#{a.attempt}</span>
                      )}
                      <span className="truncate max-w-[180px]">{a.name}</span>
                      <span className="text-[10px] text-neutral-600">{a.type}</span>
                    </a>
                  )
                })}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
