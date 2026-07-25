import { useState } from "react"
import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { SuperAdminTenantsSkeleton } from "@/components/shared/LoadingSkeletons"
import StatCard from "@/components/shared/StatCard"
import {
  Building2,
  Zap,
  Shield,
  AlertTriangle,
  Search,
  Download,
  MoreVertical,
  Eye,
  Pencil,
  Ban,
  Trash2,
} from "lucide-react"
import type { SuperAdminTenant } from "@/services/backendClient"
import {
  createSuperAdminTenant,
  updateSuperAdminTenant,
  updateSuperAdminTenantStatus,
  deleteSuperAdminTenant,
} from "@/services/backendClient"

interface TenantsProps {
  tenants: SuperAdminTenant[]
  loading: boolean
  onRefresh: () => void
}



export default function SuperAdminTenants({ tenants, loading, onRefresh }: TenantsProps) {
  const [searchQuery, setSearchQuery] = useState("")
  const [planFilter, setPlanFilter] = useState("all")
  const [statusFilter, setStatusFilter] = useState("all")

  // Dialogs
  const [createOpen, setCreateOpen] = useState(false)
  const [editingTenant, setEditingTenant] = useState<SuperAdminTenant | null>(null)
  const [deletingTenant, setDeletingTenant] = useState<SuperAdminTenant | null>(null)
  const [saving, setSaving] = useState(false)

  // Form state
  const [formName, setFormName] = useState("")
  const [formEmail, setFormEmail] = useState("")
  const [formPassword, setFormPassword] = useState("")
  const [formPlan, setFormPlan] = useState("Free")

  // Stats
  const activeTenants = tenants.filter(t => t.status === "ACTIVE").length
  const enterpriseTenants = tenants.filter(t => (t.plan || "").toUpperCase() === "ENTERPRISE").length
  const suspendedTenants = tenants.filter(t => t.status === "SUSPENDED").length

  // Filter
  const filtered = tenants.filter(t => {
    const matchSearch =
      t.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      t.email.toLowerCase().includes(searchQuery.toLowerCase())
    const matchPlan = planFilter === "all" || (t.plan || "FREE").toUpperCase() === planFilter.toUpperCase()
    const matchStatus = statusFilter === "all" || t.status === statusFilter.toUpperCase()
    return matchSearch && matchPlan && matchStatus
  })

  const getPlanBadge = (plan: string) => {
    const p = (plan || "FREE").toUpperCase()
    if (p === "ENTERPRISE") return <Badge className="bg-primary/10 text-primary border-primary/20 hover:bg-primary/10">Enterprise</Badge>
    if (p === "PRO" || p === "PROFESSIONAL") return <Badge className="bg-secondary text-secondary-foreground border-border hover:bg-secondary">Pro</Badge>
    return <Badge className="bg-muted text-muted-foreground border-border hover:bg-muted">Free</Badge>
  }

  const getStatusBadge = (status: string) => {
    const s = (status || "").toUpperCase()
    if (s === "ACTIVE") return <Badge className="bg-primary/10 text-primary border-primary/20 hover:bg-primary/10">Active</Badge>
    if (s === "SUSPENDED") return <Badge className="bg-destructive/10 text-destructive border-destructive/20 hover:bg-destructive/10">Suspended</Badge>
    return <Badge variant="outline">{status || "Unknown"}</Badge>
  }

  const getBillingBadge = (plan: string) => {
    const p = (plan || "FREE").toUpperCase()
    if (p === "FREE") return <span className="text-primary font-medium text-sm">Current</span>
    return <span className="text-destructive font-medium text-sm">Overdue</span>
  }

  const handleCreate = async () => {
    if (!formEmail) return
    setSaving(true)
    try {
      await createSuperAdminTenant({
        name: formName || undefined,
        email: formEmail,
        password: formPassword || undefined,
        plan: formPlan,
      })
      setCreateOpen(false)
      resetForm()
      onRefresh()
    } catch (err) {
      console.error("Failed to create tenant:", err)
    } finally {
      setSaving(false)
    }
  }

  const handleEdit = async () => {
    if (!editingTenant) return
    setSaving(true)
    try {
      await updateSuperAdminTenant(editingTenant.id, {
        name: formName || undefined,
        email: formEmail || undefined,
        password: formPassword || undefined,
        plan: formPlan,
      })
      setEditingTenant(null)
      resetForm()
      onRefresh()
    } catch (err) {
      console.error("Failed to update tenant:", err)
    } finally {
      setSaving(false)
    }
  }

  const handleSuspend = async (tenant: SuperAdminTenant) => {
    const newStatus = tenant.status === "SUSPENDED" ? "ACTIVE" : "SUSPENDED"
    try {
      await updateSuperAdminTenantStatus(tenant.id, newStatus)
      onRefresh()
    } catch (err) {
      console.error("Failed to update tenant status:", err)
    }
  }

  const handleDelete = async () => {
    if (!deletingTenant) return
    setSaving(true)
    try {
      await deleteSuperAdminTenant(deletingTenant.id)
      setDeletingTenant(null)
      onRefresh()
    } catch (err) {
      console.error("Failed to delete tenant:", err)
    } finally {
      setSaving(false)
    }
  }

  const openEdit = (tenant: SuperAdminTenant) => {
    setFormName(tenant.name)
    setFormEmail(tenant.email)
    setFormPassword("")
    const p = (tenant.plan || "FREE").toUpperCase()
    setFormPlan(p === "PRO" ? "Professional" : p === "ENTERPRISE" ? "Enterprise" : p === "STARTER" ? "Starter" : "Free")
    setEditingTenant(tenant)
  }

  const resetForm = () => {
    setFormName("")
    setFormEmail("")
    setFormPassword("")
    setFormPlan("Free")
  }

  const stats = [
    {
      label: "Total Tenants",
      value: tenants.length,
      sub: null,
      icon: Building2,
      iconColor: "text-primary",
    },
    {
      label: "Active Tenants",
      value: activeTenants,
      sub: `${tenants.length ? Math.round((activeTenants / tenants.length) * 100) : 0}% active rate`,
      icon: Zap,
      iconColor: "text-primary",
    },
    {
      label: "Enterprise Plans",
      value: enterpriseTenants,
      sub: `${tenants.length ? Math.round((enterpriseTenants / tenants.length) * 100) : 0}% of total`,
      icon: Shield,
      iconColor: "text-primary",
    },
    {
      label: "Suspended",
      value: suspendedTenants,
      sub: suspendedTenants > 0 ? "Requires attention" : "All clear",
      subColor: suspendedTenants > 0 ? "text-red-500" : "text-emerald-500",
      icon: AlertTriangle,
      iconColor: "text-primary",
    },
  ]

  if (loading) {
    return <SuperAdminTenantsSkeleton />
  }

  return (
    <div className="space-y-6">
      {/* Stat Cards */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        {stats.map(s => (
          <StatCard
            key={s.label}
            title={s.label}
            value={s.value}
            icon={s.icon}
            helperText={s.sub || undefined}
          />
        ))}
      </div>

      {/* Filters + Table */}
      <Card className="rounded-xl border border-border/60 bg-white shadow-sm overflow-hidden">
        <div className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between border-b border-border/50">
          <div className="relative w-full sm:max-w-sm">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search tenants..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              className="pl-9"
            />
          </div>
          <div className="flex items-center gap-3">
            <Select value={planFilter} onValueChange={setPlanFilter}>
              <SelectTrigger className="w-[130px] h-9 text-sm">
                <SelectValue placeholder="All Plans" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Plans</SelectItem>
                <SelectItem value="FREE">Free</SelectItem>
                <SelectItem value="PRO">Pro</SelectItem>
                <SelectItem value="ENTERPRISE">Enterprise</SelectItem>
              </SelectContent>
            </Select>
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-[130px] h-9 text-sm">
                <SelectValue placeholder="All Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Status</SelectItem>
                <SelectItem value="ACTIVE">Active</SelectItem>
                <SelectItem value="SUSPENDED">Suspended</SelectItem>
              </SelectContent>
            </Select>
            <Button variant="outline" size="sm" className="gap-2 text-xs">
              <Download className="h-3.5 w-3.5" /> Export
            </Button>
          </div>
        </div>

        <div className="overflow-x-auto">
          <Table>
            <TableHeader className="bg-muted/40">
              <TableRow>
                <TableHead className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Tenant Name</TableHead>
                <TableHead className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Plan</TableHead>
                <TableHead className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Users</TableHead>
                <TableHead className="text-xs font-medium uppercase tracking-wide text-muted-foreground">API Usage</TableHead>
                <TableHead className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Status</TableHead>
                <TableHead className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Billing</TableHead>
                <TableHead className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Created</TableHead>
                <TableHead className="text-xs font-medium uppercase tracking-wide text-muted-foreground text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={8} className="text-center py-12">
                    <Building2 className="mx-auto h-10 w-10 text-muted-foreground/40 mb-3" />
                    <p className="text-sm text-muted-foreground">No tenants found</p>
                  </TableCell>
                </TableRow>
              ) : (
                filtered.map(tenant => (
                  <TableRow key={tenant.id} className="hover:bg-muted/40">
                    <TableCell className="font-medium text-foreground">{tenant.name}</TableCell>
                    <TableCell>{getPlanBadge(tenant.plan)}</TableCell>
                    <TableCell className="text-sm text-muted-foreground">{tenant.team.length} users</TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {(tenant.projects.length * 150).toLocaleString()} calls
                    </TableCell>
                    <TableCell>{getStatusBadge(tenant.status)}</TableCell>
                    <TableCell>{getBillingBadge(tenant.plan)}</TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {tenant.createdAt ? new Date(tenant.createdAt).toISOString().split("T")[0] : "N/A"}
                    </TableCell>
                    <TableCell className="text-right">
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="icon" className="h-8 w-8">
                            <MoreVertical className="h-4 w-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem>
                            <Eye className="mr-2 h-4 w-4" /> View
                          </DropdownMenuItem>
                          <DropdownMenuItem onClick={() => openEdit(tenant)}>
                            <Pencil className="mr-2 h-4 w-4" /> Edit
                          </DropdownMenuItem>
                          <DropdownMenuItem onClick={() => handleSuspend(tenant)}>
                            <Ban className="mr-2 h-4 w-4" />
                            {tenant.status === "SUSPENDED" ? "Activate" : "Suspend"}
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            className="text-destructive focus:text-destructive"
                            onClick={() => setDeletingTenant(tenant)}
                          >
                            <Trash2 className="mr-2 h-4 w-4" /> Delete
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </div>

        {filtered.length > 0 && (
          <div className="flex items-center justify-between border-t border-border/50 px-4 py-3 text-xs text-muted-foreground">
            <p>
              Showing <span className="font-medium text-foreground">{filtered.length}</span> of{" "}
              <span className="font-medium text-foreground">{tenants.length}</span> tenants
            </p>
          </div>
        )}
      </Card>

      {/* Create Tenant Dialog */}
      <Dialog open={createOpen} onOpenChange={v => { if (!v) { setCreateOpen(false); resetForm() } }}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Create New Tenant</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 mt-2">
            <div className="space-y-2">
              <label className="text-sm font-medium">Tenant Name</label>
              <Input placeholder="Acme Inc." value={formName} onChange={e => setFormName(e.target.value)} />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Admin Email</label>
              <Input type="email" placeholder="admin@tenant.com" value={formEmail} onChange={e => setFormEmail(e.target.value)} />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Password</label>
              <Input type="password" placeholder="••••••••" value={formPassword} onChange={e => setFormPassword(e.target.value)} />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Plan</label>
              <Select value={formPlan} onValueChange={setFormPlan}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="Free">Free</SelectItem>
                  <SelectItem value="Starter">Starter</SelectItem>
                  <SelectItem value="Professional">Professional</SelectItem>
                  <SelectItem value="Enterprise">Enterprise</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="outline" onClick={() => { setCreateOpen(false); resetForm() }} disabled={saving}>Cancel</Button>
              <Button onClick={handleCreate} disabled={saving || !formEmail}>
                {saving ? "Creating..." : "Create Tenant"}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Edit Tenant Dialog */}
      <Dialog open={!!editingTenant} onOpenChange={v => { if (!v) { setEditingTenant(null); resetForm() } }}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Edit Tenant</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 mt-2">
            <div className="space-y-2">
              <label className="text-sm font-medium">Tenant Name</label>
              <Input value={formName} onChange={e => setFormName(e.target.value)} />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Admin Email</label>
              <Input type="email" value={formEmail} onChange={e => setFormEmail(e.target.value)} />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Update Password (optional)</label>
              <Input type="password" placeholder="Leave blank to keep current" value={formPassword} onChange={e => setFormPassword(e.target.value)} />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Plan</label>
              <Select value={formPlan} onValueChange={setFormPlan}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="Free">Free</SelectItem>
                  <SelectItem value="Starter">Starter</SelectItem>
                  <SelectItem value="Professional">Professional</SelectItem>
                  <SelectItem value="Enterprise">Enterprise</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="outline" onClick={() => { setEditingTenant(null); resetForm() }} disabled={saving}>Cancel</Button>
              <Button onClick={handleEdit} disabled={saving}>
                {saving ? "Saving..." : "Save Changes"}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog open={!!deletingTenant} onOpenChange={v => { if (!v) setDeletingTenant(null) }}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle className="text-destructive">Delete Tenant</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Are you sure you want to permanently delete <strong className="text-foreground">{deletingTenant?.name}</strong>?
            This will remove all users, projects, and data. This action cannot be undone.
          </p>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" onClick={() => setDeletingTenant(null)} disabled={saving}>Cancel</Button>
            <Button variant="destructive" onClick={handleDelete} disabled={saving}>
              {saving ? "Deleting..." : "Delete Tenant"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
