import { useEffect, useState, useMemo } from 'react'

interface Artifact {
  path: string
  name: string
  type: string  // "image" | "trace" | "report" | "log"
  test?: string
  result?: string  // "pass" | "fail" — from profile plugin
  label?: string   // human-readable test name
  meta?: string    // HTML snippet with extra details (populated by profile plugin)
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

  const loadArtifacts = () => {
    setLoading(true)
    fetch(`/api/${project}/changes/${changeName}/screenshots`)
      .then(r => r.json())
      .then((data) => {
        const items = data.artifacts ?? data.e2e ?? []
        setArtifacts(items)
      })
      .catch(() => setArtifacts([]))
      .finally(() => setLoading(false))
  }

  useEffect(() => { loadArtifacts() }, [project, changeName])

  const images = useMemo(() => artifacts.filter(a => a.type === 'image'), [artifacts])
  const nonImages = useMemo(() => artifacts.filter(a => a.type !== 'image'), [artifacts])

  const serveUrl = (a: Artifact) => `/api/${project}/screenshots/${encodeURIComponent(a.path)}`

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
    return <div className="px-4 py-6 text-sm text-neutral-500">No test artifacts found</div>
  }

  const selected = images[selectedIndex]
  const testLabel = selected?.label
    || selected?.test
      ?.replace(/-chromium$/, '')
      ?.replace(/^[a-z]+-/, '')
      ?.replace(/-{2,}/g, ' — ')
      ?.replace(/-/g, ' ')
    || selected?.name || ''

  return (
    <div className="flex flex-col" style={{ height: 'min(80vh, 700px)' }}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-neutral-800">
        <div className="flex items-center gap-3">
          <span className="text-sm text-neutral-300 font-medium">
            {images.length} screenshots
          </span>
          {nonImages.length > 0 && (
            <span className="text-xs text-neutral-500">+ {nonImages.length} other files</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-neutral-600">
            {selectedIndex + 1} / {images.length}
          </span>
          <button
            onClick={loadArtifacts}
            className="text-xs text-neutral-600 hover:text-neutral-300 px-1.5 py-0.5 rounded hover:bg-neutral-800 transition-colors"
            title="Re-scan worktree for artifacts"
          >
            Refresh
          </button>
          <button onClick={onClose} className="text-sm text-neutral-500 hover:text-neutral-300 ml-1">
            Close
          </button>
        </div>
      </div>

      {images.length > 0 && (
        <>
          {/* Main preview */}
          <div className="flex-1 min-h-0 relative bg-neutral-950 flex items-center justify-center px-2 py-2">
            {/* Nav arrows */}
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

          {/* Test name + meta label */}
          <div className="px-4 py-1.5 border-b border-neutral-800 bg-neutral-900/50 flex items-center gap-2">
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

          {/* Thumbnail strip */}
          <div className="flex gap-1 px-3 py-2 overflow-x-auto bg-neutral-900/30" style={{ minHeight: 64 }}>
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
      )}

      {/* Non-image artifacts */}
      {nonImages.length > 0 && (
        <div className="px-4 py-2 border-t border-neutral-800 space-y-1">
          <div className="text-xs text-neutral-500 mb-1">Other files</div>
          <div className="flex flex-wrap gap-1.5">
            {nonImages.map(a => (
              <a
                key={a.path}
                href={serveUrl(a)}
                download={a.name}
                className="flex items-center gap-1.5 px-2 py-1 rounded border border-neutral-800 text-xs text-neutral-400 hover:border-neutral-600 hover:text-neutral-200 transition-colors"
              >
                <span className="truncate max-w-[140px]">{a.name}</span>
              </a>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
