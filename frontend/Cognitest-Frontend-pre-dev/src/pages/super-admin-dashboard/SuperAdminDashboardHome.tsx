import { useOutletContext } from "react-router-dom"
import SuperAdminDashboard from "./SuperAdminDashboard"
import type { SuperAdminLayoutOutletContext } from "./SuperAdminLayout"

export default function SuperAdminDashboardHome() {
  const { stats, tenants, loading } = useOutletContext<SuperAdminLayoutOutletContext>()

  return (
    <SuperAdminDashboard
      stats={stats}
      tenants={tenants}
      loading={loading}
    />
  )
}
