import { useState, useEffect } from "react"
import PageHeader from "@/components/shared/PageHeader"
import { useNavigate } from "react-router-dom"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import {
    ArrowLeft,
    Eye,
    EyeOff,
    Loader2,
    Plus,
    Trash2,
    UserPlus,
    Bell,
    BellOff,
    FolderKanban,
} from "lucide-react"
import { useMembers } from "@/context/MembersContext"
import { useProjects } from "@/context/ProjectContext"
import { useAuth } from "@/context/AuthContext"
import { getRoles, type RoleData, type ProjectAssignment } from "@/services/backendClient"
import { generateUUID } from "@/lib/utils"

// ── Workspace role options ────────────────────────────────────────────────────

const WORKSPACE_ROLES = [
    { value: "ADMIN", label: "Admin", desc: "Full access to workspace and settings" },
    { value: "TESTER", label: "Tester", desc: "Can create and run tests" },
    { value: "QA", label: "QA", desc: "Can review results and generate reports" },
    { value: "AUDIT", label: "Audit", desc: "Read-only access to all data" },
]

// ── Password strength bar ─────────────────────────────────────────────────────

function PasswordStrengthBar({ password }: { password: string }) {
    const rules = [
        { label: "Min 6 chars", pass: password.length >= 6 },
        { label: "Uppercase", pass: /[A-Z]/.test(password) },
        { label: "Number", pass: /[0-9]/.test(password) },
        { label: "Special char", pass: /[^a-zA-Z0-9]/.test(password) },
    ]
    const score = rules.filter((r) => r.pass).length
    const colors = ["bg-primary/25", "bg-primary/40", "bg-primary/55", "bg-primary/70"]
    if (!password) return null
    return (
        <div className="mt-2 space-y-1.5">
            <div className="flex gap-1">
                {rules.map((_, i) => (
                    <div key={i} className={`h-1.5 flex-1 rounded-full transition-colors ${i < score ? colors[score - 1] : "bg-muted"}`} />
                ))}
            </div>
            <div className="flex flex-wrap gap-x-3 gap-y-0.5">
                {rules.map((r) => (
                    <span key={r.label} className={`text-[10px] font-medium ${r.pass ? "text-primary" : "text-muted-foreground"}`}>
                        {r.pass ? "✓" : "·"} {r.label}
                    </span>
                ))}
            </div>
        </div>
    )
}

// ── Per-project assignment row type ──────────────────────────────────────────

interface AssignmentRow {
    id: string
    projectId: string
    roleId: string
}

// ── Main Component ────────────────────────────────────────────────────────────

const CreateMemberPage = () => {
    const navigate = useNavigate()
    const { createUser } = useMembers()
    const { projects } = useProjects()
    const { user: adminUser } = useAuth()

    // Identity fields
    const [name, setName] = useState("")
    const [email, setEmail] = useState("")
    const [password, setPassword] = useState("")
    const [showPassword, setShowPassword] = useState(false)

    // Workspace role (the role picked here is the workspace-level role shown in Members list)
    const [workspaceRoleName, setWorkspaceRoleName] = useState("TESTER")

    // Additional fields
    const [company, setCompany] = useState(adminUser?.company || "")
    const [contactNumber, setContactNumber] = useState("")

    useEffect(() => {
        if (adminUser?.company) {
            setCompany(adminUser.company)
        }
    }, [adminUser])

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
        if (!name.trim()) { setError("Full name is required."); return }
        if (!email.trim()) { setError("Email address is required."); return }
        if (password.length < 6) { setError("Password must be at least 6 characters."); return }

        const validAssignments: ProjectAssignment[] = assignments
            .filter((a) => a.projectId && a.roleId)
            .map(({ projectId, roleId }) => ({ projectId, roleId }))

        setIsSubmitting(true)
        try {
            await createUser({
                name,
                email,
                password,
                company,
                contactNumber,
                systemRole: "USER",          // always a regular user; admin manages via workspace role
                workspaceRoleName,
                projectAssignments: validAssignments,
                inviteMessage: inviteMessage.trim() || undefined,
                sendInAppNotification,
            })
            navigate("/dashboard/members")
        } catch (err: any) {
            setError(err?.message || "Failed to create member.")
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
                    <PageHeader title="Create New Member" description="Create an account and assign projects for this user" />
                    </div>
                </div>

                {/* ── Section 1: Identity & Credentials ── */}
                <div className="rounded-2xl border border-border bg-card shadow-sm overflow-hidden">
                    <div className="flex items-center gap-3 px-6 py-4 border-b border-border bg-muted/30">
                        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 text-primary border border-border">
                            <UserPlus className="h-4 w-4" />
                        </div>
                        <div>
                            <p className="text-sm font-bold">Identity &amp; Credentials</p>
                            <p className="text-xs text-muted-foreground">Basic account information</p>
                        </div>
                    </div>

                    <div className="p-6 space-y-5">
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
                            {/* Full Name */}
                            <div className="space-y-1.5">
                                <Label htmlFor="name" className="text-sm font-semibold">
                                    Full Name <span className="text-destructive">*</span>
                                </Label>
                                <Input
                                    id="name"
                                    placeholder="Jane Smith"
                                    value={name}
                                    onChange={(e) => setName(e.target.value)}
                                    disabled={isSubmitting}
                                    className="h-11 rounded-lg"
                                />
                            </div>

                            {/* Email */}
                            <div className="space-y-1.5">
                                <Label htmlFor="email" className="text-sm font-semibold">
                                    Email Address <span className="text-destructive">*</span>
                                </Label>
                                <Input
                                    id="email"
                                    type="email"
                                    placeholder="jane@company.com"
                                    value={email}
                                    onChange={(e) => setEmail(e.target.value)}
                                    disabled={isSubmitting}
                                    className="h-11 rounded-lg"
                                />
                            </div>
                        </div>

                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
                            {/* Company */}
                            <div className="space-y-1.5">
                                <Label htmlFor="company" className="text-sm font-semibold">Company</Label>
                                <Input
                                    id="company"
                                    placeholder="Company Name"
                                    value={company}
                                    onChange={(e) => setCompany(e.target.value)}
                                    disabled={isSubmitting}
                                    className="h-11 rounded-lg"
                                />
                            </div>

                            {/* Contact Number */}
                            <div className="space-y-1.5">
                                <Label htmlFor="contact" className="text-sm font-semibold">Contact Number</Label>
                                <Input
                                    id="contact"
                                    placeholder="+1 234 567 890"
                                    value={contactNumber}
                                    onChange={(e) => setContactNumber(e.target.value)}
                                    disabled={isSubmitting}
                                    className="h-11 rounded-lg"
                                />
                            </div>
                        </div>

                        {/* Password */}
                        <div className="space-y-1.5">
                            <Label htmlFor="password" className="text-sm font-semibold">
                                Temporary Password <span className="text-destructive">*</span>
                            </Label>
                            <div className="relative">
                                <Input
                                    id="password"
                                    type={showPassword ? "text" : "password"}
                                    placeholder="Set a secure password"
                                    value={password}
                                    onChange={(e) => setPassword(e.target.value)}
                                    disabled={isSubmitting}
                                    className="h-11 rounded-lg pr-11"
                                />
                                <Button
                                    type="button"
                                    variant="ghost"
                                    size="icon"
                                    onClick={() => setShowPassword((v) => !v)}
                                    className="absolute right-2 top-1/2 h-8 w-8 -translate-y-1/2 p-0 text-muted-foreground hover:text-foreground transition-colors"
                                >
                                    {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                                </Button>
                            </div>
                            <PasswordStrengthBar password={password} />
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
                                placeholder={`e.g. "Welcome to the team, ${name || "Jane"}! Here's your Cognitest access for the new API specs."`}
                                value={inviteMessage}
                                onChange={(e) => setInviteMessage(e.target.value)}
                                disabled={isSubmitting}
                                className="w-full rounded-lg border border-input bg-background px-3 py-2.5 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-primary/20 placeholder:text-muted-foreground/60"
                            />
                            <p className="text-[11px] text-muted-foreground">Shown to the user on their first login.</p>
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
                                        {sendInAppNotification ? "Notify on first login" : "No in-app notification"}
                                    </span>
                                </div>
                                <span className="text-xs text-muted-foreground">
                                    {sendInAppNotification
                                        ? "User will see a welcome ping the moment they log in."
                                        : "User logs in silently with no notification banner."}
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
                        disabled={isSubmitting || !name.trim() || !email.trim() || password.length < 6}
                    >
                        {isSubmitting ? (
                            <><Loader2 className="mr-2 h-4 w-4 animate-spin" />Creating account…</>
                        ) : (
                            <><UserPlus className="mr-2 h-4 w-4" />Create &amp; Invite Member</>
                        )}
                    </Button>
                </div>
            </div>
        </div >
    )
}

export default CreateMemberPage
