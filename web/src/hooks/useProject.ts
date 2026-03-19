import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getProjects, type ProjectInfo } from '../lib/api'
import { sortByLastUpdated } from '../lib/sort'

export function useProject() {
  const { project: urlProject } = useParams<{ project: string }>()
  const navigate = useNavigate()
  const [projects, setProjects] = useState<ProjectInfo[]>([])

  useEffect(() => {
    getProjects()
      .then((ps) => setProjects(sortByLastUpdated(ps)))
      .catch(() => {})
  }, [])

  const setProject = (name: string) => {
    navigate(`/set/${name}`)
  }

  return { project: urlProject ?? null, setProject, projects }
}
