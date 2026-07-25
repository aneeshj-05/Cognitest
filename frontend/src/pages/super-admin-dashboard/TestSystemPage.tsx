import { useOutletContext } from "react-router-dom"
import SuperAdminTestSystem from "./SuperAdminTestSystem"
import type { SuperAdminLayoutOutletContext } from "./SuperAdminLayout"

export default function TestSystemPage() {
  const { stats, tenants, loading } = useOutletContext<SuperAdminLayoutOutletContext>()

  return (
    <SuperAdminTestSystem
      stats={stats}
      tenants={tenants}
      loading={loading}
    />
  )
}
