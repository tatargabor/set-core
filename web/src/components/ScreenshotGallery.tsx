import { useEffect, useState } from 'react'

interface Artifact {
  path: string
  name: string
  type: string  // "image" | "trace" | "report" | "log"
  test?: string
}

interface Props {
  project: string
  changeName: string
  onClose: () => void
}

const TYPE_ICONS: Record<string, string> = {
  image: '',
  trace: '{}',
  report: 'doc',
  log: 'log',
}

export default function ScreenshotGallery({ project, changeName, onClose }: Props) {
  const [artifacts, setArtifacts] = useState<Artifact[]>([])
  const [loading, setLoading] = useState(true)
  const [modalImg, setModalImg] = useState<string | null>(null)

  useEffect(() => {
    setLoading(true)
    fetch(`/api/${project}/changes/${changeName}/screenshots`)
      .then(r => r.json())
      .then((data) => {
        // Use unified artifacts list, fallback to e2e array
        const items = data.artifacts ?? data.e2e ?? []
        setArtifacts(items)
      })
      .catch(() => setArtifacts([]))
      .finally(() => setLoading(false))
  }, [project, changeName])

  const serveUrl = (a: Artifact) => `/api/${project}/screenshots/${encodeURIComponent(a.path)}`

  if (loading) {
    return <div className="px-4 py-3 text-sm text-neutral-500">Loading artifacts...</div>
  }

  if (artifacts.length === 0) {
    return <div className="px-4 py-3 text-sm text-neutral-500">No test artifacts found</div>
  }

  // Group by test name
  const byTest: Record<string, Artifact[]> = {}
  for (const a of artifacts) {
    const key = a.test || '_ungrouped'
    if (!byTest[key]) byTest[key] = []
    byTest[key].push(a)
  }

  return (
    <>
      <div className="px-4 py-3 space-y-2">
        <div className="flex items-center justify-between mb-1">
          <span className="text-sm text-neutral-400">{artifacts.length} artifact(s)</span>
          <button onClick={onClose} className="text-sm text-neutral-500 hover:text-neutral-300">Close</button>
        </div>

        {Object.entries(byTest).map(([testName, items]) => (
          <div key={testName}>
            {testName !== '_ungrouped' && (
              <div className="text-xs text-neutral-500 mb-1 truncate" title={testName}>{testName}</div>
            )}
            <div className="flex flex-wrap gap-1.5">
              {items.map(a => (
                a.type === 'image' ? (
                  <button
                    key={a.path}
                    onClick={() => setModalImg(serveUrl(a))}
                    className="group relative w-28 h-18 rounded border border-neutral-800 overflow-hidden hover:border-neutral-500 transition-colors"
                    title={a.test || a.name}
                  >
                    <img
                      src={serveUrl(a)}
                      alt={a.name}
                      className="w-full h-full object-cover"
                      loading="lazy"
                    />
                  </button>
                ) : (
                  <a
                    key={a.path}
                    href={serveUrl(a)}
                    download={a.name}
                    className="flex items-center gap-1.5 px-2.5 py-1.5 rounded border border-neutral-800 text-sm text-neutral-400 hover:border-neutral-500 hover:text-neutral-200 transition-colors"
                    title={`Download ${a.name}`}
                  >
                    <span className="text-xs text-neutral-600">{TYPE_ICONS[a.type] || a.type}</span>
                    <span className="truncate max-w-[120px]">{a.name}</span>
                  </a>
                )
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* Modal overlay for images */}
      {modalImg && (
        <div
          className="fixed inset-0 z-50 bg-black/85 flex items-center justify-center"
          onClick={() => setModalImg(null)}
        >
          <div className="relative max-w-[90vw] max-h-[90vh]" onClick={e => e.stopPropagation()}>
            <img
              src={modalImg}
              alt="Test screenshot"
              className="max-w-full max-h-[90vh] rounded shadow-2xl"
            />
            <button
              onClick={() => setModalImg(null)}
              className="absolute -top-3 -right-3 w-8 h-8 bg-neutral-800 text-neutral-300 rounded-full hover:bg-neutral-700 flex items-center justify-center"
            >
              x
            </button>
          </div>
        </div>
      )}
    </>
  )
}
