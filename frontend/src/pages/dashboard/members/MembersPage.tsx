import { useState, useEffect } from "react"
import { useNavigate } from "react-router-dom"
import { MoreHorizontal, Plus, Search, Mail, RotateCw, XCircle } from "lucide-react"

import PageHeader from "@/components/shared/PageHeader"
import DataTable, { type DataTableColumn } from "@/components/shared/DataTable"
import EmptyState from "@/components/shared/EmptyState"
import SectionCard from "@/components/shared/SectionCard"
import { PageHeaderSkeleton, TableSkeleton } from "@/components/shared/LoadingSkeletons"

import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Input } from "@/components/ui/input"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"
import { useMembers, type Member } from "@/context/MembersContext"
import { useAuth } from "@/context/AuthContext"
import { 
  getInvitations, 
  revokeInvitation, 
  resendInvitation, 
  type FullInvitationResponse 
} from "@/services/backendClient"

const roleFilters = [
  { value: "all", label: "All" },
  { value: "admin", label: "Admin" },
  { value: "tester", label: "Tester" },
  { value: "qa", label: "QA" },
  { value: "audit", label: "Audit" },
]

type MemberRow =
  | { kind: "workspace"; member: Member }
  | { kind: "project"; member: Member; projectName: string; projectRole: string }

function getInitials(name: string) {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  const initials = parts.slice(0, 2).map((p) => p[0]?.toUpperCase() ?? "")
  return initials.join("") || "?"
}

function matchesRoleFilter(member: Member, activeFilter: string) {
  if (activeFilter === "all") return true
  const role = (member.roleName ?? "").toLowerCase()
  return role.includes(activeFilter)
}

const MembersPage = () => {
  const navigate = useNavigate()
  const { workspace } = useAuth()
  const { members, loading: membersLoading } = useMembers()
  const [search, setSearch] = useState("")
  const [activeFilter, setActiveFilter] = useState("all")
  const [mainTab, setMainTab] = useState("members")

  // Invitations state
  const [invitations, setInvitations] = useState<FullInvitationResponse[]>([])
  const [invitationsLoading, setInvitationsLoading] = useState(false)

  const fetchInvitations = async () => {
    if (!workspace?.id) return
    setInvitationsLoading(true)
    try {
      const data = await getInvitations(workspace.id)
      setInvitations(data)
    } catch (err) {
      console.error("Failed to load invitations", err)
    } finally {
      setInvitationsLoading(false)
    }
  }

  useEffect(() => {
    if (mainTab === "invitations") {
      fetchInvitations()
    }
  }, [mainTab, workspace?.id])

  const handleRevoke = async (id: string) => {
    try {
      await revokeInvitation(id)
      fetchInvitations()
    } catch (err) {
      console.error(err)
    }
  }

  const handleResend = async (id: string) => {
    try {
      await resendInvitation(id)
      fetchInvitations()
    } catch (err) {
      console.error(err)
    }
  }

  const filteredMembers = members.filter((m) => {
    const q = search.trim().toLowerCase()
    const matchesSearch =
      q.length === 0 ||
      m.name.toLowerCase().includes(q) ||
      m.email.toLowerCase().includes(q)
    return matchesSearch && matchesRoleFilter(m, activeFilter)
  })

  const rows: MemberRow[] = filteredMembers.flatMap((m): MemberRow[] => {
    if (!m.projects || m.projects.length === 0) return [{ kind: "workspace", member: m }]
    return m.projects.map((p) => ({
      kind: "project",
      member: m,
      projectName: p.name,
      projectRole: p.role,
    }))
  })

  const memberColumns: Array<DataTableColumn<MemberRow>> = [
    {
      key: "user",
      header: "User",
      cell: (row) => (
        <div className="flex items-center gap-3">
          <Avatar className="h-9 w-9">
            <AvatarFallback>{getInitials(row.member.name)}</AvatarFallback>
          </Avatar>
          <div className="min-w-0">
            <p className="truncate text-sm font-medium">{row.member.name}</p>
            <p className="truncate text-sm text-muted-foreground">{row.member.email}</p>
          </div>
        </div>
      ),
      className: "w-[45%]",
    },
    {
      key: "access",
      header: "Access Level",
      cell: (row) => (
        <Badge variant="secondary" className="whitespace-nowrap">
          {row.kind === "project" ? row.projectRole : row.member.roleName}
        </Badge>
      ),
      className: "w-[20%]",
    },
    {
      key: "project",
      header: "Project",
      cell: (row) =>
        row.kind === "project" ? (
          <Badge variant="outline" className="whitespace-nowrap">
            {row.projectName}
          </Badge>
        ) : (
          <span className="text-sm text-muted-foreground">No projects assigned</span>
        ),
      className: "w-[25%]",
    },
    {
      key: "actions",
      header: <div className="text-right">Actions</div>,
      cell: (row) => (
        <div className="flex justify-end">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" aria-label="Row actions">
                <MoreHorizontal className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => navigate(`/dashboard/members/edit/${row.member.userId}`)}>
                Manage
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      ),
      className: "w-[10%]",
    },
  ]

  const invitationColumns: Array<DataTableColumn<FullInvitationResponse>> = [
    {
      key: "user",
      header: "Invited Email",
      cell: (row) => (
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-primary/10 text-primary">
            <Mail className="h-4 w-4" />
          </div>
          <div className="min-w-0">
            <p className="truncate text-sm font-medium">{row.email}</p>
            <p className="truncate text-xs text-muted-foreground">
              Sent on {new Date(row.createdAt).toLocaleDateString()}
            </p>
          </div>
        </div>
      ),
      className: "w-[40%]",
    },
    {
      key: "status",
      header: "Status",
      cell: (row) => {
        const isExpired = new Date(row.expiresAt) < new Date() && row.status === "PENDING"
        let variant: "default" | "secondary" | "destructive" | "outline" = "secondary"
        if (row.status === "ACCEPTED") variant = "default"
        else if (row.status === "REVOKED") variant = "destructive"
        else if (isExpired) variant = "outline"
        
        return (
          <Badge variant={variant} className="whitespace-nowrap">
            {isExpired ? "EXPIRED" : row.status}
          </Badge>
        )
      },
      className: "w-[20%]",
    },
    {
      key: "role",
      header: "Role Context",
      cell: (row) => (
         <div className="flex flex-col">
           <span className="text-sm font-medium">{row.roleId}</span>
           <span className="text-xs text-muted-foreground">
              {row.projectId ? "Project-level" : "Workspace-level"}
           </span>
         </div>
      ),
      className: "w-[25%]",
    },
    {
      key: "actions",
      header: <div className="text-right">Actions</div>,
      cell: (row) => {
        const isPending = row.status === "PENDING"
        return (
          <div className="flex justify-end">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="icon" aria-label="Row actions" disabled={!isPending}>
                  <MoreHorizontal className="h-4 w-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onClick={() => handleResend(row.id)}>
                  <RotateCw className="mr-2 h-4 w-4" />
                  Resend Invite
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => handleRevoke(row.id)} className="text-destructive">
                  <XCircle className="mr-2 h-4 w-4" />
                  Revoke Invite
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        )
      },
      className: "w-[15%]",
    },
  ]

  if (membersLoading) {
    return (
      <div className="p-6 space-y-6">
        <PageHeaderSkeleton />
        <Card className="border-border/50">
          <CardHeader className="pb-2">
            <div className="space-y-2">
              <CardTitle className="text-sm font-medium">Members</CardTitle>
              <div className="h-4 w-64 rounded bg-muted" />
            </div>
            <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="h-10 w-full sm:max-w-sm rounded-md bg-muted" />
              <div className="h-10 w-64 rounded-md bg-muted" />
            </div>
          </CardHeader>
          <CardContent>
            <div className="rounded-lg border border-border/50 overflow-hidden">
              <TableSkeleton
                columns={[
                  { header: "User", widthClassName: "w-40" },
                  { header: "Access Level", widthClassName: "w-28" },
                  { header: "Project", widthClassName: "w-28" },
                  { header: "Actions", widthClassName: "w-12", align: "right" },
                ]}
                rowCount={6}
              />
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="space-y-6 p-6">
      <PageHeader
        title="Users & Access"
        description="Manage user access and roles within this organization."
        actions={
          <Button onClick={() => navigate("/dashboard/members/invite")}>
            <Plus className="h-4 w-4" />
            <span className="ml-2">Invite Member</span>
          </Button>
        }
      />

      <Tabs value={mainTab} onValueChange={setMainTab} className="space-y-6">
        <TabsList>
          <TabsTrigger value="members">Active Members</TabsTrigger>
          <TabsTrigger value="invitations">Pending Invitations</TabsTrigger>
        </TabsList>

        <TabsContent value="members">
          <SectionCard title="Members" description="Search, filter, and manage member access.">
            <div className="space-y-4">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="relative w-full sm:max-w-sm">
                  <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    placeholder="Search by name or email"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    className="pl-9"
                  />
                </div>

                <Tabs value={activeFilter} onValueChange={setActiveFilter}>
                  <TabsList>
                    {roleFilters.map((r) => (
                      <TabsTrigger key={r.value} value={r.value}>
                        {r.label}
                      </TabsTrigger>
                    ))}
                  </TabsList>
                </Tabs>
              </div>

              {rows.length === 0 ? (
                <EmptyState
                  title="No members found"
                  description="Try adjusting your search or filters."
                />
              ) : (
                <div className="animate-in fade-in duration-300">
                  <DataTable
                    columns={memberColumns}
                    data={rows}
                    getRowKey={(row) =>
                      row.kind === "project"
                        ? `${row.member.id}:${row.projectName}:${row.projectRole}`
                        : `${row.member.id}:workspace`
                    }
                    empty={
                      <div className="text-center text-sm text-muted-foreground">No members found.</div>
                    }
                  />
                </div>
              )}
            </div>
          </SectionCard>
        </TabsContent>

        <TabsContent value="invitations">
          <SectionCard title="Invitations" description="Manage invitations sent to join this workspace.">
            {invitationsLoading ? (
              <div className="rounded-lg border border-border/50 overflow-hidden">
                <TableSkeleton
                  columns={[
                    { header: "Invited Email", widthClassName: "w-40" },
                    { header: "Status", widthClassName: "w-28" },
                    { header: "Role Context", widthClassName: "w-28" },
                    { header: "Actions", widthClassName: "w-12", align: "right" },
                  ]}
                  rowCount={3}
                />
              </div>
            ) : invitations.length === 0 ? (
              <EmptyState
                title="No invitations found"
                description="There are no pending invitations for this workspace."
              />
            ) : (
              <div className="animate-in fade-in duration-300">
                <DataTable
                  columns={invitationColumns}
                  data={invitations}
                  getRowKey={(row) => row.id}
                  empty={
                    <div className="text-center text-sm text-muted-foreground">No invitations found.</div>
                  }
                />
              </div>
            )}
          </SectionCard>
        </TabsContent>
      </Tabs>
    </div>
  )
}

export default MembersPage
