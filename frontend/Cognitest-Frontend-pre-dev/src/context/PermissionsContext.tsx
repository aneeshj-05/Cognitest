import { createContext, useContext, useMemo, type ReactNode } from "react"
import { useAuth } from "./AuthContext"

// These must match the DB Permission model: resource.action format
// Resources seeded: UPLOAD_SWAGGER, TEST_CASE, TEST_RUN, REPORT, PROJECT, MEMBER, ROLE
// Actions seeded: READ, CREATE, UPDATE, DELETE, EXECUTE, MANAGE
type Permission =
  | "UPLOAD_SWAGGER.READ"
  | "UPLOAD_SWAGGER.CREATE"
  | "UPLOAD_SWAGGER.UPDATE"
  | "UPLOAD_SWAGGER.DELETE"
  | "TEST_CASE.READ"
  | "TEST_CASE.CREATE"
  | "TEST_CASE.UPDATE"
  | "TEST_CASE.DELETE"
  | "TEST_RUN.READ"
  | "TEST_RUN.EXECUTE"
  | "TEST_RUN.CREATE"
  | "REPORT.READ"
  | "PROJECT.READ"
  | "PROJECT.CREATE"
  | "PROJECT.UPDATE"
  | "PROJECT.DELETE"
  | "MEMBER.READ"
  | "MEMBER.CREATE"
  | "MEMBER.MANAGE"
  | "ROLE.READ"
  | "ROLE.MANAGE"

interface PermissionsContextValue {
  hasPermission: (permission: Permission) => boolean
  // Swagger
  canViewSwagger: boolean
  canUploadSwagger: boolean
  // Tests
  canCreateTests: boolean
  canRunTests: boolean
  canModifyTests: boolean
  canDeleteTests: boolean
  // Projects
  canCreateProject: boolean
  canModifyProject: boolean
  // Members / Roles
  canManageMembers: boolean
  canManageRoles: boolean
}

const PermissionsContext = createContext<PermissionsContextValue | null>(null)

export function PermissionsProvider({ children }: { children: ReactNode }) {
  const { user, workspacePermissions, workspace, isAdmin } = useAuth()

  const value = useMemo<PermissionsContextValue>(() => {
    // Admins get all permissions
    if (isAdmin) {
      const allTrue: PermissionsContextValue = {
        hasPermission: () => true,
        canViewSwagger: true,
        canUploadSwagger: true,
        canCreateTests: true,
        canRunTests: true,
        canModifyTests: true,
        canDeleteTests: true,
        canCreateProject: true,
        canModifyProject: true,
        canManageMembers: true,
        canManageRoles: true,
      }
      return allTrue
    }

    const wsId = workspace?.id
    // workspacePermissions is a map of { workspaceId: ["RESOURCE.ACTION", ...] }
    const perms: string[] = (wsId && workspacePermissions?.[wsId]) || []

    const hasPermission = (p: Permission): boolean => perms.includes(p)

    return {
      hasPermission,
      canViewSwagger: hasPermission("UPLOAD_SWAGGER.READ"),
      canUploadSwagger: hasPermission("UPLOAD_SWAGGER.CREATE") || hasPermission("UPLOAD_SWAGGER.UPDATE"),
      canCreateTests: hasPermission("TEST_CASE.CREATE"),
      canRunTests: hasPermission("TEST_RUN.EXECUTE") || hasPermission("TEST_RUN.CREATE"),
      canModifyTests: hasPermission("TEST_CASE.UPDATE"),
      canDeleteTests: hasPermission("TEST_CASE.DELETE"),
      canCreateProject: hasPermission("PROJECT.CREATE"),
      canModifyProject: hasPermission("PROJECT.UPDATE"),
      canManageMembers: hasPermission("MEMBER.MANAGE") || hasPermission("MEMBER.CREATE"),
      canManageRoles: hasPermission("ROLE.MANAGE"),
    }
  }, [user, workspacePermissions, workspace, isAdmin])

  return <PermissionsContext.Provider value={value}>{children}</PermissionsContext.Provider>
}

export function usePermissions(): PermissionsContextValue {
  const ctx = useContext(PermissionsContext)
  if (!ctx) throw new Error("usePermissions must be used within PermissionsProvider")
  return ctx
}
