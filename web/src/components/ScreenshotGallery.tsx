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
  // Always scoped to a single attempt — no "all" mix-and-match because
  // viewing 200 thumbnails from multiple attempts at once was not useful.
  // Defaults to the latest attempt as soon as data lands (triage = start
  // with the most recent failure).
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
    // Before the defaulting effect runs (first render frame), attemptFilter
    // is still null. Fall back to the latest attempt's artifacts so the
    // first paint isn't the full union.
    const n = attemptFilter ?? (attempts.length > 0 ? attempts[attempts.length - 1] : null)
    if (n === null) return artifacts
    return artifacts.filter(a => a.attempt === n)
  }, [artifacts, attemptFilter, attempts])

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
    return <div className="px-4 py-6 text-sm text-fg-faint">Loading artifacts...</div>
  }

  if (artifacts.length === 0) {
    return (
      <div className="px-4 py-6 text-sm text-fg-faint space-y-1">
        <div>No test artifacts found.</div>
        <div className="text-xs text-fg-ghost">
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
          ? 'border-blue-500 text-fg-loud bg-surface-panel/40'
          : 'border-transparent text-fg-faint hover:text-fg-normal hover:bg-surface-panel/30'
      }`}
    >
      {children}
    </button>
  )

  return (
    // Fill the parent flex slot — the modal wrapper decides height. We only
    // need flex-col + min-h-0 so our inner flex children can shrink properly.
    <div className="flex flex-col flex-1 min-h-0">
      {/* Attempt TABS + Refresh on one row. `overflow-y-hidden` is explicit
          because `overflow-x-auto` by itself leaves vertical overflow visible,
          and the tabs' `-mb-px` pulls 1px past the border → a vertical
          scrollbar would appear on the right side of the tab row. */}
      {attempts.length > 0 && (
        <div
          className="flex items-center gap-0 px-3 border-b border-surface-line overflow-x-auto"
          style={{ overflowY: 'hidden' }}
        >
          {attempts.map(n => {
            const c = attemptCounts.get(n) ?? { images: 0, others: 0 }
            const effectiveActive = (attemptFilter ?? attempts[attempts.length - 1]) === n
            return (
              <TabBtn
                key={n}
                active={effectiveActive}
                onClick={() => setAttemptFilter(n)}
                title={`attempt #${n}: ${c.images} screenshots, ${c.others} other files`}
              >
                attempt #{n}
                <span className="ml-1 text-xs text-fg-faint">
                  ({c.images} img{c.others > 0 ? ` +${c.others}` : ''})
                </span>
              </TabBtn>
            )
          })}
          {/* Refresh sits on the tab-bar baseline on the right, outside the
              tab group so it doesn't overflow sideways. */}
          <div className="ml-auto pr-1">
            <button
              onClick={loadArtifacts}
              className="text-xs text-fg-ghost hover:text-fg-normal px-1.5 py-0.5 rounded hover:bg-surface-raised transition-colors"
              title="Re-scan worktree for artifacts"
            >
              Refresh
            </button>
          </div>
        </div>
      )}

      {/* Row 3: summary strip (counts + image counter for the active tab) */}
      <div className="flex items-center justify-between px-4 py-1 bg-surface-panel/40 border-b border-surface-line text-xs text-fg-faint">
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
            <div className="flex-1 min-h-[280px] relative bg-surface-page flex items-center justify-center px-2 py-2">
              {selectedIndex > 0 && (
                <button
                  onClick={() => setSelectedIndex(i => i - 1)}
                  className="absolute left-2 top-1/2 -translate-y-1/2 w-8 h-8 bg-surface-raised/80 hover:bg-surface-strong rounded-full flex items-center justify-center text-fg-normal z-10"
                >
                  &lt;
                </button>
              )}
              {selectedIndex < images.length - 1 && (
                <button
                  onClick={() => setSelectedIndex(i => i + 1)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 w-8 h-8 bg-surface-raised/80 hover:bg-surface-strong rounded-full flex items-center justify-center text-fg-normal z-10"
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
            <div className="px-4 py-1.5 border-t border-surface-line bg-surface-panel/50 flex items-center gap-2 flex-shrink-0">
              {typeof selected?.attempt === 'number' && (
                <span className="text-xs font-bold px-1.5 py-0.5 rounded uppercase bg-surface-strong text-fg-strong">
                  #{selected.attempt}
                </span>
              )}
              {selected?.result && (
                <span className={`text-xs font-bold px-1.5 py-0.5 rounded uppercase ${
                  selected.result === 'fail'
                    ? 'bg-red-500/20 text-red-400'
                    : 'bg-green-500/15 text-green-500/80'
                }`}>
                  {selected.result === 'fail' ? 'FAIL' : 'PASS'}
                </span>
              )}
              <span className="text-xs text-fg-muted truncate flex-1" title={selected?.test || ''}>
                {testLabel}
              </span>
              {selected?.meta && (
                <span
                  className="text-xs text-fg-faint flex-shrink-0"
                  dangerouslySetInnerHTML={{ __html: selected.meta }}
                />
              )}
            </div>

            {/* Thumbnail strip — horizontal scroll, fixed height so it never
                eats the viewer area. */}
            <div className="flex gap-1 px-3 py-2 overflow-x-auto bg-surface-panel/30 flex-shrink-0" style={{ height: 68 }}>
              {images.map((img, i) => (
                <button
                  key={img.path}
                  onClick={() => setSelectedIndex(i)}
                  className={`flex-shrink-0 w-16 h-11 rounded overflow-hidden border-2 transition-all relative ${
                    i === selectedIndex
                      ? 'border-blue-500 opacity-100 scale-105'
                      : img.result === 'fail'
                        ? 'border-red-500/60 opacity-80 hover:opacity-100'
                        : 'border-transparent opacity-60 hover:opacity-90 hover:border-surface-edge-soft'
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
          <div className="flex-1 flex items-center justify-center text-sm text-fg-faint min-h-[200px]">
            No screenshots in this attempt
            {nonImages.length > 0 && ' — see other files below'}
            .
          </div>
        )}

        {/* Non-image artifacts: collapsible drawer so 121 items don't flood
            the dialog. Header is always visible with the count. */}
        {nonImages.length > 0 && (
          <div className="border-t border-surface-line flex-shrink-0">
            <button
              onClick={() => setOtherFilesOpen(v => !v)}
              className="w-full flex items-center justify-between px-4 py-2 text-xs text-fg-muted hover:bg-surface-panel/30 transition-colors"
            >
              <span>
                Other files <span className="text-fg-ghost">({nonImages.length})</span>
              </span>
              <span className="text-fg-faint">{otherFilesOpen ? '▼ hide' : '▶ show'}</span>
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
                      className="flex items-center gap-1.5 px-2 py-1 rounded border border-surface-line text-xs text-fg-muted hover:border-surface-edge-soft hover:text-fg-strong transition-colors"
                      title={
                        (typeof a.attempt === 'number' ? `attempt #${a.attempt} · ` : '') +
                        (a.test ?? '') + ' · ' +
                        (openInline ? 'open inline' : 'download')
                      }
                    >
                      {typeof a.attempt === 'number' && (
                        <span className="text-xs font-semibold text-fg-faint">#{a.attempt}</span>
                      )}
                      <span className="truncate max-w-[180px]">{a.name}</span>
                      <span className="text-xs text-fg-ghost">{a.type}</span>
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
