import * as React from "react"

import type { LucideIcon } from "lucide-react"

import { cn } from "@/lib/utils"
import { Card, CardContent } from "@/components/ui/card"

type StatCardProps = {
  title: string
  value: string | number
  helperText?: string
  icon: LucideIcon
  /** Extra class for the icon wrapper (e.g. colored background) */
  iconClassName?: string
  /** Optional trend indicator shown next to value */
  trend?: { value: string; direction: "up" | "down" }
  className?: string
}

export default function StatCard({
  title,
  value,
  helperText,
  icon: Icon,
  iconClassName,
  trend,
  className,
}: StatCardProps) {
  return (
    <Card
      className={cn(
        "relative overflow-hidden rounded-xl border border-border shadow-sm transition-shadow hover:shadow-md bg-white",
        className,
      )}
    >
      <CardContent className="p-4 min-h-26">
        <div className="flex items-start justify-between gap-3">
          <p className="text-[10px] sm:text-[11px] font-medium text-muted-foreground">{title}</p>
          <div
            className={cn(
              "h-8 w-8 rounded-lg flex items-center justify-center bg-muted/60 shrink-0 border border-border/60 text-foreground",
              iconClassName,
            )}
          >
            <Icon className="h-4 w-4" />
          </div>
        </div>

        <div className="mt-3 flex items-baseline gap-2">
          <div className={cn("text-xl sm:text-2xl font-semibold text-foreground tracking-tight leading-none", typeof value === "number" ? "tabular-nums" : "")}>{value}</div>
          {trend ? (
            <span
              className={cn(
                "text-xs font-semibold",
                trend.direction === "up" ? "text-primary" : "text-destructive",
              )}
            >
              {trend.value}
            </span>
          ) : null}
        </div>

        {helperText ? <p className="mt-1 text-xs text-muted-foreground">{helperText}</p> : null}
      </CardContent>

      <div className="pointer-events-none absolute -right-6 -bottom-6 opacity-[0.06] text-foreground">
        <Icon className="h-24 w-24" />
      </div>
    </Card>
  )
}
