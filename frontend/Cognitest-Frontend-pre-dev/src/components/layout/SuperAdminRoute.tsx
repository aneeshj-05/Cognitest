import type { ReactNode } from "react"
import { Navigate } from "react-router-dom"
import { useAuth } from "@/context/AuthContext"

type SuperAdminRouteProps = {
    children: ReactNode
}

const SuperAdminRoute = ({ children }: SuperAdminRouteProps) => {
    const { user } = useAuth()

    // Check if systemRole is SUPER_ADMIN
    if (user?.systemRole !== "SUPER_ADMIN") {
        return <Navigate to="/dashboard" replace />
    }

    return children
}

export default SuperAdminRoute
