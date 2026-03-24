import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getManagerProjects, type ManagerProjectStatus } from '../lib/api'

export interface ProjectInfo {
  name: string
  path: string
  status?: string
}

export function useProject() {
  const { project: urlProject } = useParams<{ project: string }>()
  const navigate = useNavigate()
  const [projects, setProjects] = useState<ProjectInfo[]>([])

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>
    let fails = 0
    const poll = () => {
      getManagerProjects()
        .then((ps: ManagerProjectStatus[]) => {
          fails = 0
          setProjects(ps.map(p => ({
            name: p.name,
            path: p.path,
            status: p.sentinel?.alive ? 'running' : p.orchestrator?.alive ? 'running' : undefined,
          })))
          timer = setTimeout(poll, 10000)
        })
        .catch(() => {
          fails++
          timer = setTimeout(poll, Math.min(10000 * Math.pow(2, fails), 60000))
        })
    }
    poll()
    return () => clearTimeout(timer)
  }, [])

  const setProject = (name: string) => {
    navigate(`/p/${name}/orch`)
  }

  return { project: urlProject ?? null, setProject, projects }
}
