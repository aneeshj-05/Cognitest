import PublicNavbar, { NAV_LINKS } from "./PublicNavbar"
import AnimatedOutlet from "@/components/motion/AnimatedOutlet"
import { useLocation } from "react-router-dom"

const PublicLayout = () => {
  const location = useLocation()
  const isAuthPage = location.pathname === "/login" || location.pathname === "/signup"

  return (
    <div className="flex h-screen min-h-0 flex-col overflow-hidden bg-background">
      {!isAuthPage && <PublicNavbar />}
      <main className="flex-1 min-h-0 overflow-y-auto bg-background">
        <AnimatedOutlet />
      </main>
    </div>
  )
}

export default PublicLayout
