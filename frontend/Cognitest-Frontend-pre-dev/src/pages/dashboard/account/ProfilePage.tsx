import { useState, useRef, useEffect, type ChangeEvent } from "react"
import PageHeader from "@/components/shared/PageHeader"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Textarea } from "@/components/ui/textarea"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Camera, Mail, Phone, Lock, Eye, EyeOff, User, AlertCircle,
  Building2, MapPin, Globe, Calendar, Shield, CheckCircle2, Loader2,
  ChevronDown,
} from "lucide-react"
import { useAuth } from "@/context/AuthContext"
import { changePassword as apiChangePassword } from "@/services/backendClient"

/* ─── Types ─── */
type PasswordErrors = { current?: string; newPw?: string; confirm?: string }
type CC = { code: string; flag: string; country: string }

const COUNTRY_CODES: CC[] = [
  { code: "+1",   flag: "🇺🇸", country: "US" },
  { code: "+44",  flag: "🇬🇧", country: "UK" },
  { code: "+91",  flag: "🇮🇳", country: "IN" },
  { code: "+49",  flag: "🇩🇪", country: "DE" },
  { code: "+33",  flag: "🇫🇷", country: "FR" },
  { code: "+81",  flag: "🇯🇵", country: "JP" },
  { code: "+86",  flag: "🇨🇳", country: "CN" },
  { code: "+61",  flag: "🇦🇺", country: "AU" },
  { code: "+55",  flag: "🇧🇷", country: "BR" },
  { code: "+971", flag: "🇦🇪", country: "AE" },
  { code: "+65",  flag: "🇸🇬", country: "SG" },
  { code: "+82",  flag: "🇰🇷", country: "KR" },
  { code: "+7",   flag: "🇷🇺", country: "RU" },
  { code: "+39",  flag: "🇮🇹", country: "IT" },
  { code: "+34",  flag: "🇪🇸", country: "ES" },
  { code: "+52",  flag: "🇲🇽", country: "MX" },
  { code: "+27",  flag: "🇿🇦", country: "ZA" },
  { code: "+234", flag: "🇳🇬", country: "NG" },
  { code: "+62",  flag: "🇮🇩", country: "ID" },
  { code: "+60",  flag: "🇲🇾", country: "MY" },
]

const parseContactNumber = (raw?: string | null) => {
  if (!raw) return { code: "+1", number: "" }
  const m = raw.match(/^(\+\d{1,4})(\d+)$/)
  return m ? { code: m[1], number: m[2] } : { code: "+1", number: raw.replace(/\D/g, "") }
}

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
  const colors = ["bg-primary/20","bg-primary/20","bg-primary/20","bg-primary/20","bg-primary/20"]
  const labels = ["Very Weak","Weak","Fair","Good","Strong"]
  return (
    <div className="flex items-center gap-2 mt-1">
      <div className="flex gap-0.5 flex-1">
        {[0,1,2,3,4].map((n) => (
          <div key={n} className={`h-0.5 flex-1 rounded-full transition-colors ${n <= idx ? colors[idx] : "bg-border"}`} />
        ))}
      </div>
      <span className="text-[10px] text-muted-foreground">
        {labels[idx]}
      </span>
    </div>
  )
}

/* ─── Country code dropdown ─── */
const CountryCodeSelect = ({ value, onChange }: { value: string; onChange: (c: string) => void }) => {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const sel = COUNTRY_CODES.find((c) => c.code === value) ?? COUNTRY_CODES[0]
  useEffect(() => {
    const h = (e: MouseEvent) => {
      if (ref.current && e.target instanceof Node && !ref.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener("mousedown", h)
    return () => document.removeEventListener("mousedown", h)
  }, [])
  return (
    <div ref={ref} className="relative shrink-0 w-22.5">
      <Button
        type="button"
        variant="outline"
        onClick={() => setOpen((o) => !o)}
        className="flex h-9 w-full items-center justify-between gap-1 rounded-md border border-input bg-background px-2 text-sm text-foreground hover:bg-accent/40 transition-colors"
      >
        <span className="text-xs">{sel.flag} {sel.code}</span>
        <ChevronDown className={`h-3 w-3 text-muted-foreground transition-transform ${open ? "rotate-180" : ""}`} />
      </Button>
      {open && (
        <div className="absolute z-50 mt-1 max-h-48 w-35 overflow-auto rounded-md border border-border bg-popover shadow-xl">
          {COUNTRY_CODES.map((cc) => (
            <Button
              key={cc.code}
              type="button"
              variant="ghost"
              onClick={() => { onChange(cc.code); setOpen(false) }}
              className={`h-auto flex w-full items-center justify-start gap-2 px-2.5 py-1.5 text-xs hover:bg-accent/50 ${cc.code === value ? "bg-accent" : ""}`}
            >
              <span>{cc.flag}</span><span>{cc.country}</span>
              <span className="ml-auto text-muted-foreground">{cc.code}</span>
            </Button>
          ))}
        </div>
      )}
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
      <Button
        type="button"
        variant="ghost"
        size="icon"
        onClick={onToggle}
        className="absolute right-1.5 top-1/2 -translate-y-1/2 h-7 w-7 p-0 text-muted-foreground hover:text-foreground"
      >
        {show ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
      </Button>
    </div>
    <FieldError msg={err} />
  </div>
)

/* ─── Account info row ─── */
const InfoRow = ({
  label, value, icon: Icon, dim,
}: { label: string; value: string; icon?: React.ElementType; dim?: boolean }) => (
  <div className="flex items-center justify-between py-2 border-b border-border/40 last:border-none">
    <span className={`flex items-center gap-1.5 text-sm ${dim ? "text-primary" : "text-muted-foreground"}`}>
      {Icon && <Icon className="h-3.5 w-3.5" />}
      {label}
    </span>
    <span className="text-sm text-foreground font-medium">{value}</span>
  </div>
)

/* ════════════════════════════════════════
   PAGE
════════════════════════════════════════ */
export default function ProfilePage() {
  const { user } = useAuth()
  const fileInputRef = useRef<HTMLInputElement>(null)

  const parts  = (user?.displayName || "").trim().split(/\s+/)
  const parsed = parseContactNumber(user?.contactNumber)

  /* form state */
  const [avatarUrl,   setAvatarUrl]   = useState("")
  const [fullName,    setFullName]    = useState(parts.join(" ") || "")
  const [displayName, setDisplayName] = useState(user?.username || "")
  const [email,       setEmail]       = useState(user?.email || "")
  const [company,     setCompany]     = useState(user?.company || "")
  const [location,    setLocation]    = useState("")
  const [website,     setWebsite]     = useState("")
  const [bio,         setBio]         = useState("")
  const [countryCode, setCountryCode] = useState(parsed.code)
  const [phone,       setPhone]       = useState(parsed.number)
  const [saving,      setSaving]      = useState(false)
  const [saved,       setSaved]       = useState(false)

  /* change password (collapsed by default) */
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

  useEffect(() => {
    if (!user) return
    const p = (user.displayName || "").trim().split(/\s+/)
    setFullName(p.join(" ") || "")
    setDisplayName(user.username || "")
    setEmail(user.email || "")
    setCompany(user.company || "")
    const c = parseContactNumber(user.contactNumber)
    setCountryCode(c.code); setPhone(c.number)
  }, [user])

  const handleAvatarChange = (e: ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]
    if (f) setAvatarUrl(URL.createObjectURL(f))
  }

  const handleSave = () => {
    setSaving(true); setSaved(false)
    setTimeout(() => { setSaving(false); setSaved(true); setTimeout(() => setSaved(false), 3000) }, 700)
  }

  const handleCancel = () => {
    if (!user) return
    const p = (user.displayName || "").trim().split(/\s+/)
    setFullName(p.join(" ") || "")
    setDisplayName(user.username || "")
    setEmail(user.email || "")
    setCompany(user.company || "")
    const c = parseContactNumber(user.contactNumber)
    setCountryCode(c.code); setPhone(c.number)
    setBio(""); setLocation(""); setWebsite("")
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

  const initials = displayName?.[0]?.toUpperCase() || fullName?.[0]?.toUpperCase() || "U"
  const joinDate  = user ? "Member" : "—"

  return (
    <div className="space-y-6 p-6">
      <PageHeader title="Profile" description="Manage your account information and preferences" />

      {/* ══ Two-col layout ══ */}
      <div className="flex gap-6 items-start">

        {/* ──────── LEFT: Main form card ──────── */}
        <Card className="flex-1 min-w-0 rounded-xl border border-border/50 bg-card shadow-sm hover:shadow-md transition-all duration-200">

          {/* ── Personal Information section ── */}
          <CardHeader className="p-6 pb-0">
            <div className="flex items-center gap-2 mb-5">
              <User className="h-4 w-4 text-muted-foreground" />
              <div>
                <CardTitle className="text-lg font-semibold text-foreground">Personal Information</CardTitle>
                <p className="text-sm text-muted-foreground">Update your personal details and contact information</p>
              </div>
            </div>

          </CardHeader>

          <CardContent className="space-y-6 p-6 pt-0">
              {/* Row 1: Full Name + Display Name */}
              <div className="grid grid-cols-2 gap-4">
                <FL id="full-name" label="Full Name" required>
                  <Input id="full-name" className="h-9 text-sm" value={fullName} onChange={(e) => setFullName(e.target.value)} placeholder="Admin" />
                </FL>
                <FL id="disp-name" label="Display Name">
                  <Input id="disp-name" className="h-9 text-sm" value={displayName} onChange={(e) => setDisplayName(e.target.value)} placeholder="ad" />
                </FL>
              </div>

              {/* Row 2: Email + Phone */}
              <div className="grid grid-cols-2 gap-4">
                <FL id="email" label="Email Address" icon={Mail} required>
                  <Input id="email" className="h-9 text-sm" type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="admin@company.com" />
                </FL>
                <FL id="phone" label="Phone Number" icon={Phone}>
                  <div className="flex gap-1.5">
                    <CountryCodeSelect value={countryCode} onChange={setCountryCode} />
                    <Input id="phone" className="h-9 text-sm flex-1" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="98765 43210" type="tel" />
                  </div>
                </FL>
              </div>

              {/* Row 3: Company + Location */}
              <div className="grid grid-cols-2 gap-4">
                <FL id="company" label="Company" icon={Building2}>
                  <Input id="company" className="h-9 text-sm" value={company} onChange={(e) => setCompany(e.target.value)} placeholder="Acme Corp" />
                </FL>
                <FL id="location" label="Location" icon={MapPin}>
                  <Input id="location" className="h-9 text-sm" value={location} onChange={(e) => setLocation(e.target.value)} placeholder="Bangalore, India" />
                </FL>
              </div>

              {/* Row 4: Website full-width + Bio */}
              <FL id="website" label="Website" icon={Globe}>
                <Input id="website" className="h-9 text-sm" value={website} onChange={(e) => setWebsite(e.target.value)} placeholder="https://yoursite.com" />
              </FL>

              <FL id="bio" label="Bio">
                <Textarea
                  id="bio"
                  value={bio}
                  onChange={(e) => setBio(e.target.value)}
                  placeholder="A short bio about yourself…"
                  className="min-h-15 resize-none text-sm"
                  maxLength={256}
                />
                <p className="text-[10px] text-muted-foreground text-right">{bio.length}/256</p>
              </FL>
          </CardContent>

          {/* Divider */}
          <div className="border-t border-border/50 mx-6" />

          {/* ── Change Password section ── */}
          <CardHeader className="p-6 pb-0">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Lock className="h-4 w-4 text-muted-foreground" />
                <div>
                  <CardTitle className="text-lg font-semibold text-foreground">Change Password</CardTitle>
                  <p className="text-sm text-muted-foreground">Update your password for enhanced security</p>
                </div>
              </div>
              {!pwOpen && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPwOpen(true)}
                  className="h-8 text-xs gap-1.5 transition-all duration-200"
                >
                  Change Password
                </Button>
              )}
            </div>

          </CardHeader>

          <CardContent className="p-6 pt-4">

            {/* Expanded password fields */}
            {pwOpen && (
              <div className="mt-4 space-y-3">
                {pwSaved && (
                  <div className="flex items-center gap-2 rounded-md border border-primary/20 bg-primary/10 px-3 py-2 text-xs text-primary">
                    <CheckCircle2 className="h-3.5 w-3.5" /> Password changed successfully.
                  </div>
                )}
                <div className="grid grid-cols-3 gap-3">
                  <div className="space-y-1">
                    <Label htmlFor="cur-pw" className="text-xs text-muted-foreground">Current Password</Label>
                    <PwInput id="cur-pw" placeholder="••••••••" value={currentPw} onChange={setCurrentPw} show={showCur} onToggle={() => setShowCur((s) => !s)} err={pwErrors.current} />
                  </div>
                  <div className="space-y-1">
                    <Label htmlFor="new-pw" className="text-xs text-muted-foreground">New Password</Label>
                    <PwInput id="new-pw" placeholder="••••••••" value={newPw} onChange={setNewPw} show={showNew} onToggle={() => setShowNew((s) => !s)} err={pwErrors.newPw} />
                    <PasswordStrength password={newPw} />
                  </div>
                  <div className="space-y-1">
                    <Label htmlFor="con-pw" className="text-xs text-muted-foreground">Confirm Password</Label>
                    <PwInput id="con-pw" placeholder="••••••••" value={confirmPw} onChange={setConfirmPw} show={showCon} onToggle={() => setShowCon((s) => !s)} err={pwErrors.confirm} />
                  </div>
                </div>
                <div className="flex gap-2 pt-1">
                  <Button size="sm" onClick={handlePasswordChange} disabled={pwSaving} className="h-8 text-xs gap-1.5 transition-all duration-200">
                    {pwSaving ? <><Loader2 className="h-3 w-3 animate-spin" />Updating…</> : "Update Password"}
                  </Button>
                  <Button variant="ghost" size="sm" onClick={() => { setPwOpen(false); setCurrentPw(""); setNewPw(""); setConfirmPw(""); setPwErrors({}) }} className="h-8 text-xs transition-all duration-200">
                    Cancel
                  </Button>
                </div>
              </div>
            )}
          </CardContent>

          {/* Bottom action bar */}
          <div className="border-t border-border/50 px-6 py-4 flex items-center justify-end gap-2.5">
            <Button variant="outline" size="sm" onClick={handleCancel} className="h-9 px-5 text-sm">
              Cancel
            </Button>
            <Button size="sm" onClick={handleSave} disabled={saving} className="h-9 px-5 text-sm gap-2 transition-all duration-200">
              {saving ? <><Loader2 className="h-3.5 w-3.5 animate-spin" />Saving…</> : (
                <>
                  {saved ? <CheckCircle2 className="h-3.5 w-3.5" /> : null}
                  Save Changes
                </>
              )}
            </Button>
          </div>
        </Card>

        {/* ──────── RIGHT: Sidebar cards ──────── */}
        <div className="w-60 shrink-0 space-y-6">

          {/* Card 1: Profile */}
          <Card className="rounded-xl border border-border/50 bg-card shadow-sm hover:shadow-md transition-all duration-200">
            <CardContent className="p-5 flex flex-col items-center text-center">
            <div className="relative group">
              <Avatar className="h-16 w-16 ring-2 ring-border">
                {avatarUrl && <AvatarImage src={avatarUrl} alt="Avatar" />}
                <AvatarFallback className="text-xl font-semibold bg-muted text-foreground">{initials}</AvatarFallback>
              </Avatar>
              <Button
                type="button"
                variant="ghost"
                onClick={() => fileInputRef.current?.click()}
                className="absolute inset-0 h-full w-full rounded-full bg-background/80 p-0 opacity-0 group-hover:opacity-100 transition-opacity"
              >
                <Camera className="h-4 w-4 text-foreground" />
              </Button>
              <input ref={fileInputRef} type="file" accept="image/*" className="hidden" onChange={handleAvatarChange} />
            </div>
            <p className="mt-3 text-sm font-semibold">{fullName || "Your Name"}</p>
            <p className="text-xs text-muted-foreground mt-0.5">{email || "email@example.com"}</p>
            <div className="flex items-center gap-1 mt-1.5 text-xs text-muted-foreground">
              <Shield className="h-3 w-3" />
              <span>{displayName || "username"}</span>
            </div>
            </CardContent>
          </Card>

          {/* Card 2: Account Information */}
          <Card className="rounded-xl border border-border/50 bg-card shadow-sm hover:shadow-md transition-all duration-200">
            <CardHeader className="p-4 pb-0">
              <CardTitle className="text-lg font-semibold text-foreground">Account Information</CardTitle>
            </CardHeader>
            <CardContent className="p-4 pt-3">
              <InfoRow label="User ID" value={user?.id ? `${String(user.id).slice(0, 8)}…` : "—"} />
              <InfoRow label="Login ID" value={user?.username || "Not set"} />
              <InfoRow label="Member since" value={joinDate} icon={Calendar} dim />
              <InfoRow label="Last updated" value="Recently" icon={Calendar} dim />
            </CardContent>
          </Card>

          {/* Card 3: Quick Actions */}
          <Card className="rounded-xl border border-border/50 bg-card shadow-sm hover:shadow-md transition-all duration-200">
            <CardHeader className="p-4 pb-0">
              <CardTitle className="text-lg font-semibold text-foreground">Actions</CardTitle>
            </CardHeader>
            <CardContent className="p-4 pt-3">
              <Button
                type="button"
                variant="outline"
                className="w-full justify-start gap-2.5 transition-all duration-200"
                onClick={() => { setPwOpen(true); document.getElementById("cur-pw")?.scrollIntoView({ behavior: "smooth", block: "center" }) }}
              >
                <Lock className="h-4 w-4 text-muted-foreground" />
                Change Password
              </Button>
            </CardContent>
          </Card>

        </div>
      </div>
    </div>
  )
}
