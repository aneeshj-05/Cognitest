import { useEffect, useState, useMemo } from "react"
import { getSuperAdminTokenUsage, type TokenUsageEntry } from "@/services/backendClient"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Skeleton } from "@/components/ui/skeleton"
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from "recharts"
import {
  Coins,
  DollarSign,
  Zap,
  FileText,
  Search,
  TrendingUp,
  RefreshCw,
} from "lucide-react"
import { Button } from "@/components/ui/button"

// ── Color maps ────────────────────────────────────────────────────────────────
const TEST_TYPE_COLORS: Record<string, string> = {
  Functional: "#22c55e",
  Security:   "#3b82f6",
  Negative:   "#f59e0b",
  Fuzz:       "#ec4899",
  Contract:   "#8b5cf6",
  Other:      "#64748b",
}

const METHOD_COLORS: Record<string, string> = {
  GET:    "#22c55e",
  POST:   "#3b82f6",
  PUT:    "#f59e0b",
  PATCH:  "#8b5cf6",
  DELETE: "#ef4444",
}

function typeColor(type: string) {
  return TEST_TYPE_COLORS[type] ?? TEST_TYPE_COLORS.Other
}

function methodBadgeClass(method: string) {
  const map: Record<string, string> = {
    GET:    "bg-green-100 text-green-700 border-green-200",
    POST:   "bg-blue-100 text-blue-700 border-blue-200",
    PUT:    "bg-amber-100 text-amber-700 border-amber-200",
    PATCH:  "bg-purple-100 text-purple-700 border-purple-200",
    DELETE: "bg-red-100 text-red-700 border-red-200",
  }
  return map[method?.toUpperCase()] ?? "bg-muted text-muted-foreground border-border"
}

function fmtCost(usd: number) {
  if (usd >= 1) return `$${usd.toFixed(4)}`
  return `$${usd.toFixed(6)}`
}

function fmtTs(ts: string) {
  try {
    return new Date(ts).toLocaleString(undefined, {
      month: "short", day: "numeric", year: "numeric",
      hour: "2-digit", minute: "2-digit",
    })
  } catch {
    return ts
  }
}

// ── Stat Card ────────────────────────────────────────────────────────────────
function StatCard({
  title,
  value,
  sub,
  icon: Icon,
  iconColor,
}: {
  title: string
  value: string
  sub?: string
  icon: React.ComponentType<{ className?: string }>
  iconColor?: string
}) {
  return (
    <Card className="rounded-xl border border-border/60 bg-white shadow-sm">
      <CardContent className="p-5">
        <div className="flex items-start justify-between">
          <div className="space-y-1">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">{title}</p>
            <p className="text-2xl font-bold text-foreground leading-tight">{value}</p>
            {sub && <p className="text-xs text-muted-foreground">{sub}</p>}
          </div>
          <span className={`p-2.5 rounded-lg bg-muted/60 ${iconColor ?? "text-primary"}`}>
            <Icon className="h-5 w-5" />
          </span>
        </div>
      </CardContent>
    </Card>
  )
}

// ── Loading skeleton ─────────────────────────────────────────────────────────
function LoadingSkeleton() {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Card key={i} className="rounded-xl border border-border/60 bg-white shadow-sm">
            <CardContent className="p-5 space-y-2">
              <Skeleton className="h-3 w-24" />
              <Skeleton className="h-7 w-32" />
              <Skeleton className="h-3 w-20" />
            </CardContent>
          </Card>
        ))}
      </div>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card className="rounded-xl border border-border/60 bg-white shadow-sm">
          <CardContent className="p-5"><Skeleton className="h-64 w-full" /></CardContent>
        </Card>
        <Card className="rounded-xl border border-border/60 bg-white shadow-sm">
          <CardContent className="p-5"><Skeleton className="h-64 w-full" /></CardContent>
        </Card>
      </div>
      <Card className="rounded-xl border border-border/60 bg-white shadow-sm">
        <CardContent className="p-5"><Skeleton className="h-64 w-full" /></CardContent>
      </Card>
    </div>
  )
}

// ── Main Component ────────────────────────────────────────────────────────────
export default function TokenUsageAnalytics() {
  const [entries, setEntries] = useState<TokenUsageEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState("")
  const [filterType, setFilterType] = useState("All")
  const [filterProject, setFilterProject] = useState("All")
  const [filterMethod, setFilterMethod] = useState("All")
  const [filterApiMode, setFilterApiMode] = useState("All")

  const fetchData = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await getSuperAdminTokenUsage()
      setEntries(res.entries)
    } catch (e: any) {
      setError(e?.message ?? "Failed to load token usage data")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchData() }, [])

  // ── Derived aggregate stats ───────────────────────────────────────────────
  const totalTokens    = useMemo(() => entries.reduce((a, e) => a + e.total_tokens, 0), [entries])
  const totalInputTok  = useMemo(() => entries.reduce((a, e) => a + e.input_tokens, 0), [entries])
  const totalOutputTok = useMemo(() => entries.reduce((a, e) => a + e.output_tokens, 0), [entries])
  const totalCcTok     = useMemo(() => entries.reduce((a, e) => a + (e.cache_creation_tokens ?? 0), 0), [entries])
  const totalCrTok     = useMemo(() => entries.reduce((a, e) => a + (e.cache_read_tokens ?? 0), 0), [entries])
  const totalCost      = useMemo(() => entries.reduce((a, e) => a + e.cost_usd, 0), [entries])
  const totalSavings   = useMemo(() => entries.reduce((a, e) => a + (e.savings_usd ?? 0), 0), [entries])
  const totalTestCases = entries.length

  const batchInputTok  = useMemo(() => entries.filter(e => e.is_batch).reduce((a, e) => a + e.input_tokens, 0), [entries])
  const batchOutputTok = useMemo(() => entries.filter(e => e.is_batch).reduce((a, e) => a + e.output_tokens, 0), [entries])
  const batchTotalTok  = useMemo(() => entries.filter(e => e.is_batch).reduce((a, e) => a + e.total_tokens, 0), [entries])
  const batchCost      = useMemo(() => entries.filter(e => e.is_batch).reduce((a, e) => a + e.cost_usd, 0), [entries])
  const batchCount     = useMemo(() => entries.filter(e => e.is_batch).length, [entries])

  const stdInputTok    = useMemo(() => entries.filter(e => !e.is_batch).reduce((a, e) => a + e.input_tokens, 0), [entries])
  const stdOutputTok   = useMemo(() => entries.filter(e => !e.is_batch).reduce((a, e) => a + e.output_tokens, 0), [entries])
  const stdTotalTok    = useMemo(() => entries.filter(e => !e.is_batch).reduce((a, e) => a + e.total_tokens, 0), [entries])
  const stdCost        = useMemo(() => entries.filter(e => !e.is_batch).reduce((a, e) => a + e.cost_usd, 0), [entries])
  const stdCount       = useMemo(() => entries.filter(e => !e.is_batch).length, [entries])

  const batchTotal = batchInputTok + batchOutputTok
  const batchInputPct = batchTotal > 0 ? (batchInputTok / batchTotal) * 100 : 0
  const batchOutputPct = batchTotal > 0 ? (batchOutputTok / batchTotal) * 100 : 0

  const stdTotal = stdInputTok + stdOutputTok
  const stdInputPct = stdTotal > 0 ? (stdInputTok / stdTotal) * 100 : 0
  const stdOutputPct = stdTotal > 0 ? (stdOutputTok / stdTotal) * 100 : 0

  const totalTokCombined = totalTokens || 1
  const batchSharePct = (batchTotalTok / totalTokCombined) * 100
  const stdSharePct = (stdTotalTok / totalTokCombined) * 100

  // Unique values for filters
  const allTypes    = useMemo(() => ["All", ...Array.from(new Set(entries.map(e => e.test_type)))], [entries])
  const allProjects = useMemo(() => ["All", ...Array.from(new Set(entries.map(e => e.project_name)))], [entries])
  const allMethods  = useMemo(() => ["All", ...Array.from(new Set(entries.map(e => e.method?.toUpperCase())))], [entries])

  // ── Filtered table rows ───────────────────────────────────────────────────
  const filtered = useMemo(() => {
    const q = search.toLowerCase()
    return entries.filter(e => {
      const matchSearch =
        !q ||
        e.test_case_name.toLowerCase().includes(q) ||
        e.project_name.toLowerCase().includes(q) ||
        e.endpoint_path.toLowerCase().includes(q) ||
        e.test_type.toLowerCase().includes(q)
      const matchType    = filterType    === "All" || e.test_type === filterType
      const matchProject = filterProject === "All" || e.project_name === filterProject
      const matchMethod  = filterMethod  === "All" || e.method?.toUpperCase() === filterMethod
      const matchApiMode =
        filterApiMode === "All" ||
        (filterApiMode === "Batch" && e.is_batch) ||
        (filterApiMode === "Real-time" && !e.is_batch)
      return matchSearch && matchType && matchProject && matchMethod && matchApiMode
    })
  }, [entries, search, filterType, filterProject, filterMethod, filterApiMode])

  // ── Chart: tokens by test type ────────────────────────────────────────────
  const tokensByType = useMemo(() => {
    const map: Record<string, { input: number; output: number; cost: number; count: number }> = {}
    for (const e of entries) {
      const t = e.test_type || "Other"
      if (!map[t]) map[t] = { input: 0, output: 0, cost: 0, count: 0 }
      map[t].input  += e.input_tokens
      map[t].output += e.output_tokens
      map[t].cost   += e.cost_usd
      map[t].count  += 1
    }
    return Object.entries(map).map(([type, v]) => ({
      type, ...v,
      total: v.input + v.output,
      color: typeColor(type),
    }))
  }, [entries])

  // ── Chart: cost by project ─────────────────────────────────────────────────
  const costByProject = useMemo(() => {
    const map: Record<string, number> = {}
    for (const e of entries) {
      map[e.project_name] = (map[e.project_name] ?? 0) + e.cost_usd
    }
    const PIE_COLORS = ["#22c55e", "#3b82f6", "#f59e0b", "#8b5cf6", "#ec4899", "#14b8a6", "#ef4444"]
    return Object.entries(map).map(([name, value], i) => ({
      name,
      value: +value.toFixed(6),
      color: PIE_COLORS[i % PIE_COLORS.length],
    }))
  }, [entries])

  // ── Chart: tokens by HTTP method ─────────────────────────────────────────
  const tokensByMethod = useMemo(() => {
    const map: Record<string, number> = {}
    for (const e of entries) {
      const m = e.method?.toUpperCase() || "UNKNOWN"
      map[m] = (map[m] ?? 0) + e.total_tokens
    }
    return Object.entries(map).map(([method, total]) => ({
      method, total, color: METHOD_COLORS[method] ?? "#64748b",
    }))
  }, [entries])

  if (loading) return <LoadingSkeleton />

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-24 space-y-4">
        <p className="text-destructive font-medium">{error}</p>
        <Button variant="outline" onClick={fetchData}><RefreshCw className="h-4 w-4 mr-2" />Retry</Button>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* ── Header row ──────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-foreground">AI Token Usage Analytics</h2>
          <p className="text-sm text-muted-foreground mt-0.5">
            Live breakdown of all AI-generated test tokens and costs across projects
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={fetchData} className="gap-2">
          <RefreshCw className="h-3.5 w-3.5" />
          Refresh
        </Button>
      </div>

      {/* ── Stat cards ──────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-5">
        <StatCard
          title="Total Test Cases"
          value={totalTestCases.toLocaleString()}
          sub="AI-generated entries"
          icon={FileText}
          iconColor="text-blue-600"
        />
        <StatCard
          title="Total Tokens"
          value={totalTokens.toLocaleString()}
          sub={`CC: ${totalCcTok.toLocaleString()} · CR: ${totalCrTok.toLocaleString()}`}
          icon={Coins}
          iconColor="text-amber-600"
        />
        <StatCard
          title="Total Cost (USD)"
          value={fmtCost(totalCost)}
          sub="Claude Sonnet pricing"
          icon={DollarSign}
          iconColor="text-emerald-600"
        />
        <StatCard
          title="Total Savings (USD)"
          value={fmtCost(totalSavings)}
          sub="50% batch + caching"
          icon={TrendingUp}
          iconColor="text-teal-600"
        />
        <StatCard
          title="Avg Cost / Case"
          value={totalTestCases > 0 ? fmtCost(totalCost / totalTestCases) : "$0.00"}
          sub="Per test case generated"
          icon={TrendingUp}
          iconColor="text-purple-600"
        />
      </div>

      {/* ── Empty state ─────────────────────────────────────────────────────── */}
      {entries.length === 0 && (
        <Card className="rounded-xl border border-border/60 bg-white shadow-sm">
          <CardContent className="py-20 flex flex-col items-center justify-center gap-3">
            <Zap className="h-12 w-12 text-muted-foreground/30" />
            <p className="text-base font-medium text-muted-foreground">No token usage recorded yet</p>
            <p className="text-sm text-muted-foreground/70 text-center max-w-xs">
              Token data will appear here as soon as users generate test cases using the AI option.
            </p>
          </CardContent>
        </Card>
      )}

      {entries.length > 0 && (
        <>
          {/* ── Batch API vs Real-time API Breakdown ──────────────────────────── */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Batch API Card */}
            <Card className="rounded-xl border border-border/60 bg-white shadow-sm overflow-hidden hover:shadow-md transition-all duration-200">
              <CardHeader className="bg-gradient-to-r from-blue-50/50 to-indigo-50/10 pb-3 border-b border-border/40">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div className="p-1 rounded bg-blue-100 text-blue-700">
                      <Zap className="h-4 w-4 animate-pulse" />
                    </div>
                    <div>
                      <CardTitle className="text-sm font-semibold text-foreground">Batch API Consumption</CardTitle>
                      <p className="text-[10px] text-muted-foreground mt-0.5">Asynchronous suite generation</p>
                    </div>
                  </div>
                  <Badge variant="outline" className="bg-blue-50 hover:bg-blue-100 text-blue-700 border-blue-200 font-semibold text-[10px] uppercase tracking-wider px-1.5 py-0.5">
                    50% Discount Active
                  </Badge>
                </div>
              </CardHeader>
              <CardContent className="pt-4 grid grid-cols-2 gap-4">
                <div className="space-y-1">
                  <p className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">Input Tokens</p>
                  <p className="text-2xl font-extrabold text-blue-600 font-mono tabular-nums">{batchInputTok.toLocaleString()}</p>
                  <p className="text-[10px] text-muted-foreground">Suite request payloads</p>
                </div>
                <div className="space-y-1">
                  <p className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">Output Tokens</p>
                  <p className="text-2xl font-extrabold text-green-600 font-mono tabular-nums">{batchOutputTok.toLocaleString()}</p>
                  <p className="text-[10px] text-muted-foreground">Generated test cases</p>
                </div>

                <div className="space-y-1 border-t border-border/40 pt-3">
                  <p className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">Total Tokens</p>
                  <p className="text-lg font-bold text-foreground font-mono tabular-nums">{batchTotalTok.toLocaleString()}</p>
                  <p className="text-[10px] text-muted-foreground">{batchSharePct.toFixed(1)}% of total volume</p>
                </div>
                <div className="space-y-1 border-t border-border/40 pt-3">
                  <p className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">Total Cost (USD)</p>
                  <p className="text-lg font-bold text-emerald-600 font-mono tabular-nums">{fmtCost(batchCost)}</p>
                  <p className="text-[10px] text-muted-foreground">{batchCount} test cases generated</p>
                </div>

                {/* Stacked bar visualization */}
                <div className="col-span-2 space-y-1.5 mt-2">
                  <div className="flex items-center justify-between text-[11px] font-medium">
                    <span className="text-blue-600 flex items-center gap-1">
                      <span className="h-2 w-2 rounded-full bg-blue-500" />
                      Input ({batchInputPct.toFixed(1)}%)
                    </span>
                    <span className="text-green-600 flex items-center gap-1">
                      <span className="h-2 w-2 rounded-full bg-green-500" />
                      Output ({batchOutputPct.toFixed(1)}%)
                    </span>
                  </div>
                  <div className="h-2.5 w-full bg-slate-100/80 rounded-full overflow-hidden flex">
                    <div style={{ width: `${batchInputPct}%` }} className="bg-blue-500 h-full transition-all duration-500" />
                    <div style={{ width: `${batchOutputPct}%` }} className="bg-green-500 h-full transition-all duration-500" />
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Standard/Real-time API Card */}
            <Card className="rounded-xl border border-border/60 bg-white shadow-sm overflow-hidden hover:shadow-md transition-all duration-200">
              <CardHeader className="bg-gradient-to-r from-amber-50/50 to-orange-50/10 pb-3 border-b border-border/40">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div className="p-1 rounded bg-amber-100 text-amber-700">
                      <Coins className="h-4 w-4" />
                    </div>
                    <div>
                      <CardTitle className="text-sm font-semibold text-foreground">Standard (Real-time) API</CardTitle>
                      <p className="text-[10px] text-muted-foreground mt-0.5">Interactive / Failure analysis queries</p>
                    </div>
                  </div>
                  <Badge variant="outline" className="bg-slate-100 hover:bg-slate-200 text-slate-700 border-slate-200 font-semibold text-[10px] uppercase tracking-wider px-1.5 py-0.5">
                    Standard Pricing
                  </Badge>
                </div>
              </CardHeader>
              <CardContent className="pt-4 grid grid-cols-2 gap-4">
                <div className="space-y-1">
                  <p className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">Input Tokens</p>
                  <p className="text-2xl font-extrabold text-blue-600 font-mono tabular-nums">{stdInputTok.toLocaleString()}</p>
                  <p className="text-[10px] text-muted-foreground">Interactive request payloads</p>
                </div>
                <div className="space-y-1">
                  <p className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">Output Tokens</p>
                  <p className="text-2xl font-extrabold text-green-600 font-mono tabular-nums">{stdOutputTok.toLocaleString()}</p>
                  <p className="text-[10px] text-muted-foreground">AI response payloads</p>
                </div>

                <div className="space-y-1 border-t border-border/40 pt-3">
                  <p className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">Total Tokens</p>
                  <p className="text-lg font-bold text-foreground font-mono tabular-nums">{stdTotalTok.toLocaleString()}</p>
                  <p className="text-[10px] text-muted-foreground">{stdSharePct.toFixed(1)}% of total volume</p>
                </div>
                <div className="space-y-1 border-t border-border/40 pt-3">
                  <p className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">Total Cost (USD)</p>
                  <p className="text-lg font-bold text-emerald-600 font-mono tabular-nums">{fmtCost(stdCost)}</p>
                  <p className="text-[10px] text-muted-foreground">{stdCount} test cases generated</p>
                </div>

                {/* Stacked bar visualization */}
                <div className="col-span-2 space-y-1.5 mt-2">
                  <div className="flex items-center justify-between text-[11px] font-medium">
                    <span className="text-blue-600 flex items-center gap-1">
                      <span className="h-2 w-2 rounded-full bg-blue-500" />
                      Input ({stdInputPct.toFixed(1)}%)
                    </span>
                    <span className="text-green-600 flex items-center gap-1">
                      <span className="h-2 w-2 rounded-full bg-green-500" />
                      Output ({stdOutputPct.toFixed(1)}%)
                    </span>
                  </div>
                  <div className="h-2.5 w-full bg-slate-100/80 rounded-full overflow-hidden flex">
                    <div style={{ width: `${stdInputPct}%` }} className="bg-blue-500 h-full transition-all duration-500" />
                    <div style={{ width: `${stdOutputPct}%` }} className="bg-green-500 h-full transition-all duration-500" />
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* ── Charts row ────────────────────────────────────────────────────── */}
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2 xl:grid-cols-3">
            {/* Tokens by test type */}
            <Card className="rounded-xl border border-border/60 bg-white shadow-sm xl:col-span-2">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-semibold">Token Usage by Test Type</CardTitle>
                <p className="text-xs text-muted-foreground">Input vs output tokens per category</p>
              </CardHeader>
              <CardContent className="pt-0">
                <div className="h-[260px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={tokensByType} margin={{ left: 10, right: 10, top: 5, bottom: 5 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                      <XAxis dataKey="type" fontSize={11} tickLine={false} axisLine={false} tick={{ fill: "hsl(var(--muted-foreground))" }} />
                      <YAxis fontSize={11} tickLine={false} axisLine={false} tick={{ fill: "hsl(var(--muted-foreground))" }} tickFormatter={(v) => v >= 1000 ? `${(v/1000).toFixed(0)}k` : v} />
                      <RechartsTooltip
                        contentStyle={{ borderRadius: "8px", border: "1px solid hsl(var(--border))", fontSize: "12px" }}
                        formatter={(val: any, name: any) => [Number(val || 0).toLocaleString(), String(name) === "input" ? "Input Tokens" : "Output Tokens"]}
                      />
                      <Bar dataKey="input"  name="input"  stackId="a" fill="#3b82f6" radius={[0,0,0,0]} />
                      <Bar dataKey="output" name="output" stackId="a" fill="#22c55e" radius={[6,6,0,0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>

            {/* Cost by project */}
            <Card className="rounded-xl border border-border/60 bg-white shadow-sm">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-semibold">Cost by Project</CardTitle>
                <p className="text-xs text-muted-foreground">Total USD spent per project</p>
              </CardHeader>
              <CardContent className="pt-0">
                <div className="h-[260px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie data={costByProject} cx="50%" cy="45%" outerRadius={80} dataKey="value" nameKey="name" label={({ name, percent }) => `${name} (${((percent || 0) * 100).toFixed(0)}%)`} labelLine={false} fontSize={10}>
                        {costByProject.map((entry, i) => (
                          <Cell key={i} fill={entry.color} />
                        ))}
                      </Pie>
                      <RechartsTooltip formatter={(v: any) => [fmtCost(Number(v || 0)), "Cost"]} contentStyle={{ borderRadius: "8px", border: "1px solid hsl(var(--border))", fontSize: "12px" }} />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* ── Per-type summary cards ────────────────────────────────────────── */}
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-3 xl:grid-cols-5">
            {tokensByType.map(t => (
              <Card key={t.type} className="rounded-xl border border-border/60 bg-white p-4 shadow-sm hover:shadow-md transition-shadow">
                <div className="flex items-center gap-2 mb-2">
                  <span className="h-2.5 w-2.5 rounded-full flex-shrink-0" style={{ backgroundColor: t.color }} />
                  <p className="text-xs font-semibold text-foreground truncate">{t.type}</p>
                </div>
                <p className="text-lg font-bold text-foreground">{t.total.toLocaleString()}</p>
                <p className="text-xs text-muted-foreground">tokens · {t.count} cases</p>
                <p className="text-xs font-medium mt-1" style={{ color: t.color }}>{fmtCost(t.cost)}</p>
              </Card>
            ))}
          </div>

          {/* ── Tokens by HTTP method ─────────────────────────────────────────── */}
          <Card className="rounded-xl border border-border/60 bg-white shadow-sm">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-semibold">Tokens by HTTP Method</CardTitle>
              <p className="text-xs text-muted-foreground">Which request methods consume most tokens</p>
            </CardHeader>
            <CardContent className="pt-0">
              <div className="h-[200px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={tokensByMethod} margin={{ left: 10, right: 10, top: 5, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                    <XAxis dataKey="method" fontSize={11} tickLine={false} axisLine={false} tick={{ fill: "hsl(var(--muted-foreground))" }} />
                    <YAxis fontSize={11} tickLine={false} axisLine={false} tick={{ fill: "hsl(var(--muted-foreground))" }} tickFormatter={(v) => v >= 1000 ? `${(v/1000).toFixed(0)}k` : v} />
                    <RechartsTooltip contentStyle={{ borderRadius: "8px", border: "1px solid hsl(var(--border))", fontSize: "12px" }} formatter={(v: any) => [Number(v || 0).toLocaleString(), "Tokens"]} />
                    <Bar dataKey="total" radius={[6, 6, 0, 0]} maxBarSize={60}>
                      {tokensByMethod.map((entry, i) => (
                        <Cell key={i} fill={entry.color} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>

          {/* ── Detailed log table ────────────────────────────────────────────── */}
          <Card className="rounded-xl border border-border/60 bg-white shadow-sm overflow-hidden">
            {/* Table toolbar */}
            <div className="p-4 border-b border-border/50 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h3 className="text-sm font-semibold text-foreground">Detailed Token Log</h3>
                <p className="text-xs text-muted-foreground">
                  {filtered.length} of {entries.length} entries
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                {/* Search */}
                <div className="relative">
                  <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
                  <Input
                    placeholder="Search tests, projects, endpoints…"
                    value={search}
                    onChange={e => setSearch(e.target.value)}
                    className="pl-8 h-8 w-56 text-xs"
                  />
                </div>
                {/* Type filter */}
                <Select value={filterType} onValueChange={setFilterType}>
                  <SelectTrigger className="h-8 w-36 text-xs"><SelectValue placeholder="Test Type" /></SelectTrigger>
                  <SelectContent>
                    {allTypes.map(t => <SelectItem key={t} value={t} className="text-xs">{t}</SelectItem>)}
                  </SelectContent>
                </Select>
                {/* Project filter */}
                <Select value={filterProject} onValueChange={setFilterProject}>
                  <SelectTrigger className="h-8 w-40 text-xs"><SelectValue placeholder="Project" /></SelectTrigger>
                  <SelectContent>
                    {allProjects.map(p => <SelectItem key={p} value={p} className="text-xs">{p}</SelectItem>)}
                  </SelectContent>
                </Select>
                {/* API Mode filter */}
                <Select value={filterApiMode} onValueChange={setFilterApiMode}>
                  <SelectTrigger className="h-8 w-32 text-xs">
                    <SelectValue placeholder="API Mode" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="All" className="text-xs">All API Modes</SelectItem>
                    <SelectItem value="Batch" className="text-xs">Batch API</SelectItem>
                    <SelectItem value="Real-time" className="text-xs">Real-time</SelectItem>
                  </SelectContent>
                </Select>
                {/* Method filter */}
                <Select value={filterMethod} onValueChange={setFilterMethod}>
                  <SelectTrigger className="h-8 w-28 text-xs"><SelectValue placeholder="Method" /></SelectTrigger>
                  <SelectContent>
                    {allMethods.map(m => <SelectItem key={m} value={m} className="text-xs">{m}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="overflow-x-auto">
              <Table>
                <TableHeader className="bg-muted/40">
                  <TableRow>
                    <TableHead className="text-xs font-medium uppercase tracking-wide text-muted-foreground whitespace-nowrap">Timestamp</TableHead>
                    <TableHead className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Project</TableHead>
                    <TableHead className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Test Case</TableHead>
                    <TableHead className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Endpoint</TableHead>
                    <TableHead className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Method</TableHead>
                    <TableHead className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Type</TableHead>
                    <TableHead className="text-xs font-medium uppercase tracking-wide text-muted-foreground text-right">Input</TableHead>
                    <TableHead className="text-xs font-medium uppercase tracking-wide text-muted-foreground text-right">Output</TableHead>
                    <TableHead className="text-xs font-medium uppercase tracking-wide text-muted-foreground text-right">Total</TableHead>
                    <TableHead className="text-xs font-medium uppercase tracking-wide text-muted-foreground text-right">Cost (USD)</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filtered.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={10} className="text-center py-12">
                        <Search className="mx-auto h-8 w-8 text-muted-foreground/30 mb-2" />
                        <p className="text-sm text-muted-foreground">No entries match your filters</p>
                      </TableCell>
                    </TableRow>
                  ) : (
                    filtered.map((entry, i) => (
                      <TableRow key={i} className="hover:bg-muted/30">
                        <TableCell className="text-xs text-muted-foreground whitespace-nowrap">{fmtTs(entry.timestamp)}</TableCell>
                        <TableCell className="text-xs font-medium text-foreground max-w-[120px] truncate">{entry.project_name}</TableCell>
                        <TableCell className="text-xs text-foreground max-w-[200px]">
                          <span className="line-clamp-2">{entry.test_case_name}</span>
                        </TableCell>
                        <TableCell className="text-xs text-muted-foreground font-mono max-w-[160px] truncate">{entry.endpoint_path}</TableCell>
                        <TableCell>
                          <Badge variant="outline" className={`text-[10px] font-semibold px-1.5 py-0.5 ${methodBadgeClass(entry.method)}`}>
                            {entry.method?.toUpperCase()}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <div className="flex flex-col gap-1 items-start">
                            <span
                              className="inline-flex items-center gap-1 text-xs font-medium px-1.5 py-0.5 rounded-full"
                              style={{ backgroundColor: `${typeColor(entry.test_type)}18`, color: typeColor(entry.test_type) }}
                            >
                              {entry.test_type}
                            </span>
                            {entry.is_batch ? (
                              <Badge className="bg-blue-50 hover:bg-blue-100 text-blue-700 border-blue-200 text-[9px] font-semibold px-1 py-0" variant="outline">
                                Batch
                              </Badge>
                            ) : (
                              <Badge className="bg-slate-50 hover:bg-slate-100 text-slate-600 border-slate-200 text-[9px] font-semibold px-1 py-0" variant="outline">
                                Real-time
                              </Badge>
                            )}
                          </div>
                        </TableCell>
                        <TableCell className="text-xs text-right text-blue-600 font-mono tabular-nums">{entry.input_tokens.toLocaleString()}</TableCell>
                        <TableCell className="text-xs text-right text-green-600 font-mono tabular-nums">{entry.output_tokens.toLocaleString()}</TableCell>
                        <TableCell className="text-xs text-right font-semibold text-foreground font-mono tabular-nums">{entry.total_tokens.toLocaleString()}</TableCell>
                        <TableCell className="text-xs text-right text-emerald-600 font-semibold font-mono tabular-nums">{fmtCost(entry.cost_usd)}</TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </div>

            {/* Table footer totals */}
            {filtered.length > 0 && (
              <div className="px-4 py-3 border-t border-border/50 bg-muted/20 flex flex-wrap items-center justify-between gap-2">
                <p className="text-xs text-muted-foreground">
                  Showing <span className="font-semibold text-foreground">{filtered.length}</span> entries
                </p>
                <div className="flex items-center gap-6 text-xs">
                  <span className="text-muted-foreground">
                    Input: <span className="font-semibold text-blue-600">{filtered.reduce((a,e)=>a+e.input_tokens,0).toLocaleString()}</span>
                  </span>
                  <span className="text-muted-foreground">
                    Output: <span className="font-semibold text-green-600">{filtered.reduce((a,e)=>a+e.output_tokens,0).toLocaleString()}</span>
                  </span>
                  <span className="text-muted-foreground">
                    Total: <span className="font-semibold text-foreground">{filtered.reduce((a,e)=>a+e.total_tokens,0).toLocaleString()}</span>
                  </span>
                  <span className="text-muted-foreground">
                    Cost: <span className="font-semibold text-emerald-600">{fmtCost(filtered.reduce((a,e)=>a+e.cost_usd,0))}</span>
                  </span>
                </div>
              </div>
            )}
          </Card>
        </>
      )}
    </div>
  )
}
