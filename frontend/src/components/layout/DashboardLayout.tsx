import { useState } from "react"
import { Navigate, Outlet } from "react-router-dom"

import { useAuth } from "@/context/AuthContext"
import AppHeader from "@/components/layout/AppHeader"
import AppSidebar from "@/components/layout/AppSidebar"
import DashboardBreadcrumb from "@/components/layout/DashboardBreadcrumb"
import { SidebarInset, SidebarProvider, useSidebar } from "@/components/ui/sidebar"
import MiniPostman from "@/components/api-tester/MiniPostman"

function DashboardShell() {
  const { openMobile, setOpenMobile, isMobile } = useSidebar()
  const [postmanOpen, setPostmanOpen] = useState(false)

  return (
    <div className="flex h-screen min-h-screen min-w-0 overflow-hidden bg-muted/30">
      {isMobile && openMobile ? (
        <button
          type="button"
          aria-label="Close sidebar"
          onClick={() => setOpenMobile(false)}
          className="fixed inset-0 z-40 bg-background/80"
        />
      ) : null}

      <AppSidebar />

      <SidebarInset>
        <AppHeader />
        <main className="flex flex-1 min-h-0 min-w-0 flex-col overflow-y-auto bg-muted/30">
          <DashboardBreadcrumb />
          <Outlet />
        </main>
      </SidebarInset>

      {/* Pull tab */}
      {!postmanOpen && (
        <button
          onClick={() => setPostmanOpen(true)}
          className="fixed right-0 top-1/2 -translate-y-1/2 z-50 flex items-center gap-1.5 bg-emerald-500 hover:bg-emerald-600 text-white text-xs font-semibold px-2 py-3 rounded-l-lg shadow-lg transition-colors cursor-pointer"
          style={{ writingMode: "vertical-rl", textOrientation: "mixed" }}
        >
          <span className="rotate-180 tracking-wide">API Tester</span>
        </button>
      )}

      {/* Sliding panel */}
      <div
        className={`fixed top-0 right-0 h-full w-[580px] max-w-[95vw] z-50 shadow-2xl transition-transform duration-300 ease-in-out ${
          postmanOpen ? "translate-x-0" : "translate-x-full"
        }`}
      >
        <MiniPostman onClose={() => setPostmanOpen(false)} />
      </div>

      {/* Backdrop */}
      {postmanOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm"
          onClick={() => setPostmanOpen(false)}
        />
      )}
    </div>
  )
}

const DashboardLayout = () => {
  const { user } = useAuth()

  if (!user) {
    return <Navigate to="/login" replace />
  }

  return (
    <SidebarProvider>
      <DashboardShell />
    </SidebarProvider>
  )
}

export default DashboardLayout
