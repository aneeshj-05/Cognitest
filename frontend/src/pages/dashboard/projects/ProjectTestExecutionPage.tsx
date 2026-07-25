import { useEffect, useState } from "react"
import { useNavigate, useParams } from "react-router-dom"
import { ChevronRight, Zap, FileCode, Activity, Lock, MinusCircle } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { PageHeaderSkeleton, StatCardsGridSkeleton, TableSkeleton } from "@/components/shared/LoadingSkeletons"
import PageHeader from "@/components/shared/PageHeader"
import StatCard from "@/components/shared/StatCard"
import EmptyState from "@/components/shared/EmptyState"
import { getCategoryStats, getProjectSpecs, type CategoryStatsItem, type SpecInfo } from "@/services/backendClient"

interface CategoryConfig {
  icon: React.ReactNode
  label: string
  colorClass: string
  bgClass: string
  borderClass: string
}

const CATEGORY_CONFIGS: Record<string, CategoryConfig> = {
  FUNCTIONAL: {
    icon: <Activity className="h-5 w-5" />,
    label: "Functional",
    colorClass: "text-primary",
    bgClass: "bg-primary/10",
    borderClass: "border-primary/20",
  },
  SECURITY: {
    icon: <Lock className="h-5 w-5" />,
    label: "Security",
    colorClass: "text-destructive",
    bgClass: "bg-destructive/10",
    borderClass: "border-destructive/20",
  },
  NEGATIVE: {
    icon: <MinusCircle className="h-5 w-5" />,
    label: "Negative",
    colorClass: "text-foreground",
    bgClass: "bg-muted/50",
    borderClass: "border-border/50",
  },
  CONTRACT: {
    icon: <FileCode className="h-5 w-5" />,
    label: "Contract",
    colorClass: "text-foreground",
    bgClass: "bg-secondary/60",
    borderClass: "border-border/50",
  },
  FUZZ: {
    icon: <Zap className="h-5 w-5" />,
    label: "Fuzz",
    colorClass: "text-foreground",
    bgClass: "bg-accent/60",
    borderClass: "border-border/50",
  },
}

const getConfig = (category: string): CategoryConfig =>
  CATEGORY_CONFIGS[category.toUpperCase()] ?? {
    icon: <Activity className="h-5 w-5" />,
    label: category,
    colorClass: "text-foreground",
    bgClass: "bg-muted/50",
    borderClass: "border-border/50",
  }

const ProjectTestExecutionPage = () => {
  const { projectId } = useParams()
  const navigate = useNavigate()

  const [categoryStats, setCategoryStats] = useState<CategoryStatsItem[]>([])
  const [latestSpec, setLatestSpec] = useState<SpecInfo | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    async function load() {
      if (!projectId) return
      setLoading(true)
      setError(null)
      try {
        const [specs, stats] = await Promise.all([
          getProjectSpecs(projectId),
          getCategoryStats(projectId),
        ])
        if (!cancelled) {
          const sorted = [...specs].sort(
            (a: any, b: any) => Date.parse(b.createdAt) - Date.parse(a.createdAt)
          )
          setLatestSpec(sorted[0] ?? null)
          setCategoryStats(stats)
        }
      } catch (err: any) {
        if (!cancelled) setError(err?.message || "Failed to load test data.")
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => { cancelled = true }
  }, [projectId])

  const handleViewCategory = (category: string) => {
    if (!projectId || !latestSpec) return
    navigate(
      `/dashboard/projects/${projectId}/ter?version=${encodeURIComponent(latestSpec.version)}&category=${encodeURIComponent(category)}&specId=${encodeURIComponent(latestSpec.id)}`
    )
  }

  if (!projectId) return null

  const totalPassed = categoryStats.reduce((s, c) => s + c.passed, 0)
  const totalFailed = categoryStats.reduce((s, c) => s + c.failed, 0)
  const totalRuns = categoryStats.reduce((s, c) => s + c.totalRuns, 0)
  const executedCount = totalPassed + totalFailed
  const overallRate = executedCount > 0 ? Math.round((totalPassed / executedCount) * 100) : 0

  if (loading) {
    return (
      <div className="flex flex-col min-h-0 p-6 space-y-6">
        <PageHeaderSkeleton showActions={false} />
        <StatCardsGridSkeleton count={4} className="gap-4" />
        <Card className="border-border/50">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Test Categories</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="rounded-lg border border-border/50 overflow-hidden">
              <TableSkeleton
                columns={[
                  { header: "Test Category", widthClassName: "w-40" },
                  { header: "Total Runs", widthClassName: "w-16", align: "right" },
                  { header: "Passed", widthClassName: "w-16", align: "right" },
                  { header: "Failed", widthClassName: "w-16", align: "right" },
                  { header: "Actions", widthClassName: "w-16", align: "center" },
                ]}
                rowCount={6}
              />
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="flex flex-col min-h-0 p-6 space-y-6">
      <PageHeader title="All Category Results" description="Select a test category to view detailed results" />

      {!loading && categoryStats.length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard title="Total Runs" value={totalRuns} icon={Activity} />
          <StatCard title="Passed" value={totalPassed} icon={Activity} />
          <StatCard title="Failed" value={totalFailed} icon={Activity} />
          <StatCard title="Pass Rate" value={`${overallRate}%`} icon={Activity} />
        </div>
      )}

      {/* Categories */}
      <Card className="rounded-[14px] border border-border bg-card shadow-sm">
        <CardHeader className="p-8 pb-5">
          <CardTitle className="text-sm font-medium">Test Categories</CardTitle>
        </CardHeader>
        <CardContent className="px-8 pb-8">
          {error ? (
            <div className="py-12 text-center text-sm text-destructive">{error}</div>
          ) : categoryStats.length === 0 ? (
            <EmptyState
              title="No test results yet"
              description="Run tests from the project page to see category results here."
              icon={Activity}
            />
          ) : (
            <div className="overflow-x-auto">
              <Table className="w-full animate-in fade-in duration-300">
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-[45%]">Test Category</TableHead>
                    <TableHead className="w-[15%] text-right">Total Runs</TableHead>
                    <TableHead className="w-[15%] text-right">Passed</TableHead>
                    <TableHead className="w-[15%] text-right">Failed</TableHead>
                    <TableHead className="w-[10%] text-center">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {categoryStats.map((row) => {
                    const config = getConfig(row.category)
                    const rowExecuted = row.passed + row.failed
                    const passRate = rowExecuted > 0 ? Math.round((row.passed / rowExecuted) * 100) : 0

                    return (
                      <TableRow key={row.category} className="hover:bg-muted/20 transition-colors">
                        <TableCell>
                          <div className="flex items-center gap-3">
                            <div className={`p-2 rounded-lg ${config.bgClass} ${config.colorClass}`}>
                              {config.icon}
                            </div>
                            <div>
                              <p className="text-sm font-medium text-foreground">{config.label}</p>
                              <p className="text-[11px] text-muted-foreground">{passRate}% pass rate</p>
                            </div>
                          </div>
                        </TableCell>
                        <TableCell className="text-right text-sm text-foreground">{row.totalRuns}</TableCell>
                        <TableCell className="text-right text-sm text-primary font-medium">{row.passed}</TableCell>
                        <TableCell className="text-right text-sm text-destructive font-medium">{row.failed}</TableCell>
                        <TableCell className="text-center">
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            className="gap-1.5 text-primary hover:text-primary"
                            onClick={() => handleViewCategory(row.category)}
                            disabled={!latestSpec}
                            title={!latestSpec ? "No spec available" : `View ${config.label} results`}
                          >
                            View <ChevronRight className="h-4 w-4" />
                          </Button>
                        </TableCell>
                      </TableRow>
                    )
                  })}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

export default ProjectTestExecutionPage
