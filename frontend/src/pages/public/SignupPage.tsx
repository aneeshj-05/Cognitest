import {
    useState,
    useRef,
    useEffect,
    type CSSProperties,
    type ReactNode,
} from "react";
import { useNavigate, useLocation, useSearchParams } from "react-router-dom";
import { useForm, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
    Zap,
    Loader2,
    Eye,
    EyeOff,
    ArrowRight,
    Lock,
    Mail,
    User,
    Building2,
    Phone,
    ChevronDown,
    Search,
    CheckCircle2,
} from "lucide-react";
import logoImg from "@/images/logo.png";
import Navbar from "@/components/landing/Navbar";
import { NAV_LINKS } from "@/components/layout/PublicNavbar";

// ── Types ───────────────────────────────────────────────────────────
interface CountryCode {
    code: string;
    iso: string;
    flag: string;
    name: string;
}

interface CountryCodeSelectProps {
    value: string;
    onChange: (value: string) => void;
}

interface FieldProps {
    id: string;
    label: string;
    error?: string;
    children: ReactNode;
}

// ── Country codes ────────────────────────────────────────────────────
const COUNTRY_CODES: CountryCode[] = [
    { code: "+91", iso: "IN", flag: "\u{1F1EE}\u{1F1F3}", name: "India" },
    {
        code: "+1",
        iso: "US",
        flag: "\u{1F1FA}\u{1F1F8}",
        name: "United States",
    },
    { code: "+1", iso: "CA", flag: "\u{1F1E8}\u{1F1E6}", name: "Canada" },
    {
        code: "+44",
        iso: "GB",
        flag: "\u{1F1EC}\u{1F1E7}",
        name: "United Kingdom",
    },
    { code: "+61", iso: "AU", flag: "\u{1F1E6}\u{1F1FA}", name: "Australia" },
    { code: "+49", iso: "DE", flag: "\u{1F1E9}\u{1F1EA}", name: "Germany" },
    { code: "+33", iso: "FR", flag: "\u{1F1EB}\u{1F1F7}", name: "France" },
    { code: "+81", iso: "JP", flag: "\u{1F1EF}\u{1F1F5}", name: "Japan" },
    { code: "+86", iso: "CN", flag: "\u{1F1E8}\u{1F1F3}", name: "China" },
    { code: "+82", iso: "KR", flag: "\u{1F1F0}\u{1F1F7}", name: "South Korea" },
    { code: "+65", iso: "SG", flag: "\u{1F1F8}\u{1F1EC}", name: "Singapore" },
    { code: "+971", iso: "AE", flag: "\u{1F1E6}\u{1F1EA}", name: "UAE" },
    {
        code: "+966",
        iso: "SA",
        flag: "\u{1F1F8}\u{1F1E6}",
        name: "Saudi Arabia",
    },
    { code: "+55", iso: "BR", flag: "\u{1F1E7}\u{1F1F7}", name: "Brazil" },
    { code: "+52", iso: "MX", flag: "\u{1F1F2}\u{1F1FD}", name: "Mexico" },
    {
        code: "+27",
        iso: "ZA",
        flag: "\u{1F1FF}\u{1F1E6}",
        name: "South Africa",
    },
    { code: "+234", iso: "NG", flag: "\u{1F1F3}\u{1F1EC}", name: "Nigeria" },
    { code: "+254", iso: "KE", flag: "\u{1F1F0}\u{1F1EA}", name: "Kenya" },
    { code: "+62", iso: "ID", flag: "\u{1F1EE}\u{1F1E9}", name: "Indonesia" },
    { code: "+60", iso: "MY", flag: "\u{1F1F2}\u{1F1FE}", name: "Malaysia" },
    { code: "+63", iso: "PH", flag: "\u{1F1F5}\u{1F1ED}", name: "Philippines" },
    { code: "+66", iso: "TH", flag: "\u{1F1F9}\u{1F1ED}", name: "Thailand" },
    { code: "+84", iso: "VN", flag: "\u{1F1FB}\u{1F1F3}", name: "Vietnam" },
    { code: "+880", iso: "BD", flag: "\u{1F1E7}\u{1F1E9}", name: "Bangladesh" },
    { code: "+94", iso: "LK", flag: "\u{1F1F1}\u{1F1F0}", name: "Sri Lanka" },
    { code: "+977", iso: "NP", flag: "\u{1F1F3}\u{1F1F5}", name: "Nepal" },
    { code: "+92", iso: "PK", flag: "\u{1F1F5}\u{1F1F0}", name: "Pakistan" },
    { code: "+39", iso: "IT", flag: "\u{1F1EE}\u{1F1F9}", name: "Italy" },
    { code: "+34", iso: "ES", flag: "\u{1F1EA}\u{1F1F8}", name: "Spain" },
    { code: "+31", iso: "NL", flag: "\u{1F1F3}\u{1F1F1}", name: "Netherlands" },
    { code: "+46", iso: "SE", flag: "\u{1F1F8}\u{1F1EA}", name: "Sweden" },
    { code: "+41", iso: "CH", flag: "\u{1F1E8}\u{1F1ED}", name: "Switzerland" },
    { code: "+47", iso: "NO", flag: "\u{1F1F3}\u{1F1F4}", name: "Norway" },
    { code: "+48", iso: "PL", flag: "\u{1F1F5}\u{1F1F1}", name: "Poland" },
    { code: "+7", iso: "RU", flag: "\u{1F1F7}\u{1F1FA}", name: "Russia" },
    { code: "+90", iso: "TR", flag: "\u{1F1F9}\u{1F1F7}", name: "Turkey" },
    { code: "+20", iso: "EG", flag: "\u{1F1EA}\u{1F1EC}", name: "Egypt" },
    { code: "+64", iso: "NZ", flag: "\u{1F1F3}\u{1F1FF}", name: "New Zealand" },
    { code: "+353", iso: "IE", flag: "\u{1F1EE}\u{1F1EA}", name: "Ireland" },
    { code: "+972", iso: "IL", flag: "\u{1F1EE}\u{1F1F1}", name: "Israel" },
];

// ── Zod schema ───────────────────────────────────────────────────────
const signupSchema = z.object({
    fullName: z
        .string()
        .min(3, { message: "Full name must be at least 3 characters" })
        .max(100)
        .refine((v) => /^[A-Za-z\s]+$/.test(v.trim()), {
            message: "Name must contain only letters",
        }),
    email: z
        .string()
        .min(1, { message: "Email is required" })
        .email({ message: "Must be a valid email address" })
        .toLowerCase(),
    password: z
        .string()
        .min(8, { message: "Password must be at least 8 characters" })
        .max(50),
    companyName: z.string().min(1, { message: "Company name is required" }),
    countryCode: z.string(),
    contactNumber: z
        .string()
        .optional()
        .refine((val) => !val || /^\d{6,14}$/.test(val.replace(/\s+/g, "")), {
            message: "Enter a valid contact number (6–14 digits)",
        }),
});

type SignupFormValues = z.infer<typeof signupSchema>;

// ── CountryCodeSelect ────────────────────────────────────────────────
const CountryCodeSelect = ({ value, onChange }: CountryCodeSelectProps) => {
    const [open, setOpen] = useState(false);
    const [search, setSearch] = useState("");
    const ref = useRef<HTMLDivElement | null>(null);
    const searchRef = useRef<HTMLInputElement | null>(null);

    const selected =
        COUNTRY_CODES.find((c) => `${c.code}-${c.iso}` === value) ||
        COUNTRY_CODES[0];

    useEffect(() => {
        const handler = (e: MouseEvent) => {
            if (
                ref.current &&
                e.target instanceof Node &&
                !ref.current.contains(e.target)
            )
                setOpen(false);
        };
        document.addEventListener("mousedown", handler);
        return () => document.removeEventListener("mousedown", handler);
    }, []);

    useEffect(() => {
        if (open && searchRef.current) searchRef.current.focus();
    }, [open]);

    const filtered = COUNTRY_CODES.filter((c) => {
        const q = search.toLowerCase();
        return (
            c.name.toLowerCase().includes(q) ||
            c.iso.toLowerCase().includes(q) ||
            c.code.includes(q)
        );
    });

    return (
        <div ref={ref} className="relative">
            <button
                type="button"
                onClick={() => {
                    setOpen((o) => !o);
                    setSearch("");
                }}
                className="flex items-center gap-1.5 h-11 rounded-md border border-border bg-background px-3 text-sm font-medium hover:bg-muted/50 transition-colors min-w-[120px] cursor-pointer">
                <span className="text-base leading-none">{selected.flag}</span>
                <span className="text-muted-foreground">{selected.iso}</span>
                <span>{selected.code}</span>
                <ChevronDown className="h-3.5 w-3.5 ml-auto text-muted-foreground" />
            </button>

            {open && (
                <div className="absolute left-0 top-full mt-1 z-50 w-64 rounded-lg border border-border bg-background shadow-xl">
                    <div className="flex items-center gap-2 px-3 py-2 border-b border-border">
                        <Search className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                        <input
                            ref={searchRef}
                            type="text"
                            placeholder="Search country..."
                            value={search}
                            onChange={(e) => setSearch(e.target.value)}
                            className="w-full bg-transparent text-sm outline-none placeholder:text-muted-foreground"
                        />
                    </div>
                    <div className="max-h-52 overflow-y-auto py-1">
                        {filtered.length === 0 && (
                            <p className="text-xs text-muted-foreground text-center py-3">
                                No results
                            </p>
                        )}
                        {filtered.map((c) => {
                            const key = `${c.code}-${c.iso}`;
                            const isActive = key === value;
                            return (
                                <button
                                    key={key}
                                    type="button"
                                    onClick={() => {
                                        onChange(key);
                                        setOpen(false);
                                    }}
                                    className={`flex items-center gap-2.5 w-full px-3 py-2 text-sm transition-colors cursor-pointer ${
                                        isActive
                                            ? "bg-emerald-500/10 text-emerald-600 font-medium"
                                            : "hover:bg-muted/50"
                                    }`}>
                                    <span className="text-base leading-none">
                                        {c.flag}
                                    </span>
                                    <span className="flex-1 text-left truncate">
                                        {c.name}
                                    </span>
                                    <span className="text-xs text-muted-foreground">
                                        {c.iso}
                                    </span>
                                    <span className="text-xs font-medium tabular-nums">
                                        {c.code}
                                    </span>
                                </button>
                            );
                        })}
                    </div>
                </div>
            )}
        </div>
    );
};

// ── Field wrapper ────────────────────────────────────────────────────
const Field = ({ id, label, error, children }: FieldProps) => (
    <div className="space-y-1.5">
        <label
            htmlFor={id}
            className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
            {label}
        </label>
        {children}
        {error && <p className="text-xs text-red-400 mt-0.5">{error}</p>}
    </div>
);

// ── Decorative Left Panel ────────────────────────────────────────────
// Colors extracted from the app screenshot:
//   Sidebar bg:  #0f1623  (very dark navy-black)
//   Green accent: #10b981 (emerald-500, matches Run Tests / Generate Tests buttons)
//   Text on dark: white / slate-400

const GREEN = "#10b981";
const GREEN_DIM = "rgba(16,185,129,0.15)";
const GREEN_BORDER = "rgba(16,185,129,0.25)";
const PANEL_BG = "#0f1623";
const PANEL_STRIPE = "#131d2e";

const BrandingPanel = () => {
    const features = [
        "Generate tests from Swagger / OpenAPI specs",
        "Execute & track API tests in real time",
        "Collaborate across your team workspace",
    ];

    return (
        <div
            className="hidden lg:flex w-1/2 relative overflow-hidden shrink-0 flex-col"
            style={{ background: PANEL_BG }}>
            {/* Vertical stripe texture — same pattern as reference component */}
            <div className="absolute inset-0 flex overflow-hidden pointer-events-none">
                {[...Array(10)].map((_, i) => (
                    <div
                        key={i}
                        className="flex-1 h-full"
                        style={{
                            background: i % 2 === 0 ? PANEL_STRIPE : PANEL_BG,
                            opacity: 0.5,
                        }}
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
            <svg
                className="absolute inset-0 w-full h-full pointer-events-none"
                style={{ opacity: 0.035 }}>
                <defs>
                    <pattern
                        id="grid"
                        width="36"
                        height="36"
                        patternUnits="userSpaceOnUse">
                        <path
                            d="M 36 0 L 0 0 0 36"
                            fill="none"
                            stroke="white"
                            strokeWidth="0.6"
                        />
                    </pattern>
                </defs>
                <rect width="100%" height="100%" fill="url(#grid)" />
            </svg>

            {/* Single diagonal accent line */}
            <svg
                className="absolute inset-0 w-full h-full pointer-events-none"
                style={{ opacity: 0.06 }}
                preserveAspectRatio="none">
                <line
                    x1="0"
                    y1="100%"
                    x2="100%"
                    y2="0"
                    stroke={GREEN}
                    strokeWidth="1.5"
                />
            </svg>

            {/* Floating HTTP method badges — behind text (z-0), white transparent */}
            <style>{`
        @keyframes floatBadge {
          0%   { transform: translateY(0px) rotate(var(--rot)); opacity: 0; }
          10%  { opacity: 1; }
          90%  { opacity: 1; }
          100% { transform: translateY(-680px) rotate(var(--rot)); opacity: 0; }
        }
      `}</style>
            <div
                className="absolute inset-0 overflow-hidden pointer-events-none"
                style={{ zIndex: 1 }}>
                {[
                    {
                        method: "GET",
                        left: "8%",
                        bottom: "-60px",
                        duration: 22,
                        delay: 0,
                        rot: "-6deg",
                        size: "text-[11px]",
                    },
                    {
                        method: "POST",
                        left: "28%",
                        bottom: "-60px",
                        duration: 28,
                        delay: 4,
                        rot: "4deg",
                        size: "text-[10px]",
                    },
                    {
                        method: "DELETE",
                        left: "52%",
                        bottom: "-60px",
                        duration: 24,
                        delay: 8,
                        rot: "-3deg",
                        size: "text-[11px]",
                    },
                    {
                        method: "PUT",
                        left: "72%",
                        bottom: "-60px",
                        duration: 30,
                        delay: 2,
                        rot: "7deg",
                        size: "text-[10px]",
                    },
                    {
                        method: "PATCH",
                        left: "18%",
                        bottom: "-60px",
                        duration: 26,
                        delay: 12,
                        rot: "-5deg",
                        size: "text-[11px]",
                    },
                    {
                        method: "GET",
                        left: "62%",
                        bottom: "-60px",
                        duration: 20,
                        delay: 16,
                        rot: "3deg",
                        size: "text-[10px]",
                    },
                    {
                        method: "POST",
                        left: "40%",
                        bottom: "-60px",
                        duration: 32,
                        delay: 6,
                        rot: "-8deg",
                        size: "text-[11px]",
                    },
                    {
                        method: "DELETE",
                        left: "82%",
                        bottom: "-60px",
                        duration: 25,
                        delay: 18,
                        rot: "5deg",
                        size: "text-[10px]",
                    },
                    {
                        method: "PATCH",
                        left: "5%",
                        bottom: "-60px",
                        duration: 29,
                        delay: 9,
                        rot: "6deg",
                        size: "text-[11px]",
                    },
                    {
                        method: "PUT",
                        left: "48%",
                        bottom: "-60px",
                        duration: 23,
                        delay: 21,
                        rot: "-4deg",
                        size: "text-[10px]",
                    },
                ].map((b, i) => (
                    <div
                        key={i}
                        className={`absolute font-bold tracking-widest uppercase ${b.size}`}
                        style={
                            {
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
                            } as CSSProperties & { "--rot": string }
                        }>
                        {b.method}
                    </div>
                ))}
            </div>

            {/* Content */}
            <div className="relative z-10 flex flex-col justify-between h-full px-10 xl:px-14 py-12">
                {/* Top: Logo — uses actual app logo */}
                <div className="flex items-center gap-2.5">
                    <img src={logoImg} alt="Cognitest" className="h-9 w-auto" />
                </div>

                {/* Middle: Headline + features */}
                <div className="space-y-7">
                    <div className="space-y-4">
                        {/* Eyebrow pill */}
                        <span
                            className="inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-widest"
                            style={{
                                background: GREEN_DIM,
                                color: GREEN,
                                border: `1px solid ${GREEN_BORDER}`,
                            }}>
                            <span
                                className="w-1.5 h-1.5 rounded-full"
                                style={{ background: GREEN }}
                            />
                            API Testing Platform
                        </span>

                        <h1 className="text-3xl xl:text-4xl font-extrabold tracking-tight leading-[1.15] text-white">
                            Create your
                            <br />
                            <span style={{ color: GREEN }}>Cognitest</span>{" "}
                            workspace
                        </h1>

                        <p
                            className="text-sm leading-relaxed max-w-xs"
                            style={{ color: "#94a3b8" }}>
                            Generate, execute, and track API tests from your
                            Swagger or OpenAPI spec — all in one place.
                        </p>
                    </div>

                    {/* Checklist */}
                    <ul className="space-y-3">
                        {features.map((feat) => (
                            <li key={feat} className="flex items-start gap-2.5">
                                <CheckCircle2
                                    className="h-4 w-4 mt-0.5 shrink-0"
                                    style={{ color: GREEN }}
                                />
                                <span
                                    className="text-sm"
                                    style={{ color: "#94a3b8" }}>
                                    {feat}
                                </span>
                            </li>
                        ))}
                    </ul>
                </div>

                {/* Bottom: spacer so content stays vertically balanced */}
                <div />
            </div>
        </div>
    );
};

// ── Page ─────────────────────────────────────────────────────────────
const SignupPage = () => {
    const navigate = useNavigate();
    const location = useLocation();
    const { signup: authSignup } = useAuth();
    const [showPw, setShowPw] = useState(false);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");

    const [searchParams] = useSearchParams();
    const inviteToken = searchParams.get("inviteToken");

    const {
        register,
        handleSubmit,
        control,
        formState: { errors },
    } = useForm<SignupFormValues>({
        resolver: zodResolver(signupSchema),
        defaultValues: {
            fullName: "",
            email: "",
            password: "",
            companyName: "",
            countryCode: `${COUNTRY_CODES[0].code}-${COUNTRY_CODES[0].iso}`,
            contactNumber: "",
        },
    });

    const onSubmit = async (data: SignupFormValues) => {
        setError("");
        setLoading(true);
        try {
            const selectedCountry =
                COUNTRY_CODES.find(
                    (c) => `${c.code}-${c.iso}` === data.countryCode,
                ) || COUNTRY_CODES[0];
            const fullContactNumber =
                data.contactNumber && data.contactNumber.trim() !== ""
                    ? `${selectedCountry.code}${data.contactNumber.replace(/[^0-9]/g, "")}`
                    : undefined;

            const result = await authSignup({
                email: data.email.trim(),
                name: data.fullName.trim(),
                passcode: data.password,
                company: data.companyName.trim() || undefined,
                contactNumber: fullContactNumber,
                inviteToken: inviteToken || undefined,
            });

            if (!result.success) {
                throw new Error(result.error || "Signup failed");
            }

            navigate("/verify-otp", { state: { email: data.email.trim(), inviteToken } });
        } catch (err) {
            setError(err instanceof Error ? err.message : "Signup failed");
        } finally {
            setLoading(false);
        }
    };

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
    ];

    return (
        <>
            <style>{`
        @keyframes floatUp {
          0%   { transform: translateY(0)   scale(1);   opacity: 0;   }
          10%  { opacity: 0.7; }
          90%  { opacity: 0.4; }
          100% { transform: translateY(-100vh) scale(0.6); opacity: 0; }
        }
      `}</style>

            <div
                className="fixed inset-0 z-40 flex flex-col overflow-hidden bg-[#f8fbff] text-black">
                <Navbar pathname={location.pathname} navLinks={NAV_LINKS} variant="light" />

                <div
                    className="absolute inset-0 pointer-events-none overflow-hidden"
                    style={{ zIndex: 0 }}>
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

                <div
                    className="absolute bottom-0 left-0 right-0 pointer-events-none"
                    style={{
                        zIndex: 0,
                        height: "65%",
                        background:
                            "linear-gradient(to top, rgba(16,185,129,0.22) 0%, rgba(16,185,129,0.12) 25%, rgba(16,185,129,0.05) 60%, transparent 100%)",
                    }}
                />

                <div
                    className="flex flex-1 items-center justify-center p-6"
                    style={{ zIndex: 10, position: "relative" }}>
                    <div
                        className="flex w-full max-w-5xl overflow-hidden shadow-2xl"
                        style={{
                            borderRadius: "1.25rem",
                            maxHeight: "calc(100dvh - 3rem)",
                        }}>
                        <BrandingPanel />

                        <div className="flex-1 overflow-y-auto bg-white">
                            <div className="flex min-h-full items-center justify-center px-8 py-10 sm:px-12">
                                <div className="w-full max-w-sm space-y-5">
                                    <div className="lg:hidden flex items-center gap-2.5 mb-2">
                                        <div
                                            className="flex h-9 w-9 items-center justify-center rounded-xl"
                                            style={{ background: "#10b981" }}>
                                            <Zap className="h-[18px] w-[18px] text-white" />
                                        </div>
                                        <span className="text-lg font-bold">
                                            Cognitest
                                        </span>
                                    </div>

                                    <div>
                                        <h2 className="text-2xl font-bold tracking-tight text-gray-900">
                                            Create account
                                        </h2>
                                        <p className="mt-1 text-sm text-gray-500">
                                            Sign up to start using Cognitest
                                        </p>
                                    </div>

                                    {error && (
                                        <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-600">
                                            {error}
                                        </div>
                                    )}

                                    <form
                                        onSubmit={handleSubmit(onSubmit)}
                                        className="space-y-3.5">
                                        <Field
                                            id="signup-fullname"
                                            label="Full Name"
                                            error={errors.fullName?.message}>
                                            <div className="relative">
                                                <User className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
                                                <Input
                                                    id="signup-fullname"
                                                    type="text"
                                                    placeholder="John Doe"
                                                    className="h-11 pl-10 border-gray-200 bg-gray-50 focus:bg-white focus:border-emerald-400 focus:ring-emerald-400/20 text-gray-900"
                                                    {...register("fullName")}
                                                />
                                            </div>
                                        </Field>

                                        <Field
                                            id="signup-email"
                                            label="Email"
                                            error={errors.email?.message}>
                                            <div className="relative">
                                                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
                                                <Input
                                                    id="signup-email"
                                                    type="email"
                                                    placeholder="name@company.com"
                                                    className="h-11 pl-10 border-gray-200 bg-gray-50 focus:bg-white focus:border-emerald-400 focus:ring-emerald-400/20 text-gray-900"
                                                    {...register("email")}
                                                />
                                            </div>
                                        </Field>

                                        <Field
                                            id="signup-password"
                                            label="Password"
                                            error={errors.password?.message}>
                                            <div className="relative">
                                                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
                                                <Input
                                                    id="signup-password"
                                                    type={
                                                        showPw
                                                            ? "text"
                                                            : "password"
                                                    }
                                                    placeholder="Min. 8 characters"
                                                    className="h-11 pl-10 pr-10 border-gray-200 bg-gray-50 focus:bg-white focus:border-emerald-400 focus:ring-emerald-400/20 text-gray-900"
                                                    {...register("password")}
                                                />
                                                <button
                                                    type="button"
                                                    onClick={() =>
                                                        setShowPw((p) => !p)
                                                    }
                                                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-700 transition-colors cursor-pointer">
                                                    {showPw ? (
                                                        <EyeOff className="h-4 w-4" />
                                                    ) : (
                                                        <Eye className="h-4 w-4" />
                                                    )}
                                                </button>
                                            </div>
                                        </Field>

                                        <Field
                                            id="signup-company"
                                            label="Company Name"
                                            error={errors.companyName?.message}>
                                            <div className="relative">
                                                <Building2 className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
                                                <Input
                                                    id="signup-company"
                                                    type="text"
                                                    placeholder="Your organization"
                                                    className="h-11 pl-10 border-gray-200 bg-gray-50 focus:bg-white focus:border-emerald-400 focus:ring-emerald-400/20 text-gray-900"
                                                    {...register("companyName")}
                                                />
                                            </div>
                                        </Field>

                                        <Field
                                            id="signup-contact"
                                            label="Contact Number (Optional)"
                                            error={
                                                errors.contactNumber?.message
                                            }>
                                            <div className="flex gap-2">
                                                <Controller
                                                    name="countryCode"
                                                    control={control}
                                                    render={({ field }) => (
                                                        <CountryCodeSelect
                                                            value={field.value}
                                                            onChange={
                                                                field.onChange
                                                            }
                                                        />
                                                    )}
                                                />
                                                <div className="relative flex-1">
                                                    <Phone className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
                                                    <Input
                                                        id="signup-contact"
                                                        type="tel"
                                                        inputMode="numeric"
                                                        placeholder="123 456 7890"
                                                        className="h-11 pl-10 border-gray-200 bg-white focus:bg-white focus:border-emerald-400 focus:ring-emerald-400/20 text-gray-900"
                                                        {...register(
                                                            "contactNumber",
                                                            {
                                                                onChange: (
                                                                    e,
                                                                ) => {
                                                                    e.target.value =
                                                                        e.target.value.replace(
                                                                            /[^0-9\s]/g,
                                                                            "",
                                                                        );
                                                                },
                                                            },
                                                        )}
                                                    />
                                                </div>
                                            </div>
                                        </Field>

                                        <div className="pt-1 space-y-3">
                                            <Button
                                                type="submit"
                                                disabled={loading}
                                                className="w-full h-11 gap-2 text-white text-sm font-semibold cursor-pointer transition-colors"
                                                style={{
                                                    background: "#10b981",
                                                }}
                                                onMouseEnter={(e) =>
                                                    (e.currentTarget.style.background =
                                                        "#059669")
                                                }
                                                onMouseLeave={(e) =>
                                                    (e.currentTarget.style.background =
                                                        "#10b981")
                                                }>
                                                {loading ? (
                                                    <>
                                                        <Loader2 className="h-4 w-4 animate-spin" />{" "}
                                                        Creating...
                                                    </>
                                                ) : (
                                                    <>
                                                        Create Account{" "}
                                                        <ArrowRight className="h-4 w-4" />
                                                    </>
                                                )}
                                            </Button>

                                            <button
                                                type="button"
                                                onClick={() =>
                                                    navigate(inviteToken ? `/login?inviteToken=${inviteToken}` : "/login")
                                                }
                                                className="w-full text-sm text-gray-500 hover:text-gray-800 transition-colors text-center cursor-pointer">
                                                Already have an account?{" "}
                                                <span className="font-semibold text-gray-800">
                                                    Sign in
                                                </span>
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
    );
};

export default SignupPage;
