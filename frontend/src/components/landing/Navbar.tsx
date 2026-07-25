import * as React from "react"
import { Link } from "react-router-dom"
import { motion, AnimatePresence } from "framer-motion"
import { Menu, ChevronDown, Rocket, ExternalLink, ShieldCheck, Sun, Moon } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu"
import { cn } from "@/lib/utils"
import logoImg from "@/images/logo.png"

type NavLink = {
  to: string
  label: string
}

type NavbarProps = {
  pathname: string
  navLinks: NavLink[]
  variant?: "light" | "dark"
}

export default function Navbar({ pathname, navLinks, variant }: NavbarProps) {
  const [isScrolled, setIsScrolled] = React.useState(false)
  const [hoveredPath, setHoveredPath] = React.useState<string | null>(null)

  const isLight = variant === "light"

  React.useEffect(() => {
    const handleScroll = () => {
      setIsScrolled(window.scrollY > 20)
    }
    window.addEventListener("scroll", handleScroll)
    return () => window.removeEventListener("scroll", handleScroll)
  }, [])

  return (
    <header
      className={cn(
        "sticky top-0 z-50 w-full transition-all duration-500 ease-in-out px-4 md:px-8",
        isScrolled ? "py-2.5" : "py-4"
      )}
    >
      <nav
        className={cn(
          "mx-auto flex max-w-7xl items-center justify-between transition-all duration-500 rounded-[2rem] border border-transparent px-3 py-1.5 md:px-6",
          isScrolled
            ? cn(
              "bg-white backdrop-blur-xl border-zinc-200 shadow-[0_8px_30px_rgb(0,0,0,0.04)]",
              !isLight && "dark:bg-[#0B1220]/95 dark:border-white/[0.06] dark:shadow-[0_8px_30px_rgb(0,0,0,0.3)]"
            )
            : cn(
              "bg-transparent",
              !isLight && "dark:bg-transparent"
            )
        )}
      >
        {/* Logo Area */}
        <Link to="/" className="group flex items-center gap-3 shrink-0">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-zinc-200 bg-white shadow-sm transition-all duration-300 group-hover:border-[#27BE8C]/30">
            <img
              src={logoImg}
              alt="Cognitest logo"
              className={cn(
                "h-6 w-6 object-contain transition-all duration-300",
                !isLight && "dark:invert dark:brightness-200"
              )}
            />
          </div>
          <span className={cn(
            "text-xl font-semibold tracking-tighter text-zinc-900 leading-none",
            !isLight && "dark:text-zinc-100"
          )}>
            Cognitest
          </span>
        </Link>

        {/* Desktop Navigation - Floating Pill Style */}
        <div className="hidden lg:flex items-center">
          <ul className={cn(
            "flex items-center gap-1 bg-zinc-100/50 p-1 rounded-full border border-zinc-300/50",
            !isLight && "dark:bg-white/[0.04] dark:border-white/[0.06]"
          )}>
            {navLinks.map((link) => (
              <li key={link.to} className="relative">
                <Link
                  to={link.to}
                  onMouseEnter={() => setHoveredPath(link.to)}
                  onMouseLeave={() => setHoveredPath(null)}
                  className={cn(
                    "relative z-10 block px-5 py-2 text-[14px] font-semibold transition-colors duration-300",
                    pathname === link.to
                      ? cn("text-zinc-900", !isLight && "dark:text-white")
                      : cn("text-zinc-500 hover:text-zinc-900", !isLight && "dark:text-zinc-400 dark:hover:text-zinc-200")
                  )}
                >
                  {link.label}
                </Link>
                <AnimatePresence>
                  {(hoveredPath === link.to || pathname === link.to) && (
                    <motion.div
                      layoutId="nav-pill"
                      initial={{ opacity: 0, scale: 0.9 }}
                      animate={{ opacity: 1, scale: 1 }}
                      exit={{ opacity: 0, scale: 0.9 }}
                      transition={{ type: "spring", bounce: 0.2, duration: 0.4 }}
                      className={cn(
                        "absolute inset-0 rounded-full",
                        pathname === link.to
                          ? cn("bg-white shadow-sm border border-zinc-200", !isLight && "dark:bg-white/10 dark:border-white/[0.08]")
                          : cn("bg-white", !isLight && "dark:bg-white/[0.06]")
                      )}
                    />
                  )}
                </AnimatePresence>
              </li>
            ))}
          </ul>
        </div>

        {/* Right Actions */}
        <div className="flex items-center gap-2 md:gap-4">
          {/* Theme Toggle */}
          <Button
            variant="outline"
            onClick={() => document.documentElement.classList.toggle('dark')}
            className={cn(
              "hidden sm:flex h-10 px-4 rounded-full border border-zinc-200 bg-white text-zinc-900 hover:bg-zinc-100 transition-colors duration-200 gap-2 items-center text-sm font-medium",
              !isLight && "dark:border-white/10 dark:bg-white/[0.05] dark:text-zinc-200 dark:hover:bg-white/10"
            )}
          >
            <Sun className={cn("h-4 w-4 hidden text-zinc-300", !isLight && "dark:block")} />
            <span className={cn("hidden", !isLight && "dark:block")}>Light</span>
            <Moon className={cn("h-4 w-4 block text-zinc-500", !isLight && "dark:hidden")} />
            <span className={cn("block", !isLight && "dark:hidden")}>Dark</span>
          </Button>

          <Link
            to="/login"
            className={cn(
              "hidden sm:block text-[14px] font-semibold text-zinc-500 transition-colors duration-200 hover:text-zinc-900 px-4 py-2 rounded-full",
              !isLight && "dark:text-zinc-200 dark:hover:text-white dark:bg-white/[0.05] dark:hover:bg-white/10"
            )}
          >
            Sign In
          </Link>

          <Button
            asChild
            className="group relative h-10 overflow-hidden rounded-full bg-[#27BE8C] px-8 text-[14px] font-semibold text-white shadow-[0_4px_14px_0_rgba(39,190,140,0.3)] transition-all duration-300 hover:bg-[#21a378] hover:shadow-[0_6px_20px_rgba(39,190,140,0.2)] hover:-translate-y-0.5 active:scale-95"
          >
            <Link to="/signup">
              <span className="relative z-10 flex items-center gap-2">
                Start Free <Rocket className="h-4 w-4 transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
              </span>
            </Link>
          </Button>

          {/* Mobile Navigation Dropdown */}
          <div className="lg:hidden flex items-center ml-1">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="icon" className={cn(
                  "h-9 w-9 rounded-full hover:bg-zinc-100",
                  !isLight && "dark:hover:bg-white/10"
                )}>
                  <Menu className={cn("h-5 w-5 text-zinc-900", !isLight && "dark:text-zinc-200")} />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className={cn(
                "w-56 p-2 rounded-2xl border-zinc-200 shadow-xl backdrop-blur-xl bg-white mt-2",
                !isLight && "dark:border-white/[0.08] dark:bg-[#020617]/95"
              )}>
                <div className={cn(
                  "px-2 py-1.5 text-[10px] font-semibold text-zinc-400 uppercase tracking-widest",
                  !isLight && "dark:text-zinc-500"
                )}>
                  Navigation
                </div>
                {navLinks.map((link) => (
                  <DropdownMenuItem key={link.to} asChild className={cn(
                    "rounded-xl p-0 focus:bg-zinc-50 focus:text-zinc-900",
                    !isLight && "dark:focus:bg-white/[0.06] dark:text-zinc-100"
                  )}>
                    <Link to={link.to} className="flex w-full items-center justify-between px-3 py-2.5 text-sm font-semibold">
                      {link.label}
                      {pathname === link.to && <div className="h-1.5 w-1.5 rounded-full bg-[#27BE8C]" />}
                    </Link>
                  </DropdownMenuItem>
                ))}
                <DropdownMenuSeparator className="my-2 bg-zinc-100" />
                <DropdownMenuItem asChild className={cn(
                  "rounded-xl p-0 focus:bg-zinc-50",
                  !isLight && "dark:focus:bg-white/[0.06]"
                )}>
                  <Link to="/login" className={cn(
                    "flex w-full items-center gap-2 px-3 py-2.5 text-sm font-semibold text-zinc-500",
                    !isLight && "dark:text-zinc-400"
                  )}>
                    Sign In
                  </Link>
                </DropdownMenuItem>
                <div className="p-1 pt-2">
                  <Button asChild className="w-full rounded-xl bg-zinc-900 text-white font-semibold h-11">
                    <Link to="/signup">Start Free</Link>
                  </Button>
                </div>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      </nav>

    </header>
  )
}
