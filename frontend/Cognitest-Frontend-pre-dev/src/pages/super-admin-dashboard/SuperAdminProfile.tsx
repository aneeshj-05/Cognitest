import { useState, useRef, useEffect, type ChangeEvent } from "react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Textarea } from "@/components/ui/textarea"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Camera, Mail, Phone, Lock, Eye, EyeOff, User, AlertCircle,
  Building2, MapPin, Globe, Calendar, Shield, CheckCircle2, Loader2, KeyRound,
  ChevronDown,
} from "lucide-react"
import { useAuth } from "@/context/AuthContext"
import { changePassword as apiChangePassword } from "@/services/backendClient"

/* ─── Types ─── */
type PasswordErrors = { current?: string; newPw?: string; confirm?: string }

/* ─── Validators ─── */
const validatePassword = (v: string) => {
  if (!v) return "Required"
  if (v.length < 8)             return "At least 8 characters"
  if (!/[A-Z]/.test(v))         return "Include an uppercase letter"
  if (!/[a-z]/.test(v))         return "Include a lowercase letter"
  if (!/[0-9]/.test(v))         return "Include a number"
  if (!/[^A-Za-z0-9]/.test(v))  return "Include a special character"
  return ""
}

/* ─── FieldError ─── */
const FieldError = ({ msg }: { msg?: string }) =>
  msg ? (
    <p className="flex items-center gap-1 text-[11px] text-destructive mt-0.5">
      <AlertCircle className="h-2.5 w-2.5 shrink-0" /> {msg}
    </p>
  ) : null

/* ─── Password Strength ─── */
const PasswordStrength = ({ password }: { password: string }) => {
  if (!password) return null
  let s = 0
  if (password.length >= 8)           s++
  if (/[A-Z]/.test(password))         s++
  if (/[a-z]/.test(password))         s++
  if (/[0-9]/.test(password))         s++
  if (/[^A-Za-z0-9]/.test(password))  s++
  const idx = Math.max(0, s - 1)
  const labels = ["Very Weak","Weak","Fair","Good","Strong"]
  return (
    <div className="flex items-center gap-2 mt-1">
      <div className="flex gap-0.5 flex-1">
        {[0,1,2,3,4].map((n) => (
          <div key={n} className={`h-0.5 flex-1 rounded-full transition-colors ${n <= idx ? "bg-primary/20" : "bg-border"}`} />
        ))}
      </div>
      <span className="text-[10px] text-muted-foreground">
        {labels[idx]}
      </span>
    </div>
  )
}

/* ─── Labelled field shell ─── */
const FL = ({
  id, label, icon: Icon, required, children,
}: {
  id?: string; label: string; icon?: React.ElementType; required?: boolean; children: React.ReactNode
}) => (
  <div className="space-y-1.5">
    <label htmlFor={id} className="flex items-center gap-1.5 text-sm font-medium text-foreground">
      {Icon && <Icon className="h-3.5 w-3.5 text-muted-foreground" />}
      {label}{required && <span className="text-destructive">*</span>}
    </label>
    {children}
  </div>
)

/* ─── Password row: 3 inline fields ─── */
const PwInput = ({
  id, placeholder, value, onChange, show, onToggle, err,
}: {
  id: string; placeholder: string; value: string; onChange: (v: string) => void
  show: boolean; onToggle: () => void; err?: string
}) => (
  <div className="space-y-1">
    <div className="relative">
      <Lock className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground pointer-events-none" />
      <Input
        id={id}
        className={`pl-9 pr-9 h-9 text-sm ${err ? "border-destructive/60" : ""}`}
        type={show ? "text" : "password"}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
      />
      <button
        type="button"
        onClick={onToggle}
        className="absolute right-1.5 top-1/2 -translate-y-1/2 h-7 w-7 flex items-center justify-center text-muted-foreground hover:text-foreground"
      >
        {show ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
      </button>
    </div>
    <FieldError msg={err} />
  </div>
)

export default function SuperAdminProfile() {
  const { user } = useAuth()
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [fullName,    setFullName]    = useState(user?.displayName || "System Super Admin")
  const [displayName, setDisplayName] = useState(user?.username || "superadmin")
  const [email,       setEmail]       = useState(user?.email || "super@gmail.com")
  const [saving,      setSaving]      = useState(false)
  const [saved,       setSaved]       = useState(false)

  const [pwOpen,      setPwOpen]      = useState(false)
  const [currentPw,   setCurrentPw]   = useState("")
  const [newPw,       setNewPw]       = useState("")
  const [confirmPw,   setConfirmPw]   = useState("")
  const [showCur,     setShowCur]     = useState(false)
  const [showNew,     setShowNew]     = useState(false)
  const [showCon,     setShowCon]     = useState(false)
  const [pwErrors,    setPwErrors]    = useState<PasswordErrors>({})
  const [pwSaving,    setPwSaving]    = useState(false)
  const [pwSaved,     setPwSaved]     = useState(false)

  const handleSave = () => {
    setSaving(true); setSaved(false)
    setTimeout(() => { setSaving(false); setSaved(true); setTimeout(() => setSaved(false), 3000) }, 700)
  }

  const handlePasswordChange = async () => {
    const errors: PasswordErrors = {}
    if (!currentPw) errors.current = "Enter your current password"
    const e2 = validatePassword(newPw); if (e2) errors.newPw = e2
    if (newPw !== confirmPw) errors.confirm = "Passwords do not match"
    setPwErrors(errors)
    if (Object.keys(errors).length) return
    setPwSaving(true); setPwSaved(false)
    try {
      await apiChangePassword(currentPw, newPw)
      setPwSaved(true)
      setCurrentPw(""); setNewPw(""); setConfirmPw(""); setPwErrors({})
      setPwOpen(false)
      setTimeout(() => setPwSaved(false), 3000)
    } catch (err) {
      setPwErrors({ current: err instanceof Error ? err.message : "Failed to change password" })
    } finally { setPwSaving(false) }
  }

  const initials = displayName?.[0]?.toUpperCase() || fullName?.[0]?.toUpperCase() || "SA"

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Account Profile</h1>
          <p className="text-sm text-muted-foreground">Manage your super admin account details and security settings</p>
        </div>
      </div>

      <div className="flex gap-6 items-start">
        <Card className="flex-1 rounded-xl border border-border/50 bg-white shadow-sm overflow-hidden">
          <CardHeader className="border-b border-border/50 bg-muted/20">
            <CardTitle className="text-lg font-semibold">Personal Information</CardTitle>
          </CardHeader>
          <CardContent className="p-6 space-y-6">
            <div className="grid grid-cols-2 gap-6">
              <FL id="full-name" label="Full Name" required>
                <Input id="full-name" value={fullName} onChange={(e) => setFullName(e.target.value)} />
              </FL>
              <FL id="disp-name" label="Username" icon={User}>
                <Input id="disp-name" value={displayName} onChange={(e) => setDisplayName(e.target.value)} />
              </FL>
            </div>
            <FL id="email" label="Email Address" icon={Mail} required>
              <Input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
            </FL>

            <div className="pt-4 border-t border-border/50">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <Lock className="h-4 w-4 text-muted-foreground" />
                  <h3 className="font-semibold">Security</h3>
                </div>
                {!pwOpen && (
                  <Button variant="outline" size="sm" onClick={() => setPwOpen(true)}>Change Password</Button>
                )}
              </div>

              {pwOpen && (
                <div className="space-y-4 bg-muted/30 p-4 rounded-lg border border-border/50">
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <FL id="cur-pw" label="Current Password">
                      <PwInput id="cur-pw" placeholder="••••••••" value={currentPw} onChange={setCurrentPw} show={showCur} onToggle={() => setShowCur(!showCur)} err={pwErrors.current} />
                    </FL>
                    <FL id="new-pw" label="New Password">
                      <PwInput id="new-pw" placeholder="••••••••" value={newPw} onChange={setNewPw} show={showNew} onToggle={() => setShowNew(!showNew)} err={pwErrors.newPw} />
                      <PasswordStrength password={newPw} />
                    </FL>
                    <FL id="con-pw" label="Confirm Password">
                      <PwInput id="con-pw" placeholder="••••••••" value={confirmPw} onChange={setConfirmPw} show={showCon} onToggle={() => setShowCon(!showCon)} err={pwErrors.confirm} />
                    </FL>
                  </div>
                  <div className="flex justify-end gap-2">
                    <Button variant="ghost" size="sm" onClick={() => setPwOpen(false)}>Cancel</Button>
                    <Button size="sm" onClick={handlePasswordChange} disabled={pwSaving}>
                      {pwSaving ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
                      Update Password
                    </Button>
                  </div>
                </div>
              )}
            </div>
          </CardContent>
          <div className="bg-muted/10 border-t border-border/50 p-4 flex justify-end gap-3">
            <Button variant="outline" onClick={() => {}}>Discard</Button>
            <Button onClick={handleSave} disabled={saving}>
              {saving ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
              {saved ? <CheckCircle2 className="h-4 w-4 mr-2" /> : null}
              Save Changes
            </Button>
          </div>
        </Card>

        <div className="w-80 shrink-0 space-y-6">
          <Card className="rounded-xl border border-border/50 bg-white shadow-sm overflow-hidden text-center p-8">
            <div className="relative inline-block mx-auto mb-4">
              <Avatar className="h-24 w-24 ring-4 ring-muted">
                <AvatarFallback className="text-3xl font-bold bg-emerald-500 text-white">{initials}</AvatarFallback>
              </Avatar>
              <button className="absolute bottom-0 right-0 h-8 w-8 rounded-full bg-white border border-border shadow-sm flex items-center justify-center hover:bg-muted transition-colors">
                <Camera className="h-4 w-4 text-muted-foreground" />
              </button>
            </div>
            <h2 className="text-xl font-bold">{fullName}</h2>
            <p className="text-sm text-muted-foreground">{email}</p>
            <div className="mt-4 flex items-center justify-center gap-2">
              <Badge variant="outline" className="bg-emerald-50 text-emerald-700 border-emerald-100 uppercase tracking-wider text-[10px] font-bold px-3 py-1">
                Super Admin
              </Badge>
            </div>
          </Card>

          <Card className="rounded-xl border border-border/50 bg-white shadow-sm p-6 space-y-4">
            <h3 className="font-semibold text-sm uppercase tracking-wider text-muted-foreground">Account Status</h3>
            <div className="space-y-3">
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Role</span>
                <span className="font-medium">Administrator</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Two-Factor Auth</span>
                <span className="text-emerald-600 font-medium">Enabled</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Last Login</span>
                <span className="font-medium">2 hours ago</span>
              </div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  )
}
