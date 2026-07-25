import { useLocation } from "react-router-dom"

import Navbar from "@/components/landing/Navbar"

export const NAV_LINKS = [
  { to: "/", label: "Home" },
  { to: "/pricing", label: "Pricing" },
  { to: "/docs", label: "Documentation" },
  { to: "/contact", label: "Contact Us" },
]

const PublicNavbar = () => {
  const location = useLocation()

  return (
    <Navbar pathname={location.pathname} navLinks={NAV_LINKS} />
  )
}

export default PublicNavbar
