import { useState, useEffect } from "react"
import PageHeader from "@/components/shared/PageHeader"
import { useNavigate, useParams } from "react-router-dom"
import { Button } from "@/components/ui/button"
import { ArrowLeft, Loader2, Mail, Plus, Trash2 } from "lucide-react"
import { useMembers } from "@/context/MembersContext"
import { useProjects } from "@/context/ProjectContext"
import { getRoles, updateProjectAssignments, type RoleData } from "@/services/backendClient"
import { useAuth } from "@/context/AuthContext"
import { generateUUID } from "@/lib/utils"

interface AssignmentRow {
  id: string
  projectId: string
  roleId: string
}

const ManageMemberPage = () => {
  const navigate = useNavigate()
  const { id } = useParams<{ id?: string }>()
  const { members, refreshMembers } = useMembers()
  const { workspace: authWorkspace } = useAuth()
  const { workspace: projectWorkspace, projects } = useProjects()
  const workspaceId: string = authWorkspace?.id ?? projectWorkspace?.id ?? ""

  const member = members.find((m) => m.userId === id)

  const [availableRoles, setAvailableRoles] = useState<RoleData[]>([])
  const [assignments, setAssignments] = useState<AssignmentRow[]>([])
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState("")
  const [saved, setSaved] = useState(false)

  // Load roles once
  useEffect(() => {
    getRoles().then(setAvailableRoles).catch(() => { })
  }, [])

  // Seed assignments from member data
  useEffect(() => {
    if (member && availableRoles.length > 0) {
      setAssignments(
        member.projects.map((p) => {
          const role = availableRoles.find(r => r.name === p.role)
          return {
            id: generateUUID(),
            projectId: p.projectId,
            roleId: role?.id || "",
          }
        })
      )
    }
  }, [member?.userId, availableRoles.length])


  const addRow = () =>
    setAssignments(prev => [...prev, { id: generateUUID(), projectId: "", roleId: "" }])

  const removeRow = (rowId: string) =>
    setAssignments(prev => prev.filter(r => r.id !== rowId))

  const updateRow = (rowId: string, field: "projectId" | "roleId", value: string) =>
    setAssignments(prev => prev.map(r => r.id === rowId ? { ...r, [field]: value } : r))

  const handleSave = async () => {
    if (!id || !workspaceId) return
    const valid = assignments.filter(a => a.projectId && a.roleId)
    setIsSubmitting(true)
    setError("")
    setSaved(false)
    try {
      await updateProjectAssignments(workspaceId, id, valid)
      await refreshMembers()
      setSaved(true)
      setTimeout(() => navigate("/dashboard/members"), 800)
    } catch (err: any) {
      setError(err?.message || "Failed to update project assignments")
    } finally {
      setIsSubmitting(false)
    }
  }

  if (!member) {
    return (
      <div className="flex flex-col items-center justify-center min-h-100 gap-4">
        <p className="text-muted-foreground">Member not found.</p>
        <Button variant="outline" onClick={() => navigate("/dashboard/members")}>Back to Members</Button>
      </div>
    )
  }

  const initials = member.name.split(" ").map((n: string) => n[0]).join("").toUpperCase().slice(0, 2)

  return (
    <div className="space-y-6 p-6">
      <div className="mx-auto w-full max-w-2xl space-y-6">

        {/* Header */}
        <div className="flex items-center gap-3">
          <Button
            type="button"
            variant="ghost"
            size="icon"
            onClick={() => navigate("/dashboard/members")}
            className="text-muted-foreground hover:text-foreground"
          >
            <ArrowLeft className="h-5 w-5" />
          </Button>
          <div>
            <PageHeader title="Manage Member" description="Edit project assignments for this member" />
          </div>
        </div>

        {/* Member profile */}
        <div className="rounded-2xl border border-border bg-card shadow-sm p-5">
          <div className="flex items-center gap-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary text-primary-foreground font-bold text-base shrink-0">
              {initials}
            </div>
            <div>
              <p className="text-base font-semibold">{member.name}</p>
              <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
                <Mail className="h-3.5 w-3.5" />
                {member.email}
              </div>
            </div>
            <span className="ml-auto text-[11px] font-bold uppercase tracking-wider text-muted-foreground border border-border rounded-full px-2.5 py-0.5 bg-muted/30">
              {member.roleName}
            </span>
          </div>
        </div>

        {/* Editable project assignments */}
        <div className="rounded-2xl border border-border bg-card shadow-sm overflow-hidden">
          <div className="flex items-center justify-between px-6 py-4 border-b border-border">
            <div>
              <p className="text-sm font-semibold">Project Assignments</p>
              <p className="text-xs text-muted-foreground">Set which projects this member can access and what role they have</p>
            </div>
          </div>

          <div className="p-5 space-y-3">
            {assignments.length === 0 && (
              <p className="text-sm text-muted-foreground italic text-center py-4">No projects assigned. Click "Add Project" to assign one.</p>
            )}

            {assignments.map((row) => (
              <div key={row.id} className="flex items-center gap-3">
                {/* Project selector */}
                <select
                  value={row.projectId}
                  onChange={e => updateRow(row.id, "projectId", e.target.value)}
                  className="flex-1 h-10 rounded-lg border border-border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary/20"
                  disabled={isSubmitting}
                >
                  <option value="">Select Project</option>
                  {projects.map((p) => (
                    <option key={p.id} value={p.id}>{p.name}</option>
                  ))}

                </select>

                {/* Role selector */}
                <select
                  value={row.roleId}
                  onChange={e => updateRow(row.id, "roleId", e.target.value)}
                  className="w-36 h-10 rounded-lg border border-border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary/20"
                  disabled={isSubmitting}
                >
                  <option value="">Select Role</option>
                  {availableRoles.map(r => (
                    <option key={r.id} value={r.id}>{r.name}</option>
                  ))}
                </select>

                {/* Remove button */}
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  onClick={() => removeRow(row.id)}
                  disabled={isSubmitting}
                  className="h-9 w-9 rounded-lg text-destructive hover:bg-destructive/10 transition-colors"
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            ))}

            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={addRow}
              disabled={isSubmitting}
              className="mt-1 h-8 justify-start gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
            >
              <Plus className="h-4 w-4" />
              Add Project
            </Button>
          </div>
        </div>

        {error && (
          <div className="rounded-lg bg-destructive/10 border border-destructive/20 px-4 py-3">
            <p className="text-xs text-destructive font-semibold">{error}</p>
          </div>
        )}

        {saved && (
          <div className="rounded-lg bg-primary/10 border border-primary/20 px-4 py-3">
            <p className="text-xs text-primary font-semibold">✓ Changes saved! Redirecting…</p>
          </div>
        )}

        <div className="flex justify-end gap-3">
          <Button variant="outline" className="h-11 px-6 rounded-xl" onClick={() => navigate("/dashboard/members")} disabled={isSubmitting}>
            Cancel
          </Button>
          <Button
            className="h-11 px-8 rounded-xl min-w-35"
            onClick={handleSave}
            disabled={isSubmitting || !workspaceId}
          >
            {isSubmitting ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" />Saving…</> : "Save Changes"}
          </Button>
        </div>
      </div>
    </div>
  )
}

export default ManageMemberPage
