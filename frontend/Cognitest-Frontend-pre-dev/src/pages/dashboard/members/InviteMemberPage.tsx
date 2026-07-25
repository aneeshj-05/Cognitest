import { useState, useEffect } from "react"
import PageHeader from "@/components/shared/PageHeader"
import { useNavigate } from "react-router-dom"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import {
    ArrowLeft,
    Loader2,
    Plus,
    Trash2,
    UserPlus,
    Bell,
    BellOff,
    FolderKanban,
} from "lucide-react"
import { useProjects } from "@/context/ProjectContext"
import { useAuth } from "@/context/AuthContext"
import { getRoles, createInvitation, type RoleData, type ProjectAssignment } from "@/services/backendClient"
import { generateUUID } from "@/lib/utils"

// ── Per-project assignment row type ──────────────────────────────────────────

interface AssignmentRow {
    id: string
    projectId: string
    roleId: string
}

// ── Main Component ────────────────────────────────────────────────────────────

const InviteMemberPage = () => {
    const navigate = useNavigate()
    const { projects } = useProjects()
    const { workspace } = useAuth()

    // Target User
    const [email, setEmail] = useState("")

    // Project assignment repeater
    const [assignments, setAssignments] = useState<AssignmentRow[]>([
        { id: generateUUID(), projectId: "", roleId: "" },
    ])

    // Roles fetched from backend (for per-project role dropdowns)
    const [roles, setRoles] = useState<RoleData[]>([])
    useEffect(() => { getRoles().then(setRoles).catch(console.error) }, [])

    // Invite message & notification
    const [inviteMessage, setInviteMessage] = useState("")
    const [sendInAppNotification, setSendInAppNotification] = useState(true)

    // UI
    const [isSubmitting, setIsSubmitting] = useState(false)
    const [error, setError] = useState("")

    // ── Repeater helpers ──────────────────────────────────────────────────────

    const addAssignment = () =>
        setAssignments((prev) => [...prev, { id: generateUUID(), projectId: "", roleId: "" }])

    const removeAssignment = (id: string) =>
        setAssignments((prev) => prev.filter((a) => a.id !== id))

    const updateAssignment = (id: string, field: "projectId" | "roleId", value: string) =>
        setAssignments((prev) => prev.map((a) => (a.id === id ? { ...a, [field]: value } : a)))

    // ── Submit ────────────────────────────────────────────────────────────────

    const handleSubmit = async () => {
        setError("")
        if (!email.trim()) { setError("Email address is required."); return }

        const validAssignments: ProjectAssignment[] = assignments
            .filter((a) => a.projectId && a.roleId)
            .map(({ projectId, roleId }) => ({ projectId, roleId }))

        if (validAssignments.length === 0) {
            setError("Please assign at least one project and role.")
            return
        }

        setIsSubmitting(true)
        try {
            // Send invitations for each valid assignment
            for (const assignment of validAssignments) {
                await createInvitation({
                    email,
                    roleId: assignment.roleId,
                    projectId: assignment.projectId,
                    workspaceId: workspace?.id, // Optional, depending on your auth context shape
                    message: inviteMessage.trim() || undefined
                })
            }
            
            // Notification pref could be saved locally or passed in the invite if your backend supports it.
            
            navigate("/dashboard/members")
        } catch (err: any) {
            setError(err?.message || "Failed to send invitation.")
        } finally {
            setIsSubmitting(false)
        }
    }

    // ── Render ────────────────────────────────────────────────────────────────

    return (
        <div className="p-6 min-h-full">
            <div className="mx-auto w-full max-w-2xl space-y-6">

                {/* Header */}
                <div className="flex items-center gap-4">
                    <Button
                        onClick={() => navigate("/dashboard/members")}
                        variant="outline"
                        size="icon"
                        className="h-9 w-9 rounded-full text-muted-foreground hover:text-foreground"
                    >
                        <ArrowLeft className="h-4 w-4" />
                    </Button>
                    <div>
                    <PageHeader title="Invite New Member" description="Send an invitation to join your workspace" />
                    </div>
                </div>

                {/* ── Section 1: Target Identity ── */}
                <div className="rounded-2xl border border-border bg-card shadow-sm overflow-hidden">
                    <div className="flex items-center gap-3 px-6 py-4 border-b border-border bg-muted/30">
                        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 text-primary border border-border">
                            <UserPlus className="h-4 w-4" />
                        </div>
                        <div>
                            <p className="text-sm font-bold">Recipient</p>
                            <p className="text-xs text-muted-foreground">Who do you want to invite?</p>
                        </div>
                    </div>

                    <div className="p-6 space-y-5">
                        <div className="space-y-1.5">
                            <Label htmlFor="email" className="text-sm font-semibold">
                                Email Address <span className="text-destructive">*</span>
                            </Label>
                            <Input
                                id="email"
                                type="email"
                                placeholder="colleague@company.com"
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                                disabled={isSubmitting}
                                className="h-11 rounded-lg"
                            />
                        </div>
                    </div>
                </div>


                {/* ── Section 2: Project Assignments ── */}
                <div className="rounded-2xl border border-border bg-card shadow-sm overflow-hidden">
                    <div className="flex items-center gap-3 px-6 py-4 border-b border-border bg-muted/30">
                        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 text-primary border border-border">
                            <FolderKanban className="h-4 w-4" />
                        </div>
                        <div>
                            <p className="text-sm font-semibold">Project Assignments</p>
                            <p className="text-xs text-muted-foreground">Assign this user to one or more projects with specific roles</p>
                        </div>
                    </div>

                    <div className="p-6 space-y-3">
                        {assignments.map((row) => (
                            <div
                                key={row.id}
                                className="flex flex-col sm:flex-row items-start sm:items-end gap-3 rounded-xl border border-border/70 bg-muted/30 p-4"
                            >
                                {/* Project dropdown */}
                                <div className="flex-1 space-y-1 w-full">
                                    <label className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Project</label>
                                    <select
                                        value={row.projectId}
                                        onChange={(e) => updateAssignment(row.id, "projectId", e.target.value)}
                                        disabled={isSubmitting}
                                        className="w-full h-10 rounded-lg border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary/20"
                                    >
                                        <option value="">— Select project —</option>
                                        {projects.map((p) => (
                                            <option key={p.id} value={p.id}>{p.name}</option>
                                        ))}
                                    </select>
                                </div>

                                {/* Role dropdown */}
                                <div className="flex-1 space-y-1 w-full">
                                    <label className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Role on this project</label>
                                    <select
                                        value={row.roleId}
                                        onChange={(e) => updateAssignment(row.id, "roleId", e.target.value)}
                                        disabled={isSubmitting}
                                        className="w-full h-10 rounded-lg border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary/20"
                                    >
                                        <option value="">— Select role —</option>
                                        {roles.map((r) => (
                                            <option key={r.id} value={r.id}>{r.name}</option>
                                        ))}
                                    </select>
                                </div>

                                {/* Remove button */}
                                {assignments.length > 1 && (
                                    <Button
                                        type="button"
                                        variant="outline"
                                        size="icon"
                                        onClick={() => removeAssignment(row.id)}
                                        disabled={isSubmitting}
                                        className="h-10 w-10 shrink-0 rounded-lg border border-destructive/20 text-destructive hover:bg-destructive/10 transition-colors"
                                        title="Remove"
                                    >
                                        <Trash2 className="h-4 w-4" />
                                    </Button>
                                )}
                            </div>
                        ))}

                        <Button
                            type="button"
                            variant="outline"
                            onClick={addAssignment}
                            disabled={isSubmitting}
                            className="h-auto w-full justify-center gap-2 rounded-xl border border-dashed border-border/70 px-4 py-3 text-sm font-medium text-muted-foreground hover:text-foreground hover:bg-muted/40 transition-all"
                        >
                            <Plus className="h-4 w-4" />
                            Add Another Project
                        </Button>
                    </div>
                </div>

                {/* ── Section 3: Invitation & Notification ── */}
                <div className="rounded-2xl border border-border bg-card shadow-sm overflow-hidden">
                    <div className="flex items-center gap-3 px-6 py-4 border-b border-border bg-muted/30">
                        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 text-primary border border-border">
                            <Bell className="h-4 w-4" />
                        </div>
                        <div>
                            <p className="text-sm font-semibold">Invitation &amp; Notification</p>
                            <p className="text-xs text-muted-foreground">Customise the welcome experience</p>
                        </div>
                    </div>

                    <div className="p-6 space-y-5">
                        {/* Personalised message */}
                        <div className="space-y-1.5">
                            <Label htmlFor="inviteMsg" className="text-sm font-semibold">
                                Personalised Message{" "}
                                <span className="text-muted-foreground font-normal">(optional)</span>
                            </Label>
                            <textarea
                                id="inviteMsg"
                                rows={3}
                                placeholder={`e.g. "Welcome to the team! Here's your Cognitest access for the new API specs."`}
                                value={inviteMessage}
                                onChange={(e) => setInviteMessage(e.target.value)}
                                disabled={isSubmitting}
                                className="w-full rounded-lg border border-input bg-background px-3 py-2.5 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-primary/20 placeholder:text-muted-foreground/60"
                            />
                            <p className="text-[11px] text-muted-foreground">Shown to the user when they view the invitation.</p>
                        </div>

                        {/* In-app notification toggle */}
                        <div className="flex items-center gap-4 rounded-xl border border-border p-4 hover:bg-muted/40 transition-colors">
                            <Switch
                                checked={sendInAppNotification}
                                onCheckedChange={setSendInAppNotification}
                                aria-label="Send in-app notification"
                            />
                            <div className="flex flex-col">
                                <div className="flex items-center gap-1.5">
                                    {sendInAppNotification
                                        ? <Bell className="h-3.5 w-3.5 text-foreground" />
                                        : <BellOff className="h-3.5 w-3.5 text-muted-foreground" />}
                                    <span className="text-sm font-semibold">
                                        {sendInAppNotification ? "Notify on acceptance" : "No in-app notification"}
                                    </span>
                                </div>
                                <span className="text-xs text-muted-foreground">
                                    {sendInAppNotification
                                        ? "User will see a welcome ping the moment they accept."
                                        : "User accepts silently with no notification banner."}
                                </span>
                            </div>
                        </div>
                    </div>
                </div>

                {/* Error */}
                {error && (
                    <div className="rounded-xl border border-destructive/20 bg-destructive/10 px-4 py-3">
                        <p className="text-sm text-destructive font-medium">{error}</p>
                    </div>
                )}

                {/* Footer */}
                <div className="flex items-center justify-end gap-3 pb-8">
                    <Button
                        variant="outline"
                        className="h-11 px-6 rounded-xl"
                        onClick={() => navigate("/dashboard/members")}
                        disabled={isSubmitting}
                    >
                        Cancel
                    </Button>
                    <Button
                        className="h-11 px-8 rounded-xl min-w-50 font-semibold"
                        onClick={handleSubmit}
                        disabled={isSubmitting || !email.trim()}
                    >
                        {isSubmitting ? (
                            <><Loader2 className="mr-2 h-4 w-4 animate-spin" />Sending…</>
                        ) : (
                            <><UserPlus className="mr-2 h-4 w-4" />Send Invitation</>
                        )}
                    </Button>
                </div>
            </div>
        </div >
    )
}

export default InviteMemberPage
