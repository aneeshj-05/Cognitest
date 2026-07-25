import { useState, type CSSProperties, type ReactNode } from "react"
import { useNavigate, useLocation, useSearchParams } from "react-router-dom"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import * as z from "zod"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Loader2, Eye, EyeOff, ArrowRight, Mail, Lock, CheckCircle2, Zap } from "lucide-react"
import { useAuth } from "@/context/AuthContext"
import logoImg from "@/images/logo.png"
import Navbar from "@/components/landing/Navbar"
import { NAV_LINKS } from "@/components/layout/PublicNavbar"

// ── Theme constants ──────────────────────────────────────────────────
const GREEN = "#10b981"
const GREEN_DIM = "rgba(16,185,129,0.15)"
const GREEN_BORDER = "rgba(16,185,129,0.25)"
const PANEL_BG = "#0f1623"
const PANEL_STRIPE = "#131d2e"

interface FieldProps {
  id: string
  label: string
  error?: string
  children: ReactNode
}

// ── Field wrapper ────────────────────────────────────────────────────
const Field = ({ id, label, error, children }: FieldProps) => (
  <div className="space-y-1.5">
    <label
      htmlFor={id}
      className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground"
    >
      {label}
    </label>
    {children}
    {error && <p className="text-xs text-red-400 mt-0.5">{error}</p>}
  </div>
)

// ── Zod schema ───────────────────────────────────────────────────────
const loginSchema = z.object({
  email: z
    .string()
    .min(1, { message: "Email is required" })
    .email({ message: "Must be a valid email address" })
    .toLowerCase(),
  password: z.string().min(1, { message: "Password is required" }),
})

type LoginFormValues = z.infer<typeof loginSchema>

// ── Branding Panel ───────────────────────────────────────────────────
const BrandingPanel = () => {
  const features = [
    "Automated security & regression testing",
    "Real-time execution across all endpoints",
    "Built for high-growth API engineering teams",
  ]

  return (
    <div
      className="hidden lg:flex w-1/2 relative overflow-hidden shrink-0 flex-col"
      style={{ background: PANEL_BG }}
    >
      {/* Vertical stripe texture */}
      <div className="absolute inset-0 flex overflow-hidden pointer-events-none">
        {[...Array(10)].map((_, i) => (
          <div
            key={i}
            className="flex-1 h-full"
            style={{ background: i % 2 === 0 ? PANEL_STRIPE : PANEL_BG, opacity: 0.5 }}
          />
        ))}
      </div>

      {/* Top-right green glow orb */}
      <div
        className="absolute -top-20 -right-20 w-80 h-80 rounded-full pointer-events-none"
        style={{
          background: `radial-gradient(circle, ${GREEN} 0%, transparent 70%)`,
          opacity: 0.1,
          filter: "blur(48px)",
        }}
      />

      {/* Bottom-left green glow orb */}
      <div
        className="absolute -bottom-24 -left-24 w-72 h-72 rounded-full pointer-events-none"
        style={{
          background: `radial-gradient(circle, ${GREEN} 0%, transparent 70%)`,
          opacity: 0.08,
          filter: "blur(56px)",
        }}
      />

      {/* Subtle grid */}
      <svg className="absolute inset-0 w-full h-full pointer-events-none" style={{ opacity: 0.035 }}>
        <defs>
          <pattern id="grid" width="36" height="36" patternUnits="userSpaceOnUse">
            <path d="M 36 0 L 0 0 0 36" fill="none" stroke="white" strokeWidth="0.6" />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#grid)" />
      </svg>

      {/* Diagonal accent line */}
      <svg
        className="absolute inset-0 w-full h-full pointer-events-none"
        style={{ opacity: 0.06 }}
        preserveAspectRatio="none"
      >
        <line x1="0" y1="100%" x2="100%" y2="0" stroke={GREEN} strokeWidth="1.5" />
      </svg>

      {/* Floating HTTP method badges */}
      <style>{`
        @keyframes floatBadge {
          0%   { transform: translateY(0px) rotate(var(--rot)); opacity: 0; }
          10%  { opacity: 1; }
          90%  { opacity: 1; }
          100% { transform: translateY(-680px) rotate(var(--rot)); opacity: 0; }
        }
      `}</style>
      <div className="absolute inset-0 overflow-hidden pointer-events-none" style={{ zIndex: 1 }}>
        {[
          { method: "GET", left: "8%", bottom: "-60px", duration: 22, delay: 0, rot: "-6deg", size: "text-[11px]" },
          { method: "POST", left: "28%", bottom: "-60px", duration: 28, delay: 4, rot: "4deg", size: "text-[10px]" },
          { method: "DELETE", left: "52%", bottom: "-60px", duration: 24, delay: 8, rot: "-3deg", size: "text-[11px]" },
          { method: "PUT", left: "72%", bottom: "-60px", duration: 30, delay: 2, rot: "7deg", size: "text-[10px]" },
          { method: "PATCH", left: "18%", bottom: "-60px", duration: 26, delay: 12, rot: "-5deg", size: "text-[11px]" },
          { method: "GET", left: "62%", bottom: "-60px", duration: 20, delay: 16, rot: "3deg", size: "text-[10px]" },
          { method: "POST", left: "40%", bottom: "-60px", duration: 32, delay: 6, rot: "-8deg", size: "text-[11px]" },
          { method: "DELETE", left: "82%", bottom: "-60px", duration: 25, delay: 18, rot: "5deg", size: "text-[10px]" },
          { method: "PATCH", left: "5%", bottom: "-60px", duration: 29, delay: 9, rot: "6deg", size: "text-[11px]" },
          { method: "PUT", left: "48%", bottom: "-60px", duration: 23, delay: 21, rot: "-4deg", size: "text-[10px]" },
        ].map((b, i) => (
          <div
            key={i}
            className={`absolute font-bold tracking-widest uppercase ${b.size}`}
            style={{
              left: b.left,
              bottom: b.bottom,
              color: "rgba(255,255,255,0.13)",
              border: "1px solid rgba(255,255,255,0.09)",
              borderRadius: "6px",
              padding: "3px 8px",
              background: "rgba(255,255,255,0.04)",
              letterSpacing: "0.1em",
              "--rot": b.rot,
              animation: `floatBadge ${b.duration}s ease-in-out infinite`,
              animationDelay: `${b.delay}s`,
              opacity: 0,
              whiteSpace: "nowrap",
            } as CSSProperties & { "--rot": string }}
          >
            {b.method}
          </div>
        ))}
      </div>

      {/* Panel content */}
      <div className="relative z-10 flex flex-col justify-between h-full px-10 xl:px-14 py-12">
        {/* Logo */}
        <div className="flex items-center gap-2.5">
          <img src={logoImg} alt="Cognitest" className="h-9 w-auto" />
        </div>

        {/* Headline + features */}
        <div className="space-y-7">
          <div className="space-y-4">
            <span
              className="inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-widest"
              style={{ background: GREEN_DIM, color: GREEN, border: `1px solid ${GREEN_BORDER}` }}
            >
              <span className="w-1.5 h-1.5 rounded-full" style={{ background: GREEN }} />
              API Testing Platform
            </span>

            <h1 className="text-3xl xl:text-4xl font-extrabold tracking-tight leading-[1.15] text-white">
              Welcome back to<br />
              <span style={{ color: GREEN }}>Cognitest</span>
            </h1>

            <p className="text-sm leading-relaxed max-w-xs" style={{ color: "#94a3b8" }}>
              Log in to continue automating your API tests and tracking results in real time.
            </p>
          </div>

          <ul className="space-y-3">
            {features.map((feat) => (
              <li key={feat} className="flex items-start gap-2.5">
                <CheckCircle2 className="h-4 w-4 mt-0.5 shrink-0" style={{ color: GREEN }} />
                <span className="text-sm" style={{ color: "#94a3b8" }}>{feat}</span>
              </li>
            ))}
          </ul>
        </div>

        <div />
      </div>
    </div>
  )
}

// ── Page ─────────────────────────────────────────────────────────────
const LoginPage = () => {
  const navigate = useNavigate()
  const location = useLocation()
  const { login } = useAuth()
  const [showPw, setShowPw] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")
  const [searchParams] = useSearchParams()
  const inviteToken = searchParams.get("inviteToken")

  // Show a non-error informational banner when redirected due to session expiry
  const sessionExpired = searchParams.get("reason") === "session_expired"

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "" },
  })

  const onSubmit = async (data: LoginFormValues) => {
    setError("")
    setLoading(true)
    try {
      const result = await login(data.email, data.password, inviteToken || undefined)
      if (result.success) {
        if (result.user?.systemRole === "SUPER_ADMIN") {
          navigate("/super-admin-dashboard")
        } else {
          navigate("/dashboard")
        }
      } else {
        setError(result.error ?? "Invalid credentials")
      }
    } catch {
      setError("An unexpected error occurred")
    } finally {
      setLoading(false)
    }
  }

  // Particles — identical to SignupPage
  const particles = [
    { left: "8%", size: 5, duration: 18, delay: 0 },
    { left: "16%", size: 3, duration: 25, delay: 2 },
    { left: "24%", size: 6, duration: 22, delay: 4.5 },
    { left: "33%", size: 4, duration: 20, delay: 1 },
    { left: "42%", size: 3, duration: 28, delay: 3 },
    { left: "55%", size: 5, duration: 21, delay: 6 },
    { left: "64%", size: 4, duration: 24, delay: 0.5 },
    { left: "72%", size: 3, duration: 30, delay: 7 },
    { left: "81%", size: 6, duration: 19, delay: 2.5 },
    { left: "90%", size: 4, duration: 23, delay: 5 },
    { left: "12%", size: 3, duration: 32, delay: 8 },
    { left: "48%", size: 5, duration: 21, delay: 9 },
    { left: "78%", size: 3, duration: 27, delay: 3.5 },
    { left: "93%", size: 4, duration: 20, delay: 1.5 },
  ]

  return (
    <>
      <style>{`
        @keyframes floatUp {
          0%   { transform: translateY(0)   scale(1);   opacity: 0; }
          10%  { opacity: 0.7; }
          90%  { opacity: 0.4; }
          100% { transform: translateY(-100vh) scale(0.6); opacity: 0; }
        }
      `}</style>

      {/* Full-viewport overlay — now forced light mode */}
      <div
        className="fixed inset-0 z-40 flex flex-col overflow-hidden bg-[#f8fbff] text-black"
      >
        <Navbar pathname={location.pathname} navLinks={NAV_LINKS} variant="light" />

        {/* Floating particles */}
        <div className="absolute inset-0 pointer-events-none overflow-hidden" style={{ zIndex: 0 }}>
          {particles.map((p, i) => (
            <div
              key={i}
              className="absolute bottom-0 rounded-full"
              style={{
                left: p.left,
                width: p.size,
                height: p.size,
                background: "#10b981",
                animation: `floatUp ${p.duration}s ease-in infinite`,
                animationDelay: `${p.delay}s`,
                opacity: 0,
              }}
            />
          ))}
        </div>

        {/* Bottom green wash */}
        <div
          className="absolute bottom-0 left-0 right-0 pointer-events-none"
          style={{
            zIndex: 0,
            height: "65%",
            background:
              "linear-gradient(to top, rgba(16,185,129,0.22) 0%, rgba(16,185,129,0.12) 25%, rgba(16,185,129,0.05) 60%, transparent 100%)",
          }}
        />

        {/* ── Card — identical shape & constraints to SignupPage ── */}
        <div
          className="flex flex-1 items-center justify-center p-6"
          style={{ zIndex: 10, position: "relative" }}
        >
          <div
            className="flex w-full max-w-5xl overflow-hidden shadow-2xl"
            style={{
              borderRadius: "1.25rem",
              maxHeight: "calc(100dvh - 3rem)",
            }}
          >
            {/* Left branding panel */}
            <BrandingPanel />

            {/*
              Right form panel.
              `minHeight: 620px` ensures the white panel has the same
              visual height as the signup card even though login has fewer
              fields, so both cards look identical in proportion.
            */}
            <div
              className="flex-1 overflow-y-auto bg-white"
              style={{ minHeight: "620px" }}
            >
              <div className="flex min-h-full items-center justify-center px-8 py-10 sm:px-12">
                <div className="w-full max-w-sm space-y-5">

                  {/* Mobile logo */}
                  <div className="lg:hidden flex items-center gap-2.5 mb-2">
                    <div
                      className="flex h-9 w-9 items-center justify-center rounded-xl"
                      style={{ background: "#10b981" }}
                    >
                      <Zap className="h-[18px] w-[18px] text-white" />
                    </div>
                    <span className="text-lg font-bold">Cognitest</span>
                  </div>

                  {/* Heading */}
                  <div>
                    <h2 className="text-2xl font-bold tracking-tight text-gray-900">Sign In</h2>
                    <p className="mt-1 text-sm text-gray-500">
                      Enter your email and password to sign in
                    </p>
                  </div>

                  {/* Session-expired banner — shown when redirected after 401 */}
                  {sessionExpired && !error && (
                    <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-700 flex items-center gap-2">
                      <svg className="h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
                      </svg>
                      Your session has expired. Please sign in again.
                    </div>
                  )}

                  {/* Error banner */}
                  {error && (
                    <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-600">
                      {error}
                    </div>
                  )}

                  <form onSubmit={handleSubmit(onSubmit)} className="space-y-3.5">

                    {/* Email */}
                    <Field id="login-email" label="Email Address" error={errors.email?.message}>
                      <div className="relative">
                        <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
                        <Input
                          id="login-email"
                          type="email"
                          placeholder="name@company.com"
                          className="h-11 pl-10 border-gray-200 bg-gray-50 focus:bg-white focus:border-emerald-400 focus:ring-emerald-400/20 text-gray-900"
                          {...register("email")}
                        />
                      </div>
                    </Field>

                    {/* Password */}
                    <Field id="login-password" label="Password" error={errors.password?.message}>
                      <div className="relative">
                        <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
                        <Input
                          id="login-password"
                          type={showPw ? "text" : "password"}
                          placeholder="••••••••"
                          className="h-11 pl-10 pr-10 border-gray-200 bg-gray-50 focus:bg-white focus:border-emerald-400 focus:ring-emerald-400/20 text-gray-900"
                          {...register("password")}
                        />
                        <button
                          type="button"
                          onClick={() => setShowPw((p) => !p)}
                          className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-700 transition-colors cursor-pointer"
                        >
                          {showPw ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                        </button>
                      </div>
                    </Field>

                    {/* Forgot password */}
                    <div className="flex justify-end">
                      <button
                        type="button"
                        className="text-[13px] font-medium text-gray-500 hover:text-gray-800 transition-colors cursor-pointer"
                      >
                        Forgot Password?
                      </button>
                    </div>

                    {/* Submit + nav link */}
                    <div className="pt-1 space-y-3">
                      <Button
                        type="submit"
                        disabled={loading}
                        className="w-full h-11 gap-2 text-white text-sm font-semibold cursor-pointer transition-colors"
                        style={{ background: "#10b981" }}
                        onMouseEnter={(e) => (e.currentTarget.style.background = "#059669")}
                        onMouseLeave={(e) => (e.currentTarget.style.background = "#10b981")}
                      >
                        {loading ? (
                          <><Loader2 className="h-4 w-4 animate-spin" /> Logging In...</>
                        ) : (
                          <>Sign In <ArrowRight className="h-4 w-4" /></>
                        )}
                      </Button>

                      <button
                        type="button"
                        onClick={() => navigate(inviteToken ? `/signup?inviteToken=${inviteToken}` : "/signup")}
                        className="w-full text-sm text-gray-500 hover:text-gray-800 transition-colors text-center cursor-pointer"
                      >
                        Don't have an account?{" "}
                        <span className="font-semibold text-gray-800">Sign up</span>
                      </button>
                    </div>
                  </form>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  )
}

export default LoginPage
