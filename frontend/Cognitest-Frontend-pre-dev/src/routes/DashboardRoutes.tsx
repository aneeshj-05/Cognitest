import { lazy, Suspense, type ReactNode } from "react"
import { Navigate, Route } from "react-router-dom"
import DashboardLayout from "@/components/layout/DashboardLayout"
import AdminRoute from "@/components/layout/AdminRoute"
import SuperAdminRoute from "@/components/layout/SuperAdminRoute"

const DashboardPage = lazy(() => import("@/pages/dashboard/DashboardPage"))
const NewProjectPage = lazy(() => import("@/pages/dashboard/projects/NewProjectPage"))
const ProjectDetailPage = lazy(() => import("@/pages/dashboard/projects/ProjectDetailPageNew"))
const MembersPage = lazy(() => import("@/pages/dashboard/members/MembersPage"))
const EditUserAccessPage = lazy(() => import("@/pages/dashboard/members/EditUserAccessPage"))
const InviteMemberPage = lazy(() => import("@/pages/dashboard/members/InviteMemberPage"))
const SettingsPage = lazy(() => import("@/pages/dashboard/account/SettingsPage"))
const ProfilePage = lazy(() => import("@/pages/dashboard/account/ProfilePage"))
const PlansPage = lazy(() => import("@/pages/dashboard/account/PlansPage"))
const SupportPage = lazy(() => import("@/pages/dashboard/account/SupportPage"))
const RolesPage = lazy(() => import("@/pages/dashboard/roles/RolesPage"))
const DocsPage = lazy(() => import("@/pages/public/DocsPage"))
const SuperAdmin = lazy(() => import("@/pages/super-admin-dashboard/SuperAdmin"))
const SuperAdminDashboardHome = lazy(() => import("@/pages/super-admin-dashboard/SuperAdminDashboardHome"))
const SuperAdminTenantsPage = lazy(() => import("@/pages/super-admin-dashboard/TenantsPage"))
const SuperAdminUsersRolesPage = lazy(() => import("@/pages/super-admin-dashboard/UsersRolesPage"))
const SuperAdminBillingPage = lazy(() => import("@/pages/super-admin-dashboard/BillingPage"))
const SuperAdminInfrastructurePage = lazy(() => import("@/pages/super-admin-dashboard/InfrastructurePage"))
const SuperAdminTestSystemPage = lazy(() => import("@/pages/super-admin-dashboard/TestSystemPage"))
const SuperAdminTokenUsagePage = lazy(() => import("@/pages/super-admin-dashboard/TokenUsagePage"))
const SuperAdminProfilePage = lazy(() => import("@/pages/super-admin-dashboard/SuperAdminProfile"))

const withSuspense = (element: ReactNode) => (
  <Suspense fallback={<div className="p-6 text-sm text-muted-foreground">Loading...</div>}>
    {element}
  </Suspense>
)

const dashboardRoutes = [
  (
    <Route path="dashboard" element={<DashboardLayout />} key="dashboard-shell">
      <Route index element={withSuspense(<DashboardPage />)} />
      {/* Projects */}
      <Route path="projects/new" element={withSuspense(<NewProjectPage />)} />
      <Route path="projects/:projectId" element={withSuspense(<ProjectDetailPage />)} />
      {/* Members (admin) */}
      <Route path="members" element={<AdminRoute>{withSuspense(<MembersPage />)}</AdminRoute>} />
      <Route path="members/invite" element={<AdminRoute>{withSuspense(<InviteMemberPage />)}</AdminRoute>} />
      <Route path="members/add" element={<AdminRoute>{withSuspense(<EditUserAccessPage />)}</AdminRoute>} />
      <Route path="members/edit/:id" element={<AdminRoute>{withSuspense(<EditUserAccessPage />)}</AdminRoute>} />

      {/* Roles & Permissions (admin) */}
      <Route path="roles" element={<AdminRoute>{withSuspense(<RolesPage />)}</AdminRoute>} />
      {/* Account & Settings */}
      <Route path="settings" element={withSuspense(<SettingsPage />)} />
      <Route path="profile" element={withSuspense(<ProfilePage />)} />
      <Route path="plans" element={withSuspense(<PlansPage />)} />
      <Route path="support" element={withSuspense(<SupportPage />)} />
      <Route path="docs" element={withSuspense(<DocsPage />)} />

      {/* Catch-all inside dashboard (keeps removed legacy routes from blanking) */}
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Route>
  ),
  (
    <Route
      path="/super-admin-dashboard"
      element={
        <SuperAdminRoute>
          {withSuspense(<SuperAdmin />)}
        </SuperAdminRoute>
      }
      key="super-admin-shell"
    >
      <Route index element={withSuspense(<SuperAdminDashboardHome />)} />
      <Route path="tenants" element={withSuspense(<SuperAdminTenantsPage />)} />
      <Route path="users" element={withSuspense(<SuperAdminUsersRolesPage />)} />
      <Route path="billing" element={withSuspense(<SuperAdminBillingPage />)} />
      <Route path="infrastructure" element={withSuspense(<SuperAdminInfrastructurePage />)} />
      <Route path="test-system" element={withSuspense(<SuperAdminTestSystemPage />)} />
      <Route path="token-usage" element={withSuspense(<SuperAdminTokenUsagePage />)} />
      <Route path="profile" element={withSuspense(<SuperAdminProfilePage />)} />

      {/* Catch-all inside super-admin */}
      <Route path="*" element={<Navigate to="/super-admin-dashboard" replace />} />
    </Route>
  ),
]

export default dashboardRoutes
