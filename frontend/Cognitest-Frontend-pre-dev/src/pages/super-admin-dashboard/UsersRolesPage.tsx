import { useOutletContext } from "react-router-dom"
import SuperAdminUsersRoles from "./SuperAdminUsersRoles"
import type { SuperAdminLayoutOutletContext } from "./SuperAdminLayout"

export default function UsersRolesPage() {
  const { tenants, loading, onRefresh } = useOutletContext<SuperAdminLayoutOutletContext>()

  return (
    <SuperAdminUsersRoles
      tenants={tenants}
      loading={loading}
      onRefresh={onRefresh}
    />
  )
}
