import { useOutletContext } from "react-router-dom"
import SuperAdminTenants from "./SuperAdminTenants"
import type { SuperAdminLayoutOutletContext } from "./SuperAdminLayout"

export default function TenantsPage() {
  const { tenants, loading, onRefresh } = useOutletContext<SuperAdminLayoutOutletContext>()

  return (
    <SuperAdminTenants
      tenants={tenants}
      loading={loading}
      onRefresh={onRefresh}
    />
  )
}
