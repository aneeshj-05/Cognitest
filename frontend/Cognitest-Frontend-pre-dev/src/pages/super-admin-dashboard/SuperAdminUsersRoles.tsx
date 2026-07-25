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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { StatCardsGridSkeleton, TableSkeleton } from "@/components/shared/LoadingSkeletons"
import { Skeleton } from "@/components/ui/skeleton"
import StatCard from "@/components/shared/StatCard"
import {
  Users,
  Shield,
  Eye as EyeIcon,
  UserCheck,
  Search,
  Plus,
  Pencil,
  Trash2,
} from "lucide-react"
import type { SuperAdminTenant } from "@/services/backendClient"
import { updateSuperAdminUserStatus } from "@/services/backendClient"

// ─── Types ──────────────────────────────────────────────────────────
interface FlatUser {
  id: string
  name: string
  email: string
  role: string
  tenantId: string
  tenantName: string
  status: string
  lastLogin: string
}

interface UsersRolesProps {
  tenants: SuperAdminTenant[]
  loading: boolean
  onRefresh: () => void
}



// ─── Component ──────────────────────────────────────────────────────
export default function SuperAdminUsersRoles({ tenants, loading, onRefresh }: UsersRolesProps) {
  const [searchQuery, setSearchQuery] = useState("")
  const [roleFilter, setRoleFilter] = useState("all")
  const [permissionsOpen, setPermissionsOpen] = useState(false)

  // Flatten all users from all tenants
  const allUsers: FlatUser[] = tenants.flatMap(t =>
    t.team.map(u => ({
      id: u.id,
      name: u.name || "Unknown",
      email: u.email || "N/A",
      role: u.role || "MEMBER",
      tenantId: t.id,
      tenantName: t.name,
      status: u.status || "Active",
      lastLogin: getRelativeTime(),
    }))
  )

  const totalUsers = allUsers.length
  const adminCount = allUsers.filter(u => u.role === "TENANT_ADMIN").length
  const testerCount = allUsers.filter(u => u.role === "TESTER" || u.role === "MEMBER").length
  const viewerCount = allUsers.filter(u => u.role === "VIEWER").length

  // Filter
  const filtered = allUsers.filter(u => {
    const matchSearch =
      u.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      u.email.toLowerCase().includes(searchQuery.toLowerCase()) ||
      u.tenantName.toLowerCase().includes(searchQuery.toLowerCase())
    const matchRole =
      roleFilter === "all" ||
      (roleFilter === "ADMIN" && u.role === "TENANT_ADMIN") ||
      (roleFilter === "TESTER" && (u.role === "TESTER" || u.role === "MEMBER")) ||
      (roleFilter === "VIEWER" && u.role === "VIEWER")
    return matchSearch && matchRole
  })

  const getRoleBadge = (role: string) => {
    const r = (role || "").toUpperCase()
    if (r === "TENANT_ADMIN")
      return (
        <Badge className="bg-destructive/10 text-destructive border-destructive/20 hover:bg-destructive/10 gap-1">
          <Shield className="h-3 w-3" /> Admin
        </Badge>
      )
    if (r === "TESTER" || r === "MEMBER")
      return (
        <Badge className="bg-muted text-foreground border-border hover:bg-muted gap-1">
          <UserCheck className="h-3 w-3" /> Tester
        </Badge>
      )
    if (r === "VIEWER")
      return (
        <Badge className="bg-primary/10 text-primary border-primary/20 hover:bg-primary/10 gap-1">
          <EyeIcon className="h-3 w-3" /> Viewer
        </Badge>
      )
    return <Badge variant="outline">{role}</Badge>
  }

  const getStatusBadge = (status: string) => {
    if (status === "Active" || status === "ACTIVE")
      return <span className="text-xs font-semibold text-primary">Active</span>
    if (status === "Locked" || status === "INACTIVE")
      return <span className="text-xs font-semibold text-muted-foreground">Inactive</span>
    return <span className="text-xs font-semibold text-muted-foreground">{status}</span>
  }

  const handleToggleStatus = async (user: FlatUser) => {
    const newStatus = user.status === "Active" ? "INACTIVE" : "ACTIVE"
    try {
      await updateSuperAdminUserStatus(user.id, newStatus)
      onRefresh()
    } catch (err) {
      console.error("Failed to update user status:", err)
    }
  }

  const stats = [
    {
      label: "Total Users",
      value: totalUsers.toLocaleString(),
      sub: "+18% this month",
      subColor: "text-emerald-500",
      icon: Users,
    },
    {
      label: "Admins",
      value: adminCount,
      sub: `${totalUsers ? Math.round((adminCount / totalUsers) * 100) : 0}% of total`,
      subColor: "text-muted-foreground",
      icon: Shield,
    },
    {
      label: "Testers",
      value: testerCount.toLocaleString(),
      sub: `${totalUsers ? Math.round((testerCount / totalUsers) * 100) : 0}% of total`,
      subColor: "text-muted-foreground",
      icon: UserCheck,
    },
    {
      label: "Viewers",
      value: viewerCount,
      sub: `${totalUsers ? Math.round((viewerCount / totalUsers) * 100) : 0}% of total`,
      subColor: "text-muted-foreground",
      icon: EyeIcon,
    },
  ]

  if (loading) {
    return (
      <div className="space-y-6">
        <StatCardsGridSkeleton count={4} />
        <Card className="rounded-xl border border-border/60 bg-white shadow-sm overflow-hidden">
          <div className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between border-b border-border/50">
            <Skeleton className="h-10 w-full sm:max-w-sm rounded-md" />
            <div className="flex items-center gap-3">
              <Skeleton className="h-9 w-24 rounded-md" />
              <Skeleton className="h-9 w-24 rounded-md" />
            </div>
          </div>
          <TableSkeleton
            columns={[
              { header: "Name", widthClassName: "w-40" },
              { header: "Email", widthClassName: "w-48" },
              { header: "Role", widthClassName: "w-24" },
              { header: "Tenant", widthClassName: "w-32" },
              { header: "Last Login", widthClassName: "w-32" },
              { header: "Status", widthClassName: "w-20" },
              { header: "Actions", widthClassName: "w-8", align: "right" },
            ]}
            rowCount={6}
          />
        </Card>
      </div>
    )
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
            helperText={s.sub}
          />
        ))}
      </div>

      {/* Filters + Table */}
      <Card className="rounded-xl border border-border/60 bg-white shadow-sm overflow-hidden">
        <div className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between border-b border-border/50">
          <div className="relative w-full sm:max-w-sm">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search users..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              className="pl-9"
            />
          </div>
          <div className="flex items-center gap-3">
            <Select value={roleFilter} onValueChange={setRoleFilter}>
              <SelectTrigger className="w-[130px] h-9 text-sm">
                <SelectValue placeholder="All Roles" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Roles</SelectItem>
                <SelectItem value="ADMIN">Admin</SelectItem>
                <SelectItem value="TESTER">Tester</SelectItem>
                <SelectItem value="VIEWER">Viewer</SelectItem>
              </SelectContent>
            </Select>
            <Button variant="outline" size="sm" className="gap-2 text-xs" onClick={() => setPermissionsOpen(true)}>
              <EyeIcon className="h-3.5 w-3.5" /> View Permissions
            </Button>
            <Button size="sm" className="gap-2 text-xs">
              <Plus className="h-3.5 w-3.5" /> Add User
            </Button>
          </div>
        </div>

        <div className="overflow-x-auto">
          <Table>
            <TableHeader className="bg-muted/40">
              <TableRow>
                <TableHead className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Name</TableHead>
                <TableHead className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Email</TableHead>
                <TableHead className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Role</TableHead>
                <TableHead className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Tenant</TableHead>
                <TableHead className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Last Login</TableHead>
                <TableHead className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Status</TableHead>
                <TableHead className="text-xs font-medium uppercase tracking-wide text-muted-foreground text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={7} className="text-center py-12">
                    <Users className="mx-auto h-10 w-10 text-muted-foreground/40 mb-3" />
                    <p className="text-sm text-muted-foreground">No users found</p>
                  </TableCell>
                </TableRow>
              ) : (
                filtered.map(user => (
                  <TableRow key={user.id} className="hover:bg-muted/40">
                    <TableCell className="font-medium text-foreground">{user.name}</TableCell>
                    <TableCell className="text-sm text-muted-foreground">{user.email}</TableCell>
                    <TableCell>{getRoleBadge(user.role)}</TableCell>
                    <TableCell className="text-sm text-muted-foreground">{user.tenantName}</TableCell>
                    <TableCell className="text-sm text-muted-foreground">{user.lastLogin}</TableCell>
                    <TableCell>{getStatusBadge(user.status)}</TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-1">
                        <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground hover:text-foreground">
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 text-destructive hover:text-destructive hover:bg-destructive/10"
                          onClick={() => handleToggleStatus(user)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
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
              <span className="font-medium text-foreground">{totalUsers}</span> users
            </p>
          </div>
        )}
      </Card>

      {/* Permissions Dialog */}
      <Dialog open={permissionsOpen} onOpenChange={setPermissionsOpen}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>Role Permissions Overview</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 mt-2">
            {[
              { role: "Admin", perms: ["Full access", "Manage users", "Manage projects", "Upload specs", "Run tests", "View reports"] },
              { role: "Tester", perms: ["Run tests", "View test results", "Upload specs", "View reports"] },
              { role: "Viewer", perms: ["View projects", "View test results", "View reports"] },
            ].map(r => (
              <div key={r.role} className="rounded-lg border border-border p-4">
                <p className="text-sm font-semibold text-foreground mb-2">{r.role}</p>
                <div className="flex flex-wrap gap-2">
                  {r.perms.map(p => (
                    <Badge key={p} variant="secondary" className="text-xs">
                      {p}
                    </Badge>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}

// Helper to generate random "last login" times
function getRelativeTime(): string {
  const options = [
    "2 hours ago",
    "1 day ago",
    "3 days ago",
    "5 hours ago",
    "2 weeks ago",
    "Just now",
    "1 hour ago",
    "4 days ago",
  ]
  return options[Math.floor(Math.random() * options.length)]
}
