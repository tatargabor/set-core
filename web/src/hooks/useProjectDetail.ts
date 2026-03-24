import { useState, useEffect, useRef } from 'react'
import { getManagerProjectStatus, getProjectDocs, type ManagerProjectStatus, type DocsEntry } from '../lib/api'

export function useProjectDetail(projectName: string | undefined) {
  const [project, setProject] = useState<ManagerProjectStatus | null>(null)
  const [docs, setDocs] = useState<DocsEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const jsonRef = useRef('')

  useEffect(() => {
    if (!projectName) return

    const poll = () => {
      getManagerProjectStatus(projectName)
        .then(data => {
          const json = JSON.stringify(data)
          if (json !== jsonRef.current) {
            jsonRef.current = json
            setProject(data)
          }
          setError(null)
          setLoading(false)
        })
        .catch(e => {
          setError(e.message?.includes('404') ? 'Project not found' : e.message)
          setLoading(false)
        })
    }
    poll()
    const interval = setInterval(poll, 5000)
    return () => clearInterval(interval)
  }, [projectName])

  // Docs — fetch once (not polled)
  useEffect(() => {
    if (!projectName) return
    getProjectDocs(projectName)
      .then(data => setDocs(data.docs))
      .catch(() => setDocs([]))
  }, [projectName])

  // Top-level dirs for spec autocomplete
  const specPaths = [...new Set(
    docs.filter(d => d.type === 'dir').map(d => d.path)
  )]
  // Always include "docs/" as an option if there are any docs
  if (docs.length > 0 && !specPaths.includes('docs/')) {
    specPaths.unshift('docs/')
  }

  return { project, docs, specPaths, loading, error }
}
