import { useEffect, useState } from 'react'

interface ScreenshotFile {
  path: string
  name: string
}

interface Props {
  project: string
  changeName: string
  onClose: () => void
}

export default function ScreenshotGallery({ project, changeName }: Props) {
  const [smoke, setSmoke] = useState<ScreenshotFile[]>([])
  const [e2e, setE2e] = useState<ScreenshotFile[]>([])
  const [loading, setLoading] = useState(true)
  const [lightbox, setLightbox] = useState<string | null>(null)

  useEffect(() => {
    setLoading(true)
    fetch(`/api/${project}/changes/${changeName}/screenshots`)
      .then(r => r.json())
      .then((data: { smoke: ScreenshotFile[]; e2e: ScreenshotFile[] }) => {
        setSmoke(data.smoke ?? [])
        setE2e(data.e2e ?? [])
      })
      .catch(() => {
        setSmoke([])
        setE2e([])
      })
      .finally(() => setLoading(false))
  }, [project, changeName])

  const imgUrl = (s: ScreenshotFile) => `/api/${project}/screenshots/${s.path}`

  if (loading) {
    return <div className="px-4 py-3 text-xs text-neutral-500">Loading screenshots...</div>
  }

  if (smoke.length === 0 && e2e.length === 0) {
    return <div className="px-4 py-3 text-xs text-neutral-500">No screenshots found</div>
  }

  return (
    <>
      <div className="px-4 py-3 space-y-3">
        {smoke.length > 0 && (
          <div>
            <h4 className="text-xs font-medium text-neutral-400 mb-2">Smoke Screenshots ({smoke.length})</h4>
            <div className="flex flex-wrap gap-2">
              {smoke.map(s => (
                <button
                  key={s.path}
                  onClick={() => setLightbox(imgUrl(s))}
                  className="group relative w-32 h-20 rounded border border-neutral-800 overflow-hidden hover:border-neutral-600 transition-colors"
                >
                  <img
                    src={imgUrl(s)}
                    alt={s.name}
                    className="w-full h-full object-cover"
                    loading="lazy"
                  />
                  <span className="absolute bottom-0 inset-x-0 bg-black/70 text-[9px] text-neutral-400 px-1 py-0.5 truncate opacity-0 group-hover:opacity-100 transition-opacity">
                    {s.name}
                  </span>
                </button>
              ))}
            </div>
          </div>
        )}
        {e2e.length > 0 && (
          <div>
            <h4 className="text-xs font-medium text-neutral-400 mb-2">E2E Screenshots ({e2e.length})</h4>
            <div className="flex flex-wrap gap-2">
              {e2e.map(s => (
                <button
                  key={s.path}
                  onClick={() => setLightbox(imgUrl(s))}
                  className="group relative w-32 h-20 rounded border border-neutral-800 overflow-hidden hover:border-neutral-600 transition-colors"
                >
                  <img
                    src={imgUrl(s)}
                    alt={s.name}
                    className="w-full h-full object-cover"
                    loading="lazy"
                  />
                  <span className="absolute bottom-0 inset-x-0 bg-black/70 text-[9px] text-neutral-400 px-1 py-0.5 truncate opacity-0 group-hover:opacity-100 transition-opacity">
                    {s.name}
                  </span>
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Lightbox overlay */}
      {lightbox && (
        <div
          className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center"
          onClick={() => setLightbox(null)}
        >
          <div className="relative max-w-[90vw] max-h-[90vh]">
            <img
              src={lightbox}
              alt="Screenshot"
              className="max-w-full max-h-[90vh] rounded shadow-2xl"
              onClick={e => e.stopPropagation()}
            />
            <button
              onClick={() => setLightbox(null)}
              className="absolute -top-3 -right-3 w-7 h-7 bg-neutral-800 text-neutral-300 rounded-full text-sm hover:bg-neutral-700 flex items-center justify-center"
            >
              x
            </button>
          </div>
        </div>
      )}
    </>
  )
}
