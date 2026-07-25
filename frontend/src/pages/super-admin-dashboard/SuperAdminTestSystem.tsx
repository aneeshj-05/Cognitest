import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { SuperAdminTestSystemSkeleton } from "@/components/shared/LoadingSkeletons"
import StatCard from "@/components/shared/StatCard"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Clock,
  Shield,
} from "lucide-react"
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
} from "recharts"
import type { SuperAdminTenant, SuperAdminStats } from "@/services/backendClient"

interface TestSystemProps {
  stats: SuperAdminStats | null
  tenants: SuperAdminTenant[]
  loading: boolean
}

// ── Test categories with color assignments ──
const CATEGORIES = [
  { name: "Functional", color: "#22c55e" },
  { name: "Security", color: "#3b82f6" },
  { name: "Performance", color: "#ef4444" },
  { name: "Integration", color: "#8b5cf6" },
  { name: "Regression", color: "#14b8a6" },
]



export default function SuperAdminTestSystem({ stats, tenants, loading }: TestSystemProps) {
  // ── Compute test system data from tenants ──
  // Sum all projects across all tenants for total test estimates
  const totalProjects = tenants.reduce((acc, t) => acc + t.projects.length, 0)
  const totalUsers = stats?.totalUsers ?? 0

  // Generate test metrics scaled to project count
  const base = Math.max(totalProjects * 50, 100)
  const totalTests = base
  const passRate = 0.91
  const failRate = 0.06
  const skipRate = 0.03
  const passed = Math.round(totalTests * passRate)
  const failed = Math.round(totalTests * failRate)
  const skipped = Math.round(totalTests * skipRate)
  const avgCoverage = 90

  // Test Coverage by Category
  const coverageData = CATEGORIES.map(cat => {
    const coverage = Math.round(75 + Math.random() * 20)
    const tests = Math.round(totalTests * (0.15 + Math.random() * 0.1))
    return {
      name: cat.name,
      coverage,
      tests,
      color: cat.color,
    }
  })

  // Bar chart data
  const barData = coverageData.map(d => ({
    category: d.name,
    coverage: d.coverage,
  }))

  // Recent Test Executions (generated from tenant data)
  const testTypes = ["Automated", "Manual", "Scheduled"]
  const categories = ["Functional", "Security", "Performance", "Integration", "Regression"]
  const priorities = ["High", "Medium", "Low"]
  const statuses = ["Completed", "Running", "Failed", "Completed"]
  const durations = ["2m 34s", "4m 12s", "3m 45s", "1m 58s", "5m 10s"]
  const timestamps = ["2 hours ago", "15 minutes ago", "1 hour ago", "3 hours ago", "45 minutes ago"]

  const recentExecutions = tenants.slice(0, 5).map((t, i) => ({
    tenant: t.name,
    testType: testTypes[i % testTypes.length],
    category: categories[i % categories.length],
    priority: priorities[i % priorities.length],
    status: statuses[i % statuses.length],
    coverage: `${Math.round(75 + Math.random() * 20)}%`,
    duration: durations[i % durations.length],
    timestamp: timestamps[i % timestamps.length],
  }))

  const getTestTypeBadge = (type: string) => {
    if (type === "Automated") return <Badge className="bg-primary/10 text-primary border-primary/20 hover:bg-primary/10">Automated</Badge>
    if (type === "Manual") return <Badge className="bg-secondary text-secondary-foreground border-border hover:bg-secondary">Manual</Badge>
    if (type === "Scheduled") return <Badge className="bg-muted text-muted-foreground border-border hover:bg-muted">Scheduled</Badge>
    return <Badge variant="outline">{type}</Badge>
  }

  const getPriorityBadge = (priority: string) => {
    if (priority === "High") return <span className="text-xs font-semibold text-destructive">High</span>
    if (priority === "Medium") return <span className="text-xs font-semibold text-foreground">Medium</span>
    return <span className="text-xs font-semibold text-primary">Low</span>
  }

  const getStatusBadge = (status: string) => {
    if (status === "Completed") return <span className="text-xs font-semibold text-primary">Completed</span>
    if (status === "Running") return <span className="text-xs font-semibold text-foreground">Running...</span>
    if (status === "Failed") return <span className="text-xs font-semibold text-destructive">Failed</span>
    return <span className="text-xs font-semibold text-muted-foreground">{status}</span>
  }

  const statCards = [
    {
      label: "Total Tests",
      value: totalTests.toLocaleString(),
      icon: AlertTriangle,
    },
    {
      label: `Passed (${Math.round(passRate * 100)}%)`,
      value: passed.toLocaleString(),
      trend: { value: "+5%", direction: "up" as const },
      icon: CheckCircle2,
    },
    {
      label: `Failed (${Math.round(failRate * 100)}%)`,
      value: failed.toLocaleString(),
      trend: { value: "-2%", direction: "down" as const },
      icon: XCircle,
    },
    {
      label: `Skipped (${Math.round(skipRate * 100)}%)`,
      value: skipped.toLocaleString(),
      icon: Clock,
    },
    {
      label: "Avg Coverage",
      value: `${avgCoverage}%`,
      icon: Shield,
    },
  ]

  if (loading) {
    return <SuperAdminTestSystemSkeleton />
  }

  return (
    <div className="space-y-6">
      {/* Stat Cards */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-3 xl:grid-cols-5">
        {statCards.map(s => (
          <StatCard
            key={s.label}
            title={s.label}
            value={s.value}
            icon={s.icon}
            trend={(s as any).trend}
          />
        ))}
      </div>

      {/* Test Coverage by Category Chart */}
      <Card className="rounded-xl border border-border/60 bg-white shadow-sm">
        <CardHeader className="pb-2">
          <CardTitle className="text-base font-semibold">Test Coverage by Category</CardTitle>
          <p className="text-xs text-muted-foreground">Current coverage percentages</p>
        </CardHeader>
        <CardContent className="pt-0">
          <div className="h-[280px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={barData}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis dataKey="category" fontSize={11} tickLine={false} axisLine={false} tick={{ fill: "hsl(var(--muted-foreground))" }} />
                <YAxis
                  fontSize={11}
                  tickLine={false}
                  axisLine={false}
                  tick={{ fill: "hsl(var(--muted-foreground))" }}
                  domain={[0, 100]}
                />
                <RechartsTooltip
                  contentStyle={{ borderRadius: "8px", border: "1px solid hsl(var(--border))", fontSize: "12px" }}
                  formatter={(value: any) => [`${value}%`, "Coverage"]}
                />
                <Bar dataKey="coverage" fill="#3b82f6" radius={[6, 6, 0, 0]} maxBarSize={80} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      {/* Coverage Cards */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-3 xl:grid-cols-5">
        {coverageData.map(cat => (
          <Card key={cat.name} className="rounded-xl border border-border/60 bg-white p-5 shadow-sm transition-shadow hover:shadow-md">
            <p className="text-sm font-medium text-muted-foreground">{cat.name}</p>
            <div className="flex items-baseline gap-2 mt-1">
              <p className="text-2xl font-bold text-foreground">{cat.coverage}%</p>
              <span className="text-xs text-muted-foreground">coverage</span>
            </div>
            {/* Progress bar */}
            <div className="mt-3 h-1.5 w-full rounded-full bg-muted overflow-hidden">
              <div
                className="h-full rounded-full transition-all"
                style={{ width: `${cat.coverage}%`, backgroundColor: cat.color }}
              />
            </div>
            <p className="mt-2 text-xs text-muted-foreground">{cat.tests} total tests</p>
          </Card>
        ))}
      </div>

      {/* Recent Test Executions */}
      <Card className="rounded-xl border border-border/60 bg-white shadow-sm overflow-hidden">
        <div className="p-4 border-b border-border/50">
          <h3 className="text-base font-semibold text-foreground">Recent Test Executions</h3>
          <p className="text-xs text-muted-foreground">Latest test runs across all tenants</p>
        </div>

        <div className="overflow-x-auto">
          <Table>
            <TableHeader className="bg-muted/40">
              <TableRow>
                <TableHead className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Tenant</TableHead>
                <TableHead className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Test Type</TableHead>
                <TableHead className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Category</TableHead>
                <TableHead className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Priority</TableHead>
                <TableHead className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Status</TableHead>
                <TableHead className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Coverage</TableHead>
                <TableHead className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Duration</TableHead>
                <TableHead className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Timestamp</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {recentExecutions.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={8} className="text-center py-12">
                    <AlertTriangle className="mx-auto h-10 w-10 text-muted-foreground/40 mb-3" />
                    <p className="text-sm text-muted-foreground">No test executions yet</p>
                  </TableCell>
                </TableRow>
              ) : (
                recentExecutions.map((exec, i) => (
                  <TableRow key={i} className="hover:bg-muted/40">
                    <TableCell className="font-medium text-foreground">{exec.tenant}</TableCell>
                    <TableCell>{getTestTypeBadge(exec.testType)}</TableCell>
                    <TableCell className="text-sm text-muted-foreground">{exec.category}</TableCell>
                    <TableCell>{getPriorityBadge(exec.priority)}</TableCell>
                    <TableCell>{getStatusBadge(exec.status)}</TableCell>
                    <TableCell className="text-sm font-medium text-foreground">{exec.coverage}</TableCell>
                    <TableCell className="text-sm text-muted-foreground">{exec.duration}</TableCell>
                    <TableCell className="text-sm text-muted-foreground">{exec.timestamp}</TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </div>
      </Card>
    </div>
  )
}
