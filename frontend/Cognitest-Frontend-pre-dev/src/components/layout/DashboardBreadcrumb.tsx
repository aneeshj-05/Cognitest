import * as React from "react"
import { Link, useLocation } from "react-router-dom"
import { LayoutDashboard } from "lucide-react"

import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb"
import { getProjectMeta } from "@/services/backendClient"

type Crumb = {
  label: string
  href?: string
  isCurrent?: boolean
  icon?: React.ReactNode
}

const LABELS: Record<string, string> = {
  dashboard: "Dashboard",

  // Common sections
  projects: "Projects",
  project: "Project",
  workspace: "Workspace",
  workspaces: "Workspaces",

  roles: "Roles",
  rbac: "Roles",
  permissions: "Permissions",

  reports: "Reports",
  analytics: "Analytics",

  account: "Account",
  profile: "Profile",
  plans: "Plans",
  subscription: "Subscription",
  billing: "Billing",

  settings: "Settings",
  members: "Members",
  users: "Users",

  tests: "Tests",
  test: "Test",
  runs: "Runs",
  run: "Run",

  new: "New",
  create: "Create",
  edit: "Edit",

}

function titleize(segment: string): string {
  const cleaned = segment.replace(/[-_]+/g, " ").trim()
  if (!cleaned) return ""
  return cleaned
    .split(" ")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ")
}

function looksLikeId(segment: string): boolean {
  // UUID (v4-ish) or numeric IDs
  if (/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(segment)) {
    return true
  }
  if (/^\d+$/.test(segment)) return true
  // Prisma/cuid-ish
  if (/^c[a-z0-9]{20,}$/i.test(segment)) return true
  return false
}

function segmentLabel(segment: string, previous?: string): string {
  const normalized = segment.toLowerCase()

  if (LABELS[normalized]) return LABELS[normalized]

  if (looksLikeId(normalized)) {
    // Never echo the previous plural label (prevents "Projects > Projects").
    if (previous === "projects") return "Project"
    if (previous && LABELS[previous]) return LABELS[previous]
    return "Details"
  }

  return titleize(segment)
}

export default function DashboardBreadcrumb() {
  const location = useLocation()

  const rawSegments = React.useMemo(() => location.pathname.split("/").filter(Boolean), [location.pathname])
  const dashboardIndex = React.useMemo(() => rawSegments.indexOf("dashboard"), [rawSegments])
  const afterDashboard = React.useMemo(
    () => (dashboardIndex >= 0 ? rawSegments.slice(dashboardIndex + 1) : rawSegments),
    [dashboardIndex, rawSegments]
  )

  const projectId = React.useMemo(() => {
    if (afterDashboard[0] !== "projects") return null
    const id = afterDashboard[1]
    if (!id || id === "new") return null
    return id
  }, [afterDashboard])

  const projectNameFromState = React.useMemo(() => {
    const stateAny = location.state as any
    const fromState = stateAny?.project?.name
    return typeof fromState === "string" && fromState.trim() ? fromState.trim() : null
  }, [location.state])

  const [projectName, setProjectName] = React.useState<string | null>(projectNameFromState)

  React.useEffect(() => {
    let cancelled = false

    async function load() {
      if (!projectId) {
        setProjectName(projectNameFromState)
        return
      }
      if (projectNameFromState) {
        setProjectName(projectNameFromState)
        return
      }

      try {
        const meta = await getProjectMeta(projectId)
        if (!cancelled) setProjectName(meta?.name || "Project")
      } catch {
        if (!cancelled) setProjectName("Project")
      }
    }

    load()
    return () => {
      cancelled = true
    }
  }, [projectId, projectNameFromState])

  const crumbs = React.useMemo<Crumb[]>(() => {
    const searchParams = new URLSearchParams(location.search)
    const categoryParam = searchParams.get("category")

    const items: Crumb[] = []

    // 1) Icon-only dashboard crumb
    items.push({
      label: "",
      href: "/dashboard",
      icon: <LayoutDashboard className="h-4 w-4" aria-hidden="true" />,
    })

    // 2) Dashboard text crumb
    items.push({ label: "Dashboard", href: "/dashboard" })

    // 3) Route-derived crumbs
    if (afterDashboard.length > 0) {
      // Special-case /dashboard/projects/... so we can inject project name
      if (afterDashboard[0] === "projects") {
        items.push({ label: "Projects" })

        const projectSeg = afterDashboard[1]
        if (projectSeg) {
          if (projectSeg === "new") {
            items.push({ label: "Create Project", href: "/dashboard/projects/new" })
          } else {
            items.push({
              label: projectName || "Project",
              href: `/dashboard/projects/${projectSeg}`,
            })
          }
        }

        const rest = afterDashboard.slice(2)
        rest.forEach((segment, i) => {
          const previous = (i === 0 ? afterDashboard[1] : rest[i - 1])?.toLowerCase()
          const href = "/dashboard/projects/" + [afterDashboard[1], ...rest.slice(0, i + 1)].join("/")
          const normalized = segment.toLowerCase()

          let label = segmentLabel(segment, previous)
          if (normalized === "ter") {
            label = categoryParam ? titleize(categoryParam) : "Contract"
          }

          items.push({ label, href })
        })
      } else {
        afterDashboard.forEach((segment, i) => {
          const previous = i === 0 ? "dashboard" : afterDashboard[i - 1]?.toLowerCase()
          const href = "/dashboard/" + afterDashboard.slice(0, i + 1).join("/")
          const normalized = segment.toLowerCase()

          let label = segmentLabel(segment, previous)
          if (normalized === "ter") {
            label = categoryParam ? titleize(categoryParam) : "Contract"
          }

          items.push({ label, href })
        })
      }
    }

    // Remove consecutive duplicates (label or href)
    const deduped: Crumb[] = []
    for (const item of items) {
      const prev = deduped[deduped.length - 1]
      if (prev && prev.label === item.label && prev.href === item.href && !item.icon) continue
      deduped.push(item)
    }

    // Mark current page as the last crumb
    deduped.forEach((item) => {
      item.isCurrent = false
    })
    const last = deduped[deduped.length - 1]
    if (last) {
      last.isCurrent = true
      // Keep icon crumb always linkable
      if (!last.icon) delete last.href
    }

    // If we're exactly at /dashboard, make the Dashboard text crumb current.
    if (afterDashboard.length === 0) {
      return [
        deduped[0],
        { label: "Dashboard", isCurrent: true },
      ]
    }

    return deduped
  }, [afterDashboard, location.search, projectName, location.state])

  return (
    <div className="sticky top-0 z-20 bg-muted/20 px-6 pt-4 backdrop-blur-xl border-b border-border/50">
      <Breadcrumb>
        <BreadcrumbList className="gap-2">
          {crumbs.map((c, idx) => {
            const isLast = idx === crumbs.length - 1

            return (
              <React.Fragment key={`${c.label}-${idx}`}>
                <BreadcrumbItem>
                  {c.icon ? (
                    <BreadcrumbLink asChild className="text-muted-foreground transition-colors duration-200 hover:text-foreground">
                      <Link to={c.href || "/dashboard"} aria-label="Dashboard">
                        {c.icon}
                      </Link>
                    </BreadcrumbLink>
                  ) : c.isCurrent ? (
                    <BreadcrumbPage>{c.label}</BreadcrumbPage>
                  ) : c.href ? (
                    <BreadcrumbLink asChild className="text-muted-foreground transition-colors duration-200 hover:text-foreground">
                      <Link to={c.href}>{c.label}</Link>
                    </BreadcrumbLink>
                  ) : (
                    <BreadcrumbLink asChild className="text-muted-foreground">
                      <span>{c.label}</span>
                    </BreadcrumbLink>
                  )}
                </BreadcrumbItem>

                {!isLast ? <BreadcrumbSeparator /> : null}
              </React.Fragment>
            )
          })}
        </BreadcrumbList>
      </Breadcrumb>
    </div>
  )
}
