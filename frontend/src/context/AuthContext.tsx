import { createContext, useContext, useState, useEffect, useCallback } from "react"
import type { ReactNode } from "react"
import {
  loginUser as apiLogin,
  signupUser as apiSignup,
  verifyOtp as apiVerifyOtp,
  setAuthToken,
  clearAuthState,
  getAuthToken,
  parseJwt,
  type TenantData,
  type SubscriptionData,
} from "@/services/backendClient"

export interface AuthUser {
  id: string
  tenantId: string
  email: string
  name?: string | null
  systemRole: string
  role: string // mapped from systemRole
  company?: string | null
  contactNumber?: string | null
  username?: string
  displayName?: string
}

export interface AuthWorkspace {
  id: string
  tenantId: string
  name: string
  createdBy: string | null
}

export interface AuthProject {
  id: string
  tenantId: string
  workspaceId: string
  name: string
  description?: string | null
}

interface AuthResult {
  success: boolean
  user?: AuthUser
  tenant?: TenantData | null
  workspace?: AuthWorkspace
  project?: AuthProject
  subscription?: SubscriptionData
  error?: string
}

interface AuthContextValue {
  user: AuthUser | null
  token: string | null
  tenantId: string | null
  workspace: AuthWorkspace | null
  project: AuthProject | null
  workspacePermissions: Record<string, string[]> | null
  login: (email: string, passcode: string, inviteToken?: string) => Promise<AuthResult>
  signup: (data: {
    email: string
    name: string
    passcode: string
    company?: string
    contactNumber?: string
    inviteToken?: string
  }) => Promise<{ success: boolean; email?: string; error?: string }>
  verify: (email: string, otp: string, inviteToken?: string) => Promise<AuthResult>
  logout: () => void
  isAdmin: boolean
}

const AuthContext = createContext<AuthContextValue | null>(null)

interface AuthProviderProps {
  children: ReactNode
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [user, setUser] = useState<AuthUser | null>(() => {
    const stored = localStorage.getItem("cognitest-user")
    if (!stored) return null
    try {
      return JSON.parse(stored) as AuthUser
    } catch {
      return null
    }
  })

  const [token, setToken] = useState<string | null>(() => {
    const t = getAuthToken()
    if (!t) return null
    const payload = parseJwt(t)
    if (payload?.exp && payload.exp * 1000 < Date.now()) {
      clearAuthState()
      localStorage.removeItem("cognitest-user")
      localStorage.removeItem("cognitest-tenant-id")
      localStorage.removeItem("cognitest-workspace")
      localStorage.removeItem("cognitest-project")
      return null
    }
    return t
  })
  const [tenantId, setTenantIdState] = useState<string | null>(() => {
    return localStorage.getItem("cognitest-tenant-id")
  })

  const [workspacePermissions, setWorkspacePermissions] = useState<Record<string, string[]> | null>(() => {
    const t = getAuthToken()
    if (!t) return null
    const payload = parseJwt(t)
    return payload?.workspacePermissions || null
  })

  const [workspace, setWorkspace] = useState<AuthWorkspace | null>(() => {
    const stored = localStorage.getItem("cognitest-workspace")
    if (!stored) return null
    try {
      return JSON.parse(stored) as AuthWorkspace
    } catch {
      return null
    }
  })

  const [project, setProject] = useState<AuthProject | null>(() => {
    const stored = localStorage.getItem("cognitest-project")
    if (!stored) return null
    try {
      return JSON.parse(stored) as AuthProject
    } catch {
      return null
    }
  })

  useEffect(() => {
    if (user) {
      localStorage.setItem("cognitest-user", JSON.stringify(user))
    } else {
      localStorage.removeItem("cognitest-user")
    }
  }, [user])

  useEffect(() => {
    if (tenantId) {
      localStorage.setItem("cognitest-tenant-id", tenantId)
    } else {
      localStorage.removeItem("cognitest-tenant-id")
    }
  }, [tenantId])

  useEffect(() => {
    if (workspace) {
      localStorage.setItem("cognitest-workspace", JSON.stringify(workspace))
    } else {
      localStorage.removeItem("cognitest-workspace")
    }
  }, [workspace])

  useEffect(() => {
    if (project) {
      localStorage.setItem("cognitest-project", JSON.stringify(project))
    } else {
      localStorage.removeItem("cognitest-project")
    }
  }, [project])

  const login = useCallback(async (email: string, passcode: string, inviteToken?: string): Promise<AuthResult> => {
    console.log('AuthContext.login called', { email, passcode, inviteToken });
    try {
      const result = await apiLogin(email, passcode, inviteToken)

      setAuthToken(result.token)
      setToken(result.token)
      if (result.tenant) {
        setTenantIdState(result.tenant.id)
      }

      const payload = parseJwt(result.token)
      setWorkspacePermissions(payload?.workspacePermissions || null)

      // Store workspace so it's available for MembersContext and other consumers
      if (result.workspace) {
        setWorkspace(result.workspace)
      }

      const userData: AuthUser = {
        ...result.user,
        role: result.user.systemRole.toLowerCase(),
        username: result.user.name || result.user.email.split("@")[0],
        displayName: result.user.name || result.user.email.split("@")[0],
      }

      setUser(userData)
      return { success: true, user: userData, tenant: result.tenant }
    } catch (err) {
      const message = err instanceof Error ? err.message : "Login failed"
      return { success: false, error: message }
    }
  }, [])


  const signup = useCallback(async (data: {
    email: string
    name: string
    passcode: string
    company?: string
    contactNumber?: string
    inviteToken?: string
  }): Promise<{ success: boolean; email?: string; error?: string }> => {
    try {
      const resp = await apiSignup(data)
      return { success: true, email: resp.email }
    } catch (err) {
      const message = err instanceof Error ? err.message : "Signup failed"
      return { success: false, error: message }
    }
  }, [])

  const verify = useCallback(async (email: string, otp: string, inviteToken?: string): Promise<AuthResult> => {
    try {
      // console.log removed: API_BASE_URL and path were undefined
      const resp = await apiVerifyOtp(email, otp, inviteToken)
      
      const userData: AuthUser = {
        ...resp.user,
        role: resp.user.systemRole.toLowerCase(),
        username: resp.user.name || resp.user.email.split("@")[0],
        displayName: resp.user.name || resp.user.email.split("@")[0],
      }

      setUser(userData)
      setAuthToken(resp.token)
      setToken(resp.token)
      setTenantIdState(resp.tenant.id)
      setWorkspace(resp.workspace)
      setProject(resp.project)

      const payload = parseJwt(resp.token)
      setWorkspacePermissions(payload?.workspacePermissions || null)

      return {
        success: true,
        user: userData,
        tenant: resp.tenant,
        workspace: resp.workspace,
        project: resp.project,
        subscription: resp.subscription
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "Verification failed"
      return { success: false, error: message }
    }
  }, [])

  const logout = useCallback(() => {
    setUser(null)
    setToken(null)
    setTenantIdState(null)
    setWorkspace(null)
    setProject(null)
    setWorkspacePermissions(null)
    clearAuthState()
    localStorage.removeItem("cognitest-user")
    localStorage.removeItem("cognitest-tenant-id")
    localStorage.removeItem("cognitest-workspace")
    localStorage.removeItem("cognitest-project")
  }, [])

  const isAdmin = user?.systemRole === "TENANT_ADMIN" || user?.systemRole === "SUPER_ADMIN"

  return (
    <AuthContext.Provider value={{ user, token, tenantId, workspace, project, workspacePermissions, login, signup, verify, logout, isAdmin }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error("useAuth must be used within AuthProvider")
  return ctx
}
