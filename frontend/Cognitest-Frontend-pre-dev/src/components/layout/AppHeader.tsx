import { useLocation, useNavigate } from "react-router-dom"
import { LogOut, Menu, User as UserIcon } from "lucide-react"

import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { SidebarTrigger, useSidebar } from "@/components/ui/sidebar"
import { useAuth } from "@/context/AuthContext"

function getTitleFromPath(pathname: string): string {
  if (pathname === "/dashboard") return "Dashboard"
  if (pathname.startsWith("/dashboard/projects/new")) return "Create Project"
  if (pathname.startsWith("/dashboard/projects/")) return "Project Details"
  if (pathname.startsWith("/dashboard/reports")) return "Reports"
  if (pathname.startsWith("/dashboard/members")) return "Members"
  if (pathname.startsWith("/dashboard/roles")) return "Roles & Permissions"
  if (pathname.startsWith("/dashboard/plans")) return "Plans"
  if (pathname.startsWith("/dashboard/profile")) return "Profile"
  if (pathname.startsWith("/dashboard/settings")) return "Settings"
  if (pathname.startsWith("/dashboard/support")) return "Support"
  if (pathname.startsWith("/dashboard/docs")) return "Docs"
  return "Dashboard"
}

export default function AppHeader() {
  const location = useLocation()
  const navigate = useNavigate()
  const { user, workspace, logout } = useAuth()
  const { open } = useSidebar()

  const orgLabel =
    workspace?.name && workspace.name.trim() && workspace.name.trim().toLowerCase() !== "default workspace"
      ? workspace.name
      : user?.company || "Workspace"

  const initials = String(user?.displayName || user?.username || "U")
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase())
    .join("")

  return (
    <header className="sticky top-0 z-40 flex h-17 shrink-0 items-center justify-between border-b border-border/50 bg-background px-4">
      <div className="flex items-center gap-3">
        <SidebarTrigger aria-label="Toggle sidebar">
          <Menu className="h-4 w-4" />
        </SidebarTrigger>
        <div className="min-w-0">
          <p className="text-sm font-medium truncate">{getTitleFromPath(location.pathname)}</p>
          {open ? null : (
            <p className="text-sm text-muted-foreground truncate">
              {orgLabel}
            </p>
          )}
        </div>
      </div>

      <div className="flex items-center gap-3 min-w-0">
        <span className="hidden sm:inline text-sm font-medium truncate max-w-45 text-foreground">
          {orgLabel}
        </span>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" className="gap-2 min-w-0">
              <Avatar className="h-8 w-8">
                <AvatarFallback>{initials || "U"}</AvatarFallback>
              </Avatar>
              <span className="hidden sm:inline text-sm font-medium truncate max-w-45">
                {user?.displayName || user?.username || "User"}
              </span>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={() => navigate("/dashboard/profile")}>
              <UserIcon className="h-4 w-4" />
              <span>Profile</span>
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              onClick={() => {
                logout()
                navigate("/")
              }}
            >
              <LogOut className="h-4 w-4" />
              <span>Logout</span>
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  )
}
