import React, { useMemo } from "react"
import { useOutletContext } from "react-router-dom"
import type { SuperAdminLayoutOutletContext } from "./SuperAdminLayout"
import { SuperAdminInfrastructureSkeleton } from "@/components/shared/LoadingSkeletons"
import { Skeleton } from "@/components/ui/skeleton"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  PieChart,
  Pie,
  Cell,
} from "recharts"
import { getComputedColor } from "@/lib/design-tokens"
import { Cpu, MemoryStick, HardDrive, Cloud, Coins } from "lucide-react"
type SectionHeaderProps = {
  title: string
  description?: string
}

function SectionHeader({ title, description }: SectionHeaderProps) {
  return (
    <div className="space-y-1">
      <h2 className="text-base font-semibold text-foreground">{title}</h2>
      {description ? (
        <p className="text-sm text-muted-foreground">{description}</p>
      ) : null}
    </div>
  )
}

type UsageProgressProps = {
  value: number
  labelLeft?: string
  labelRight?: string
  helperText?: string
}

function UsageProgress({ value, labelLeft, labelRight, helperText }: UsageProgressProps) {
  return (
    <div className="space-y-2">
      <Progress value={value} className="h-2" />
      {(labelLeft || labelRight) ? (
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>{labelLeft}</span>
          <span>{labelRight}</span>
        </div>
      ) : null}
      {helperText ? (
        <p className="text-xs text-muted-foreground">{helperText}</p>
      ) : null}
    </div>
  )
}

function MetricCard({ title, value, subtext, icon: Icon }: { title: string; value: React.ReactNode; subtext?: React.ReactNode; icon: React.ElementType }) {
  return (
    <Card className="relative overflow-hidden bg-white border border-border shadow-sm rounded-xl">
      <div className="p-4">
        <div className="flex items-start justify-between">
          <p className="text-sm font-medium text-muted-foreground">{title}</p>
          <div className="rounded-lg bg-muted/50 p-2 border border-border/50">
            <Icon className="h-4 w-4 text-muted-foreground" />
          </div>
        </div>
        <div className="mt-4">
          <h3 className="text-2xl font-semibold text-foreground">{value}</h3>
          {subtext && <p className="text-xs text-muted-foreground mt-1">{subtext}</p>}
        </div>
      </div>
      <Icon className="absolute -bottom-4 -right-4 h-24 w-24 text-muted-foreground opacity-[0.08]" />
    </Card>
  )
}

function AxisTick(props: any) {
  const { x, y, payload, textAnchor, dy } = props
  return (
    <text x={x} y={y} dy={dy} textAnchor={textAnchor} className="fill-muted-foreground text-[11px]">
      {payload?.value}
    </text>
  )
}

function ChartTooltipContent({ active, payload, label }: any) {
  if (!active || !payload || payload.length === 0) return null

  return (
    <div className="rounded-lg border border-border bg-white p-2 shadow-sm">
      <div className="text-xs font-medium text-foreground">{label}</div>
      <div className="mt-1 space-y-0.5">
        {payload.map((p: any) => (
          <div key={p.dataKey} className="flex items-center justify-between gap-3 text-xs">
            <span className="text-muted-foreground">{p.name ?? p.dataKey}</span>
            <span className="font-medium text-foreground">{p.value}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

export default function InfrastructurePage() {
  const { loading } = useOutletContext<SuperAdminLayoutOutletContext>()

  // Overview metrics (mock)
  const cpuUsagePct = 65
  const ramUsedGb = 12
  const ramTotalGb = 16
  const diskUsedGb = 120
  const diskTotalGb = 256
  const s3UsedGb = 80
  const s3TotalGb = 100

  // Credits (mock)
  const creditsTotal = 1000
  const creditsUsed = 650
  const creditsRemaining = creditsTotal - creditsUsed

  const cpuSeries = useMemo(() => {
    const today = new Date()
    return Array.from({ length: 7 }, (_, i) => {
      const d = new Date(today)
      d.setDate(d.getDate() - (6 - i))
      const label = d.toLocaleDateString("en-US", { month: "short", day: "numeric" })
      return {
        date: label,
        usage: Math.max(30, Math.min(95, Math.round(55 + Math.random() * 25))),
      }
    })
  }, [])

  const ramSeries = useMemo(() => {
    const today = new Date()
    return Array.from({ length: 7 }, (_, i) => {
      const d = new Date(today)
      d.setDate(d.getDate() - (6 - i))
      const label = d.toLocaleDateString("en-US", { month: "short", day: "numeric" })
      return {
        date: label,
        usedGb: Math.max(6, Math.min(ramTotalGb, Number((9 + Math.random() * 5).toFixed(1)))),
      }
    })
  }, [ramTotalGb])

  const chartStrokeCpu = useMemo(() => getComputedColor("chart-1"), [])
  const chartStrokeRam = useMemo(() => getComputedColor("chart-2"), [])
  const chartFillLocal = useMemo(() => getComputedColor("chart-3"), [])
  const chartFillS3 = useMemo(() => getComputedColor("chart-4"), [])

  const storageData = useMemo(() => (
    [
      { name: "Local Storage", value: diskUsedGb },
      { name: "S3 Storage", value: s3UsedGb },
    ]
  ), [diskUsedGb, s3UsedGb])

  if (loading) {
    return <SuperAdminInfrastructureSkeleton />
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
        <MetricCard
          title="CPU Usage"
          value={`${cpuUsagePct}%`}
          icon={Cpu}
        />
        <MetricCard
          title="RAM Usage"
          value={`${Math.round((ramUsedGb / ramTotalGb) * 100)}%`}
          subtext={`${ramUsedGb}GB / ${ramTotalGb}GB`}
          icon={MemoryStick}
        />
        <MetricCard
          title="Disk Usage"
          value={`${Math.round((diskUsedGb / diskTotalGb) * 100)}%`}
          subtext={`${diskUsedGb}GB / ${diskTotalGb}GB`}
          icon={HardDrive}
        />
        <MetricCard
          title="S3 Storage"
          value={`${s3UsedGb}GB`}
          icon={Cloud}
        />
        <MetricCard
          title="Credits"
          value={`${Math.round((creditsUsed / creditsTotal) * 100)}%`}
          subtext={`${creditsUsed} / ${creditsTotal}`}
          icon={Coins}
        />
      </div>

      {/* SECTION 3: CPU + RAM Trends */}
      <SectionHeader
        title="Trends"
        description="Last 7 days resource usage"
      />
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card className="rounded-xl border border-border/60 bg-white shadow-sm">
          <CardHeader className="pb-2">
            <CardTitle className="text-base font-semibold">CPU Usage Over Time</CardTitle>
            <p className="text-sm text-muted-foreground">Daily CPU utilization (%)</p>
          </CardHeader>
          <CardContent className="pt-0">
            <div className="h-[280px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={cpuSeries}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                  <XAxis dataKey="date" tickLine={false} axisLine={false} tick={<AxisTick dy={14} />} />
                  <YAxis tickLine={false} axisLine={false} tick={<AxisTick textAnchor="end" dy={4} />} />
                  <RechartsTooltip content={<ChartTooltipContent />} />
                  <Line
                    type="monotone"
                    dataKey="usage"
                    name="CPU %"
                    stroke={chartStrokeCpu}
                    strokeWidth={2}
                    dot={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        <Card className="rounded-xl border border-border/60 bg-white shadow-sm">
          <CardHeader className="pb-2">
            <CardTitle className="text-base font-semibold">RAM Usage Over Time</CardTitle>
            <p className="text-sm text-muted-foreground">Daily used memory (GB)</p>
          </CardHeader>
          <CardContent className="pt-0">
            <div className="h-[280px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={ramSeries}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                  <XAxis dataKey="date" tickLine={false} axisLine={false} tick={<AxisTick dy={14} />} />
                  <YAxis tickLine={false} axisLine={false} tick={<AxisTick textAnchor="end" dy={4} />} />
                  <RechartsTooltip content={<ChartTooltipContent />} />
                  <Line
                    type="monotone"
                    dataKey="usedGb"
                    name="Used GB"
                    stroke={chartStrokeRam}
                    strokeWidth={2}
                    dot={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* SECTION 4: Storage Breakdown */}
      <Card className="rounded-xl border border-border/60 bg-white shadow-sm">
        <CardHeader className="pb-2">
          <CardTitle className="text-base font-semibold">Storage Distribution</CardTitle>
          <p className="text-sm text-muted-foreground">Local vs S3 usage</p>
        </CardHeader>
        <CardContent className="pt-0">
          <div className="grid grid-cols-1 items-center gap-6 lg:grid-cols-2">
            <div className="h-[260px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={storageData}
                    dataKey="value"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    innerRadius={70}
                    outerRadius={100}
                    paddingAngle={2}
                  >
                    <Cell fill={chartFillLocal} stroke={getComputedColor("background")} />
                    <Cell fill={chartFillS3} stroke={getComputedColor("background")} />
                  </Pie>
                  <RechartsTooltip content={<ChartTooltipContent />} />
                </PieChart>
              </ResponsiveContainer>
            </div>

            <div className="space-y-3">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="outline" className="border-border">Local Storage: {diskUsedGb}GB</Badge>
                <Badge variant="outline" className="border-border">S3 Storage: {s3UsedGb}GB</Badge>
              </div>
              <div className="space-y-2 text-sm">
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Local Storage</span>
                  <span className="font-medium text-foreground">{Math.round((diskUsedGb / (diskUsedGb + s3UsedGb)) * 100)}%</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">S3 Storage</span>
                  <span className="font-medium text-foreground">{Math.round((s3UsedGb / (diskUsedGb + s3UsedGb)) * 100)}%</span>
                </div>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
