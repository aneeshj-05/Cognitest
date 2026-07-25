import * as React from "react"

import { cn } from "@/lib/utils"

import { Skeleton } from "@/components/ui/skeleton"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

export function PageHeaderSkeleton({
  className,
  showActions = true,
}: {
  className?: string
  showActions?: boolean
}) {
  return (
    <div
      className={cn(
        "flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between",
        className
      )}
    >
      <div className="space-y-2">
        <Skeleton className="h-8 w-56 rounded-md" />
        <Skeleton className="h-4 w-80 max-w-[70vw] rounded-md" />
      </div>
      {showActions ? <Skeleton className="h-10 w-36 rounded-md" /> : null}
    </div>
  )
}

export function StatCardSkeleton({ className }: { className?: string }) {
  return (
    <Card className={cn("relative overflow-hidden rounded-xl border border-border shadow-sm bg-white", className)}>
      <CardContent className="p-4 min-h-26">
        <div className="flex items-start justify-between gap-3">
          <Skeleton className="h-3 w-20 rounded-md" />
          <Skeleton className="h-8 w-8 rounded-lg shrink-0" />
        </div>
        <div className="mt-3 flex items-baseline gap-2">
          <Skeleton className="h-7 w-24 rounded-md" />
        </div>
      </CardContent>
    </Card>
  )
}

export function StatCardsGridSkeleton({
  count = 4,
  className,
}: {
  count?: number
  className?: string
}) {
  return (
    <div className={cn("grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4", className)}>
      {Array.from({ length: count }).map((_, idx) => (
        <StatCardSkeleton key={idx} />
      ))}
    </div>
  )
}

type TableSkeletonColumn = {
  header: React.ReactNode
  widthClassName?: string
  align?: "left" | "right" | "center"
}

export function TableSkeleton({
  columns,
  rowCount = 8,
  tableClassName,
  headerClassName,
  rowClassName,
  cellClassName,
}: {
  columns: TableSkeletonColumn[]
  rowCount?: number
  tableClassName?: string
  headerClassName?: string
  rowClassName?: string
  cellClassName?: string
}) {
  return (
    <Table className={tableClassName}>
      <TableHeader className={cn("bg-muted/40", headerClassName)}>
        <TableRow>
          {columns.map((c, idx) => (
            <TableHead key={idx} className="h-11">
              {typeof c.header === "string" ? (
                <Skeleton className="h-3 w-16 rounded-md" />
              ) : (
                c.header
              )}
            </TableHead>
          ))}
        </TableRow>
      </TableHeader>
      <TableBody>
        {Array.from({ length: rowCount }).map((_, rIdx) => (
          <TableRow key={rIdx} className={cn("h-14", rowClassName)}>
            {columns.map((c, cIdx) => (
              <TableCell key={cIdx} className={cellClassName}>
                {(() => {
                  const align = c.align ?? "left"
                  const skeleton = (
                    <Skeleton
                      className={cn(
                        "h-4 rounded-md",
                        c.widthClassName ?? "w-24",
                        align === "center" && "mx-auto",
                        align === "right" && "ml-auto"
                      )}
                    />
                  )
                  return skeleton
                })()}
              </TableCell>
            ))}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}

export function ReportsListSkeleton({ className }: { className?: string }) {
  return (
    <div className={cn("space-y-3", className)}>
      {Array.from({ length: 3 }).map((_, idx) => (
        <Card key={idx} className="border-border/50 overflow-hidden">
          <div className="w-full flex items-center gap-4 p-4">
            <Skeleton className="h-10 w-10 rounded-lg shrink-0" />
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <Skeleton className="h-5 w-40 rounded-md" />
                <Skeleton className="h-5 w-16 rounded-full" />
              </div>
              <div className="mt-2 flex items-center gap-3">
                <Skeleton className="h-3 w-32 rounded-md" />
                <div className="flex items-center gap-1.5">
                  <Skeleton className="h-4 w-16 rounded-md" />
                  <Skeleton className="h-4 w-16 rounded-md" />
                  <Skeleton className="h-4 w-16 rounded-md" />
                </div>
              </div>
            </div>
            <div className="shrink-0 flex items-center gap-3 ml-2">
              <div className="w-20">
                <Skeleton className="h-3 w-20 rounded-md" />
                <Skeleton className="mt-2 h-2 w-20 rounded-full" />
              </div>
              <Skeleton className="h-5 w-5 rounded-md" />
            </div>
          </div>
        </Card>
      ))}
    </div>
  )
}

export function ChartSkeleton({
  className,
  height = 260,
  title,
}: {
  className?: string
  height?: number
  title?: string
}) {
  return (
    <Card className={cn("overflow-hidden", className)}>
      <CardHeader className="pb-2">
        {title ? (
          <Skeleton className="h-5 w-36 rounded-md" />
        ) : (
          <Skeleton className="h-5 w-36 rounded-md" />
        )}
        <Skeleton className="h-3 w-48 mt-1 rounded-md" />
      </CardHeader>
      <CardContent>
        <Skeleton className="w-full rounded-lg" style={{ height }} />
      </CardContent>
    </Card>
  )
}

export function ProjectDetailSkeleton() {
  return (
    <div className="flex flex-col min-h-0 p-6 space-y-6 bg-background">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="mt-2 flex flex-wrap items-end gap-x-3 gap-y-1">
            <Skeleton className="h-9 w-72 max-w-[70vw] rounded-md" />
            <Skeleton className="h-4 w-40 rounded-md" />
            <Skeleton className="h-5 w-16 rounded-full" />
          </div>
        </div>
      </div>

      {/* Stats Cards Row - 5 cards */}
      <div className="grid grid-cols-1 min-[540px]:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4">
        {Array.from({ length: 5 }).map((_, idx) => (
          <Card key={idx} className="relative overflow-hidden rounded-xl border border-border shadow-sm bg-muted/30">
            <CardContent className="p-4 min-h-26">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <Skeleton className="h-3 w-20 rounded-md" />
                </div>
                <Skeleton className="h-8 w-8 rounded-lg shrink-0" />
              </div>
              <div className="mt-3 flex items-baseline gap-2">
                <Skeleton className="h-7 w-16 rounded-md" />
                <Skeleton className="h-4 w-12 rounded-md" />
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Category Breakdown Title */}
      <div className="mt-2">
        <Skeleton className="h-6 w-64 rounded-md mb-4" />
        
        {/* Category Cards - 5 cards */}
        <div className="grid grid-cols-1 min-[540px]:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4">
          {Array.from({ length: 5 }).map((_, idx) => (
            <Card key={idx} className="relative overflow-hidden rounded-xl border border-border shadow-sm">
              <CardContent className="p-4 min-h-28">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0 flex items-center gap-1.5">
                    <Skeleton className="h-3 w-20 rounded-md" />
                  </div>
                  <Skeleton className="h-8 w-8 rounded-lg shrink-0" />
                </div>
                <div className="mt-3 flex items-baseline gap-2">
                  <Skeleton className="h-6 w-8 rounded-md" />
                  <Skeleton className="h-4 w-10 rounded-md" />
                </div>
                <div className="mt-1.5 flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <Skeleton className="h-3 w-24 rounded-md" />
                  </div>
                  <Skeleton className="h-3 w-8 rounded-md" />
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>

      {/* Test Cases Table */}
      <Card className="border-border/50">
        <CardHeader className="pb-3 border-b border-border/50">
          <div className="flex items-center justify-between">
            <Skeleton className="h-5 w-32 rounded-md" />
            <div className="flex items-center gap-2">
              <Skeleton className="h-9 w-32 rounded-md" />
              <Skeleton className="h-9 w-24 rounded-md" />
            </div>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          <div className="rounded-lg overflow-hidden">
            <TableSkeleton
              columns={[
                { header: "Test Name", widthClassName: "w-40" },
                { header: "Endpoint Path", widthClassName: "w-48" },
                { header: "Method", widthClassName: "w-16" },
                { header: "Actions", widthClassName: "w-16", align: "right" },
              ]}
              rowCount={8}
            />
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

export function MembersPageSkeleton() {
  return (
    <div className="space-y-6 p-6">
      <PageHeaderSkeleton />
      <Card>
        <CardHeader className="border-b border-border/50 pb-4">
          <div className="flex items-center justify-between">
            <Skeleton className="h-5 w-32 rounded-md" />
            <Skeleton className="h-9 w-32 rounded-md" />
          </div>
        </CardHeader>
        <CardContent className="p-0">
          <TableSkeleton
            columns={[
              { header: "Member", widthClassName: "w-48" },
              { header: "Email", widthClassName: "w-48" },
              { header: "Role", widthClassName: "w-24" },
              { header: "Status", widthClassName: "w-20" },
              { header: "Actions", widthClassName: "w-16", align: "right" },
            ]}
            rowCount={5}
          />
        </CardContent>
      </Card>
    </div>
  )
}

export function ActiveProjectsCardSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <Card className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-xl border border-border/60 bg-card shadow-sm">
      <CardHeader className="flex flex-col gap-3 border-b border-border/50 p-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="space-y-2">
          <Skeleton className="h-5 w-32 rounded-md" />
          <Skeleton className="h-4 w-56 rounded-md" />
        </div>
        <div className="flex w-full flex-col gap-3 sm:w-auto sm:flex-row sm:items-center">
          <Skeleton className="h-9 w-full sm:w-64 rounded-md" />
          <Skeleton className="h-9 w-full sm:w-40 rounded-md" />
        </div>
      </CardHeader>

      <div className="min-h-0 flex-1 overflow-hidden bg-background">
        <Table className="table-fixed w-full">
          <TableHeader className="sticky top-0 z-10 bg-muted/40">
            <TableRow>
              <TableHead className="h-12 w-[80px] px-4 py-2"><Skeleton className="h-3 w-10 rounded-md" /></TableHead>
              <TableHead className="h-12 w-[40%] px-4 py-2"><Skeleton className="h-3 w-20 rounded-md" /></TableHead>
              <TableHead className="h-12 w-[120px] px-4 py-2"><Skeleton className="h-3 w-10 rounded-md" /></TableHead>
              <TableHead className="h-12 w-[140px] px-4 py-2"><Skeleton className="h-3 w-14 rounded-md" /></TableHead>
              <TableHead className="h-12 w-[140px] px-4 py-2"><Skeleton className="h-3 w-16 rounded-md" /></TableHead>
              <TableHead className="h-12 w-[100px] px-4 py-2 text-right"><Skeleton className="ml-auto h-3 w-10 rounded-md" /></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody className="divide-y divide-border/50">
            {Array.from({ length: rows }).map((_, idx) => (
              <TableRow key={idx} className="h-16 hover:bg-muted/40">
                <TableCell className="px-4 py-2 text-center"><Skeleton className="mx-auto h-4 w-10 rounded-md" /></TableCell>
                <TableCell className="px-4 py-2">
                  <div className="space-y-2">
                    <Skeleton className="h-4 w-48 rounded-md" />
                    <Skeleton className="h-3 w-64 bg-muted/70 rounded-md" />
                  </div>
                </TableCell>
                <TableCell className="px-4 py-2 text-center"><Skeleton className="mx-auto h-5 w-16 rounded-full" /></TableCell>
                <TableCell className="px-4 py-2 text-center"><Skeleton className="mx-auto h-4 w-20 rounded-md" /></TableCell>
                <TableCell className="px-4 py-2 text-center"><Skeleton className="mx-auto h-4 w-16 rounded-md" /></TableCell>
                <TableCell className="px-4 py-2"><Skeleton className="ml-auto h-8 w-8 rounded-md" /></TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      <div className="flex items-center justify-between border-t border-border/50 bg-card px-4 py-3 text-xs">
        <Skeleton className="h-4 w-44 rounded-md" />
        <Skeleton className="h-8 w-36 rounded-md" />
      </div>
    </Card>
  )
}

// ─── Super Admin Dashboard Skeletons ──────────────────────────────────

export function SuperAdminDashboardSkeleton() {
  return (
    <div className="space-y-6">
      <StatCardsGridSkeleton count={6} className="lg:grid-cols-3 xl:grid-cols-6" />
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <ChartSkeleton title="User Distribution" />
        <ChartSkeleton title="Active Users" />
      </div>
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <ChartSkeleton title="Test Execution Trends" height={300} />
      </div>
    </div>
  )
}

export function SuperAdminTenantsSkeleton() {
  return (
    <div className="space-y-6">
      <StatCardsGridSkeleton count={4} />
      <Card className="rounded-xl border border-border/60 bg-white shadow-sm overflow-hidden">
        <div className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between border-b border-border/50">
          <Skeleton className="h-10 w-full sm:max-w-sm rounded-md" />
          <div className="flex items-center gap-3">
            <Skeleton className="h-9 w-[130px] rounded-md" />
            <Skeleton className="h-9 w-[130px] rounded-md" />
            <Skeleton className="h-9 w-24 rounded-md" />
          </div>
        </div>
        <TableSkeleton
          columns={[
            { header: "Tenant Name", widthClassName: "w-40" },
            { header: "Plan", widthClassName: "w-20" },
            { header: "Users", widthClassName: "w-24" },
            { header: "API Usage", widthClassName: "w-24" },
            { header: "Status", widthClassName: "w-20" },
            { header: "Billing", widthClassName: "w-20" },
            { header: "Created", widthClassName: "w-24" },
            { header: "Actions", widthClassName: "w-8", align: "right" },
          ]}
          rowCount={6}
        />
      </Card>
    </div>
  )
}

export function SuperAdminBillingSkeleton() {
  return (
    <div className="space-y-6">
      <StatCardsGridSkeleton count={4} />
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <ChartSkeleton title="Revenue & Churn Trends" />
        <ChartSkeleton title="Revenue by Plan" />
      </div>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {Array.from({ length: 3 }).map((_, idx) => (
          <Card key={idx} className="rounded-xl border border-border/60 bg-white p-5 shadow-sm">
            <Skeleton className="h-4 w-20 rounded-md" />
            <Skeleton className="mt-2 h-9 w-12 rounded-md" />
            <div className="mt-4 space-y-2">
              <div className="flex justify-between"><Skeleton className="h-4 w-24 rounded-md" /><Skeleton className="h-4 w-12 rounded-md" /></div>
              <div className="flex justify-between"><Skeleton className="h-4 w-24 rounded-md" /><Skeleton className="h-4 w-12 rounded-md" /></div>
            </div>
          </Card>
        ))}
      </div>
      <Card className="rounded-xl border border-border/60 bg-white shadow-sm overflow-hidden">
        <div className="p-4 border-b border-border/50 flex justify-between items-center">
          <Skeleton className="h-6 w-32 rounded-md" />
          <Skeleton className="h-9 w-24 rounded-md" />
        </div>
        <TableSkeleton
          columns={[
            { header: "Invoice ID", widthClassName: "w-24" },
            { header: "Tenant", widthClassName: "w-32" },
            { header: "Plan", widthClassName: "w-20" },
            { header: "Amount", widthClassName: "w-20" },
            { header: "Renewal Date", widthClassName: "w-24" },
            { header: "Status", widthClassName: "w-20" },
            { header: "Actions", widthClassName: "w-8", align: "right" },
          ]}
          rowCount={5}
        />
      </Card>
    </div>
  )
}

export function SuperAdminTestSystemSkeleton() {
  return (
    <div className="space-y-6">
      <StatCardsGridSkeleton count={5} className="xl:grid-cols-5" />
      <ChartSkeleton title="Test Coverage by Category" />
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-3 xl:grid-cols-5">
        {Array.from({ length: 5 }).map((_, idx) => (
          <Card key={idx} className="rounded-xl border border-border/60 bg-white p-5 shadow-sm">
            <Skeleton className="h-4 w-24 rounded-md" />
            <Skeleton className="mt-2 h-8 w-16 rounded-md" />
            <Skeleton className="mt-3 h-1.5 w-full rounded-full" />
            <Skeleton className="mt-2 h-3 w-20 rounded-md" />
          </Card>
        ))}
      </div>
      <Card className="rounded-xl border border-border/60 bg-white shadow-sm overflow-hidden">
        <div className="p-4 border-b border-border/50">
          <Skeleton className="h-6 w-48 rounded-md" />
        </div>
        <TableSkeleton
          columns={[
            { header: "Tenant", widthClassName: "w-32" },
            { header: "Test Type", widthClassName: "w-24" },
            { header: "Category", widthClassName: "w-24" },
            { header: "Priority", widthClassName: "w-16" },
            { header: "Status", widthClassName: "w-20" },
            { header: "Coverage", widthClassName: "w-16" },
            { header: "Duration", widthClassName: "w-20" },
            { header: "Timestamp", widthClassName: "w-32" },
          ]}
          rowCount={5}
        />
      </Card>
    </div>
  )
}

export function SuperAdminInfrastructureSkeleton() {
  return (
    <div className="space-y-6">
      <StatCardsGridSkeleton count={5} className="lg:grid-cols-5" />
      <div className="space-y-4">
        <div className="space-y-2">
          <Skeleton className="h-6 w-24 rounded-md" />
          <Skeleton className="h-4 w-48 rounded-md" />
        </div>
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <ChartSkeleton title="CPU Usage Over Time" />
          <ChartSkeleton title="RAM Usage Over Time" />
        </div>
      </div>
    </div>
  )
}
