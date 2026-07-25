import { useEffect, useState } from "react"
import { NavLink, useLocation, useNavigate } from "react-router-dom"
import {
  LayoutDashboard,
  Settings,
  LifeBuoy,
  CreditCard,
  ChevronDown,
  Users,
  Shield,
  LogOut,
  PanelLeftClose,
} from "lucide-react"

import { useAuth } from "@/context/AuthContext"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar"
import { Button } from "@/components/ui/button"

type NavItem = {
  title: string
  to: string
  icon: React.ComponentType<{ className?: string }>
  adminOnly?: boolean
}

const NAV_TOP: NavItem[] = [{ title: "Dashboard", to: "/dashboard", icon: LayoutDashboard }]

const NAV_BOTTOM: NavItem[] = [{ title: "Support", to: "/dashboard/support", icon: LifeBuoy }]

const NAV_SETTINGS_SUB: NavItem[] = [
  { title: "General", to: "/dashboard/settings", icon: Settings },
  { title: "Members", to: "/dashboard/members", icon: Users, adminOnly: true },
  { title: "Roles & Permissions", to: "/dashboard/roles", icon: Shield, adminOnly: true },
  { title: "Subscription Plans", to: "/dashboard/plans", icon: CreditCard, adminOnly: true },
]

export default function AppSidebar() {
  const location = useLocation()
  const navigate = useNavigate()
  const { isAdmin, logout } = useAuth()
  const { open, setOpen, isMobile, setOpenMobile } = useSidebar()

  const isSettingsRoute =
    location.pathname.startsWith("/dashboard/settings") ||
    location.pathname.startsWith("/dashboard/members") ||
    location.pathname.startsWith("/dashboard/roles") ||
    location.pathname.startsWith("/dashboard/plans")

  const [settingsOpen, setSettingsOpen] = useState(isSettingsRoute)

  useEffect(() => {
    // Keep the accordion open when navigating within settings routes.
    if (isSettingsRoute) setSettingsOpen(true)
  }, [isSettingsRoute])

  const handleLogout = async () => {
    logout()
    navigate("/")
  }

  const renderItem = (item: NavItem) => {
    if (item.adminOnly && !isAdmin) return null

    const Icon = item.icon
    const isActive =
      item.to === "/dashboard"
        ? location.pathname === "/dashboard"
        : location.pathname.startsWith(item.to)

    return (
      <SidebarMenuItem key={item.to}>
        <SidebarMenuButton
          asChild
          isActive={isActive}
          className={
            (open ? "" : "justify-center px-0") +
            " data-[active=true]:bg-sidebar-accent data-[active=true]:text-sidebar-primary data-[active=true]:shadow-sm"
          }
        >
          <NavLink
            to={item.to}
            onClick={() => {
              if (isMobile) setOpenMobile(false)
            }}
          >
            <span
              className={
                "p-1.5 rounded-md border border-sidebar-border/60 " +
                (isActive
                  ? "bg-sidebar-primary/20 text-sidebar-primary"
                  : "bg-sidebar-accent/40 text-sidebar-foreground/70")
              }
            >
              <Icon className="h-4 w-4" />
            </span>
            {open ? <span className="truncate">{item.title}</span> : null}
          </NavLink>
        </SidebarMenuButton>
      </SidebarMenuItem>
    )
  }

  return (
    <Sidebar>
      <SidebarHeader>
        {open ? (
          <div className="flex w-full items-center justify-between gap-2">
            <NavLink to="/dashboard" className="flex min-w-0 items-center gap-2">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-sidebar-primary text-sidebar-primary-foreground">
                <span className="text-sm font-semibold">C</span>
              </div>
              <span className="truncate text-sm font-semibold text-sidebar-foreground">Cognitest</span>
            </NavLink>

            {!isMobile ? (
              <Button
                variant="ghost"
                size="icon"
                className="shrink-0 text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
                onClick={() => setOpen(false)}
                aria-label="Collapse sidebar"
              >
                <PanelLeftClose className="h-4 w-4" />
              </Button>
            ) : null}
          </div>
        ) : (
          <div className="flex w-full items-center justify-center">
            {!isMobile ? (
              <NavLink
                to="/dashboard"
                aria-label="Expand sidebar"
                className="flex"
                onClick={() => setOpen(true)}
              >
                <div className="flex h-8 w-8 items-center justify-center rounded-md bg-sidebar-primary text-sidebar-primary-foreground">
                  <span className="text-sm font-semibold">C</span>
                </div>
              </NavLink>
            ) : null}
          </div>
        )}
      </SidebarHeader>

      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupContent>
            <SidebarMenu>
              {NAV_TOP.map(renderItem)}
              {NAV_BOTTOM.map(renderItem)}

              <SidebarMenuItem>
                <SidebarMenuButton
                  onClick={() => setSettingsOpen((v) => !v)}
                  isActive={isSettingsRoute}
                  className={
                    (open ? "" : "justify-center px-0") +
                    " data-[active=true]:bg-sidebar-accent data-[active=true]:text-sidebar-primary data-[active=true]:shadow-sm"
                  }
                >
                  <span
                    className={
                      "p-1.5 rounded-md border border-sidebar-border/60 " +
                      (isSettingsRoute
                        ? "bg-sidebar-primary/20 text-sidebar-primary"
                        : "bg-sidebar-accent/40 text-sidebar-foreground/70")
                    }
                  >
                    <Settings className="h-4 w-4" />
                  </span>
                  {open ? <span className="truncate">Settings</span> : null}
                  {open ? (
                    <ChevronDown
                      className={
                        "ml-auto h-4 w-4 transition-transform " +
                        (settingsOpen ? "rotate-180" : "rotate-0")
                      }
                    />
                  ) : null}
                </SidebarMenuButton>
              </SidebarMenuItem>

              {open && settingsOpen ? (
                <div className="ml-6 border-l border-sidebar-border pl-2">
                  <SidebarMenu className="gap-1">
                    {NAV_SETTINGS_SUB.map((item) => {
                      if (item.adminOnly && !isAdmin) return null
                      const isActive = location.pathname.startsWith(item.to)

                      return (
                        <SidebarMenuItem key={item.to}>
                          <SidebarMenuButton
                            asChild
                            isActive={isActive}
                            className="py-1.5 data-[active=true]:bg-sidebar-accent data-[active=true]:text-sidebar-primary data-[active=true]:font-medium"
                          >
                            <NavLink
                              to={item.to}
                              onClick={() => {
                                if (isMobile) setOpenMobile(false)
                              }}
                            >
                              <span className="truncate">{item.title}</span>
                            </NavLink>
                          </SidebarMenuButton>
                        </SidebarMenuItem>
                      )
                    })}
                  </SidebarMenu>
                </div>
              ) : null}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton
              onClick={handleLogout}
              className={
                "text-red-400 hover:bg-red-500/10 hover:text-red-400 " +
                (open ? "text-[13px] font-medium" : "justify-center px-0")
              }
            >
              <LogOut className="h-4 w-4" />
              {open ? <span>Logout</span> : null}
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
    </Sidebar>
  )
}