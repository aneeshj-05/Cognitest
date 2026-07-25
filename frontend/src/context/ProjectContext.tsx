import { createContext, useCallback, useContext, useMemo, useState, useEffect, useRef, type ReactNode } from "react"
import {
  getWorkspaceProjects,
  createProject,
  getWorkspaceId as getStoredWorkspaceId,
  setWorkspaceId as setStoredWorkspaceId,
  listWorkspaces,
  createWorkspace,
  type ProjectData,
  type WorkspaceData
} from "@/services/backendClient"
import { useAuth } from "@/context/AuthContext"

export type Project = ProjectData & {
  tested?: boolean
  passRate?: number | null
  passed?: number
  failed?: number
  status?: string
}

type ProjectUpdate = Partial<Project> | ((project: Project) => Partial<Project>)

export type ProjectsContextValue = {
  projects: Project[]
  workspaces: WorkspaceData[]
  workspace: WorkspaceData | null
  selectedWorkspaceId: string | null
  loading: boolean
  getProjectById: (id?: string) => Project | null
  refreshProjects: () => Promise<void>
  refreshWorkspaces: () => Promise<void>
  setSelectedWorkspace: (id: string) => void
  createNewProject: (name: string, description?: string, workspaceIdOverride?: string) => Promise<Project>
  createNewWorkspace: (name: string) => Promise<WorkspaceData>
  updateProject: (projectId: string, updater: ProjectUpdate) => void
}

const ProjectContext = createContext<ProjectsContextValue | null>(null)

export const ProjectsProvider = ({ children }: { children: ReactNode }) => {
  const { token, workspace: authWorkspace } = useAuth()
  const [projects, setProjects] = useState<Project[]>([])
  const [workspaces, setWorkspaces] = useState<WorkspaceData[]>([])
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState<string | null>(getStoredWorkspaceId())
  const [loading, setLoading] = useState(true)
  const prevTokenRef = useRef<string | null>(token)

  // Sync workspace ID when auth state changes (login/signup sets authWorkspace)
  useEffect(() => {
    if (authWorkspace?.id && authWorkspace.id !== selectedWorkspaceId) {
      setSelectedWorkspaceId(authWorkspace.id)
      setStoredWorkspaceId(authWorkspace.id)
    }
  }, [authWorkspace?.id])

  // When the token changes (login/logout), re-fetch workspaces and projects
  useEffect(() => {
    if (token !== prevTokenRef.current) {
      prevTokenRef.current = token
      if (token) {
        refreshWorkspaces()
      } else {
        // Logged out
        setProjects([])
        setWorkspaces([])
        setSelectedWorkspaceId(null)
      }
    }
  }, [token])

  const refreshWorkspaces = useCallback(async () => {
    try {
      const data = await listWorkspaces()
      setWorkspaces(data)

      // Validation: Ensure selectedWorkspaceId is still valid
      if (data.length > 0) {
        const isValid = data.some(ws => ws.id === selectedWorkspaceId)
        if (!selectedWorkspaceId || !isValid) {
          // If none selected or current one is invalid, pick the first one
          setSelectedWorkspaceId(data[0].id)
          setStoredWorkspaceId(data[0].id)
        }
      } else {
        // No workspaces found
        setSelectedWorkspaceId(null)
        setStoredWorkspaceId("")
      }
    } catch (err) {
      console.error("Failed to load workspaces:", err)
    }
  }, [selectedWorkspaceId])

  const refreshProjects = useCallback(async () => {
    if (!selectedWorkspaceId) {
      setProjects([])
      setLoading(false)
      return
    }
    setLoading(true)
    try {
      const data = await getWorkspaceProjects(selectedWorkspaceId)
      const mapped: Project[] = data.map(p => ({
        ...p,
        tested: false,
        passRate: null,
        passed: 0,
        failed: 0,
        status: "Pending"
      }))
      setProjects(mapped)
    } catch (err) {
      console.error("Failed to load projects:", err)
    } finally {
      setLoading(false)
    }
  }, [selectedWorkspaceId])

  useEffect(() => {
    if (token) refreshWorkspaces()
  }, [refreshWorkspaces])

  useEffect(() => {
    refreshProjects()
  }, [refreshProjects])

  const setSelectedWorkspace = useCallback((id: string) => {
    setSelectedWorkspaceId(id)
    setStoredWorkspaceId(id)
  }, [])

  const createNewWorkspace = useCallback(async (name: string) => {
    const ws = await createWorkspace({ name })
    setWorkspaces(prev => [ws, ...prev])
    setSelectedWorkspaceId(ws.id)
    setStoredWorkspaceId(ws.id)
    return ws
  }, [])

  const createNewProject = useCallback(async (name: string, description?: string, workspaceIdOverride?: string) => {
    const wsId = workspaceIdOverride || selectedWorkspaceId
    if (!wsId) throw new Error("No workspace selected")
    const newProj = await createProject({ name, description, workspaceId: wsId })
    const mapped: Project = {
      ...newProj,
      tested: false,
      passRate: null,
      passed: 0,
      failed: 0,
      status: "Pending"
    }
    if (wsId === selectedWorkspaceId) {
      setProjects(prev => [mapped, ...prev])
    }
    return mapped
  }, [selectedWorkspaceId])

  const updateProject = useCallback((projectId: string, updater: ProjectUpdate) => {
    setProjects((prev) =>
      prev.map((project) => {
        if (project.id !== projectId) return project
        const updates = typeof updater === "function" ? updater(project) : updater
        return { ...project, ...updates } as Project
      })
    )
  }, [])

  const value = useMemo<ProjectsContextValue>(() => ({
    projects,
    workspaces,
    workspace: workspaces.find(w => w.id === selectedWorkspaceId) || workspaces[0] || null,
    selectedWorkspaceId,
    loading,
    getProjectById: (id?: string) => projects.find((p) => p.id === id) || null,
    refreshProjects,
    refreshWorkspaces,
    setSelectedWorkspace,
    createNewProject,
    createNewWorkspace,
    updateProject,
  }), [projects, workspaces, selectedWorkspaceId, loading, refreshProjects, refreshWorkspaces, setSelectedWorkspace, createNewProject, createNewWorkspace, updateProject])

  return <ProjectContext.Provider value={value}>{children}</ProjectContext.Provider>
}

export const useProjects = () => {
  const ctx = useContext(ProjectContext)
  if (!ctx) throw new Error("useProjects must be used within ProjectsProvider")
  return ctx
}
