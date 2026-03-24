import { useState, useEffect, useRef } from 'react'
import { getManagerProjects, type ManagerProjectStatus } from '../lib/api'

export function useProjectOverview() {
  const [projects, setProjects] = useState<ManagerProjectStatus[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const jsonRef = useRef('')

  useEffect(() => {
    const poll = () => {
      getManagerProjects()
        .then(data => {
          const json = JSON.stringify(data)
          if (json !== jsonRef.current) {
            jsonRef.current = json
            setProjects(data)
          }
          setError(null)
          setLoading(false)
        })
        .catch(e => {
          setError(e.message?.includes('Failed to fetch') ? 'Manager not running' : e.message)
          setLoading(false)
        })
    }
    poll()
    const interval = setInterval(poll, 5000)
    return () => clearInterval(interval)
  }, [])

  return { projects, loading, error }
}
