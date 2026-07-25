import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from "react"
import {
  listMembers,
  addMemberToWorkspace,
  updateMemberRole,
  createUserByAdmin,
  type CreateUserByAdminPayload,
} from "@/services/backendClient"
import { useAuth } from "@/context/AuthContext"
import { useProjects } from "@/context/ProjectContext"

export type MemberProject = {
  name: string
  role: string
  projectId: string
}

export type Member = {
  id: string
  userId: string
  name: string
  username: string
  email: string
  projects: MemberProject[]
  roleName: string
}

type MembersContextValue = {
  members: Member[]
  loading: boolean
  addMember: (email: string, roleName: string) => Promise<void>
  updateMemberAccess: (userId: string, roleName: string) => Promise<void>
  refreshMembers: () => Promise<void>
  createUser: (data: CreateUserByAdminPayload) => Promise<void>
}

const MembersContext = createContext<MembersContextValue | null>(null)

export const MembersProvider = ({ children }: { children: ReactNode }) => {
  // AuthContext.workspace is set on signup and now also on login
  const { workspace: authWorkspace, token } = useAuth()
  // ProjectContext.workspace is always reliably resolved after login via listWorkspaces()
  const { workspace: projectWorkspace } = useProjects()

  const [members, setMembers] = useState<Member[]>([])
  const [loading, setLoading] = useState(false)

  /** Prefer projectWorkspace (live API data) over authWorkspace (stale localStorage) */
  const workspaceId = projectWorkspace?.id ?? authWorkspace?.id ?? null

  const refreshMembers = useCallback(async () => {
    if (!workspaceId || !token) return
    setLoading(true)
    try {
      const data = await listMembers(workspaceId)
      setMembers(data.map(m => ({
        id: m.id,
        userId: m.userId,
        name: m.user?.name || "Unknown",
        username: m.user?.email.split("@")[0] || "unknown",
        email: m.user?.email || "",
        projects: (m.user?.projectMembers || []).map(pm => ({
          projectId: pm.projectId,
          name: pm.project?.name || "Untitled Project",
          role: pm.role?.name || "Member",
        })),
        roleName: m.role?.name || "Viewer",
      })))
    } catch (err) {
      console.error("Failed to load members:", err)
    } finally {
      setLoading(false)
    }
  }, [workspaceId])

  useEffect(() => {
    refreshMembers()
  }, [refreshMembers])

  const addMember = async (email: string, roleName: string) => {
    if (!workspaceId) throw new Error("No active workspace — please refresh the page.")
    await addMemberToWorkspace(workspaceId, email, roleName)
    await refreshMembers()
  }

  const updateMemberAccess = async (userId: string, roleName: string) => {
    if (!workspaceId) throw new Error("No active workspace — please refresh the page.")
    await updateMemberRole(workspaceId, userId, roleName)
    await refreshMembers()
  }

  const createUser = async (data: CreateUserByAdminPayload) => {
    if (!workspaceId) throw new Error("No active workspace found. Please refresh and try again.")
    await createUserByAdmin(workspaceId, data)
    await refreshMembers()
  }

  return (
    <MembersContext.Provider value={{ members, loading, addMember, updateMemberAccess, refreshMembers, createUser }}>
      {children}
    </MembersContext.Provider>
  )
}

export const useMembers = () => {
  const ctx = useContext(MembersContext)
  if (!ctx) throw new Error("useMembers must be used within MembersProvider")
  return ctx
}
