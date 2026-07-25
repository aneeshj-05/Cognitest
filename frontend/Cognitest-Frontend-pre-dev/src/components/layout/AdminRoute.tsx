import type { ReactNode } from "react"
import { Navigate } from "react-router-dom"
import { useAuth } from "@/context/AuthContext"

type AdminRouteProps = {
  children: ReactNode
}

const AdminRoute = ({ children }: AdminRouteProps) => {
  const { isAdmin } = useAuth()

  if (!isAdmin) {
    return <Navigate to="/dashboard" replace />
  }

  return children
}

export default AdminRoute
