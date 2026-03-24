import { useState, useEffect, useRef } from 'react'
import { getManagerProjectStatus, getProjectDocs, type ManagerProjectStatus, type DocsEntry } from '../lib/api'

export function useProjectDetail(projectName: string | undefined) {
  const [project, setProject] = useState<ManagerProjectStatus | null>(null)
  const [docs, setDocs] = useState<DocsEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const jsonRef = useRef('')
  const failCountRef = useRef(0)

  useEffect(() => {
    if (!projectName) return
    let timer: ReturnType<typeof setTimeout>
    let cancelled = false

    const poll = () => {
      getManagerProjectStatus(projectName)
        .then(data => {
          if (cancelled) return
          failCountRef.current = 0
          const json = JSON.stringify(data)
          if (json !== jsonRef.current) {
            jsonRef.current = json
            setProject(data)
          }
          setError(null)
          setLoading(false)
          timer = setTimeout(poll, 5000)
        })
        .catch(e => {
          if (cancelled) return
          failCountRef.current++
          setError(e.message?.includes('404') ? 'Project not found' : e.message)
          setLoading(false)
          // Back off: 5s, 10s, 20s, max 30s
          const delay = Math.min(5000 * Math.pow(2, failCountRef.current - 1), 30000)
          timer = setTimeout(poll, delay)
        })
    }
    poll()
    return () => { cancelled = true; clearTimeout(timer) }
  }, [projectName])

  // Docs — fetch once (not polled)
  useEffect(() => {
    if (!projectName) return
    getProjectDocs(projectName)
      .then(data => setDocs(data.docs))
      .catch(() => setDocs([]))
  }, [projectName])

  // All docs paths for spec autocomplete (dirs first, then files)
  const specPaths = [...new Set([
    ...docs.filter(d => d.type === 'dir').map(d => d.path),
    ...docs.filter(d => d.type === 'file').map(d => d.path),
  ])]
  // Always include "docs/" as an option if there are any docs
  if (docs.length > 0 && !specPaths.includes('docs/')) {
    specPaths.unshift('docs/')
  }

  return { project, docs, specPaths, loading, error }
}
