import React, { useEffect, useState } from "react"
import { useNavigate } from "react-router-dom"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
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
import { Activity, FolderOpenDot, Layers, TrendingUp, Search, Plus, Upload, Eye, Maximize2, Minimize2, Pencil, MoreHorizontal, Trash2 } from "lucide-react"
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
import { usePermissions } from "@/context/PermissionsContext"
import { useAuth } from "@/context/AuthContext"
import { cn } from "@/lib/utils"
import { Skeleton } from "@/components/ui/skeleton"

import StatCard from "@/components/shared/StatCard"
import EmptyState from "@/components/shared/EmptyState"
import { ActiveProjectsCardSkeleton } from "@/components/shared/LoadingSkeletons"

import { getDashboardStats, type DashboardStats, uploadProjectSpec, getProjectSpecs, type SpecInfo, getProjectSpecContent, updateProject, deleteProject } from "@/services/backendClient"


function DashboardStatCardSkeleton() {
  return (
    <Card className="transition-shadow hover:shadow-md">
      <CardHeader className="flex flex-row items-center justify-between">
        <Skeleton className="h-4 w-28 rounded-md" />
        <Skeleton className="h-8 w-8 rounded-md" />
      </CardHeader>
      <CardContent className="space-y-1">
        <Skeleton className="h-7 w-20 rounded-md" />
      </CardContent>
    </Card>
  )
}

function TestDistributionCardSkeleton() {
  return (
    <div className="flex flex-col justify-between rounded-xl border border-border/60 bg-card p-4 shadow-sm transition-shadow hover:shadow-md">
      <div className="mb-3 flex items-center justify-between">
        <Skeleton className="h-4 w-28 rounded-md" />
        <Skeleton className="h-4 w-4 rounded-md" />
      </div>
      <div className="flex flex-1 flex-col justify-end space-y-3">
        <Skeleton className="h-3 w-full rounded-full" />
        <div className="flex flex-wrap gap-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-3 w-16 rounded-md" />
          ))}
        </div>
      </div>
    </div>
  )
}



const DashboardPage = () => {
  const navigate = useNavigate()
  const { canUploadSwagger } = usePermissions()
  const { isAdmin } = useAuth()
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState("")
  const [activeProjectsPage, setActiveProjectsPage] = useState(1)
  const ACTIVE_PROJECTS_PER_PAGE = 5
  const [uploadingId, setUploadingId] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)
  const fileInputRef = React.useRef<HTMLInputElement>(null)

  const [viewingSpecProjectId, setViewingSpecProjectId] = useState<string | null>(null)
  const [specList, setSpecList] = useState<SpecInfo[]>([])
  const [specContent, setSpecContent] = useState<any>(null)
  const [loadingSpec, setLoadingSpec] = useState(false)
  const [isSpecMaximized, setIsSpecMaximized] = useState(false)

  // ── Edit project dialog state ──
  const [editingProject, setEditingProject] = useState<{ id: string; name: string; description: string } | null>(null)
  const [editName, setEditName] = useState("")
  const [editDescription, setEditDescription] = useState("")
  const [saving, setSaving] = useState(false)

  // ── Delete project dialog state ──
  const [deletingProject, setDeletingProject] = useState<{ id: string; name: string } | null>(null)
  const [confirmName, setConfirmName] = useState("")
  const [isDeleting, setIsDeleting] = useState(false)
  const [deleteError, setDeleteError] = useState("")

  useEffect(() => {
    let cancelled = false
    const fetchStats = async () => {
      try {
        const data = await getDashboardStats()
        if (!cancelled) setStats(data)
      } catch (err) {
        console.error("Failed to load dashboard stats:", err)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    fetchStats()
    return () => { cancelled = true }
  }, [])

  const handleEditProject = (project: { id: string; name: string; description?: string | null }) => {
    setEditingProject({ id: project.id, name: project.name, description: project.description || "" })
    setEditName(project.name)
    setEditDescription(project.description || "")
  }

  const handleSaveProject = async () => {
    if (!editingProject) return
    setSaving(true)
    try {
      await updateProject(editingProject.id, {
        name: editName.trim() || editingProject.name,
        description: editDescription.trim(),
      })
      const data = await getDashboardStats()
      setStats(data)
      setEditingProject(null)
    } catch (err) {
      console.error("Failed to update project:", err)
    } finally {
      setSaving(false)
    }
  }

  const handleDeleteProject = async () => {
    if (!deletingProject) return
    if (confirmName !== deletingProject.name) return

    setIsDeleting(true)
    setDeleteError("")
    try {
      await deleteProject(deletingProject.id)
      const data = await getDashboardStats()
      setStats(data)
      setDeletingProject(null)
      setConfirmName("")
    } catch (err: any) {
      console.error("Failed to delete project:", err)
      setDeleteError(err.message || "Failed to delete project")
    } finally {
      setIsDeleting(false)
    }
  }

  const handleActionUpload = (id: string) => {
    setUploadingId(id)
    fileInputRef.current?.click()
  }

  const handleUploadSpec = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file || !uploadingId) return
    setUploading(true)
    try {
      await uploadProjectSpec(uploadingId, file)
      const data = await getDashboardStats()
      setStats(data)
    } catch (err) {
      console.error("Upload failed:", err)
    } finally {
      setUploading(false)
      setUploadingId(null)
    }
  }

  const handleViewSpec = async (id: string) => {
    setViewingSpecProjectId(id)
    setLoadingSpec(true)
    setSpecContent(null)
    try {
      const specs = await getProjectSpecs(id)
      setSpecList(specs)
      if (specs.length > 0) {
        try {
          const data = await getProjectSpecContent(id, specs[0].id)
          setSpecContent(data)
        } catch (err) {
          setSpecContent({ error: "Failed to fetch content from server" })
        }
      }
    } catch (err) {
      console.error("View spec failed:", err)
    } finally {
      setLoadingSpec(false)
    }
  }

  const isDashboardLoading = loading && !stats

  const statCards = [
    {
      label: "Total Projects",
      value: stats?.totalProjects ?? 0,
      icon: FolderOpenDot,
    },
    {
      label: "Total Runs",
      value: stats?.totalTestRuns ?? 0,
      icon: Activity,
    },
    {
      label: "Total APIs Tested",
      value: stats?.totalApisTested ?? 0,
      icon: Layers,
    },
    {
      label: "Credits",
      value: "Unlimited",
      icon: TrendingUp,
    },
  ]

  const projects = stats?.activeProjects || []
  const filteredProjects = projects.filter(p =>
    p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    (p.description && p.description.toLowerCase().includes(searchQuery.toLowerCase()))
  )

  const totalActiveProjects = filteredProjects.length
  const totalActiveProjectsPages = Math.max(1, Math.ceil(totalActiveProjects / ACTIVE_PROJECTS_PER_PAGE))
  const activeProjectsPageStart = (activeProjectsPage - 1) * ACTIVE_PROJECTS_PER_PAGE
  const activeProjectsPageItems = filteredProjects.slice(
    activeProjectsPageStart,
    activeProjectsPageStart + ACTIVE_PROJECTS_PER_PAGE
  )

  const activeProjectsPagination = React.useMemo(() => {
    const total = totalActiveProjectsPages
    const current = activeProjectsPage
    const items: Array<number | "ellipsis"> = []

    if (total <= 7) {
      return Array.from({ length: total }, (_, i) => i + 1)
    }

    items.push(1)

    const start = Math.max(2, current - 1)
    const end = Math.min(total - 1, current + 1)

    if (start > 2) items.push("ellipsis")
    for (let p = start; p <= end; p++) items.push(p)
    if (end < total - 1) items.push("ellipsis")

    items.push(total)
    return items
  }, [activeProjectsPage, totalActiveProjectsPages])

  useEffect(() => {
    setActiveProjectsPage(1)
  }, [searchQuery, totalActiveProjects])

  useEffect(() => {
    if (activeProjectsPage > totalActiveProjectsPages) setActiveProjectsPage(totalActiveProjectsPages)
  }, [activeProjectsPage, totalActiveProjectsPages])

  const getStatusBadge = (status?: string | null): { label: "Completed" | "Running" | "Pending" | "Unknown"; variant: "default" | "secondary" | "destructive" | "outline" } => {
    const raw = String(status || "").trim()
    const normalized = raw.toUpperCase()
    if (!raw) return { label: "Unknown", variant: "outline" }
    if (normalized === "PENDING") return { label: "Pending", variant: "secondary" }
    if (normalized === "RUNNING") return { label: "Running", variant: "secondary" }
    if (normalized === "COMPLETED") return { label: "Completed", variant: "default" }
    return { label: "Unknown", variant: "outline" }
  }

  if (isDashboardLoading) {
    return (
      <div className="dashboard-container flex min-h-0 flex-col gap-6 p-6">
        {/* Stats Grid Skeleton - matching the actual grid dimensions */}
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-[1fr_1fr_1fr_1fr_2.2fr]">
          {Array.from({ length: 4 }).map((_, i) => (
            <DashboardStatCardSkeleton key={i} />
          ))}
          <TestDistributionCardSkeleton />
        </div>

        <ActiveProjectsCardSkeleton rows={ACTIVE_PROJECTS_PER_PAGE} />
      </div>
    )
  }

  return (
    <div className="dashboard-container flex min-h-0 flex-col gap-6 p-6">

      {/* Stats Grid — Using c2 dimensions/grid and c1 alignment strictly */}
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-[1fr_1fr_1fr_1fr_2.2fr]">
        {/* Cards 1-4 using the original c1 StatCard implementation */}
        {statCards.map((s) => (
          <StatCard
            key={s.label}
            title={s.label}
            value={s.value}
            icon={s.icon}
          />
        ))}

        {/* 5th card — Test Type Distribution (C1 Internal Structure inside C2 Grid) */}
        {(() => {
          const dist = stats?.testDistribution || {}
          const testTypes = [
            { key: "FUNCTIONAL", label: "Functional", count: Number(dist.FUNCTIONAL ?? 0), barClass: "bg-blue-500" },
            { key: "SECURITY", label: "Security", count: Number(dist.SECURITY ?? 0), barClass: "bg-red-500" },
            { key: "CONTRACT", label: "Contract", count: Number(dist.CONTRACT ?? 0), barClass: "bg-emerald-500" },
            { key: "NEGATIVE", label: "Negative", count: Number(dist.NEGATIVE ?? 0), barClass: "bg-orange-500" },
            { key: "FUZZ", label: "Fuzz", count: Number(dist.FUZZ ?? 0), barClass: "bg-purple-500" },
          ]

          const total = testTypes.reduce((sum, t) => sum + (Number.isFinite(t.count) ? t.count : 0), 0)

          return (
            <div className="relative overflow-hidden flex flex-col justify-between rounded-xl border border-border shadow-sm hover:shadow-md transition-shadow bg-muted/30 p-4 min-h-26">
              <div className="flex items-start justify-between gap-3">
                <p className="text-[10px] sm:text-[11px] font-medium text-muted-foreground">Test Distribution</p>
                <div className="h-8 w-8 rounded-lg flex items-center justify-center bg-muted/60 shrink-0 border border-border/60 text-foreground">
                  <Activity className="h-4 w-4" />
                </div>
              </div>
              <div className="flex flex-1 flex-col justify-end space-y-3">
                {/* Stacked bar */}
                <div className="flex h-3 w-full overflow-hidden rounded-full border border-border/40">
                  {testTypes.map((t) => (
                    <div
                      key={t.label}
                      className={`h-full transition-all duration-500 ${t.barClass}`}
                      style={{ width: total > 0 ? `${(t.count / total) * 100}%` : "0%" }}
                      title={`${t.label}: ${t.count}`}
                    />
                  ))}
                </div>

                {/* Legend */}
                <div className="flex flex-wrap items-center gap-x-2 gap-y-1 mt-auto">
                  {testTypes.map((t) => (
                    <span key={t.label} className="flex items-center gap-1 text-[10px] text-muted-foreground leading-none">
                      <span className={`inline-block h-1.5 w-1.5 shrink-0 rounded-full ${t.barClass}`} />
                      <span>{t.label} <span className="font-medium text-foreground">{t.count}</span></span>
                    </span>
                  ))}
                </div>
              </div>

              <div className="pointer-events-none absolute -right-6 -bottom-6 opacity-[0.06] text-foreground">
                <Activity className="h-24 w-24" />
              </div>
            </div>
          )
        })()}
      </div>

      {/* Active Projects */}
      <Card className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-xl border border-border/60 bg-card shadow-sm transition-shadow hover:shadow-md">
        <CardHeader className="flex flex-col gap-3 border-b border-border/50 p-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="space-y-1">
            <CardTitle className="text-lg font-medium">Active Projects</CardTitle>
            <p className="text-sm text-muted-foreground">Recently active projects in this workspace.</p>
          </div>
          <div className="flex w-full flex-col gap-3 sm:w-auto sm:flex-row sm:items-center">
            <div className="relative w-full sm:w-64">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search projects..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9"
              />
            </div>
            <Button className="w-full gap-2 sm:w-auto" onClick={() => navigate("/dashboard/projects/new")}>
              <Plus className="h-4 w-4" />
              Create Project
            </Button>
          </div>
        </CardHeader>

        <CardContent className="min-h-0 flex-1 overflow-y-auto bg-background p-0">
          {filteredProjects.length === 0 ? (
            <div className="py-4">
              <EmptyState
                title={searchQuery ? "No projects found" : "No projects yet"}
                description={searchQuery ? "Try a different search term" : "Create a project to get started"}
                icon={FolderOpenDot}
              />
            </div>
          ) : (
            <Table className="table-fixed w-full animate-in fade-in duration-300">
              <TableHeader className="sticky top-0 z-10 bg-muted/40">
                <TableRow>
                  <TableHead className="h-12 w-[80px] px-4 py-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">Sl No.</TableHead>
                  <TableHead className="h-12 w-[40%] px-4 py-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">Project</TableHead>
                  <TableHead className="h-12 w-[120px] px-4 py-2 text-xs font-medium uppercase tracking-wide text-muted-foreground text-center">Runs</TableHead>
                  <TableHead className="h-12 w-[140px] px-4 py-2 text-xs font-medium uppercase tracking-wide text-muted-foreground text-center">Status</TableHead>
                  <TableHead className="h-12 w-[140px] px-4 py-2 text-xs font-medium uppercase tracking-wide text-muted-foreground text-center">API Version</TableHead>
                  <TableHead className="h-12 w-[100px] px-4 py-2 text-xs font-medium uppercase tracking-wide text-muted-foreground text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody className="divide-y divide-border/50">
                {activeProjectsPageItems.map((project, idx) => (
                  <TableRow
                    key={project.id}
                    className="h-12 cursor-pointer hover:bg-muted/40"
                    onClick={() => navigate(`/dashboard/projects/${project.id}`, { state: { project } })}
                  >
                    <TableCell className="px-4 py-2 text-sm text-foreground text-center">{activeProjectsPageStart + idx + 1}</TableCell>
                    <TableCell className="px-4 py-2">
                      <div className="flex flex-col min-w-0">
                        <span className="truncate font-medium text-foreground" title={project.name}>
                          {project.name}
                        </span>
                        <span className="truncate text-sm text-muted-foreground" title={project.description || "Auto-generated project"}>
                          {project.description || "Auto-generated project"}
                        </span>
                      </div>
                    </TableCell>
                    <TableCell className="px-4 py-2 text-sm font-medium tabular-nums text-foreground text-center">{project.totalRuns ?? 0}</TableCell>
                    <TableCell className="px-4 py-2 text-center">
                      {(() => {
                        const badge = getStatusBadge(project.lastRunStatus)
                        return (
                          <Badge variant={badge.variant} className="capitalize">
                            {badge.label}
                          </Badge>
                        )
                      })()}
                    </TableCell>
                    <TableCell className="px-4 py-2 text-sm font-medium text-foreground text-center">{project.apiVersion || "—"}</TableCell>
                    <TableCell className="px-4 py-2">
                      <div className="flex justify-end">
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button variant="ghost" size="icon" aria-label="Row actions" onClick={(e) => e.stopPropagation()}>
                              <MoreHorizontal className="h-4 w-4" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem
                              onClick={(e) => {
                                e.stopPropagation()
                                handleViewSpec(project.id)
                              }}
                            >
                              <Eye className="mr-2 h-4 w-4" />
                              View
                            </DropdownMenuItem>
                            {isAdmin && (
                              <>
                                <DropdownMenuItem
                                  onClick={(e) => {
                                    e.stopPropagation()
                                    handleEditProject(project)
                                  }}
                                >
                                  <Pencil className="mr-2 h-4 w-4" />
                                  Edit
                                </DropdownMenuItem>
                                <DropdownMenuItem
                                  className="text-destructive focus:text-destructive focus:bg-destructive/10"
                                  onClick={(e) => {
                                    e.stopPropagation()
                                    setDeletingProject({ id: project.id, name: project.name })
                                    setConfirmName("")
                                    setDeleteError("")
                                  }}
                                >
                                  <Trash2 className="mr-2 h-4 w-4" />
                                  Delete
                                </DropdownMenuItem>
                              </>
                            )}
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}

                {Array.from({ length: Math.max(0, ACTIVE_PROJECTS_PER_PAGE - activeProjectsPageItems.length) }).map((_, i) => (
                  <TableRow key={`pad-${i}`} className="h-12 hover:bg-transparent">
                    <TableCell className="px-4 py-2 text-center">&nbsp;</TableCell>
                    <TableCell className="px-4 py-2">&nbsp;</TableCell>
                    <TableCell className="px-4 py-2 text-center">&nbsp;</TableCell>
                    <TableCell className="px-4 py-2 text-center">&nbsp;</TableCell>
                    <TableCell className="px-4 py-2 text-center">&nbsp;</TableCell>
                    <TableCell className="px-4 py-2">&nbsp;</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>

        {filteredProjects.length > 0 ? (
          <div className="flex items-center justify-between border-t border-border/50 bg-card px-4 py-3 text-xs">
            <p className="text-muted-foreground">
              Showing <span className="font-medium text-foreground">{activeProjectsPageStart + 1}</span> to{" "}
              <span className="font-medium text-foreground">
                {Math.min(activeProjectsPageStart + ACTIVE_PROJECTS_PER_PAGE, totalActiveProjects)}
              </span>{" "}
              of <span className="font-medium text-foreground">{totalActiveProjects}</span> projects
            </p>

            <div className="flex items-center gap-1.5">
              <Button
                variant="outline"
                size="sm"
                className="h-8"
                disabled={activeProjectsPage === 1}
                onClick={() => setActiveProjectsPage((p) => Math.max(1, p - 1))}
              >
                Previous
              </Button>

              {activeProjectsPagination.map((item, idx) =>
                item === "ellipsis" ? (
                  <div key={`ellipsis-${idx}`} className="px-2 text-muted-foreground">
                    …
                  </div>
                ) : (
                  <Button
                    key={item}
                    variant="outline"
                    size="sm"
                    className={cn(
                      "h-8 w-8 px-0",
                      activeProjectsPage === item && "bg-primary/10 text-primary border-primary/20 hover:bg-primary/10"
                    )}
                    onClick={() => setActiveProjectsPage(item)}
                  >
                    {item}
                  </Button>
                )
              )}

              <Button
                variant="outline"
                size="sm"
                className="h-8"
                disabled={activeProjectsPage === totalActiveProjectsPages}
                onClick={() => setActiveProjectsPage((p) => Math.min(totalActiveProjectsPages, p + 1))}
              >
                Next
              </Button>
            </div>
          </div>
        ) : null}
      </Card>
      <input
        type="file"
        ref={fileInputRef}
        accept=".json,.yaml,.yml"
        className="hidden"
        onChange={handleUploadSpec}
      />

      {/* View Spec Dialog */}
      <Dialog
        open={Boolean(viewingSpecProjectId)}
        onOpenChange={(v) => {
          if (!v) {
            setViewingSpecProjectId(null)
            setIsSpecMaximized(false)
          }
        }}
      >
        <DialogContent
          className={`flex flex-col transition-all duration-200 ${isSpecMaximized
            ? "max-w-[95vw]! w-[95vw]! max-h-[95vh]! h-[95vh]!"
            : "sm:max-w-2xl max-h-[80vh]"
            }`}
        >
          <DialogHeader className="shrink-0">
            <DialogTitle className="flex items-center justify-between gap-2">
              <span className="flex items-center gap-2">
                <Eye className="h-5 w-5 text-muted-foreground" />
                Swagger Specification
              </span>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                onClick={() => setIsSpecMaximized((v) => !v)}
                className="ml-auto mr-6 h-7 w-7 text-muted-foreground hover:bg-accent hover:text-foreground"
                title={isSpecMaximized ? "Restore" : "Maximize"}
                aria-label={isSpecMaximized ? "Restore" : "Maximize"}
              >
                {isSpecMaximized ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
              </Button>
            </DialogTitle>
          </DialogHeader>

          <div className="min-h-0 flex-1 overflow-y-auto rounded-lg border border-border bg-muted/30 font-mono text-xs">
            {loadingSpec ? (
              <div className="p-4 space-y-2">
                <Skeleton className="h-3 w-56" />
                <Skeleton className="h-3 w-[90%]" />
                <Skeleton className="h-3 w-[84%]" />
                <Skeleton className="h-3 w-[88%]" />
                <Skeleton className="h-3 w-[70%]" />
              </div>
            ) : specContent ? (
              specContent.error ? (
                <p className="p-4 font-sans text-destructive">{specContent.error}</p>
              ) : (
                <pre className="whitespace-pre-wrap p-4 leading-relaxed text-foreground animate-in fade-in duration-300">{JSON.stringify(specContent, null, 2)}</pre>
              )
            ) : (
              <p className="py-10 text-center font-sans italic text-muted-foreground">No specification file loaded or empty</p>
            )}
          </div>

          {/* Only show Replace Swagger if user has upload permission */}
          <div className="mt-4 shrink-0 flex items-center justify-between">
            <div className="text-xs text-muted-foreground flex items-center gap-1.5 overflow-hidden">
              <span className="font-medium shrink-0">Base URL:</span>
              <span className="font-mono bg-muted px-1.5 py-0.5 rounded border border-border truncate cursor-help" title={specContent?.servers?.[0]?.url || specContent?.host || "Not specified"}>
                {specContent?.servers?.[0]?.url || specContent?.host || "Not specified"}
              </span>
            </div>
            {canUploadSwagger && (
              <Button
                variant="outline"
                className="gap-2 text-xs shrink-0"
                onClick={() => {
                  const id = viewingSpecProjectId
                  setViewingSpecProjectId(null)
                  setIsSpecMaximized(false)
                  if (id) handleActionUpload(id)
                }}
              >
                <Upload className="h-3.5 w-3.5" /> Replace Swagger
              </Button>
            )}
          </div>
        </DialogContent>
      </Dialog>

      {/* Edit Project Dialog */}
      <Dialog
        open={Boolean(editingProject)}
        onOpenChange={(v) => {
          if (!v) setEditingProject(null)
        }}
      >
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Pencil className="h-5 w-5 text-muted-foreground" />
              Edit Project
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-4 mt-2">
            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">Project Name</label>
              <Input
                placeholder="Project name"
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
                autoFocus
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && editName.trim() && !saving) {
                    handleSaveProject()
                  }
                }}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">Description</label>
              <textarea
                value={editDescription}
                onChange={(e) => setEditDescription(e.target.value)}
                placeholder="Project description (optional)"
                rows={3}
                className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 resize-none"
              />
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <Button
                variant="outline"
                className="h-9 text-xs"
                onClick={() => setEditingProject(null)}
                disabled={saving}
              >
                Cancel
              </Button>
              <Button
                className="h-9 text-xs"
                onClick={handleSaveProject}
                disabled={saving || !editName.trim()}
              >
                {saving ? "Saving..." : "Save Changes"}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
      {/* Delete Project Dialog */}
      <Dialog
        open={Boolean(deletingProject)}
        onOpenChange={(v) => {
          if (!v) {
            setDeletingProject(null)
            setConfirmName("")
            setDeleteError("")
          }
        }}
      >
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-destructive">
              <Trash2 className="h-5 w-5" />
              Delete Project
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-4 mt-2">
            <div className="space-y-2">
              <p className="text-sm text-muted-foreground">
                This action cannot be undone. This will permanently delete the <span className="font-semibold text-foreground">{deletingProject?.name}</span> project and all its data.
              </p>
              <label className="text-[11px] font-bold text-slate-500 uppercase tracking-widest block ml-0.5 mt-4">
                Verify by typing project name
              </label>
              <Input
                placeholder="Confirm project name"
                value={confirmName}
                onChange={(e) => setConfirmName(e.target.value)}
                className="h-10 rounded-lg border-slate-200 focus:ring-red-500 font-semibold"
                autoFocus
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && confirmName === deletingProject?.name && !isDeleting) {
                    handleDeleteProject()
                  }
                }}
              />
            </div>

            {deleteError && (
              <p className="text-sm font-medium text-destructive">{deleteError}</p>
            )}

            <div className="flex justify-end gap-2 pt-4">
              <Button
                variant="outline"
                className="h-9 text-xs"
                onClick={() => {
                  setDeletingProject(null)
                  setConfirmName("")
                  setDeleteError("")
                }}
                disabled={isDeleting}
              >
                Cancel
              </Button>
              <Button
                variant="destructive"
                className="h-9 text-xs"
                onClick={handleDeleteProject}
                disabled={isDeleting || confirmName !== deletingProject?.name}
              >
                {isDeleting ? "Deleting..." : "Delete Project"}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}

export default DashboardPage