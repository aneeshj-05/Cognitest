import type React from "react"
import { useState, useEffect, useCallback, useRef } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { Plus, Trash2, Shield, Loader2, ChevronRight, Check, X } from "lucide-react"

import {
  getRoles,
  createRole,
  deleteRole,
  updateRolePermissions,
  getAllPermissions,
  type RoleData,
  type PermissionData,
} from "@/services/backendClient"

interface PermCol {
  key: string // maps to DB PermissionAction enum value
  label: string
  isSpecial?: "none" | "full" // "none" = clear all, "full" = select all
}

const PERM_COLUMNS: PermCol[] = [
  { key: "NONE", label: "None", isSpecial: "none" },
  { key: "READ", label: "View" },
  { key: "CREATE", label: "Create" },
  { key: "EXECUTE", label: "Execute" },
  { key: "UPDATE", label: "Edit" },
  { key: "DELETE", label: "Delete" },
  { key: "FULL", label: "Full", isSpecial: "full" },
]

// The real DB actions that correspond to "FULL"
const FULL_ACTIONS = ["READ", "CREATE", "UPDATE", "DELETE", "EXECUTE", "MANAGE"]
// Real DB actions (non-special columns)
const REAL_ACTIONS = ["READ", "CREATE", "UPDATE", "DELETE", "EXECUTE"]

interface ResourceRow {
  key: string
  label: string
  group: string
}

const RESOURCE_ROWS: ResourceRow[] = [
  { key: "UPLOAD_SWAGGER", label: "Upload Swagger", group: "SWAGGER OPERATIONS" },
  { key: "TEST_CASE", label: "Test Cases", group: "TEST OPERATIONS" },
  { key: "TEST_RUN", label: "Test Runs", group: "TEST OPERATIONS" },
  { key: "REPORT", label: "Reports", group: "TEST OPERATIONS" },
  { key: "PROJECT", label: "Projects", group: "PROJECTS" },
  { key: "MEMBER", label: "Members", group: "USER MANAGEMENT" },
  { key: "ROLE", label: "Roles", group: "USER MANAGEMENT" },
]

// State shape: resource key → set of selected real DB actions e.g. { "TEST_CASE": ["READ","CREATE"] }
type ActionMap = Record<string, string[]>

function buildActionMap(allPerms: PermissionData[], rolePerms: PermissionData[]): ActionMap {
  const roleIds = new Set(rolePerms.map((p) => p.id))
  const map: ActionMap = {}
  for (const row of RESOURCE_ROWS) {
    map[row.key] = allPerms
      .filter((p) => p.resource.toUpperCase() === row.key.toUpperCase() && roleIds.has(p.id))
      .map((p) => p.action)
  }
  return map
}

function actionMapToPermIds(map: ActionMap, allPerms: PermissionData[]): string[] {
  const ids: string[] = []
  for (const row of RESOURCE_ROWS) {
    const actions = new Set(map[row.key] ?? [])
    for (const perm of allPerms) {
      if (perm.resource.toUpperCase() === row.key.toUpperCase() && actions.has(perm.action)) ids.push(perm.id)
    }
  }
  return [...new Set(ids)]
}

const RolesPage = () => {
  const [roles, setRoles] = useState<RoleData[]>([])
  const [allPerms, setAllPerms] = useState<PermissionData[]>([])
  const [selectedRoleId, setSelectedRoleId] = useState<string | null>(null)
  const [actionMap, setActionMap] = useState<ActionMap>({})

  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saveSuccess, setSaveSuccess] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [deletingId, setDeletingId] = useState<string | null>(null)

  const [showAddForm, setShowAddForm] = useState(false)
  const [newName, setNewName] = useState("")
  const [newDesc, setNewDesc] = useState("")
  const [creating, setCreating] = useState(false)

  const addButtonRef = useRef<HTMLButtonElement | null>(null)
  const addPopoverRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    if (!showAddForm) return

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return
      setShowAddForm(false)
      setNewName("")
      setNewDesc("")
    }

    const onMouseDown = (e: MouseEvent) => {
      const target = e.target as Node | null
      if (!target) return
      if (addPopoverRef.current?.contains(target)) return
      if (addButtonRef.current?.contains(target)) return
      setShowAddForm(false)
      setNewName("")
      setNewDesc("")
    }

    document.addEventListener("keydown", onKeyDown)
    document.addEventListener("mousedown", onMouseDown)
    return () => {
      document.removeEventListener("keydown", onKeyDown)
      document.removeEventListener("mousedown", onMouseDown)
    }
  }, [showAddForm])

  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const [rolesData, permsData] = await Promise.all([
        getRoles().catch(() => [] as RoleData[]),
        getAllPermissions().catch(() => [] as PermissionData[]),
      ])
      setRoles(rolesData)
      setAllPerms(permsData)
      if (rolesData.length > 0) setSelectedRoleId(rolesData[0].id)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadData()
  }, [loadData])

  useEffect(() => {
    if (!selectedRoleId) {
      setActionMap({})
      return
    }
    const role = roles.find((r) => r.id === selectedRoleId)
    if (!role) return

    if (allPerms.length === 0) {
      const empty: ActionMap = {}
      RESOURCE_ROWS.forEach((r) => {
        empty[r.key] = []
      })
      setActionMap(empty)
    } else {
      setActionMap(buildActionMap(allPerms, role.permissions))
    }
  }, [selectedRoleId, roles, allPerms])

  const selectedRole = roles.find((r) => r.id === selectedRoleId) ?? null

  const handleToggle = (resourceKey: string, col: PermCol) => {
    setActionMap((prev) => {
      const current = new Set(prev[resourceKey] ?? [])

      if (col.isSpecial === "none") {
        return { ...prev, [resourceKey]: [] }
      }

      if (col.isSpecial === "full") {
        const allSelected = REAL_ACTIONS.every((a) => current.has(a))
        return { ...prev, [resourceKey]: allSelected ? [] : [...FULL_ACTIONS] }
      }

      if (current.has(col.key)) current.delete(col.key)
      else current.add(col.key)

      return { ...prev, [resourceKey]: [...current] }
    })
    setSaveSuccess(false)
    setSaveError(null)
  }

  const handleSave = async () => {
    if (!selectedRoleId) return
    setSaving(true)
    setSaveError(null)
    setSaveSuccess(false)
    try {
      const ids = allPerms.length > 0 ? actionMapToPermIds(actionMap, allPerms) : []
      const updated = await updateRolePermissions(selectedRoleId, ids)
      setRoles((prev) => prev.map((r) => (r.id === updated.id ? updated : r)))
      setSaveSuccess(true)
      setTimeout(() => setSaveSuccess(false), 3000)
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Failed to save")
    } finally {
      setSaving(false)
    }
  }

  const handleCreate = async () => {
    if (!newName.trim()) return
    setCreating(true)
    try {
      const role = await createRole(newName.trim(), newDesc.trim() || undefined)
      setRoles((prev) => [...prev, role])
      setSelectedRoleId(role.id)
      setNewName("")
      setNewDesc("")
      setShowAddForm(false)
    } finally {
      setCreating(false)
    }
  }

  const handleDelete = async (roleId: string, e: React.MouseEvent) => {
    e.stopPropagation()
    setDeletingId(roleId)
    try {
      await deleteRole(roleId)
      const rest = roles.filter((r) => r.id !== roleId)
      setRoles(rest)
      if (selectedRoleId === roleId) setSelectedRoleId(rest[0]?.id ?? null)
    } finally {
      setDeletingId(null)
    }
  }

  if (loading) {
    return (
      <div className="flex min-h-0 gap-6 p-6">
        <Card className="relative flex w-60 shrink-0 flex-col overflow-hidden rounded-xl border border-border/50 bg-card shadow-sm">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 border-b border-border/50 px-4 py-3">
            <Skeleton className="h-4 w-16" />
            <Skeleton className="h-8 w-8 rounded-md" />
          </CardHeader>
          <CardContent className="flex-1 overflow-y-auto p-0">
            {Array.from({ length: 7 }).map((_, idx) => (
              <div key={idx} className="w-full flex items-center gap-2.5 px-4 py-3 border-b border-border/50">
                <Skeleton className="h-5 w-5 rounded-full" />
                <div className="flex-1 min-w-0 space-y-2">
                  <Skeleton className="h-3 w-28" />
                  <Skeleton className="h-3 w-20" />
                </div>
                <Skeleton className="h-6 w-6 rounded-md" />
              </div>
            ))}
          </CardContent>
        </Card>

        <div className="flex-1 min-w-0 flex flex-col gap-6">
          <Skeleton className="h-4 w-60" />

          <Card className="rounded-xl border border-border/50 bg-card shadow-sm overflow-hidden shrink-0">
            <CardHeader className="px-5 py-3.5 border-b border-border/50">
              <Skeleton className="h-5 w-40" />
            </CardHeader>
            <CardContent className="px-5 py-4 grid grid-cols-1 sm:grid-cols-2 gap-6">
              <div className="space-y-2">
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-9 w-full" />
              </div>
              <div className="space-y-2">
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-9 w-full" />
              </div>
            </CardContent>
          </Card>

          <Card className="rounded-xl border border-border/50 bg-card shadow-sm flex-1 overflow-hidden flex flex-col min-h-0">
            <CardHeader className="flex items-center justify-between px-5 py-3.5 border-b border-border/50 shrink-0 flex-row space-y-0">
              <div className="space-y-2">
                <Skeleton className="h-5 w-32" />
                <Skeleton className="h-4 w-80" />
              </div>
              <Skeleton className="h-8 w-28" />
            </CardHeader>

            <div className="flex items-center px-5 py-2 bg-muted/50 border-b border-border/50 shrink-0">
              <div className="flex-1" />
              {Array.from({ length: 6 }).map((_, idx) => (
                <Skeleton key={idx} className="ml-3 h-4 w-10" />
              ))}
            </div>

            <div className="flex-1 overflow-y-auto">
              {Array.from({ length: 12 }).map((_, idx) => (
                <div key={idx} className="flex items-center px-5 py-3.5 border-b border-border/50">
                  <Skeleton className="h-4 w-56" />
                  <div className="ml-auto flex items-center gap-6">
                    {Array.from({ length: 6 }).map((__, j) => (
                      <Skeleton key={j} className="h-4 w-4 rounded-full" />
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>
      </div>
    )
  }

  const groups: { group: string; rows: ResourceRow[] }[] = []
  for (const row of RESOURCE_ROWS) {
    const last = groups[groups.length - 1]
    if (last && last.group === row.group) last.rows.push(row)
    else groups.push({ group: row.group, rows: [row] })
  }

  return (
    <div className="flex min-h-0 gap-6 p-6">
      <Card className="relative flex w-60 shrink-0 flex-col overflow-hidden rounded-xl border border-border/50 bg-card shadow-sm hover:shadow-md transition-all duration-200">
        <CardHeader className="flex flex-row items-center justify-between space-y-0 border-b border-border/50 px-4 py-3">
          <CardTitle className="text-sm font-medium text-foreground">Roles</CardTitle>
          <Button
            ref={addButtonRef}
            type="button"
            variant="ghost"
            size="icon"
            className="h-8 w-8 transition-all duration-200"
            onClick={() => setShowAddForm((v) => !v)}
            aria-label="Add role"
          >
            <Plus className="h-4 w-4" />
          </Button>
        </CardHeader>

        {showAddForm && (
          <div
            ref={addPopoverRef}
            className="absolute left-3 right-3 top-14 z-20 rounded-xl border border-border/50 bg-popover shadow-lg p-3"
          >
            <div className="space-y-2">
              <Input
                placeholder="Role name"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleCreate()}
                className="h-8 bg-background text-xs"
                autoFocus
              />
              <Input
                placeholder="Description"
                value={newDesc}
                onChange={(e) => setNewDesc(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleCreate()}
                className="h-8 bg-background text-xs"
              />
              <div className="flex gap-1.5">
                <Button
                  size="sm"
                  className="h-7 flex-1 px-2 text-[11px] transition-all duration-200"
                  onClick={handleCreate}
                  disabled={creating || !newName.trim()}
                >
                  {creating ? <Loader2 className="h-3 w-3 animate-spin" /> : "Add"}
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-7 px-2 transition-all duration-200"
                  onClick={() => {
                    setShowAddForm(false)
                    setNewName("")
                    setNewDesc("")
                  }}
                >
                  <X className="h-3 w-3" />
                </Button>
              </div>
            </div>
          </div>
        )}

        <CardContent className="flex-1 overflow-y-auto p-0">
          {roles.length === 0 && <p className="py-8 text-center text-xs text-muted-foreground">No roles yet</p>}
          {roles.map((role) => {
            const isActive = role.id === selectedRoleId
            return (
              <div
                key={role.id}
                role="button"
                tabIndex={0}
                onClick={() => {
                  setSelectedRoleId(role.id)
                  setSaveSuccess(false)
                  setSaveError(null)
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault()
                    setSelectedRoleId(role.id)
                    setSaveSuccess(false)
                    setSaveError(null)
                  }
                }}
                className={`group w-full flex items-center gap-2.5 px-4 py-3 border-b border-border/50 text-left transition-all duration-200 cursor-pointer
                  ${
                    isActive
                      ? "bg-muted border-l-2 border-l-primary/40"
                      : "border-l-2 border-l-transparent hover:bg-muted/40"
                  }`}
              >
                <div
                  className={`shrink-0 h-5 w-5 rounded-full border-2 flex items-center justify-center
                    ${isActive ? "border-primary/50" : "border-border"}`}
                >
                  {isActive && <div className="h-2 w-2 rounded-full bg-primary/60" />}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-medium truncate text-foreground">
                    {role.name}
                  </p>
                  <p className="text-[10px] text-muted-foreground">
                    {role.permissions.length} permission{role.permissions.length !== 1 ? "s" : ""}
                  </p>
                </div>
                <Button
                  onClick={(e) => handleDelete(role.id, e)}
                  disabled={deletingId === role.id}
                  variant="ghost"
                  size="icon"
                  className="opacity-0 group-hover:opacity-100 h-7 w-7 text-muted-foreground hover:text-destructive"
                  aria-label="Delete role"
                >
                  {deletingId === role.id ? <Loader2 className="h-3 w-3 animate-spin" /> : <Trash2 className="h-3 w-3" />}
                </Button>
              </div>
            )
          })}
        </CardContent>
      </Card>

      <div className="flex-1 min-w-0 flex flex-col gap-6">
        {!selectedRole ? (
          <Card className="flex flex-1 flex-col items-center justify-center rounded-xl border border-border/50 bg-card py-20 text-muted-foreground shadow-sm">
            <CardContent className="flex flex-col items-center justify-center">
              <Shield className="mb-3 h-10 w-10 text-muted-foreground/60" />
              <p className="text-sm">Select a role to manage its permissions</p>
            </CardContent>
          </Card>
        ) : (
          <>
            <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
              <span className="hover:text-foreground transition-colors">Roles</span>
              <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />
              <span className="font-medium text-foreground">{selectedRole.name}</span>
            </div>

            <Card className="rounded-xl border border-border/50 bg-card shadow-sm hover:shadow-md transition-all duration-200 overflow-hidden shrink-0">
              <CardHeader className="px-5 py-3.5 border-b border-border/50">
                <CardTitle className="text-sm font-medium text-foreground">Basic Information</CardTitle>
              </CardHeader>
              <CardContent className="px-5 py-4 grid grid-cols-1 sm:grid-cols-2 gap-6">
                <div>
                  <label className="block text-sm text-muted-foreground mb-1">
                    Role Name <span className="text-destructive">*</span>
                  </label>
                  <Input
                    readOnly
                    value={selectedRole.name}
                    className="h-9 bg-background text-sm font-medium"
                  />
                </div>
                <div>
                  <label className="block text-sm text-muted-foreground mb-1">Description</label>
                  <Input
                    readOnly
                    value={selectedRole.description ?? ""}
                    placeholder="No description"
                    className="h-9 bg-background text-sm"
                  />
                </div>
              </CardContent>
            </Card>

            <Card className="rounded-xl border border-border/50 bg-card shadow-sm hover:shadow-md transition-all duration-200 flex-1 overflow-hidden flex flex-col min-h-0">
              <CardHeader className="flex items-center justify-between px-5 py-3.5 border-b border-border/50 shrink-0 flex-row space-y-0">
                <div>
                  <CardTitle className="text-sm font-medium text-foreground">Permissions</CardTitle>
                  <p className="text-sm text-muted-foreground mt-0.5">Select multiple actions per resource independently</p>
                </div>
                <div className="flex items-center gap-2">
                  {saveSuccess && (
                    <span className="inline-flex items-center gap-1 rounded-full border border-primary/20 bg-primary/10 px-2.5 py-0.5 text-xs font-medium text-primary">
                      <Check className="h-3 w-3" /> Saved
                    </span>
                  )}
                  {saveError && <span className="text-xs text-destructive">{saveError}</span>}
                  <Button
                    size="sm"
                    onClick={handleSave}
                    disabled={saving}
                    className="h-8 text-xs px-4 transition-all duration-200"
                  >
                    {saving && <Loader2 className="h-3 w-3 animate-spin mr-1.5" />}
                    Save Changes
                  </Button>
                </div>
              </CardHeader>

              <div className="flex items-center px-5 py-2 bg-muted/50 border-b border-border/50 shrink-0">
                <div className="flex-1 text-xs font-medium text-muted-foreground uppercase tracking-wider" />
                {PERM_COLUMNS.map((col) => (
                  <div key={col.key} className="w-16 text-center text-xs font-medium text-muted-foreground">
                    {col.label}
                  </div>
                ))}
              </div>

              <div className="flex-1 overflow-y-auto">
                {groups.map(({ group, rows }) => (
                  <div key={group}>
                    <div className="px-5 py-1.5 text-[10px] font-semibold tracking-widest text-muted-foreground uppercase bg-muted/40 border-b border-border/50">
                      {group}
                    </div>

                    {rows.map((row) => {
                      const currentActions = new Set(actionMap[row.key] ?? [])
                      const isFullActive = REAL_ACTIONS.every((a) => currentActions.has(a))
                      const isNoneActive = currentActions.size === 0

                      return (
                        <div
                          key={row.key}
                          className="flex items-center px-5 py-3.5 border-b border-border/50 hover:bg-muted/40 transition-colors"
                        >
                          <div className="flex-1 pl-2 text-sm font-medium text-foreground">{row.label}</div>

                          {PERM_COLUMNS.map((col) => {
                            let isChecked = false
                            if (col.isSpecial === "none") isChecked = isNoneActive
                            else if (col.isSpecial === "full") isChecked = isFullActive
                            else isChecked = currentActions.has(col.key)

                            return (
                              <div key={col.key} className="w-16 flex justify-center">
                                <Button
                                  type="button"
                                  onClick={() => handleToggle(row.key, col)}
                                  title={col.label}
                                  variant="ghost"
                                  size="icon"
                                  className={`h-5 w-5 p-0 rounded-full border-2 transition-all duration-150
                                    ${
                                      isChecked
                                        ? "border-primary/50 bg-primary"
                                        : "border-border bg-background hover:bg-muted/40"
                                    }`}
                                >
                                  {isChecked && <div className="h-1.75 w-1.75 rounded-full bg-primary-foreground" />}
                                </Button>
                              </div>
                            )
                          })}
                        </div>
                      )
                    })}
                  </div>
                ))}

                <div className="flex flex-wrap gap-x-5 gap-y-1.5 px-5 py-4 border-t border-border/50 bg-muted/20">
                  {PERM_COLUMNS.map((col) => (
                    <span key={col.key} className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
                      <span className="inline-block h-2.5 w-2.5 rounded-full bg-muted-foreground/60" />
                      {col.label}
                      {col.isSpecial === "none" && " — clears all"}
                      {col.isSpecial === "full" && " — selects all"}
                    </span>
                  ))}
                </div>
              </div>
            </Card>
          </>
        )}
      </div>
    </div>
  )
}

export default RolesPage
