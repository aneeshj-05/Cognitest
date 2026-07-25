import { useOutletContext } from "react-router-dom"
import SuperAdminBilling from "./SuperAdminBilling"
import type { SuperAdminLayoutOutletContext } from "./SuperAdminLayout"

export default function BillingPage() {
  const { tenants, loading } = useOutletContext<SuperAdminLayoutOutletContext>()

  return (
    <SuperAdminBilling
      tenants={tenants}
      loading={loading}
    />
  )
}
