import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { SuperAdminDashboardSkeleton } from "@/components/shared/LoadingSkeletons"
import StatCard from "@/components/shared/StatCard"
import {
  Building2,
  Users,
  Zap,
  DollarSign,
  Globe,
  Activity,
} from "lucide-react"
import {
  PieChart,
  Pie,
  Cell,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  BarChart,
  Bar,
  Legend,
} from "recharts"
import type { SuperAdminStats, SuperAdminTenant } from "@/services/backendClient"

// ─── Types ──────────────────────────────────────────────────────────
interface DashboardProps {
  stats: SuperAdminStats | null
  tenants: SuperAdminTenant[]
  loading: boolean
}



// ─── Component ──────────────────────────────────────────────────────
export default function SuperAdminDashboard({ stats, tenants, loading }: DashboardProps) {
  // Computed values from tenants
  const activeTenants = tenants.filter(t => t.status === "ACTIVE").length
  const totalUsers = stats?.totalUsers ?? 0

  // Plan distribution for pie chart
  const planCounts: Record<string, number> = {}
  tenants.forEach(t => {
    const plan = (t.plan || "FREE").toUpperCase()
    const label = plan === "PRO" ? "Pro" : plan === "ENTERPRISE" ? "Enterprise" : "Free"
    planCounts[label] = (planCounts[label] || 0) + 1
  })
  const totalForPie = tenants.length || 1
  const pieData = Object.entries(planCounts).map(([name, value]) => ({
    name,
    value,
    percentage: Math.round((value / totalForPie) * 100),
  }))
  if (pieData.length === 0) {
    pieData.push({ name: "No Data", value: 1, percentage: 100 })
  }

  const PIE_COLORS: Record<string, string> = {
    Free: "#94a3b8",     // slate-400
    Pro: "#22c55e",      // green-500
    Enterprise: "#3b82f6", // blue-500
    "No Data": "#e2e8f0",
  }

  // Mock Active Users data (DAU vs MAU) — last 7 days
  const today = new Date()
  const activeUsersData = Array.from({ length: 7 }, (_, i) => {
    const d = new Date(today)
    d.setDate(d.getDate() - (6 - i))
    const label = d.toLocaleDateString("en-US", { month: "short", day: "numeric" })
    const base = Math.max(10, totalUsers)
    return {
      date: label,
      DAU: Math.floor(base * 0.15 + Math.random() * base * 0.15),
      MAU: Math.floor(base * 0.5 + Math.random() * base * 0.3),
    }
  })

  // Mock Test Execution Trends — last 6 months
  const months = ["Oct", "Nov", "Dec", "Jan", "Feb", "Mar"]
  const totalRuns = tenants.reduce(
    (acc, t) => acc + t.projects.reduce((a, _p) => a + 1, 0),
    0
  )
  const testTrendData = months.map((m, i) => ({
    month: m,
    runs: Math.floor(Math.max(500, (totalRuns * 100)) * (0.5 + i * 0.1 + Math.random() * 0.2)),
  }))

  const statCards = [
    {
      label: "Total Tenants",
      value: stats?.totalTenants ?? 0,
      icon: Building2,
    },
    {
      label: "Total Users",
      value: (stats?.totalUsers ?? 0).toLocaleString(),
      icon: Users,
    },
    {
      label: "Active Tenants",
      value: stats?.activeTenants ?? activeTenants,
      icon: Zap,
    },
    {
      label: "Total Projects",
      value: (stats?.totalProjects ?? 0).toLocaleString(),
      icon: DollarSign,
    },
    {
      label: "Test Runs",
      value: (stats?.totalTestRuns ?? 0).toLocaleString(),
      icon: Globe,
    },
    {
      label: "System Health",
      value: "99.8%",
      icon: Activity,
    },
  ]

  if (loading) {
    return <SuperAdminDashboardSkeleton />
  }

  return (
    <div className="space-y-6">
      {/* Stat Cards */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-3 xl:grid-cols-6">
        {statCards.map(s => (
          <StatCard
            key={s.label}
            title={s.label}
            value={s.value}
            icon={s.icon}
          />
        ))}
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* User Distribution Pie Chart */}
        <Card className="rounded-xl border border-border/60 bg-white shadow-sm">
          <CardHeader className="pb-2">
            <CardTitle className="text-base font-semibold">User Distribution</CardTitle>
            <p className="text-xs text-muted-foreground">By subscription plan</p>
          </CardHeader>
          <CardContent className="pt-0">
            <div className="h-[280px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={pieData}
                    cx="50%"
                    cy="50%"
                    innerRadius={0}
                    outerRadius={100}
                    paddingAngle={2}
                    dataKey="value"
                    label={({ name, percentage }: any) => `${name}: ${percentage}%`}
                    labelLine
                  >
                    {pieData.map((entry, index) => (
                      <Cell
                        key={`cell-${index}`}
                        fill={PIE_COLORS[entry.name] || "#94a3b8"}
                        stroke="white"
                        strokeWidth={2}
                      />
                    ))}
                  </Pie>
                  <RechartsTooltip
                    contentStyle={{
                      borderRadius: "8px",
                      border: "1px solid hsl(var(--border))",
                      fontSize: "12px",
                    }}
                    formatter={(value: any, name: any) => [
                      `${value} tenants`,
                      name,
                    ]}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        {/* Active Users Line Chart */}
        <Card className="rounded-xl border border-border/60 bg-white shadow-sm">
          <CardHeader className="pb-2">
            <CardTitle className="text-base font-semibold">Active Users</CardTitle>
            <p className="text-xs text-muted-foreground">Daily vs Monthly active users</p>
          </CardHeader>
          <CardContent className="pt-0">
            <div className="h-[280px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={activeUsersData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                  <XAxis
                    dataKey="date"
                    fontSize={11}
                    tickLine={false}
                    axisLine={false}
                    tick={{ fill: "hsl(var(--muted-foreground))" }}
                  />
                  <YAxis
                    fontSize={11}
                    tickLine={false}
                    axisLine={false}
                    tick={{ fill: "hsl(var(--muted-foreground))" }}
                  />
                  <RechartsTooltip
                    contentStyle={{
                      borderRadius: "8px",
                      border: "1px solid hsl(var(--border))",
                      fontSize: "12px",
                    }}
                  />
                  <Legend
                    verticalAlign="bottom"
                    height={36}
                    iconType="plainline"
                    wrapperStyle={{ fontSize: "12px" }}
                  />
                  <Line
                    type="monotone"
                    dataKey="DAU"
                    stroke="#6366f1"
                    strokeWidth={2}
                    dot={{ r: 4, fill: "#6366f1" }}
                    activeDot={{ r: 6 }}
                  />
                  <Line
                    type="monotone"
                    dataKey="MAU"
                    stroke="#8b5cf6"
                    strokeWidth={2}
                    dot={{ r: 4, fill: "#8b5cf6" }}
                    activeDot={{ r: 6 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Test Execution Trends Bar Chart */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card className="rounded-xl border border-border/60 bg-white shadow-sm">
          <CardHeader className="pb-2">
            <CardTitle className="text-base font-semibold">Test Execution Trends</CardTitle>
            <p className="text-xs text-muted-foreground">Monthly test runs</p>
            <span className="text-slate-500/50 text-[10px] break-all">{JSON.stringify(stats)}</span>
          </CardHeader>
          <CardContent className="pt-0">
            <div className="h-[300px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={testTrendData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                  <XAxis
                    dataKey="month"
                    fontSize={11}
                    tickLine={false}
                    axisLine={false}
                    tick={{ fill: "hsl(var(--muted-foreground))" }}
                  />
                  <YAxis
                    fontSize={11}
                    tickLine={false}
                    axisLine={false}
                    tick={{ fill: "hsl(var(--muted-foreground))" }}
                  />
                  <RechartsTooltip
                    contentStyle={{
                      borderRadius: "8px",
                      border: "1px solid hsl(var(--border))",
                      fontSize: "12px",
                    }}
                    formatter={(value: any) => [Number(value).toLocaleString(), "Test Runs"]}
                  />
                  <Bar
                    dataKey="runs"
                    fill="#22c55e"
                    radius={[6, 6, 0, 0]}
                    maxBarSize={60}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
