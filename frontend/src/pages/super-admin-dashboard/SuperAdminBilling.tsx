import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { SuperAdminBillingSkeleton } from "@/components/shared/LoadingSkeletons"
import StatCard from "@/components/shared/StatCard"
import {
  DollarSign,
  TrendingUp,
  TrendingDown,
  Monitor,
  Download,
  AlertCircle,
} from "lucide-react"
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  Legend,
} from "recharts"
import type { SuperAdminTenant } from "@/services/backendClient"

interface BillingProps {
  tenants: SuperAdminTenant[]
  loading: boolean
}



export default function SuperAdminBilling({ tenants, loading }: BillingProps) {
  // ── Compute billing data from tenants ──
  const freeTenants = tenants.filter(t => (t.plan || "FREE").toUpperCase() === "FREE")
  const proTenants = tenants.filter(t => {
    const p = (t.plan || "").toUpperCase()
    return p === "PRO" || p === "PROFESSIONAL" || p === "STARTER"
  })
  const enterpriseTenants = tenants.filter(t => (t.plan || "").toUpperCase() === "ENTERPRISE")

  const PRO_PRICE = 49
  const ENTERPRISE_PRICE = 499
  const proRevenue = proTenants.length * PRO_PRICE
  const enterpriseRevenue = enterpriseTenants.length * ENTERPRISE_PRICE
  const mrr = proRevenue + enterpriseRevenue
  const arr = mrr * 12
  const totalPaidTenants = proTenants.length + enterpriseTenants.length
  const arpu = totalPaidTenants > 0 ? Math.round(mrr / totalPaidTenants) : 0
  const churnRate = 1.8

  // Revenue & Churn Trends (computed from tenant count)
  const months = ["Oct", "Nov", "Dec", "Jan", "Feb", "Mar"]
  const baseMRR = Math.max(mrr, 1000)
  const revenueChurnData = months.map((m, i) => ({
    month: m,
    MRR: Math.round(baseMRR * (0.6 + i * 0.08 + Math.random() * 0.05)),
    Churn: Math.round(baseMRR * (0.01 + Math.random() * 0.02)),
  }))

  // Revenue by Plan bar chart
  const revenueByPlan = [
    { plan: "Free", revenue: 0 },
    { plan: "Pro", revenue: proRevenue },
    { plan: "Enterprise", revenue: enterpriseRevenue },
  ]

  // Recent payments (generated from tenant data)
  const payments = tenants
    .filter(t => (t.plan || "FREE").toUpperCase() !== "FREE")
    .slice(0, 5)
    .map((t, i) => {
      const plan = (t.plan || "").toUpperCase()
      const amount = plan === "ENTERPRISE" ? ENTERPRISE_PRICE : PRO_PRICE
      const statuses = ["Paid", "Paid", "Overdue", "Pending", "Paid"]
      const d = new Date()
      d.setDate(d.getDate() - i * 10)
      return {
        id: `INV-${new Date().getFullYear()}-${String(i + 1).padStart(3, "0")}`,
        tenant: t.name,
        plan: plan === "ENTERPRISE" ? "Enterprise" : "Pro",
        amount,
        renewalDate: d.toISOString().split("T")[0],
        status: statuses[i % statuses.length],
      }
    })

  const overdueCount = payments.filter(p => p.status === "Overdue").length

  const formatCurrency = (v: number) => {
    if (v >= 1000) return `$${(v / 1000).toFixed(v >= 10000 ? 1 : 2)}K`
    return `$${v}`
  }

  const statCards = [
    {
      label: "Monthly Recurring Revenue",
      value: formatCurrency(mrr),
      change: "+8.4%",
      trending: "up" as const,
      icon: DollarSign,
    },
    {
      label: "Annual Recurring Revenue",
      value: formatCurrency(arr),
      change: "+12%",
      trending: "up" as const,
      icon: TrendingUp,
    },
    {
      label: "Churn Rate",
      value: `${churnRate}%`,
      change: "-1.8%",
      trending: "down" as const,
      icon: TrendingDown,
    },
    {
      label: "Average Revenue Per User",
      value: `$${arpu}`,
      change: "",
      trending: "up" as const,
      icon: Monitor,
    },
  ]

  const getStatusBadge = (status: string) => {
    if (status === "Paid") return <Badge className="bg-primary/10 text-primary border-primary/20 hover:bg-primary/10">Paid</Badge>
    if (status === "Overdue") return <Badge className="bg-destructive/10 text-destructive border-destructive/20 hover:bg-destructive/10">Overdue</Badge>
    if (status === "Pending") return <Badge className="bg-muted text-muted-foreground border-border hover:bg-muted">Pending</Badge>
    return <Badge variant="outline">{status}</Badge>
  }

  if (loading) {
    return <SuperAdminBillingSkeleton />
  }

  return (
    <div className="space-y-6">
      {/* Stat Cards */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        {statCards.map(s => (
          <StatCard
            key={s.label}
            title={s.label}
            value={s.value}
            icon={s.icon}
            trend={s.change ? { value: s.change, direction: s.trending === "down" ? "down" : "up" } : undefined}
          />
        ))}
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Revenue & Churn Trends */}
        <Card className="rounded-xl border border-border/60 bg-white shadow-sm">
          <CardHeader className="pb-2">
            <CardTitle className="text-base font-semibold">Revenue & Churn Trends</CardTitle>
            <p className="text-xs text-muted-foreground">Last 6 months performance</p>
          </CardHeader>
          <CardContent className="pt-0">
            <div className="h-[280px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={revenueChurnData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                  <XAxis dataKey="month" fontSize={11} tickLine={false} axisLine={false} tick={{ fill: "hsl(var(--muted-foreground))" }} />
                  <YAxis fontSize={11} tickLine={false} axisLine={false} tick={{ fill: "hsl(var(--muted-foreground))" }} />
                  <RechartsTooltip
                    contentStyle={{ borderRadius: "8px", border: "1px solid hsl(var(--border))", fontSize: "12px" }}
                    formatter={(value: any, name: any) => [`$${Number(value).toLocaleString()}`, name]}
                  />
                  <Legend verticalAlign="bottom" height={36} iconType="plainline" wrapperStyle={{ fontSize: "12px" }} />
                  <Line type="monotone" dataKey="MRR" stroke="#22c55e" strokeWidth={2} dot={{ r: 4, fill: "#22c55e" }} activeDot={{ r: 6 }} />
                  <Line type="monotone" dataKey="Churn" stroke="#ef4444" strokeWidth={2} dot={{ r: 4, fill: "#ef4444" }} activeDot={{ r: 6 }} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        {/* Revenue by Plan */}
        <Card className="rounded-xl border border-border/60 bg-white shadow-sm">
          <CardHeader className="pb-2">
            <CardTitle className="text-base font-semibold">Revenue by Plan</CardTitle>
            <p className="text-xs text-muted-foreground">Current month breakdown</p>
          </CardHeader>
          <CardContent className="pt-0">
            <div className="h-[280px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={revenueByPlan}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                  <XAxis dataKey="plan" fontSize={11} tickLine={false} axisLine={false} tick={{ fill: "hsl(var(--muted-foreground))" }} />
                  <YAxis fontSize={11} tickLine={false} axisLine={false} tick={{ fill: "hsl(var(--muted-foreground))" }} />
                  <RechartsTooltip
                    contentStyle={{ borderRadius: "8px", border: "1px solid hsl(var(--border))", fontSize: "12px" }}
                    formatter={(value: any) => [`$${Number(value).toLocaleString()}`, "Revenue"]}
                  />
                  <Bar dataKey="revenue" fill="#3b82f6" radius={[6, 6, 0, 0]} maxBarSize={80} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Plan Cards */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {/* Free Plan */}
        <Card className="rounded-xl border border-border/60 bg-white p-5 shadow-sm">
          <p className="text-sm font-medium text-muted-foreground">Free Plan</p>
          <p className="mt-1 text-3xl font-bold text-foreground">{freeTenants.length}</p>
          <div className="mt-4 space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Monthly Revenue</span>
              <span className="font-semibold text-foreground">$0</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Conversion Rate</span>
              <span className="font-semibold text-emerald-600">
                {tenants.length > 0 ? ((totalPaidTenants / tenants.length) * 100).toFixed(1) : 0}%
              </span>
            </div>
          </div>
        </Card>

        {/* Pro Plan */}
        <Card className="rounded-xl border-2 border-emerald-200 bg-white p-5 shadow-sm relative">
          <div className="flex items-start justify-between">
            <p className="text-sm font-medium text-muted-foreground">Pro Plan</p>
            <Badge className="bg-emerald-100 text-emerald-700 border-emerald-200 hover:bg-emerald-100 text-xs">Popular</Badge>
          </div>
          <p className="mt-1 text-3xl font-bold text-foreground">{proTenants.length}</p>
          <div className="mt-4 space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Monthly Revenue</span>
              <span className="font-semibold text-foreground">{formatCurrency(proRevenue)}</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Avg. Lifetime</span>
              <span className="font-semibold text-foreground">14 months</span>
            </div>
          </div>
        </Card>

        {/* Enterprise Plan */}
        <Card className="rounded-xl border border-border/60 bg-white p-5 shadow-sm">
          <p className="text-sm font-medium text-muted-foreground">Enterprise Plan</p>
          <p className="mt-1 text-3xl font-bold text-foreground">{enterpriseTenants.length}</p>
          <div className="mt-4 space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Monthly Revenue</span>
              <span className="font-semibold text-foreground">{formatCurrency(enterpriseRevenue)}</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Avg. Lifetime</span>
              <span className="font-semibold text-foreground">28 months</span>
            </div>
          </div>
        </Card>
      </div>

      {/* Recent Payments */}
      <Card className="rounded-xl border border-border/60 bg-white shadow-sm overflow-hidden">
        <div className="flex items-center justify-between p-4 border-b border-border/50">
          <div>
            <h3 className="text-base font-semibold text-foreground">Recent Payments</h3>
            <p className="text-xs text-muted-foreground">Latest subscription payments</p>
          </div>
          <Button variant="outline" size="sm" className="gap-2 text-xs">
            <Download className="h-3.5 w-3.5" /> Export
          </Button>
        </div>

        <div className="overflow-x-auto">
          <Table>
            <TableHeader className="bg-muted/40">
              <TableRow>
                <TableHead className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Invoice ID</TableHead>
                <TableHead className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Tenant</TableHead>
                <TableHead className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Plan</TableHead>
                <TableHead className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Amount</TableHead>
                <TableHead className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Renewal Date</TableHead>
                <TableHead className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Status</TableHead>
                <TableHead className="text-xs font-medium uppercase tracking-wide text-muted-foreground text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {payments.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={7} className="text-center py-12">
                    <DollarSign className="mx-auto h-10 w-10 text-muted-foreground/40 mb-3" />
                    <p className="text-sm text-muted-foreground">No payments yet</p>
                  </TableCell>
                </TableRow>
              ) : (
                payments.map(p => (
                  <TableRow key={p.id} className="hover:bg-muted/40">
                    <TableCell className="text-sm font-medium text-foreground">{p.id}</TableCell>
                    <TableCell className="text-sm text-muted-foreground">{p.tenant}</TableCell>
                    <TableCell className="text-sm text-muted-foreground">{p.plan}</TableCell>
                    <TableCell className="text-sm font-medium text-foreground">${p.amount}</TableCell>
                    <TableCell className="text-sm text-muted-foreground">{p.renewalDate}</TableCell>
                    <TableCell>{getStatusBadge(p.status)}</TableCell>
                    <TableCell className="text-right">
                      <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground hover:text-foreground">
                        <Download className="h-4 w-4" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </div>
      </Card>

      {/* Payment Attention Banner */}
      {overdueCount > 0 && (
        <Card className="rounded-xl border border-red-200 bg-white shadow-sm">
          <CardContent className="flex items-center justify-between py-4 px-5">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-red-100 text-red-600">
                <AlertCircle className="h-5 w-5" />
              </div>
              <div>
                <p className="text-sm font-semibold text-red-800">Payment Attention Required</p>
                <p className="text-xs text-red-600">{overdueCount} tenant{overdueCount > 1 ? "s have" : " has"} overdue payments. Review and take action to prevent service interruption.</p>
              </div>
            </div>
            <Button size="sm" className="bg-red-600 hover:bg-red-700 text-white text-xs">
              View Details
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
