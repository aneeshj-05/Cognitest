import { useEffect, useMemo, useRef, useState, useCallback } from "react"
import { useToast } from "@/components/ui/toast"
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Progress } from "@/components/ui/progress"
import {
    CheckCircle2, XCircle, RefreshCw, Play, Terminal,
    ChevronDown, Eye, AlertTriangle, Sparkles, Clock, Loader2,
    Maximize2, Minimize2, X, KeyRound, ChevronUp,
    OctagonAlert, MinusCircle, ShieldCheck, ShieldAlert,
} from "lucide-react"
import { analyzeFailure } from "@/services/backendClient"
import { API_BASE_URL, DEFAULT_LOCAL_TARGET_URL } from "@/config/runtime"

// ─── Types ───────────────────────────────────────────────────────────────────

interface StreamEvent {
    event: "start" | "result" | "done" | "banner"
    | "context_update"
    total?: number
    index?: number
    id?: string
    name?: string
    endpoint_path?: string
    method?: string
    expected_status?: number
    expected_statuses?: Array<string | number>
    actual_status?: number
    passed?: boolean
    inconclusive?: boolean
    log?: string
    failed?: number
    // setup/session phase fields
    step?: string
    status?: "ok" | "fail" | "pending" | "skip"
    // Enriched data
    response_time_ms?: number
    response_body?: string
    response_headers?: Record<string, string>
    error_message?: string
    request_headers?: Record<string, string> | null
    request_body?: Record<string, unknown> | null
    context?: Record<string, string>
    query_params?: Record<string, unknown> | null
    test_type?: string
    requires_auth?: boolean
    auth_provided?: boolean
    violations?: ContractViolation[]
    severity?: string
    // Workflow step variable snapshots
    extracted_vars?: Record<string, unknown> | null
    injected_vars?: Record<string, unknown> | null
    // ── Three-layer semantic fields (stateful contract backend) ──────────────
    // execution_status: runtime layer — EXECUTED | SKIPPED | TRANSPORT_ERROR | TIMEOUT | CONFIG_ERROR
    // validation_status: contract layer — PASS | FAIL | WARNING | NOT_EVALUATED | VALIDATOR_ERROR
    // final_status:      derived outcome — PASS | FAIL | WARNING | ERROR | SKIPPED
    execution_status?: string
    validation_status?: string
    final_status?: string
    // error_category distinguishes ERROR sub-types without changing final_status
    // values: runtime.transport | runtime.timeout | config.op_missing | engine.validator_crash
    error_category?: string | null
    skip_reason?: string | null
}

interface TestRow {
    id: string
    name: string
    endpoint_path: string
    method: string
    expected_status: number
    actual_status?: number
    status: "pending" | "pass" | "fail"
    pass_tone?: "green" | "yellow"
    // Enriched data
    response_time_ms?: number
    response_body?: string
    response_headers?: Record<string, string>
    error_message?: string
    request_headers?: Record<string, string> | null
    request_body?: Record<string, unknown> | null
    query_params?: Record<string, unknown> | null
    violations?: ContractViolation[]
    test_type?: string
    requires_auth?: boolean
    auth_provided?: boolean
    // Workflow step variable snapshots
    extracted_vars?: Record<string, unknown> | null
    injected_vars?: Record<string, unknown> | null
    // ── Three-layer semantic fields ──────────────────────────────────────────
    execution_status?: string
    validation_status?: string
    final_status?: string
    error_category?: string | null
    skip_reason?: string | null
}

interface ContractViolation {
    code: string
    // violation carries the normalised taxonomy type: contract.schema, contract.drift, etc.
    violation?: string
    severity: "HIGH" | "MEDIUM" | "LOW" | "CRITICAL"
    method: string
    path: string
    expected_statuses: Array<string | number>
    actual_status?: number | null
    security_required: boolean
    auth_provided: boolean
    content_type?: string | null
    schema_validation_errors?: string[] | null
}

interface AIAnalysis {
    root_cause: string
    explanation: string
    suggested_fix: string
    severity: "critical" | "high" | "medium" | "low"
}

interface RunSuiteModalProps {
    open: boolean
    onOpenChange: (open: boolean) => void
    projectId: string
    testCount: number
    baseUrl?: string
    testType?: string
    caseId?: string
    caseIds?: string[]
    onComplete?: (summary: { passed: number; failed: number }) => void
}

const SEVERITY_COLORS: Record<string, string> = {
    critical: "text-red-200 bg-red-500/25 border-red-500/55",
    high: "text-orange-200 bg-orange-500/20 border-orange-500/50",
    medium: "text-yellow-200 bg-yellow-500/20 border-yellow-500/45",
    low: "text-blue-200 bg-blue-500/20 border-blue-500/45",
}

const MAX_RESPONSE_LOG = 450

const normalizeExpectedStatuses = (event: StreamEvent): number[] => {
    const raw = (event as any)?.expected_statuses
    const parts: string[] = []

    const pushTokenized = (value: unknown) => {
        if (value === undefined || value === null) return
        const str = String(value)
        // Some backends send ["200, 401, 404"] (single string) instead of ["200","401","404"].
        str.split(",").forEach((p) => {
            const t = p.trim()
            if (t) parts.push(t)
        })
    }

    if (Array.isArray(raw)) {
        raw.forEach(pushTokenized)
    } else {
        pushTokenized(raw)
    }

    const nums = parts
        .map((p) => Number(p))
        .filter((n) => Number.isFinite(n))

    if (nums.length > 0) return nums

    const fallback = (event as any)?.expected_status
    const n = Number(fallback)
    return Number.isFinite(n) ? [n] : []
}

const formatExpectedStatuses = (event: StreamEvent) => {
    const expectedNums = normalizeExpectedStatuses(event)
    if (expectedNums.length > 0) return expectedNums.map(String).join(", ")
    const expectedRaw = (event as any)?.expected_statuses
    if (expectedRaw) return Array.isArray(expectedRaw) ? expectedRaw.map(String).join(", ") : String(expectedRaw)
    if ((event as any)?.expected_status !== undefined) return String((event as any)?.expected_status)
    return "unknown"
}

type NormalizedTestType = "positive" | "negative" | "contract" | null

const normalizeTestType = (raw?: string): NormalizedTestType => {
    if (!raw) return null
    const v = String(raw).trim().toLowerCase()
    if (v === "positive") return "positive"
    if (v === "negative") return "negative"
    if (v === "contract") return "contract"
    return null
}

const pickContractExpectedSuccess = (event: StreamEvent, expectedNums: number[]): number | null => {
    const n = Number((event as any)?.expected_status)
    if (Number.isFinite(n)) return n
    // Fallback: first expected status (backend should provide expected_status for contract tests)
    return expectedNums.length > 0 ? expectedNums[0] : null
}

const classifyResult = (event: StreamEvent) => {
    const expectedNums = normalizeExpectedStatuses(event)
    const actualRaw = (event as any)?.actual_status
    const actual = actualRaw === undefined || actualRaw === null ? NaN : Number(actualRaw)
    const testType = normalizeTestType((event as any)?.test_type)

    // ── Semantic-first path (new stateful contract backend) ──────────────────
    // When the backend provides final_status, use it directly as the single
    // source of truth.  This honours the three-layer architecture and avoids
    // re-implementing backend contract-validation logic on the frontend.
    const finalStatus = (event as any)?.final_status as string | undefined
    if (finalStatus) {
        if (finalStatus === "PASS") {
            return { status: "pass" as const, pass_tone: "green" as const, isYellowPass: false, expectedNums, actual, testType }
        }
        if (finalStatus === "WARNING") {
            return { status: "pass" as const, pass_tone: "yellow" as const, isYellowPass: true, expectedNums, actual, testType }
        }
        // FAIL, ERROR, SKIPPED all map to the "fail" visual bucket.
        // The row display layer uses execution_status / final_status to
        // distinguish ERROR and SKIPPED from true contract failures.
        return { status: "fail" as const, pass_tone: undefined, isYellowPass: false, expectedNums, actual, testType }
    }

    // ── Legacy / backward-compat path (no final_status provided) ────────────
    const expectedIncludesActual = Number.isFinite(actual) && expectedNums.includes(actual)
    const actualIs2xx = Number.isFinite(actual) && actual >= 200 && actual < 300
    const hasAny2xxExpected = expectedNums.some((n) => n >= 200 && n < 300)

    // Default fallback: rely on backend passed flag.
    if (!testType || !Number.isFinite(actual) || expectedNums.length === 0) {
        const passed = Boolean((event as any)?.passed)
        return {
            status: passed ? ("pass" as const) : ("fail" as const),
            pass_tone: passed ? ("green" as const) : undefined,
            isYellowPass: false,
            expectedNums, actual, testType,
        }
    }

    // Contract tests: must match explicit success code exactly.
    if (testType === "contract") {
        const expectedSuccess = pickContractExpectedSuccess(event, expectedNums)
        const ok = expectedSuccess !== null && actual === expectedSuccess
        return {
            status: ok ? ("pass" as const) : ("fail" as const),
            pass_tone: ok ? ("green" as const) : undefined,
            isYellowPass: false,
            expectedNums, actual, testType,
        }
    }

    // Negative tests
    if (testType === "negative") {
        const ok = expectedIncludesActual
        return {
            status: ok ? ("pass" as const) : ("fail" as const),
            pass_tone: ok ? ("green" as const) : undefined,
            isYellowPass: false,
            expectedNums, actual, testType,
        }
    }

    // Positive tests: FAIL > Yellow PASS > Green PASS
    if (!expectedIncludesActual) {
        return { status: "fail" as const, pass_tone: undefined, isYellowPass: false, expectedNums, actual, testType }
    }
    if (actualIs2xx) {
        return { status: "pass" as const, pass_tone: "green" as const, isYellowPass: false, expectedNums, actual, testType }
    }
    if (hasAny2xxExpected) {
        return { status: "pass" as const, pass_tone: "yellow" as const, isYellowPass: true, expectedNums, actual, testType }
    }
    return { status: "pass" as const, pass_tone: "green" as const, isYellowPass: false, expectedNums, actual, testType }
}

const truncateForLog = (value: string, maxLen: number) => {
    const trimmed = value.trim()
    if (trimmed.length <= maxLen) return trimmed
    return `${trimmed.slice(0, maxLen)}…`
}

// Return the single most-severe violation from the list.
// When multiple violations exist, the primary type is the highest-severity
// one so that the compact display (chip + console line) reflects the actual
// reason for FAIL rather than whichever violation happens to be first.
const _SEVERITY_RANK: Record<string, number> = { CRITICAL: 4, HIGH: 3, MEDIUM: 2, LOW: 1 }

const getPrimaryViolation = (violations?: ContractViolation[]): ContractViolation | undefined => {
    if (!violations || violations.length === 0) return undefined
    return violations.reduce((worst, v) => {
        const w = _SEVERITY_RANK[worst?.severity ?? ""] ?? 3
        const c = _SEVERITY_RANK[v?.severity ?? ""] ?? 3
        return c > w ? v : worst
    }, violations[0])
}

function parseJwtUserId(token: string): string | null {
    if (!token) return null
    try {
        const parts = token.split('.')
        if (parts.length !== 3) return null
        const base64Url = parts[1]
        const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/')
        const jsonPayload = decodeURIComponent(atob(base64).split('').map(function (c) {
            return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2)
        }).join(''))
        const payload = JSON.parse(jsonPayload)
        return String(payload.id || payload.sub || payload.userId || payload.user_id || "") || null
    } catch {
        return null
    }
}

// ─── Payload Viewer ──────────────────────────────────────────────────────────

function PayloadViewer({ label, data }: { label: string; data: unknown }) {
    if (!data || (typeof data === "object" && Object.keys(data as object).length === 0)) {
        return null
    }
    return (
        <div className="mb-2">
            <span className="text-[10px] font-semibold uppercase text-muted-foreground tracking-wider">{label}</span>
            <pre className="mt-1 p-2 rounded-md bg-[#0d1117] text-xs text-slate-300 overflow-x-auto max-h-40 border border-white/5 font-mono leading-relaxed">
                {typeof data === "string" ? data : JSON.stringify(data, null, 2)}
            </pre>
        </div>
    )
}

// ─── Component ───────────────────────────────────────────────────────────────

export function RunSuiteModal({
    open,
    onOpenChange,
    projectId,
    testCount,
    baseUrl = DEFAULT_LOCAL_TARGET_URL,
    testType = "Security",
    caseId,
    caseIds,
    onComplete,
}: RunSuiteModalProps) {
    console.log("[RunSuiteModal] testType prop:", testType)
    const [rows, setRows] = useState<TestRow[]>([])
    const [logs, setLogs] = useState<string[]>([])
    const [progress, setProgress] = useState<number>(0)
    const [total, setTotal] = useState<number>(testCount)
    const [running, setRunning] = useState<boolean>(false)
    const [finished, setFinished] = useState<boolean>(false)
    const [summary, setSummary] = useState<{ passed: number; failed: number } | null>(null)
    const [targetUrl, setTargetUrl] = useState<string>(baseUrl)
    const [expandedRowId, setExpandedRowId] = useState<string | null>(null)
    const [selectedRow, setSelectedRow] = useState<TestRow | null>(null)
    const [aiAnalyses, setAiAnalyses] = useState<Record<string, AIAnalysis>>({})
    const [analyzingId, setAnalyzingId] = useState<string | null>(null)
    const [maximized, setMaximized] = useState<boolean>(false)
    const [dialogMaximized, setDialogMaximized] = useState<boolean>(false)
    const [hasLoadedCases, setHasLoadedCases] = useState<boolean>(false)
    // ── Session-level auth context (shared across all tests in this run) ───────
    const [sessionAuthToken, setSessionAuthToken] = useState<string>("")
    const [sessionUserId, setSessionUserId] = useState<string>("")
    const [capturedContext, setCapturedContext] = useState<Record<string, string>>({})

    // ── Auth session config ───────────────────────────────────────────────────
    const [showAuthConfig, setShowAuthConfig] = useState<boolean>(false)
    const [authConfig, setAuthConfig] = useState({
        enabled: false,
        token: "",
        registerUrl: "/api/auth/register",
        loginUrl: "/api/auth/login",
        email: "",
        password: "",
    })
    const [adminToken, setAdminToken] = useState<string>("")

    const consoleRef = useRef<HTMLDivElement>(null)
    const abortRef = useRef<AbortController | null>(null)

    const doneLoggedRef = useRef<boolean>(false)
    const doneTotalRef = useRef<number>(0)
    const completedCountRef = useRef<number>(0)

    const passBreakdown = useMemo(() => {
        const green    = rows.filter((r) => r.status === "pass" && (r.pass_tone ?? "green") === "green").length
        const yellow   = rows.filter((r) => r.status === "pass" && r.pass_tone === "yellow").length
        // Separate true contract failures from runtime errors and intentional skips.
        const skipped  = rows.filter((r) => r.execution_status === "SKIPPED").length
        const errors   = rows.filter((r) => r.final_status === "ERROR" && r.execution_status !== "SKIPPED").length
        const failed   = rows.filter((r) => r.status === "fail" && r.final_status !== "ERROR" && r.execution_status !== "SKIPPED").length
        return { green, yellow, failed, errors, skipped, passed: green + yellow }
    }, [rows])

    useEffect(() => {
        if (!finished) return
        if (doneLoggedRef.current) return
        const totalExpected = doneTotalRef.current
        const accounted = passBreakdown.passed + passBreakdown.failed
        if (totalExpected > 0 && accounted < totalExpected) return
        if (accounted === 0) return
        doneLoggedRef.current = true
        const doneParts = [
            `${passBreakdown.passed} passed`,
            passBreakdown.yellow > 0 ? `(${passBreakdown.yellow} with warnings)` : null,
            `${passBreakdown.failed} failed`,
            passBreakdown.errors  > 0 ? `${passBreakdown.errors} errors` : null,
            passBreakdown.skipped > 0 ? `${passBreakdown.skipped} skipped` : null,
            `of ${totalExpected || accounted} total`,
        ].filter(Boolean).join("  ")
        setLogs((prev) => [
            ...prev,
            "─".repeat(48),
            `[DONE] ${doneParts}`,
        ])
    }, [finished, passBreakdown])

    const loadDraftCases = useCallback(async (): Promise<number> => {
        if (!open) return 0
        if (!projectId) return 0

        try {
            const token = window.localStorage.getItem("cognitest-token")
            const headers: Record<string, string> = {}
            if (token) headers["Authorization"] = `Bearer ${token}`

            const params = new URLSearchParams()
            if (caseIds && caseIds.length > 0) params.set("case_ids", caseIds.join(","))
            if (caseId) params.set("case_id", caseId)

            const res = await fetch(
                `${API_BASE_URL}/api/v1/projects/${encodeURIComponent(projectId)}/test-cases?${params.toString()}`,
                { headers },
            )

            if (!res.ok) {
                return 0
            }

            const cases = (await res.json()) as Array<{
                id: string
                name: string
                endpoint_path: string
                method: string
                expected_status: number
                test_type?: string
            }>

            const allCases = caseId
                ? cases.filter((c) => c.id === caseId)
                : caseIds && caseIds.length > 0
                    ? cases.filter((c) => caseIds.includes(c.id))
                    : cases

            const filteredCases = allCases

            if (!running && !finished) {
                setRows(
                    filteredCases.map((c) => ({
                        id: c.id,
                        name: c.name,
                        endpoint_path: c.endpoint_path,
                        method: c.method,
                        expected_status: c.expected_status,
                        test_type: c.test_type,
                        status: "pending" as const,
                    })),
                )
            }
            setTotal(filteredCases.length)
            return filteredCases.length
        } catch {
            // Best-effort only; modal can still run suite without preloading.
            return 0
        }
    }, [open, projectId, caseId, caseIds])

    // Auto-scroll the terminal
    useEffect(() => {
        if (consoleRef.current) {
            consoleRef.current.scrollTop = consoleRef.current.scrollHeight
        }
    }, [logs])

    // Reset state when dialog closes
    useEffect(() => {
        if (!open) {
            abortRef.current?.abort()
            setRows([])
            setLogs([])
            setProgress(0)
            setRunning(false)
            setFinished(false)
            setSummary(null)
            setExpandedRowId(null)
            setAiAnalyses({})
            setAnalyzingId(null)
            setHasLoadedCases(false)
            setSessionAuthToken("")
            setSessionUserId("")
            setCapturedContext({})
            setSessionUserId("")
        } else if (!hasLoadedCases) {
            setTargetUrl(baseUrl?.trim() ? baseUrl : DEFAULT_LOCAL_TARGET_URL)
            setHasLoadedCases(true)
            void loadDraftCases()
        }
    }, [open, baseUrl, loadDraftCases, hasLoadedCases])

    const handleRun = async () => {
        setRunning(true)
        setFinished(false)
        setRows((prev) =>
            prev.map((r) => ({
                ...r,
                status: "pending" as const,
                actual_status: undefined,
                response_time_ms: undefined,
                response_body: undefined,
                response_headers: undefined,
                error_message: undefined,
                request_headers: undefined,
                request_body: undefined,
                query_params: undefined,
                extracted_vars: undefined,
                injected_vars: undefined,
            })),
        )
        setLogs([])
        setLogs((prev) => [...prev, "[INFO] Connecting to execution stream..."])
        setProgress(0)
        setSummary(null)
        setExpandedRowId(null)
        setAiAnalyses({})
        // Reset session auth context for this run
        setSessionAuthToken("")
        setSessionUserId("")
        setCapturedContext({})

        completedCountRef.current = 0

        const controller = new AbortController()
        abortRef.current = controller

        try {
            const loadedCount = await loadDraftCases()
            if (caseId && loadedCount === 0) {
                setLogs((prev) => [...prev, "[ERROR] Selected test case not found in current draft cases."])
                setRunning(false)
                return
            }
            const token = window.localStorage.getItem("cognitest-token")
            const headers: Record<string, string> = {}
            if (token) headers["Authorization"] = `Bearer ${token}`

            const apiBaseUrl = targetUrl || DEFAULT_LOCAL_TARGET_URL








            // --- Ticket based streaming flow ---
            // 1️⃣ Request a one‑time ticket from backend
            const ticketRes = await fetch(
                `${API_BASE_URL}/api/v1/projects/${encodeURIComponent(projectId)}/run-suite/ticket`,
                {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        ...headers,
                    },
                    body: JSON.stringify({
                        base_url: apiBaseUrl,
                        ...(caseId ? { case_ids: caseId } : {}),
                        ...(!caseId && caseIds && caseIds.length > 0 ? { case_ids: caseIds.join(",") } : {}),
                        ...(authConfig.enabled ? {
                            ...(authConfig.token?.trim() ? { manual_token: authConfig.token.trim() } : {}),
                            ...(authConfig.registerUrl?.trim() ? { register_url: authConfig.registerUrl.trim() } : {}),
                            ...(authConfig.loginUrl?.trim() ? { login_url: authConfig.loginUrl.trim() } : {}),
                            ...(authConfig.email?.trim() ? { auth_email: authConfig.email.trim() } : {}),
                            ...(authConfig.password?.trim() ? { auth_password: authConfig.password.trim() } : {}),
                        } : {}),
                        ...(adminToken?.trim() ? { admin_token: adminToken.trim() } : {}),
                    }),
                }
            );
            if (!ticketRes.ok) {
                let detail = "";
                try {
                    const payload = await ticketRes.json();
                    detail = typeof payload?.detail === "string" ? payload.detail : "";
                } catch {}
                setLogs((prev) => [...prev, `[ERROR] Ticket request failed ${ticketRes.status}${detail ? `: ${detail}` : ""}`]);
                // Show toast notification for test generation failure
                toast.show({
                    title: "Test generation failed",
                    description: detail || `Ticket request failed ${ticketRes.status}`,
                    type: "error",
                });
                setRunning(false);
                return;
            }
            const { ticket } = await ticketRes.json();

            // 2️⃣ Connect to the event stream using the ticket
            const streamUrl = `${API_BASE_URL}/api/v1/projects/${encodeURIComponent(projectId)}/run-suite/stream?ticket=${encodeURIComponent(ticket)}`;
            const response = await fetch(streamUrl, { headers, signal: controller.signal });

            if (!response.ok) {
                let detail = "";
                try {
                    const payload = await response.json();
                    detail = typeof payload?.detail === "string" ? payload.detail : "";
                } catch {
                    // ignore
                }
                setLogs((prev) => [
                    ...prev,
                    `[ERROR] Server responded with ${response.status}${detail ? `: ${detail}` : ""}`,
                ]);
                // Show toast notification for test generation failure
                toast.show({
                    title: "Test generation failed",
                    description: detail || `Server responded with ${response.status}`,
                    type: "error",
                });
                setRunning(false);
                return;
            }

            const reader = response.body?.getReader()
            if (!reader) {
                setLogs((prev) => [...prev, "[ERROR] No response body (streaming not supported?)"])
                setRunning(false)
                return
            }
            const decoder = new TextDecoder()
            let buffer = ""

            while (reader) {
                const { done, value } = await reader.read()
                if (done) break
                buffer += decoder.decode(value, { stream: true })
                const lines = buffer.split("\n")
                buffer = lines.pop() ?? ""

                for (const line of lines) {
                    if (!line.trim()) continue
                    try {
                        const event: StreamEvent = JSON.parse(line)
                        processEvent(event)
                    } catch {
                        setLogs((prev) => [...prev, `[RAW] ${line}`])
                    }
                }
            }
        } catch (err) {
            if (err instanceof Error && err.name !== "AbortError") {
                setLogs((prev) => [...prev, `[ERROR] ${err.message}`])
            }
        } finally {
            setRunning(false)
        }
    }

    const processEvent = (event: StreamEvent) => {
        if (event.event === "start") {
            const t = event.total ?? 0
            doneLoggedRef.current = false
            doneTotalRef.current = t
            setTotal(t)
            setLogs((prev) => [
                ...prev,
                `[START] Running ${t} test case${t !== 1 ? "s" : ""}...`,
                `[INFO] Target API: ${targetUrl}`,
                ...(authConfig.enabled
                    ? [
                        authConfig.token?.trim()
                            ? "[AUTH] Token mode active — manual JWT injected when required"
                            : `[AUTH] Session mode active — ${authConfig.registerUrl ? "register →" : ""} login → inject JWT → cleanup`,
                    ]
                    : []),
                "─".repeat(48),
            ])
        } else if (event.event === "banner") {
            if (event.log) setLogs((prev) => [...prev, event.log!])
        } else if (event.event === "session_start") {
            setLogs((prev) => [...prev, "", event.log ?? "▶ Starting auth session..."])
        } else if (event.event === "session_step") {
            if (event.log) setLogs((prev) => [...prev, event.log!])
        } else if (event.event === "session_cleanup") {
            if (event.log) setLogs((prev) => [...prev, event.log!, ""])
        } else if (event.event === "setup_start") {
            setLogs((prev) => [...prev, "", event.log ?? "▶ Setting up stateful test environment..."])
        } else if (event.event === "setup_step") {
            if (event.log) setLogs((prev) => [...prev, event.log!])
        } else if (event.event === "setup_done") {
            if (event.log) setLogs((prev) => [...prev, event.log!])
        } else if (event.event === "setup_failed") {
            if (event.log) setLogs((prev) => [...prev, event.log!])
        } else if (event.event === "context_update") {
            if (event.context) {
                setCapturedContext((prev) => ({ ...prev, ...event.context }))
            }
        } else if (event.event === "result") {
            const {
                id = "",
                name = "",
                endpoint_path = "",
                method = "",
                expected_status = 0,
                expected_statuses,
                actual_status,
                passed,
                severity,
                log,
                response_time_ms,
                response_body,
                response_headers,
                error_message,
                request_headers,
                request_body,
                query_params,
                test_type,
                requires_auth,
                auth_provided,
                violations,
                extracted_vars,
                injected_vars,
                // Three-layer semantic fields
                execution_status,
                validation_status,
                final_status,
                error_category,
                skip_reason,
            } = event

            const classification = classifyResult(event)
            const expectedNums = classification.expectedNums
            const actualStatusNum = classification.actual

            // Debug requirement: deterministic log per test
            try {
                console.debug("[contract-ui] classify", {
                    id,
                    name,
                    test_type: test_type ?? null,
                    normalized_test_type: classification.testType,
                    expected: expectedNums,
                    actual: Number.isFinite(actualStatusNum) ? actualStatusNum : null,
                    final: {
                        status: classification.status,
                        pass_tone: classification.pass_tone ?? null,
                        yellow: classification.isYellowPass,
                    },
                })
            } catch {
                // ignore
            }

            setRows((prev: TestRow[]) => {
                const existing = prev.findIndex((r) => r.id === id)
                const hasMediumWarning =
                    String(severity ?? "").toUpperCase() === "MEDIUM" ||
                    (Array.isArray(violations) &&
                        violations.some((v) => String((v as any)?.severity || "").toUpperCase() === "MEDIUM"))

                const mediumAppliesToPositiveOnly = hasMediumWarning && classification.testType === "positive"

                // Backward-compatible: MEDIUM severity bumps PASS tone to yellow unless it already failed.
                const resolvedStatus: TestRow["status"] = classification.status ?? (passed ? "pass" : "fail")
                const resolvedPassTone: TestRow["pass_tone"] =
                    resolvedStatus === "pass"
                        ? ((event as any)?.inconclusive ? "yellow" : (mediumAppliesToPositiveOnly ? "yellow" : (classification.pass_tone ?? "green")))
                        : undefined

                const newRow: TestRow = {
                    id,
                    name,
                    endpoint_path,
                    method,
                    expected_status,
                    actual_status,
                    status: resolvedStatus,
                    pass_tone: resolvedPassTone,
                    response_time_ms,
                    response_body,
                    response_headers,
                    error_message,
                    request_headers,
                    request_body,
                    query_params,
                    violations,
                    test_type,
                    requires_auth,
                    auth_provided,
                    extracted_vars,
                    injected_vars,
                    // Three-layer semantic provenance
                    execution_status,
                    validation_status,
                    final_status,
                    error_category,
                    skip_reason,
                }
                if (existing >= 0) {
                    const next = [...prev]
                    next[existing] = newRow
                    return next
                }
                return [...prev, newRow]
            })

            // ── Update session-level auth context from this result event ──────
            // Merge injected + extracted vars from backend
            const allVars = { ...(injected_vars || {}), ...(extracted_vars || {}) }
            const foundToken =
                (allVars["auth_token"] as string | undefined) ||
                (request_headers?.["Authorization"] ?? request_headers?.["authorization"] ?? "").replace(/^Bearer\s+/i, "")
            const foundUserId =
                (allVars["user_id"] as string | undefined) ??
                (allVars["userId"] as string | undefined) ??
                (allVars["session_user_id"] as string | undefined) ??
                (allVars["registered_user_id"] as string | undefined)
            if (foundToken) setSessionAuthToken(foundToken)
            if (foundUserId) setSessionUserId(String(foundUserId))

            completedCountRef.current += 1
            const currentDone = completedCountRef.current
            const currentTotal = doneTotalRef.current || total || 1
            setProgress(Math.round((currentDone / currentTotal) * 100))

            // Build a compact single-line log entry
            const now = new Date()
            let ts = ""
            try {
                ts = now.toLocaleTimeString(undefined, {
                    hour12: false,
                    hour: "2-digit",
                    minute: "2-digit",
                    second: "2-digit",
                    fractionalSecondDigits: 3,
                } as Intl.DateTimeFormatOptions)
            } catch {
                const base = now.toLocaleTimeString(undefined, {
                    hour12: false,
                    hour: "2-digit",
                    minute: "2-digit",
                    second: "2-digit",
                })
                ts = `${base}.${String(now.getMilliseconds()).padStart(3, "0")}`
            }

            // ── SKIP: use execution_status as authoritative signal ─────────────
            // Fall back to log string match for backward compat with older backends.
            const isSkipped = execution_status === "SKIPPED" || (log && log.includes("[SKIP]"))
            if (isSkipped) {
                const reason = skip_reason ? `  (${skip_reason})` : (log ? `  ${log}` : "")
                setLogs((prev: string[]) => [
                    ...prev,
                    `[${ts}] ○ SKIP   ${method}  ${endpoint_path}${reason}`,
                ])
                return
            }

            const expectedStr = formatExpectedStatuses(event)
            const timeSuffix = response_time_ms !== undefined ? `  ${response_time_ms}ms` : ""

            // ── Semantic log format (three-layer backend) ─────────────────────
            // Prefer final_status + error_category over raw status-code comparison
            // so the console accurately reflects WHY a test passed or failed.
            let compactLine: string
            if (final_status === "ERROR" && error_category) {
                // Infrastructure / engine failure — NOT a contract violation
                const errDetail = error_message ? `  ${error_message.slice(0, 60)}` : ""
                compactLine = `[${ts}] ERROR  ${method}  ${endpoint_path}  [${error_category}]${errDetail}${timeSuffix}`
            } else if (final_status === "WARNING") {
                const primary = getPrimaryViolation(violations)
                const vtype = primary?.violation ?? "contract.drift"
                compactLine = `[${ts}] WARN   ${method}  ${endpoint_path}  [${vtype}]  (${actual_status ?? "n/a"})${timeSuffix}`
            } else if (final_status === "FAIL") {
                const primary = getPrimaryViolation(violations)
                const vtype = primary?.violation ?? "contract.mismatch"
                compactLine = `[${ts}] FAIL   ${method}  ${endpoint_path}  [${vtype}]  expected ${expectedStr} → got ${actual_status ?? "n/a"}${timeSuffix}`
            } else if (final_status === "PASS") {
                compactLine = `[${ts}] PASS   ${method}  ${endpoint_path}  (${actual_status ?? "n/a"})${timeSuffix}`
            } else {
                // Backward-compat fallback: no final_status provided by backend
                const hasMediumWarning =
                    String(severity ?? "").toUpperCase() === "MEDIUM" ||
                    (Array.isArray(violations) && violations.some((v) => String((v as any)?.severity || "").toUpperCase() === "MEDIUM"))
                const statusLabel = (classification.status === "fail" || passed === false) ? "FAIL" : "PASS"
                const mediumAppliesToPositiveOnly = hasMediumWarning && classification.testType === "positive"
                const isYellowPass = statusLabel === "PASS" && (mediumAppliesToPositiveOnly || classification.isYellowPass || classification.pass_tone === "yellow" || Boolean((event as any)?.inconclusive))
                const warnSuffix = isYellowPass ? " ⚠" : ""
                compactLine = `[${ts}] ${statusLabel}  ${method}  ${endpoint_path}  expected ${expectedStr} → got ${actual_status ?? "n/a"}${timeSuffix}${warnSuffix}`
            }
            setLogs((prev: string[]) => [...prev, compactLine])

        } else if (event.event === "workflow_step") {
            // Workflow step events carry per-step extracted_vars and injected_vars (auth_token, user_id, etc.)
            const ev = event as unknown as {
                step_id: string
                name: string
                method: string
                endpoint_path: string
                expected_status: number
                actual_status: number
                passed: boolean
                skipped?: boolean
                response_time_ms: number
                response_body: string
                response_headers: Record<string, string>
                error_message: string
                extracted_vars: Record<string, unknown>
                injected_vars: Record<string, unknown>
                resolved_body: unknown
                resolved_headers: Record<string, string>
                workflow_id: string
            }
            const stepRowId = `${ev.workflow_id ?? "wf"}__${ev.step_id ?? ev.name}`
            setRows((prev: TestRow[]) => {
                const existing = prev.findIndex((r) => r.id === stepRowId)
                const newRow: TestRow = {
                    id: stepRowId,
                    name: ev.name,
                    endpoint_path: ev.endpoint_path,
                    method: ev.method,
                    expected_status: ev.expected_status,
                    actual_status: ev.actual_status,
                    status: ev.skipped ? "pending" : ev.passed ? "pass" : "fail",
                    response_time_ms: ev.response_time_ms,
                    response_body: ev.response_body,
                    response_headers: ev.response_headers,
                    error_message: ev.error_message,
                    request_headers: ev.resolved_headers,
                    request_body: ev.resolved_body as Record<string, unknown> | null,
                    extracted_vars: ev.extracted_vars,
                    injected_vars: ev.injected_vars,
                }
                if (existing >= 0) {
                    const next = [...prev]
                    next[existing] = newRow
                    return next
                }
                return [...prev, newRow]
            })

            // ── Update session auth context from workflow step extracted_vars ─
            // The login/register step carries the real token in extracted_vars.auth_token
            const wfExtracted = ev.extracted_vars || {}
            const wfInjected = ev.injected_vars || {}
            const wfToken =
                (wfExtracted["auth_token"] as string | undefined) ||
                (wfInjected["auth_token"] as string | undefined) ||
                (ev.resolved_headers?.["Authorization"] ?? "").replace(/^Bearer\s+/i, "")
            const wfUserId =
                (wfExtracted["user_id"] as string | undefined) ??
                (wfExtracted["userId"] as string | undefined) ??
                (wfExtracted["registered_user_id"] as string | undefined) ??
                (wfExtracted["created_id"] as string | undefined) ??
                (wfInjected["user_id"] as string | undefined) ??
                (wfInjected["session_user_id"] as string | undefined)
            if (wfToken) setSessionAuthToken(wfToken)
            if (wfUserId) setSessionUserId(String(wfUserId))

            // Log step to console
            const stepPass = ev.skipped ? "SKIP" : ev.passed ? "PASS" : "FAIL"
            const now2 = new Date()
            const ts2 = now2.toLocaleTimeString(undefined, { hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit" })
            setLogs((prev: string[]) => [
                ...prev,
                `[${ts2}]   ↳ ${stepPass}  ${ev.method}  ${ev.endpoint_path}  → ${ev.actual_status ?? "skipped"}  ${ev.response_time_ms ?? 0}ms`,
            ])

        } else if (event.event === "done") {
            setFinished(true)
            setProgress(100)
            const p = event.total !== undefined && event.failed !== undefined
                ? event.total - event.failed
                : 0
            const f: number = event.failed ?? 0
            setSummary({ passed: p, failed: f })
            doneTotalRef.current = event.total ?? (p + f)
            if (onComplete) {
                onComplete({ passed: p, failed: f })
            }
        }
    }

    const handleAnalyze = useCallback(async (row: TestRow) => {
        if (analyzingId || aiAnalyses[row.id]) return
        setAnalyzingId(row.id)
        try {
            const resp = await analyzeFailure(projectId, {
                test_name: row.name,
                test_type: testType,
                method: row.method,
                endpoint_path: row.endpoint_path,
                expected_status: row.expected_status,
                actual_status: row.actual_status ?? 0,
                response_body: row.response_body || "",
                error_message: row.error_message || "",
                request_body: row.request_body ? JSON.stringify(row.request_body) : "",
            })
            setAiAnalyses((prev) => ({ ...prev, [row.id]: resp.analysis }))
        } catch (err) {
            setAiAnalyses((prev) => ({
                ...prev,
                [row.id]: {
                    root_cause: "Analysis failed",
                    explanation: err instanceof Error ? err.message : "Unknown error",
                    suggested_fix: "Try again or check API key configuration.",
                    severity: "low" as const,
                },
            }))
        } finally {
            setAnalyzingId(null)
        }
    }, [analyzingId, aiAnalyses, projectId, testType])

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className={`${dialogMaximized ? 'max-w-[98vw] w-[98vw] h-[96vh]' : 'max-w-5xl h-[80vh]'} flex! flex-col! p-0! gap-0! overflow-hidden transition-all duration-200`}>
                {/* Maximize button — sits left of the built-in close button */}
                <button
                    className="absolute right-12 top-4 z-10 rounded-sm opacity-70 ring-offset-background transition-opacity hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 cursor-pointer"
                    onClick={() => setDialogMaximized(!dialogMaximized)}
                    title={dialogMaximized ? "Restore window" : "Maximize window"}
                >
                    {dialogMaximized
                        ? <Minimize2 className="h-4 w-4" />
                        : <Maximize2 className="h-4 w-4" />}
                </button>

                {/* Header */}
                <DialogHeader className="px-6 py-4 border-b border-border/50 shrink-0">
                    <DialogTitle className="flex items-center gap-2 text-base">
                        <Terminal className="h-5 w-5 text-emerald-400" />
                        Run Test Suite
                        {summary && (
                            <span className="ml-auto flex items-center gap-1.5 mr-14 flex-wrap justify-end">
                                <Badge className="bg-emerald-500/20 text-emerald-400 border-emerald-500/30">
                                    <CheckCircle2 className="h-3 w-3 mr-1" />
                                    {passBreakdown.green} passed
                                </Badge>
                                {passBreakdown.yellow > 0 && (
                                    <Badge className="bg-yellow-500/20 text-yellow-400 border-yellow-500/30">
                                        <AlertTriangle className="h-3 w-3 mr-1" />
                                        {passBreakdown.yellow} warnings
                                    </Badge>
                                )}
                                {passBreakdown.failed > 0 && (
                                    <Badge className="bg-red-500/20 text-red-400 border-red-500/30">
                                        <XCircle className="h-3 w-3 mr-1" />
                                        {passBreakdown.failed} failed
                                    </Badge>
                                )}
                                {passBreakdown.errors > 0 && (
                                    <Badge className="bg-orange-500/20 text-orange-400 border-orange-500/30">
                                        <OctagonAlert className="h-3 w-3 mr-1" />
                                        {passBreakdown.errors} errors
                                    </Badge>
                                )}
                                {passBreakdown.skipped > 0 && (
                                    <Badge className="bg-amber-500/15 text-amber-400 border-amber-500/25">
                                        <MinusCircle className="h-3 w-3 mr-1" />
                                        {passBreakdown.skipped} skipped
                                    </Badge>
                                )}
                            </span>
                        )}
                    </DialogTitle>

                    {/* Progress bar */}
                    <div className="mt-3 space-y-1">
                        <div className="flex items-center justify-between text-xs text-muted-foreground">
                            <span>{running ? "Running tests..." : finished ? "Completed" : "Ready to run"}</span>
                            <span>{progress}%</span>
                        </div>
                        <Progress value={progress} className="h-1.5" />
                    </div>
                </DialogHeader>

                {/* Body: two-column layout */}
                <div className="flex flex-1 min-h-0 divide-x divide-border/50 relative">
                    {/* Left — Test results list */}
                    <div className={`${maximized ? 'hidden' : 'w-1/2'} flex flex-col min-h-0`}>
                        <div className="px-4 py-2.5 text-xs font-semibold text-muted-foreground uppercase tracking-wider border-b border-border/40 bg-muted/20">
                            Test Cases
                        </div>
                        <div className="flex-1 overflow-y-auto">
                            {rows.length === 0 && !running && (
                                <div className="flex items-center justify-center h-full text-sm text-muted-foreground italic px-6 text-center">
                                    {finished ? "No results." : "Click 'Run Suite' to start execution."}
                                </div>
                            )}
                            {rows.map((row: TestRow, idx: number) => {
                                const analysis = aiAnalyses[row.id]

                                return (
                                    <div key={row.id} className="border-b border-border/30">
                                        {/* Row header */}
                                        {/* ── Row: semantic-aware visual state ──────────────── */}
                                        {(() => {
                                            const isSkipped = row.execution_status === "SKIPPED"
                                            const isError   = row.final_status === "ERROR" && !isSkipped
                                            const isWarning = row.status === "pass" && row.pass_tone === "yellow"
                                            const isPass    = row.status === "pass" && !isWarning

                                            const rowBg = isSkipped
                                                ? "bg-amber-500/8 hover:bg-amber-500/15"
                                                : isError
                                                    ? "bg-orange-500/8 hover:bg-orange-500/15"
                                                    : isWarning
                                                        ? "bg-yellow-500/8 hover:bg-yellow-500/15"
                                                        : isPass
                                                            ? "bg-emerald-500/6 hover:bg-emerald-500/12"
                                                            : row.status === "fail"
                                                                ? "bg-red-500/8 hover:bg-red-500/15"
                                                                : "hover:bg-muted/30"

                                            const statusIcon = isSkipped
                                                ? <MinusCircle className="h-4 w-4 text-amber-400" />
                                                : isError
                                                    ? <OctagonAlert className="h-4 w-4 text-orange-400" />
                                                    : isWarning
                                                        ? <AlertTriangle className="h-4 w-4 text-yellow-500" />
                                                        : isPass
                                                            ? <CheckCircle2 className="h-4 w-4 text-emerald-500" />
                                                            : row.status === "fail"
                                                                ? <XCircle className="h-4 w-4 text-red-500" />
                                                                : <div className="h-4 w-4 rounded-full border-2 border-muted-foreground/30" />

                                            const codeColor = isSkipped
                                                ? "text-amber-400/60"
                                                : isError
                                                    ? "text-orange-400"
                                                    : isWarning
                                                        ? "text-yellow-400"
                                                        : isPass
                                                            ? "text-emerald-400"
                                                            : "text-red-400"

                                            return (
                                                <div
                                                    className={`flex items-start gap-3 px-4 py-3 cursor-pointer transition-colors ${rowBg}`}
                                                    onClick={() => setSelectedRow(selectedRow?.id === row.id ? null : row)}
                                                >
                                                    <span className="text-xs text-muted-foreground w-5 shrink-0 mt-0.5 font-mono">
                                                        {idx + 1}
                                                    </span>
                                                    <div className="min-w-0 flex-1">
                                                        <p className="text-sm font-medium truncate">{row.name}</p>
                                                        <div className="flex items-center gap-1.5 mt-0.5 flex-wrap">
                                                            <Badge variant="outline" className="font-mono text-[10px] px-1.5 py-0">
                                                                {row.method}
                                                            </Badge>
                                                            <span className="text-xs text-muted-foreground truncate max-w-45">
                                                                {row.endpoint_path}
                                                            </span>
                                                            {/* Semantic state chip — replaces raw "→ status_code" */}
                                                            {isSkipped ? (
                                                                <span className="text-[10px] text-amber-300 font-mono font-semibold">
                                                                    SKIPPED{row.skip_reason ? ` · ${row.skip_reason}` : ""}
                                                                </span>
                                                            ) : isError ? (
                                                                <span className="text-[10px] text-orange-300 font-mono font-semibold">
                                                                    ERROR{row.error_category ? ` · ${row.error_category}` : ""}
                                                                </span>
                                                            ) : row.actual_status !== undefined && (
                                                                <span className={`text-[10px] font-mono ${codeColor}`}>
                                                                    → {row.actual_status}
                                                                </span>
                                                            )}
                                                            {row.response_time_ms !== undefined && !isSkipped && (
                                                                <span className="text-[10px] text-muted-foreground flex items-center gap-0.5">
                                                                    <Clock className="h-2.5 w-2.5" />
                                                                    {row.response_time_ms}ms
                                                                </span>
                                                            )}
                                                            {/* Violation type chip — shows the primary (most severe) violation */}
                                                            {(row.final_status === "FAIL" || row.final_status === "WARNING") && row.violations && row.violations.length > 0 && (
                                                                <span className={`text-[9px] font-mono font-semibold px-1.5 py-0.5 rounded border ${isWarning ? "border-yellow-500/50 text-yellow-300 bg-yellow-500/10" : "border-red-500/50 text-red-300 bg-red-500/10"}`}>
                                                                    {getPrimaryViolation(row.violations)?.violation ?? "contract"}
                                                                </span>
                                                            )}
                                                        </div>
                                                    </div>
                                                    <div className="shrink-0 mt-0.5">
                                                        {statusIcon}
                                                    </div>
                                                </div>
                                            )
                                        })()}
                                    </div>
                                )
                            })}
                            {running && rows.length < total && (
                                <div className="flex items-center gap-3 px-4 py-3">
                                    <RefreshCw className="h-4 w-4 text-muted-foreground animate-spin" />
                                    <span className="text-sm text-muted-foreground">Running…</span>
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Right — dark terminal */}
                    <div className={`${maximized ? 'w-full' : 'w-1/2'} flex flex-col min-h-0 bg-[#0d1117]`}>
                        <div className="px-4 py-2.5 text-xs font-semibold text-slate-400 uppercase tracking-wider border-b border-white/5 flex items-center justify-between">
                            <div className="flex items-center gap-2">
                                <div className="flex gap-1">
                                    <div className="h-2.5 w-2.5 rounded-full bg-red-500/80" />
                                    <div className="h-2.5 w-2.5 rounded-full bg-yellow-500/80" />
                                    <div className="h-2.5 w-2.5 rounded-full bg-emerald-500/80" />
                                </div>
                                <span className="ml-1">Console Output</span>
                            </div>
                            <Button
                                variant="ghost"
                                size="sm"
                                className="h-7 px-2 text-slate-400 hover:text-white hover:bg-white/10 flex items-center gap-1.5 rounded-md transition-all"
                                onClick={() => setMaximized(!maximized)}
                                title={maximized ? "Split view" : "Maximize console"}
                            >
                                {maximized
                                    ? <Minimize2 className="h-3.5 w-3.5" />
                                    : <Maximize2 className="h-3.5 w-3.5" />}
                                <span className="text-[10px] uppercase font-bold tracking-wide">{maximized ? "Split" : "Full"}</span>
                            </Button>
                        </div>
                        <div
                            ref={consoleRef}
                            className="flex-1 overflow-y-auto px-4 py-3 font-mono text-xs text-slate-300 space-y-0.5 leading-relaxed"
                        >
                            {logs.length === 0 && (
                                <span className="text-slate-600">$ awaiting execution…</span>
                            )}
                            {logs.map((line: string, i: number) => (
                                <div
                                    key={i}
                                    className={(() => {
                                        // ── Banner / separator lines ──────────────────────────────
                                        if (line.startsWith("━") || line.startsWith("── ") || line.startsWith("┌──") || line.startsWith("├──") || line.startsWith("└──"))
                                            return "text-slate-400 font-bold";
                                        // ── Warning-marked lines (⚠) → yellow (must beat PASS) ────
                                        if (line.includes("⚠"))
                                            return "text-yellow-400";
                                        // ── PASS lines → bright green ─────────────────────────────
                                        if (/\] PASS\b/.test(line) || line.includes("[DONE]") || line.includes("[START]"))
                                            return "text-emerald-400";
                                        // ── WARN lines → yellow ───────────────────────────────────
                                        if (/\] (WARN|WARNING)\b/.test(line) || line.includes("[WARNING]"))
                                            return "text-yellow-400";
                                        // ── ERROR lines → orange (runtime/engine — not contract) ──
                                        // SKIP lines → amber (execution state — not failure) ───────
                                        // These must be checked BEFORE the FAIL / red rule.
                                        if (/\] ERROR\b/.test(line) || line.includes("[ERROR]") || line.includes("→ ERROR"))
                                            return "text-orange-400";
                                        if (/\] ○ SKIP\b/.test(line) || line.includes("[SKIP]"))
                                            return "text-amber-400";
                                        // ── FAIL lines → red (contract violations only) ───────────
                                        if (/\] FAIL\b/.test(line))
                                            return "text-red-400";
                                        // ── Purple for stateful setup / cleanup steps ────────────
                                        if (
                                            line.includes("▶") ||
                                            line.includes("→ Creating User") ||
                                            line.includes("Creating test users") ||
                                            line.includes("Created User") ||
                                            line.includes("User A created") ||
                                            line.includes("User B created") ||
                                            line.includes("token acquired") ||
                                            line.includes("Setup complete") ||
                                            line.includes("setup complete") ||
                                            line.includes("Cleaning up test users") ||
                                            line.includes("Cleaning up") ||
                                            line.includes("cleanup skipped") ||
                                            line.includes("auth session") ||
                                            line.includes("Auth session") ||
                                            line.includes("JWT acquired") ||
                                            line.includes("attacker role") ||
                                            line.includes("real tokens") ||
                                            line.includes("resource acquired") ||
                                            line.includes("session via login") ||
                                            line.includes("BOLA tests will") ||
                                            (line.startsWith("  ✓") && (
                                                line.includes("User") ||
                                                line.includes("Setup") ||
                                                line.includes("setup") ||
                                                line.includes("deleted") ||
                                                line.includes("acquired") ||
                                                line.includes("cleanup") ||
                                                line.includes("resource") ||
                                                line.includes("token")
                                            )) ||
                                            (line.startsWith("  ℹ")) ||
                                            (line.startsWith("  →") && (
                                                line.includes("Creating") ||
                                                line.includes("session")
                                            ))
                                        )
                                            return "text-violet-400";
                                        // ── Orange for setup failures / warnings ─────────────────
                                        if (line.startsWith("  ✗") || line.includes("⚠") || line.includes("Setup failed") || line.includes("Could not create"))
                                            return "text-orange-400";
                                        // ── Horizontal dividers and blank lines → very dim ────────
                                        if (line.startsWith("─") || line === "")
                                            return "text-slate-600";
                                        // ── Default ───────────────────────────────────────────────
                                        return "text-slate-300";
                                    })()}
                                >
                                    {line}
                                </div>
                            ))}
                            {running && (
                                <div className="flex items-center gap-1.5 text-slate-500">
                                    <RefreshCw className="h-3 w-3 animate-spin" />
                                    <span>streaming…</span>
                                </div>
                            )}
                        </div>
                    </div>
                </div>

                {/* ── Detail Popup Overlay ──────────────────────────── */}
                {selectedRow && (() => {
                    const popupRow = selectedRow
                    const analysis = aiAnalyses[popupRow.id]
                    return (
                        <div
                            className="absolute inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
                            onClick={(e) => { if (e.target === e.currentTarget) setSelectedRow(null) }}
                        >
                            <div className="bg-background border border-border/60 rounded-xl shadow-2xl w-[90%] max-w-2xl max-h-[80%] flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-200">
                                {/* Popup header */}
                                <div className="flex items-start gap-3 px-5 py-4 border-b border-border/40 shrink-0">
                                    <div className="shrink-0 mt-0.5">
                                        {popupRow.execution_status === "SKIPPED"
                                            ? <MinusCircle className="h-5 w-5 text-amber-400" />
                                            : popupRow.final_status === "ERROR"
                                                ? <OctagonAlert className="h-5 w-5 text-orange-400" />
                                                : popupRow.status === "pass"
                                                    ? (popupRow.pass_tone === "yellow"
                                                        ? <AlertTriangle className="h-5 w-5 text-yellow-500" />
                                                        : <CheckCircle2 className="h-5 w-5 text-emerald-500" />)
                                                    : popupRow.status === "fail"
                                                        ? <XCircle className="h-5 w-5 text-red-500" />
                                                        : <div className="h-5 w-5 rounded-full border-2 border-muted-foreground/30" />
                                        }
                                    </div>
                                    <div className="min-w-0 flex-1">
                                        <p className="text-sm font-semibold leading-tight">{popupRow.name}</p>
                                        <div className="flex items-center gap-2 mt-1.5 flex-wrap">
                                            <Badge variant="outline" className="font-mono text-[10px] px-1.5 py-0">
                                                {popupRow.method}
                                            </Badge>
                                            <span className="text-xs text-muted-foreground">{popupRow.endpoint_path}</span>
                                            {popupRow.execution_status === "SKIPPED" ? (
                                                <span className="text-[10px] font-mono font-semibold text-amber-300">
                                                    skipped{popupRow.skip_reason ? ` · ${popupRow.skip_reason}` : ""}
                                                </span>
                                            ) : popupRow.final_status === "ERROR" ? (
                                                <span className="text-[10px] font-mono font-semibold text-orange-300">
                                                    {popupRow.error_category ?? "runtime error"}
                                                </span>
                                            ) : popupRow.actual_status !== undefined && (
                                                <span className={`text-[10px] font-mono font-semibold ${popupRow.status === "pass" ? (popupRow.pass_tone === "yellow" ? "text-yellow-300" : "text-emerald-300") : "text-red-300"}`}>
                                                    expected {popupRow.expected_status} → got {popupRow.actual_status}
                                                </span>
                                            )}
                                            {popupRow.response_time_ms !== undefined && (
                                                <span className="text-[10px] text-muted-foreground flex items-center gap-0.5">
                                                    <Clock className="h-2.5 w-2.5" /> {popupRow.response_time_ms}ms
                                                </span>
                                            )}
                                        </div>
                                    </div>
                                    <button
                                        className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors shrink-0"
                                        onClick={() => setSelectedRow(null)}
                                    >
                                        <X className="h-4 w-4" />
                                    </button>
                                </div>

                                {/* Popup body — scrollable */}
                                <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">

                                    {/* ── Contract Validation Inspection (three-layer display) ─── */}
                                    {(popupRow.execution_status || popupRow.validation_status || popupRow.final_status) && (() => {
                                        const execStatus  = popupRow.execution_status  ?? "—"
                                        const valStatus   = popupRow.validation_status ?? "—"
                                        const finStatus   = popupRow.final_status      ?? "—"

                                        const execColor = execStatus === "EXECUTED"
                                            ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/50"
                                            : execStatus === "SKIPPED"
                                                ? "bg-amber-500/20 text-amber-300 border-amber-500/50"
                                                : "bg-orange-500/20 text-orange-300 border-orange-500/50"

                                        const valColor = valStatus === "PASS"
                                            ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/50"
                                            : valStatus === "WARNING"
                                                ? "bg-yellow-500/20 text-yellow-300 border-yellow-500/50"
                                                : valStatus === "FAIL"
                                                    ? "bg-red-500/20 text-red-300 border-red-500/50"
                                                    : "bg-orange-500/20 text-orange-300 border-orange-500/50"

                                        const finColor = finStatus === "PASS"
                                            ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/50"
                                            : finStatus === "WARNING"
                                                ? "bg-yellow-500/20 text-yellow-300 border-yellow-500/50"
                                                : finStatus === "FAIL"
                                                    ? "bg-red-500/20 text-red-300 border-red-500/50"
                                                    : finStatus === "SKIPPED"
                                                        ? "bg-amber-500/20 text-amber-300 border-amber-500/50"
                                                        : "bg-orange-500/20 text-orange-300 border-orange-500/50"

                                        // Violation severity badge — opaque enough to be clearly readable
                                        const vSeverityColor = (sev?: string) => {
                                            const s = (sev ?? "").toUpperCase()
                                            if (s === "CRITICAL") return "bg-red-500/30 text-red-200 border-red-500/60 font-bold"
                                            if (s === "HIGH")     return "bg-red-500/20 text-red-300 border-red-500/50"
                                            if (s === "MEDIUM")   return "bg-orange-500/20 text-orange-300 border-orange-500/50"
                                            return "bg-yellow-500/15 text-yellow-300 border-yellow-500/40"
                                        }
                                        // Card-level border per severity (distinct from badge)
                                        const vCardBorder = (sev?: string) => {
                                            const s = (sev ?? "").toUpperCase()
                                            if (s === "CRITICAL") return "border-red-500/50 bg-red-500/8"
                                            if (s === "HIGH")     return "border-red-400/35 bg-red-500/5"
                                            if (s === "MEDIUM")   return "border-orange-400/35 bg-orange-500/5"
                                            return "border-yellow-400/25 bg-yellow-500/4"
                                        }
                                        const vTypeColor = (vtype?: string) => {
                                            if (!vtype) return "text-slate-300"
                                            if (vtype.includes("drift"))        return "text-yellow-300"
                                            if (vtype.includes("auth"))         return "text-violet-300"
                                            if (vtype.includes("server_error")) return "text-orange-300"
                                            if (vtype.includes("semantic"))     return "text-sky-300"
                                            return "text-red-300"
                                        }

                                        return (
                                            <div className="rounded-lg border border-white/20 bg-black/30 overflow-hidden">
                                                {/* Three-layer status header */}
                                                <div className="flex items-center gap-2 px-3 py-2 border-b border-white/15 bg-black/20">
                                                    {finStatus === "PASS"
                                                        ? <ShieldCheck className="h-3.5 w-3.5 text-emerald-400 shrink-0" />
                                                        : finStatus === "WARNING"
                                                            ? <ShieldAlert className="h-3.5 w-3.5 text-yellow-400 shrink-0" />
                                                            : finStatus === "SKIPPED"
                                                                ? <MinusCircle className="h-3.5 w-3.5 text-amber-400 shrink-0" />
                                                                : finStatus === "ERROR"
                                                                    ? <OctagonAlert className="h-3.5 w-3.5 text-orange-400 shrink-0" />
                                                                    : <XCircle className="h-3.5 w-3.5 text-red-400 shrink-0" />}
                                                    <span className="text-[10px] font-bold uppercase tracking-wider text-slate-300">
                                                        Contract Validation
                                                    </span>
                                                </div>

                                                {/* Three badges in a row */}
                                                <div className="px-3 py-2.5 flex items-center gap-2 border-b border-white/10">
                                                    <div className="flex-1 text-center">
                                                        <p className="text-[9px] uppercase tracking-wider text-muted-foreground/80 mb-1.5 font-semibold">Execution</p>
                                                        <span className={`inline-block text-[10px] font-mono font-bold px-2.5 py-1 rounded border ${execColor}`}>
                                                            {execStatus}
                                                        </span>
                                                    </div>
                                                    <div className="text-muted-foreground/50 text-xs font-bold">→</div>
                                                    <div className="flex-1 text-center">
                                                        <p className="text-[9px] uppercase tracking-wider text-muted-foreground/80 mb-1.5 font-semibold">Validation</p>
                                                        <span className={`inline-block text-[10px] font-mono font-bold px-2.5 py-1 rounded border ${valColor}`}>
                                                            {valStatus}
                                                        </span>
                                                    </div>
                                                    <div className="text-muted-foreground/50 text-xs font-bold">→</div>
                                                    <div className="flex-1 text-center">
                                                        <p className="text-[9px] uppercase tracking-wider text-muted-foreground/80 mb-1.5 font-semibold">Outcome</p>
                                                        <span className={`inline-block text-[10px] font-mono font-bold px-2.5 py-1 rounded border ${finColor}`}>
                                                            {finStatus}
                                                        </span>
                                                    </div>
                                                </div>

                                                {/* Error category (when ERROR) */}
                                                {popupRow.error_category && (
                                                    <div className="px-3 py-2 border-b border-white/12 flex items-center gap-2 bg-orange-500/5">
                                                        <OctagonAlert className="h-3 w-3 text-orange-300 shrink-0" />
                                                        <span className="text-[10px] text-muted-foreground font-semibold">Error category:</span>
                                                        <code className="text-[10px] font-mono text-orange-200 font-bold">{popupRow.error_category}</code>
                                                    </div>
                                                )}

                                                {/* Skip reason (when SKIPPED) */}
                                                {popupRow.skip_reason && execStatus === "SKIPPED" && (
                                                    <div className="px-3 py-2 border-b border-white/12 flex items-center gap-2 bg-amber-500/5">
                                                        <MinusCircle className="h-3 w-3 text-amber-300 shrink-0" />
                                                        <span className="text-[10px] text-muted-foreground font-semibold">Skip reason:</span>
                                                        <code className="text-[10px] font-mono text-amber-200 font-bold">{popupRow.skip_reason}</code>
                                                    </div>
                                                )}

                                                {/* Violations list */}
                                                {popupRow.violations && popupRow.violations.length > 0 && (
                                                    <div className="px-3 py-2.5">
                                                        <p className="text-[9px] uppercase tracking-wider text-muted-foreground font-semibold mb-2.5">
                                                            Violations ({popupRow.violations.length})
                                                        </p>
                                                        <div className="space-y-2">
                                                            {popupRow.violations.map((v, vi) => (
                                                                <div key={vi} className={`rounded-md border overflow-hidden ${vCardBorder(v.severity)}`}>
                                                                    {/* Violation header: type + severity */}
                                                                    <div className="flex items-center gap-2 px-2.5 py-2 border-b border-white/10 bg-black/25">
                                                                        <code className={`text-[11px] font-mono font-bold ${vTypeColor(v.violation)}`}>
                                                                            {v.violation ?? "contract.mismatch"}
                                                                        </code>
                                                                        <span className={`ml-auto text-[9px] font-mono px-2 py-0.5 rounded border ${vSeverityColor(v.severity)}`}>
                                                                            {v.severity ?? "HIGH"}
                                                                        </span>
                                                                    </div>
                                                                    {/* Schema validation errors / drift diagnostics */}
                                                                    {v.schema_validation_errors && v.schema_validation_errors.length > 0 && (() => {
                                                                        // Drift violations carry one entry per field; show more.
                                                                        const isDrift = (v.violation ?? "").includes("drift")
                                                                        const limit = isDrift ? 12 : 6
                                                                        const shown = v.schema_validation_errors.slice(0, limit)
                                                                        const overflow = v.schema_validation_errors.length - limit
                                                                        return (
                                                                            <div className="px-2.5 py-2 space-y-1.5 bg-black/20">
                                                                                {shown.map((msg, mi) => (
                                                                                    <p key={mi} className="text-[10px] text-slate-200 leading-relaxed font-mono break-words">
                                                                                        {msg}
                                                                                    </p>
                                                                                ))}
                                                                                {overflow > 0 && (
                                                                                    <p className="text-[9px] text-amber-300/80 italic font-semibold">
                                                                                        +{overflow} more diagnostic entr{overflow === 1 ? "y" : "ies"} — update schema or set additionalProperties: true
                                                                                    </p>
                                                                                )}
                                                                            </div>
                                                                        )
                                                                    })()}
                                                                </div>
                                                            ))}
                                                        </div>
                                                    </div>
                                                )}
                                            </div>
                                        )
                                    })()}

                                    {/* Error message (infrastructure failures) */}
                                    {popupRow.error_message && popupRow.execution_status !== "EXECUTED" && (
                                        <div className="flex items-start gap-2 p-3 rounded-lg bg-orange-500/10 border border-orange-500/20">
                                            <OctagonAlert className="h-4 w-4 text-orange-400 shrink-0 mt-0.5" />
                                            <p className="text-sm text-orange-300 leading-relaxed">{popupRow.error_message}</p>
                                        </div>
                                    )}
                                    {/* Error message (contract failures still show in red) */}
                                    {popupRow.error_message && popupRow.execution_status === "EXECUTED" && (
                                        <div className="flex items-start gap-2 p-3 rounded-lg bg-red-500/10 border border-red-500/20">
                                            <AlertTriangle className="h-4 w-4 text-red-400 shrink-0 mt-0.5" />
                                            <p className="text-sm text-red-300 leading-relaxed">{popupRow.error_message}</p>
                                        </div>
                                    )}

                                    {/* ── Auth Context: always-visible session fields ── */}
                                    <div className="rounded-lg border border-violet-500/25 bg-violet-500/5 overflow-hidden">
                                        <div className="flex items-center gap-2 px-3 py-2 border-b border-violet-500/15">
                                            <KeyRound className="h-3.5 w-3.5 text-violet-400 shrink-0" />
                                            <span className="text-[10px] font-semibold uppercase tracking-wider text-violet-400">Session Auth Context</span>
                                            {sessionAuthToken ? (
                                                <span className="ml-auto text-[10px] text-emerald-400 font-medium">✓ Token acquired</span>
                                            ) : (
                                                <span className="ml-auto text-[10px] text-muted-foreground/60 font-medium italic">Awaiting login…</span>
                                            )}
                                        </div>

                                        {/* Authorization Token */}
                                        <div className="px-3 py-2.5 space-y-1.5 border-b border-violet-500/10">
                                            <p className="text-[10px] text-muted-foreground uppercase tracking-wider font-semibold">Authorization Token</p>
                                            {sessionAuthToken ? (
                                                <code className="block text-[11px] font-mono text-emerald-400 bg-black/40 rounded px-2 py-1.5 break-all leading-relaxed">
                                                    Bearer {sessionAuthToken}
                                                </code>
                                            ) : (
                                                <div className="h-7 flex items-center px-2 rounded bg-muted/20 border border-dashed border-muted-foreground/20">
                                                    <span className="text-[11px] text-muted-foreground/40 italic">— not yet acquired —</span>
                                                </div>
                                            )}
                                        </div>

                                        {/* User ID */}
                                        <div className="px-3 py-2.5 space-y-1.5">
                                            <p className="text-[10px] text-muted-foreground uppercase tracking-wider font-semibold">User ID</p>
                                            {sessionUserId || (sessionAuthToken && parseJwtUserId(sessionAuthToken)) ? (
                                                <code className="block text-[11px] font-mono text-sky-400 bg-black/40 rounded px-2 py-1.5">
                                                    {sessionUserId || parseJwtUserId(sessionAuthToken)}
                                                </code>
                                            ) : (
                                                <div className="h-7 flex items-center px-2 rounded bg-muted/20 border border-dashed border-muted-foreground/20">
                                                    <span className="text-[11px] text-muted-foreground/40 italic">— not yet acquired —</span>
                                                </div>
                                            )}
                                        </div>
                                    </div>

                                    {/* Captured Dynamic Context (Generic IDs) */}
                                    {Object.keys(capturedContext).filter(k =>
                                        !['token', 'auth_token', 'email', 'password', 'token_a', 'token_b'].includes(k.toLowerCase()) &&
                                        !(k.toLowerCase() === 'user_id' && capturedContext[k] === sessionUserId) &&
                                        !(k.toLowerCase() === 'id' && capturedContext[k] === sessionUserId)
                                    ).length > 0 && (
                                            <div className="mb-4 rounded-md border border-sky-500/20 bg-[#0d1117] overflow-hidden shadow-sm">
                                                <div className="bg-sky-500/10 px-3 py-2 flex items-center gap-2 border-b border-sky-500/20">
                                                    <KeyRound className="h-3.5 w-3.5 text-sky-400" />
                                                    <span className="text-[10px] font-semibold uppercase tracking-wider text-sky-400">Captured Test Context</span>
                                                </div>
                                                <div className="divide-y divide-sky-500/10 max-h-48 overflow-y-auto">
                                                    {Object.entries(capturedContext)
                                                        .filter(([k, v]) =>
                                                            !['token', 'auth_token', 'email', 'password'].includes(k.toLowerCase()) &&
                                                            !(k.toLowerCase() === 'user_id' && String(v) === sessionUserId) &&
                                                            !(k.toLowerCase() === 'id' && String(v) === sessionUserId)
                                                        )
                                                        .map(([key, val]) => (
                                                            <div key={key} className="px-3 py-2 space-y-1">
                                                                <p className="text-[10px] text-muted-foreground uppercase tracking-wider font-semibold">{key.replace(/_/g, ' ')}</p>
                                                                <code className="block text-[11px] font-mono text-sky-300 bg-black/40 rounded px-2 py-1.5 break-all">
                                                                    {String(val)}
                                                                </code>
                                                            </div>
                                                        ))}
                                                </div>
                                            </div>
                                        )}

                                    {/* Payloads */}
                                    <div>
                                        <div className="flex items-center gap-2 text-[10px] text-muted-foreground mb-3">
                                            <Eye className="h-3 w-3" />
                                            <span className="font-semibold uppercase tracking-wider">Request & Response Payloads</span>
                                        </div>
                                        <div className="space-y-2">
                                            <PayloadViewer label="Request Headers" data={popupRow.request_headers} />
                                            <PayloadViewer label="Request Body" data={popupRow.request_body} />
                                            <PayloadViewer label="Query Params" data={popupRow.query_params} />
                                            <PayloadViewer label="Response Body" data={popupRow.response_body} />
                                            <PayloadViewer label="Response Headers" data={popupRow.response_headers} />
                                        </div>
                                    </div>

                                    {/* AI Analysis (failed tests only) */}
                                    {popupRow.status === "fail" && (
                                        <div className="pt-2 border-t border-border/30">
                                            {analysis ? (
                                                <div className={`p-4 rounded-lg border ${SEVERITY_COLORS[analysis.severity] || SEVERITY_COLORS.low}`}>
                                                    <div className="flex items-center gap-2 mb-3">
                                                        <Sparkles className="h-4 w-4" />
                                                        <span className="text-sm font-semibold uppercase tracking-wider">
                                                            AI Analysis
                                                        </span>
                                                        <Badge variant="outline" className="text-[10px] px-2 py-0.5 ml-auto">
                                                            {analysis.severity}
                                                        </Badge>
                                                    </div>
                                                    <p className="text-sm font-medium mb-1.5">Root Cause: {analysis.root_cause}</p>
                                                    <p className="text-sm opacity-80 mb-3 leading-relaxed">{analysis.explanation}</p>
                                                    <p className="text-sm italic">💡 Suggested fix: {analysis.suggested_fix}</p>
                                                </div>
                                            ) : (
                                                <Button
                                                    size="sm"
                                                    variant="outline"
                                                    className="gap-1.5 text-xs"
                                                    onClick={() => handleAnalyze(popupRow)}
                                                    disabled={analyzingId === popupRow.id}
                                                >
                                                    {analyzingId === popupRow.id ? (
                                                        <>
                                                            <Loader2 className="h-3 w-3 animate-spin" />
                                                            Analyzing…
                                                        </>
                                                    ) : (
                                                        <>
                                                            <Sparkles className="h-3 w-3" />
                                                            Analyze with AI
                                                        </>
                                                    )}
                                                </Button>
                                            )}
                                        </div>
                                    )}
                                </div>
                            </div>
                        </div>
                    )
                })()}
                {/* Footer */}
                <div className="px-6 py-3 border-t border-border/50 shrink-0 bg-muted/10 space-y-0">

                    {/* ── Admin Token field (Security suites only) ─────────── */}
                    {(testType?.toLowerCase() === "security" || rows.some(r => r.test_type?.toLowerCase() === "security")) && (
                        <div className="mb-3 p-3 rounded-lg border border-amber-500/20 bg-amber-500/5 space-y-2">
                            <div className="flex items-center gap-2 text-xs font-semibold text-amber-400 uppercase tracking-wider">
                                <KeyRound className="h-3.5 w-3.5" />
                                Admin Token <span className="font-normal normal-case text-muted-foreground">(optional — for BOLA resource creation)</span>
                            </div>
                            <input
                                type="text"
                                value={adminToken}
                                onChange={(e) => setAdminToken(e.target.value)}
                                disabled={running}
                                placeholder="Paste admin JWT here — enables BOLA testing on admin-only APIs"
                                className="w-full h-7 px-2 text-xs rounded border border-border/50 bg-background focus:outline-none focus:ring-1 focus:ring-amber-500/50 disabled:opacity-50 font-mono"
                            />
                            <p className="text-[10px] text-muted-foreground/70 leading-relaxed">
                                {adminToken.trim()
                                    ? "✓ Admin token provided — User A will use this token to create resources. User B is auto-created as a regular user (attacker)."
                                    : "If your API only allows admins to create resources, provide an admin JWT so BOLA tests have a real owned resource to attack."}
                            </p>
                        </div>
                    )}

                    {/* ── Auth session config panel ─────────────────────────── */}
                    {showAuthConfig && (
                        <div className="mb-3 p-4 rounded-lg border border-violet-500/20 bg-violet-500/5 space-y-3">
                            <div className="flex items-center gap-2 text-xs font-semibold text-violet-400 uppercase tracking-wider">
                                <KeyRound className="h-3.5 w-3.5" />
                                Auth Session Configuration
                                <label className="ml-auto flex items-center gap-1.5 cursor-pointer normal-case font-normal text-muted-foreground">
                                    <input
                                        type="checkbox"
                                        checked={authConfig.enabled}
                                        onChange={(e) => setAuthConfig((p) => ({ ...p, enabled: e.target.checked }))}
                                        className="accent-violet-500"
                                    />
                                    Enable
                                </label>
                            </div>

                            {authConfig.enabled && (
                                <div className="grid grid-cols-2 gap-2">
                                    <div className="col-span-2">
                                        <label className="text-[10px] text-muted-foreground uppercase tracking-wider block mb-1">Access Token <span className="text-muted-foreground/50">(optional)</span></label>
                                        <input
                                            type="text"
                                            value={authConfig.token}
                                            onChange={(e) => setAuthConfig((p) => ({ ...p, token: e.target.value }))}
                                            placeholder="Bearer eyJ...  (or paste raw JWT)"
                                            disabled={running}
                                            className="w-full h-7 px-2 text-xs rounded border border-border/50 bg-background focus:outline-none focus:ring-1 focus:ring-violet-500/50 disabled:opacity-50 font-mono"
                                        />
                                        <p className="mt-1 text-[10px] text-muted-foreground/70 leading-relaxed">
                                            If provided, the runner skips register/login and injects this token.
                                        </p>
                                    </div>
                                    <div className="col-span-2 flex gap-2">
                                        <div className="flex-1">
                                            <label className="text-[10px] text-muted-foreground uppercase tracking-wider block mb-1">Register URL <span className="text-muted-foreground/50">(optional)</span></label>
                                            <input
                                                type="text"
                                                value={authConfig.registerUrl}
                                                onChange={(e) => setAuthConfig((p) => ({ ...p, registerUrl: e.target.value }))}
                                                placeholder="/api/auth/register  (leave blank to skip)"
                                                disabled={running}
                                                className="w-full h-7 px-2 text-xs rounded border border-border/50 bg-background focus:outline-none focus:ring-1 focus:ring-violet-500/50 disabled:opacity-50 font-mono"
                                            />
                                        </div>
                                        <div className="flex-1">
                                            <label className="text-[10px] text-muted-foreground uppercase tracking-wider block mb-1">Login URL <span className="text-red-400">*</span></label>
                                            <input
                                                type="text"
                                                value={authConfig.loginUrl}
                                                onChange={(e) => setAuthConfig((p) => ({ ...p, loginUrl: e.target.value }))}
                                                placeholder="/api/auth/login"
                                                disabled={running}
                                                className="w-full h-7 px-2 text-xs rounded border border-border/50 bg-background focus:outline-none focus:ring-1 focus:ring-violet-500/50 disabled:opacity-50 font-mono"
                                            />
                                        </div>
                                    </div>
                                    <div>
                                        <label className="text-[10px] text-muted-foreground uppercase tracking-wider block mb-1">Email <span className="text-red-400">*</span></label>
                                        <input
                                            type="email"
                                            value={authConfig.email}
                                            onChange={(e) => setAuthConfig((p) => ({ ...p, email: e.target.value }))}
                                            placeholder="test@example.com"
                                            disabled={running}
                                            className="w-full h-7 px-2 text-xs rounded border border-border/50 bg-background focus:outline-none focus:ring-1 focus:ring-violet-500/50 disabled:opacity-50"
                                        />
                                    </div>
                                    <div>
                                        <label className="text-[10px] text-muted-foreground uppercase tracking-wider block mb-1">Password <span className="text-red-400">*</span></label>
                                        <input
                                            type="password"
                                            value={authConfig.password}
                                            onChange={(e) => setAuthConfig((p) => ({ ...p, password: e.target.value }))}
                                            placeholder="••••••••"
                                            disabled={running}
                                            className="w-full h-7 px-2 text-xs rounded border border-border/50 bg-background focus:outline-none focus:ring-1 focus:ring-violet-500/50 disabled:opacity-50"
                                        />
                                    </div>
                                </div>
                            )}

                            <p className="text-[10px] text-muted-foreground/70 leading-relaxed">
                                {authConfig.enabled
                                    ? (authConfig.token?.trim()
                                        ? "Runner will inject your token into secured requests (no login/signup)."
                                        : "Runner will register (optional) → login → inject JWT into all requests → delete test user at end.")
                                    : "Enable to run tests as an authenticated user with automatic setup & cleanup."}
                            </p>
                        </div>
                    )}

                    {/* ── Base URL row + action buttons ────────────────────── */}
                    <div className="flex items-center gap-3 pt-1">
                        {/* Auth toggle button */}
                        <button
                            onClick={() => setShowAuthConfig(!showAuthConfig)}
                            disabled={running}
                            title={showAuthConfig ? "Hide auth config" : "Configure auth session"}
                            className={`shrink-0 flex items-center gap-1.5 h-8 px-3 rounded-md border text-xs font-medium transition-all
                                ${authConfig.enabled
                                    ? "border-violet-500/50 text-violet-400 bg-violet-500/10 hover:bg-violet-500/20"
                                    : "border-border/50 text-muted-foreground hover:text-foreground hover:bg-muted/50"
                                } disabled:opacity-40`}
                        >
                            <KeyRound className="h-3.5 w-3.5" />
                            <span>Auth</span>
                            {showAuthConfig ? <ChevronDown className="h-3 w-3" /> : <ChevronUp className="h-3 w-3" />}
                            {authConfig.enabled && (
                                <span className="ml-0.5 h-1.5 w-1.5 rounded-full bg-violet-400" />
                            )}
                        </button>

                        <div className="flex-1 flex items-center gap-2">
                            <label className="text-xs text-muted-foreground whitespace-nowrap">Base URL:</label>
                            <input
                                type="text"
                                value={targetUrl}
                                onChange={(e) => setTargetUrl(e.target.value)}
                                disabled={running}
                                placeholder={DEFAULT_LOCAL_TARGET_URL}
                                className="flex-1 h-8 px-3 text-sm rounded-md border border-border/50 bg-background focus:outline-none focus:ring-2 focus:ring-emerald-500/50 disabled:opacity-50"
                            />
                        </div>
                        <div className="flex gap-2 shrink-0">
                            <Button variant="outline" size="sm" onClick={() => onOpenChange(false)}>
                                Close
                            </Button>
                            <Button
                                size="sm"
                                className="gap-1.5 bg-emerald-600 hover:bg-emerald-700"
                                onClick={handleRun}
                                disabled={running || !targetUrl.trim()}
                            >
                                {running ? (
                                    <>
                                        <RefreshCw className="h-3.5 w-3.5 animate-spin" /> Running…
                                    </>
                                ) : (
                                    <>
                                        <Play className="h-3.5 w-3.5" /> {finished ? "Re-run Suite" : "Run Suite"}
                                    </>
                                )}
                            </Button>
                        </div>
                    </div>
                </div>
            </DialogContent>
        </Dialog>
    )
}
