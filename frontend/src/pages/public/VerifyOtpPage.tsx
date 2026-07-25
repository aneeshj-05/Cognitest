import { useState, useRef, useEffect } from "react"
import { useNavigate, useLocation, Link } from "react-router-dom"
import { useAuth } from "@/context/AuthContext"
import { Button } from "@/components/ui/button"
import { Zap, Loader2, ArrowRight, MailCheck } from "lucide-react"

const VerifyOtpPage = () => {
  const navigate = useNavigate()
  const location = useLocation()
  const { verify } = useAuth()
  const email = location.state?.email || ""
  const inviteToken = location.state?.inviteToken || ""
  
  const [otp, setOtp] = useState(["", "", "", "", "", ""])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")
  const inputRefs = useRef<(HTMLInputElement | null)[]>([])

  useEffect(() => {
    if (!email) {
      navigate("/signup", { replace: true })
    }
  }, [email, navigate])

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>, index: number) => {
    if (e.key === "Backspace") {
      if (otp[index] === "" && index > 0) {
        inputRefs.current[index - 1]?.focus()
        const newOtp = [...otp]
        newOtp[index - 1] = ""
        setOtp(newOtp)
      } else {
        const newOtp = [...otp]
        newOtp[index] = ""
        setOtp(newOtp)
      }
    } else if (e.key === "ArrowLeft" && index > 0) {
      inputRefs.current[index - 1]?.focus()
    } else if (e.key === "ArrowRight" && index < 5) {
      inputRefs.current[index + 1]?.focus()
    }
  }

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>, index: number) => {
    const value = e.target.value.replace(/[^0-9]/g, "")
    if (!value) return

    const newOtp = [...otp]
    
    // Handle paste of multiple characters
    if (value.length > 1) {
      const pastedData = value.slice(0, 6).split("")
      for (let i = 0; i < pastedData.length; i++) {
        if (index + i < 6) {
          newOtp[index + i] = pastedData[i]
        }
      }
      setOtp(newOtp)
      const nextEmptyIndex = newOtp.findIndex((val) => val === "")
      const focusIndex = nextEmptyIndex === -1 ? 5 : nextEmptyIndex
      inputRefs.current[focusIndex]?.focus()
    } else {
      newOtp[index] = value
      setOtp(newOtp)
      if (index < 5 && value !== "") {
        inputRefs.current[index + 1]?.focus()
      }
    }
  }

  const handleVerify = async (e: React.FormEvent) => {
    e.preventDefault()
    const code = otp.join("")
    if (code.length !== 6) {
      setError("Please enter the 6-digit code")
      return
    }

    setError("")
    setLoading(true)
    try {
      const result = await verify(email, code, inviteToken || undefined)
      if (!result.success) {
        throw new Error(result.error || "Verification failed")
      }
      navigate("/dashboard")
    } catch (err) {
      setError(err instanceof Error ? err.message : "Verification failed")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex h-[calc(100vh-4rem)]">
      {/* Left branding layout matches Signup/Login */}
      <div className="hidden lg:flex lg:w-[45%] relative overflow-hidden border-r border-border/40 items-center justify-center shrink-0">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(0,0,0,0.03),transparent_60%)]" />
        <div className="relative z-10 flex flex-col items-center text-center px-12 xl:px-16">
          <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-muted ring-1 ring-border mb-8">
            <MailCheck className="h-8 w-8 text-foreground" />
          </div>
          <h1 className="text-3xl xl:text-4xl font-extrabold tracking-tight leading-tight">
            Secure your<br />Cognitest account
          </h1>
          <p className="mt-4 text-muted-foreground max-w-sm leading-relaxed">
            We use two-step verification to ensure only you have access to your automated test results and analytics.
          </p>
        </div>
      </div>

      {/* Right form panel */}
      <div className="flex-1 flex items-center justify-center px-6 py-10 sm:px-10 overflow-y-auto">
        <div className="w-full max-w-md space-y-8">
          <div className="lg:hidden flex items-center gap-2.5 mb-8">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-muted">
              <Zap className="h-[18px] w-[18px] text-foreground" />
            </div>
            <span className="text-lg font-bold">Cognitest</span>
          </div>

          <div className="space-y-2">
            <h2 className="text-2xl font-bold tracking-tight">Check your email</h2>
            <p className="text-sm text-muted-foreground">
              We sent a 6-digit verification code to <span className="text-foreground font-medium">{email}</span>.
            </p>
          </div>

          {error && (
            <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-400">
              {error}
            </div>
          )}

          <form onSubmit={handleVerify} className="space-y-6">
            <div className="flex justify-between gap-2 max-w-[320px] mx-auto">
              {otp.map((digit, index) => (
                <input
                  key={index}
                  ref={(el) => { inputRefs.current[index] = el }}
                  type="text"
                  inputMode="numeric"
                  maxLength={6}
                  value={digit}
                  onChange={(e) => handleChange(e, index)}
                  onKeyDown={(e) => handleKeyDown(e, index)}
                  className="w-12 h-14 text-center text-2xl font-bold rounded-lg border border-border bg-background/50 focus:bg-background focus:border-foreground focus:ring-1 focus:ring-foreground/20 transition-all outline-none tabular-nums"
                />
              ))}
            </div>

            <Button
              type="submit"
              className="w-full h-11 gap-2 bg-black hover:bg-black/80 text-white text-sm font-semibold cursor-pointer"
              disabled={loading || otp.join("").length !== 6}
            >
              {loading ? (
                <><Loader2 className="h-4 w-4 animate-spin" /> Verifying...</>
              ) : (
                <>Verify Account <ArrowRight className="h-4 w-4" /></>
              )}
            </Button>
          </form>

          <div className="text-center">
            <p className="text-sm text-muted-foreground">
              Didn't receive the email?{" "}
              <Link to="/signup" className="font-semibold text-foreground hover:underline">
                Try signing up again
              </Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

export default VerifyOtpPage
