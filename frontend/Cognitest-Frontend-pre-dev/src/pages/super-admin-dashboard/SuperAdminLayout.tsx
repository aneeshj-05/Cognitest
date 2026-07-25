import { useEffect, useCallback, useState } from "react"
import { NavLink, Outlet, useLocation, useNavigate, Link } from "react-router-dom"
import { useAuth } from "@/context/AuthContext"
import {
  getSuperAdminStats,
  getSuperAdminTenants,
  type SuperAdminStats,
  type SuperAdminTenant,
} from "@/services/backendClient"

// Icons
import {
  LayoutDashboard,
  Building2,
  Users,
  CreditCard,
  Server,
  HardDrive,
  LogOut,
  Search,
  Bell,
  Settings,
  Coins,
} from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"

// ─── Navigation Config ──────────────────────────────────────────────
type Page = "dashboard" | "tenants" | "users" | "billing" | "infrastructure" | "test-system" | "token-usage" | "profile"

interface NavItem {
  id: Page
  label: string
  icon: React.ComponentType<{ className?: string }>
  to: string
  end?: boolean
}

const NAV_ITEMS: NavItem[] = [
  { id: "dashboard", label: "Dashboard", icon: LayoutDashboard, to: "/super-admin-dashboard", end: true },
  { id: "tenants", label: "Tenants", icon: Building2, to: "/super-admin-dashboard/tenants" },
  { id: "users", label: "Users & Roles", icon: Users, to: "/super-admin-dashboard/users" },
  { id: "billing", label: "Billing", icon: CreditCard, to: "/super-admin-dashboard/billing" },
  { id: "infrastructure", label: "Infrastructure", icon: HardDrive, to: "/super-admin-dashboard/infrastructure" },
  { id: "test-system", label: "Test System", icon: Server, to: "/super-admin-dashboard/test-system" },
  { id: "token-usage", label: "Token Usage", icon: Coins, to: "/super-admin-dashboard/token-usage" },
]

const PAGE_TITLES: Record<Page, string> = {
  dashboard: "Dashboard Overview",
  tenants: "Tenant Management",
  users: "User & Role Management",
  billing: "Billing",
  infrastructure: "Infrastructure",
  "test-system": "Test System",
  "token-usage": "Token Usage Analytics",
  profile: "Account Profile",
}

export type SuperAdminLayoutOutletContext = {
  stats: SuperAdminStats | null
  tenants: SuperAdminTenant[]
  loading: boolean
  onRefresh: () => void
}

function getActivePageFromPathname(pathname: string): Page {
  const normalized = pathname.replace(/\/+$/, "")
  if (normalized === "/super-admin-dashboard") return "dashboard"

  const parts = normalized.split("/").filter(Boolean)
  const segment = parts[1]

  if (segment === "tenants") return "tenants"
  if (segment === "users") return "users"
  if (segment === "billing") return "billing"
  if (segment === "infrastructure") return "infrastructure"
  if (segment === "test-system") return "test-system"
  if (segment === "token-usage") return "token-usage"
  if (segment === "profile") return "profile"

  return "dashboard"
}

// ─── Component ──────────────────────────────────────────────────────
export default function SuperAdminLayout() {
  const location = useLocation()
  const navigate = useNavigate()
  const { user, logout } = useAuth()

  const [stats, setStats] = useState<SuperAdminStats | null>(null)
  const [tenants, setTenants] = useState<SuperAdminTenant[]>([])
  const [loading, setLoading] = useState(true)

  const fetchData = useCallback(async () => {
    try {
      const [statsData, tenantsData] = await Promise.all([
        getSuperAdminStats(),
        getSuperAdminTenants(),
      ])
      setStats(statsData)
      setTenants(tenantsData)
    } catch (err: any) {
      console.error("Failed to load super admin data:", err)
      alert("Failed to load dashboard data:\n" + (err.message || String(err)))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  const handleRefresh = () => {
    setLoading(true)
    fetchData()
  }

  const handleLogout = () => {
    logout()
    navigate("/")
  }

  const initials = String(user?.displayName || user?.username || "SA")
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map(p => p[0]?.toUpperCase())
    .join("")

  const activePage = getActivePageFromPathname(location.pathname)

  // ─── Render ───────────────────────────────────────────────────────
  return (
    <div className="flex h-screen w-full overflow-hidden bg-muted/30">
      {/* ── Sidebar ── */}
      <aside className="flex w-[260px] shrink-0 flex-col border-r border-border/30 bg-[#1a1f2e]">
        {/* Logo */}
        <div className="flex items-center gap-2.5 px-5 py-5">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-emerald-500 text-white font-bold text-sm">
            C
          </div>
          <span className="text-sm font-semibold text-white tracking-tight">Cognitest</span>
        </div>


        {/* Nav Items */}
        <nav className="flex-1 px-3 space-y-1">
          {NAV_ITEMS.map(item => {
            const Icon = item.icon
            return (
              <NavLink
                key={item.id}
                to={item.to}
                end={item.end}
                className={({ isActive }) => `
                  w-full flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all
                  ${isActive
                    ? "bg-emerald-500 text-white shadow-md shadow-emerald-500/25"
                    : "text-slate-400 hover:text-white hover:bg-white/5"
                  }
                `}
              >
                <Icon className="h-4 w-4 shrink-0" />
                <span className="truncate">{item.label}</span>
              </NavLink>
            )
          })}
        </nav>

        {/* Logout */}
        <div className="px-3 pb-5">
          <button
            onClick={handleLogout}
            className="w-full flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-red-400 hover:text-red-300 hover:bg-red-500/10 transition-all"
          >
            <LogOut className="h-4 w-4 shrink-0" />
            <span>Logout</span>
          </button>
        </div>
      </aside>

      {/* ── Main Area ── */}
      <div className="flex flex-1 flex-col min-w-0 overflow-hidden">
        {/* ── Header ── */}
        <header className="flex h-16 shrink-0 items-center justify-between border-b border-border/50 bg-background px-6">
          <h1 className="text-lg font-semibold text-foreground truncate">
            {PAGE_TITLES[activePage]}
          </h1>

          <div className="flex items-center gap-4">

            {/* Notification Bell */}
            <Button variant="ghost" size="icon" className="h-9 w-9 text-muted-foreground hover:text-foreground">
              <Bell className="h-4.5 w-4.5" />
            </Button>


            {/* User Profile */}
            <Link
              to="/super-admin-dashboard/profile"
              className="flex items-center gap-2.5 pl-2 border-l border-border/50 hover:opacity-80 transition-opacity cursor-pointer"
            >
              <Avatar className="h-9 w-9">
                <AvatarFallback className="bg-emerald-500 text-white text-xs font-semibold">
                  {initials || "SA"}
                </AvatarFallback>
              </Avatar>
              <div className="hidden sm:block">
                <p className="text-sm font-medium text-foreground leading-tight">
                  {user?.displayName || user?.username || "Super Admin"}
                </p>
                <p className="text-xs text-muted-foreground leading-tight">
                  {user?.email || "admin@cognitest.com"}
                </p>
              </div>
            </Link>
          </div>
        </header>

        {/* ── Content ── */}
        <main className="flex-1 overflow-y-auto p-6">
          <div className="mx-auto max-w-[1400px]">
            <Outlet
              context={{
                stats,
                tenants,
                loading,
                onRefresh: handleRefresh,
              } satisfies SuperAdminLayoutOutletContext}
            />
          </div>
        </main>
      </div>
    </div>
  )
}
