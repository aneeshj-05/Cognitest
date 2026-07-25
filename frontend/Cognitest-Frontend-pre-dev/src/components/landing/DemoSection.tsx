import * as React from "react"
import { Link } from "react-router-dom"
import { motion, useReducedMotion, useInView } from "framer-motion"
import { cn } from "@/lib/utils"

import { Button } from "@/components/ui/button"
import { fadeUpContainer, fadeUpItem } from "./motion"

// ─── Reveal wrapper — each step triggers independently on scroll ─────────────

function ScrollReveal({
  children,
  className,
  onReveal,
}: {
  children: React.ReactNode
  className?: string
  onReveal?: () => void
}) {
  const ref = React.useRef<HTMLDivElement>(null)
  const isInView = useInView(ref, { once: true, margin: "-12% 0px -12% 0px" })

  React.useEffect(() => {
    if (isInView && onReveal) onReveal()
  }, [isInView, onReveal])

  return (
    <div ref={ref} className={className}>
      <motion.div
        initial={{ opacity: 0, y: 6 }}
        animate={isInView ? { opacity: 1, y: 0 } : { opacity: 0, y: 6 }}
        transition={{ duration: 0.35, ease: [0.25, 0.46, 0.45, 0.94] }}
      >
        {children}
      </motion.div>
    </div>
  )
}

// ─── Vertical connector line — grows when next step is revealed ──────────────

function GrowingLine({ height, revealed }: { height: string; revealed: boolean }) {
  return (
    <div className="flex justify-center">
      <div className={cn("w-px bg-zinc-200 overflow-hidden", height)}>
        <motion.div
          initial={{ height: "0%" }}
          animate={revealed ? { height: "100%" } : { height: "0%" }}
          transition={{ duration: 0.3, ease: "easeOut" }}
          className="w-full bg-[#27BE8C]"
        />
      </div>
    </div>
  )
}

// ─── Step 1: Input ───────────────────────────────────────────────────────────

function InputCard() {
  return (
    <div className="rounded-xl border border-zinc-200 bg-white shadow-sm transition-all duration-300 ease-out p-6 max-w-[440px] w-full min-h-[120px] dark:bg-white/[0.04] dark:backdrop-blur-md dark:border-white/[0.08] dark:shadow-[0_4px_20px_rgba(0,0,0,0.4)] hover:shadow-md dark:hover:bg-white/[0.06] dark:hover:border-white/[0.12] dark:hover:shadow-[0_6px_30px_rgba(0,0,0,0.5)]">
      <div className="flex items-baseline justify-between mb-2.5">
        <span className="text-[12px] font-semibold text-zinc-800 dark:text-zinc-200">Upload API spec</span>
        <span className="text-xs text-zinc-500 dark:text-zinc-400 dark:text-zinc-500 font-medium">Step 1</span>
      </div>
      <div className="rounded-lg border-2 border-dashed border-zinc-150 bg-zinc-50/50 dark:bg-white/[0.02] px-4 py-3.5 flex items-center justify-between">
        <div>
          <div className="text-[11px] font-semibold text-zinc-900 dark:text-zinc-100 tracking-tight">payments_api.json</div>
          <div className="text-[9px] text-zinc-400 dark:text-zinc-500 mt-px">OpenAPI 3.1 · 24 KB</div>
        </div>
        <span className="text-[9px] text-zinc-400 dark:text-zinc-500 font-medium">34 endpoints</span>
      </div>
    </div>
  )
}

// ─── Step 2: AI ──────────────────────────────────────────────────────────────

function AICard() {
  const ref = React.useRef<HTMLDivElement>(null)
  const isInView = useInView(ref, { once: true, margin: "-10%" })
  const bars = [
    { label: "Mapping endpoints", pct: 100 },
    { label: "Parsing schemas", pct: 83 },
    { label: "Edge cases", pct: 57 },
  ]
  return (
    <div ref={ref} className="rounded-xl border border-zinc-200 bg-white shadow-sm transition-all duration-300 ease-out p-6 max-w-[460px] w-full min-h-[120px] dark:bg-white/[0.04] dark:backdrop-blur-md dark:border-white/[0.08] dark:shadow-[0_4px_20px_rgba(0,0,0,0.4)] hover:shadow-md dark:hover:bg-white/[0.06] dark:hover:border-white/[0.12] dark:hover:shadow-[0_6px_30px_rgba(0,0,0,0.5)]">
      <div className="flex items-baseline justify-between mb-3">
        <span className="text-[12px] font-semibold text-zinc-800 dark:text-zinc-200">Generate coverage</span>
        <span className="text-xs text-zinc-500 dark:text-zinc-400 dark:text-zinc-500 font-medium">Step 2</span>
      </div>
      <div className="space-y-[14px]">
        {bars.map((bar, i) => (
          <div key={i} className={cn("space-y-[5px]", i === 1 && "space-y-[6px]")}>
            <div className="flex justify-between items-baseline">
              <span className={cn("text-[10px] font-medium", i === 0 ? "text-zinc-600" : "text-zinc-500 dark:text-zinc-400 dark:text-zinc-500")}>{bar.label}</span>
              <span className="text-[9px] font-medium text-zinc-400 dark:text-zinc-500 tabular-nums">{bar.pct}%</span>
            </div>
            <div className={cn("w-full rounded-full bg-zinc-100 overflow-hidden", i === 2 ? "h-[5px]" : "h-1.5")}>
              <motion.div
                initial={{ width: 0 }}
                animate={isInView ? { width: `${bar.pct}%` } : { width: 0 }}
                transition={{ delay: 0.15 + i * 0.12, duration: 0.9, ease: [0.25, 0.46, 0.45, 0.94] }}
                className={cn("h-full rounded-full", i === 2 ? "bg-[#27BE8C]/85" : "bg-[#27BE8C]")}
              />
            </div>
          </div>
        ))}
      </div>
      <div className="text-[9px] text-zinc-400 dark:text-zinc-500 font-medium mt-3">128 scenarios generated</div>
    </div>
  )
}

// ─── Step 3: Security ────────────────────────────────────────────────────────

function SecurityCard() {
  const checks = [
    { name: "SQL injection vectors", status: "clear", time: "18ms" },
    { name: "Auth token validation", status: "clear", time: "32ms" },
    { name: "Rate limit bypass", status: "warn", time: "44ms" },
  ]
  return (
    <div className="rounded-xl border border-zinc-200 bg-white shadow-sm transition-all duration-300 ease-out p-6 max-w-[450px] w-full min-h-[120px] dark:bg-white/[0.04] dark:backdrop-blur-md dark:border-white/[0.08] dark:shadow-[0_4px_20px_rgba(0,0,0,0.4)] hover:shadow-md dark:hover:bg-white/[0.06] dark:hover:border-white/[0.12] dark:hover:shadow-[0_6px_30px_rgba(0,0,0,0.5)]">
      <div className="flex items-baseline justify-between mb-3">
        <span className="text-[12px] font-semibold text-zinc-800 dark:text-zinc-200">Security checks</span>
        <span className="text-xs text-zinc-500 dark:text-zinc-400 dark:text-zinc-500 font-medium">Step 3</span>
      </div>
      <div className="flex flex-col gap-[6px]">
        {checks.map((c, i) => (
          <div
            key={i}
            className={cn(
              "flex items-center justify-between rounded-lg border bg-white dark:bg-white/[0.04] dark:border-white/[0.08]",
              c.status === "warn" ? "border-amber-100 bg-amber-50/20" : "border-zinc-100",
              i === 0 && "px-3 py-[7px]",
              i === 1 && "px-[13px] py-[8px]",
              i === 2 && "px-3 py-[7px]",
            )}
          >
            <span className="text-[10px] font-medium text-zinc-700">{c.name}</span>
            <div className="flex items-center gap-2">
              <span className="text-[9px] text-zinc-400 dark:text-zinc-500 tabular-nums font-medium">{c.time}</span>
              <span className={cn("text-[9px] font-semibold", c.status === "clear" ? "text-[#27BE8C]" : "text-amber-500")}>
                {c.status === "clear" ? "CLEAR" : "WARN"}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

// ─── Step 4: Run ─────────────────────────────────────────────────────────────

function RunCard() {
  const rows = [
    { method: "GET", path: "/users", status: "PASS", time: "84ms" },
    { method: "POST", path: "/auth/login", status: "PASS", time: "112ms" },
    { method: "PUT", path: "/settings/profile", status: "403", time: "240ms" },
    { method: "GET", path: "/v1/charges", status: "PASS", time: null as string | null },
  ]
  return (
    <div className="rounded-xl border border-zinc-200 bg-white shadow-sm transition-all duration-300 ease-out p-6 max-w-[470px] w-full min-h-[120px] dark:bg-white/[0.04] dark:backdrop-blur-md dark:border-white/[0.08] dark:shadow-[0_4px_20px_rgba(0,0,0,0.4)] hover:shadow-md dark:hover:bg-white/[0.06] dark:hover:border-white/[0.12] dark:hover:shadow-[0_6px_30px_rgba(0,0,0,0.5)]">
      <div className="flex items-baseline justify-between mb-3">
        <span className="text-[12px] font-semibold text-zinc-800 dark:text-zinc-200">Run tests</span>
        <span className="text-xs text-zinc-500 dark:text-zinc-400 dark:text-zinc-500 font-medium">Step 4</span>
      </div>
      <div className="flex flex-col gap-[6px]">
        {rows.map((row, i) => (
          <div
            key={i}
            className={cn(
              "flex items-center justify-between rounded-lg border bg-white dark:bg-white/[0.04] dark:border-white/[0.08]",
              row.status === "403" ? "border-red-100 bg-red-50/25" : "border-zinc-100",
              i === 0 && "px-3 py-[8px]",
              i === 1 && "px-[13px] py-[7px]",
              i === 2 && "px-3 py-[9px]",
              i === 3 && "px-[14px] py-[7px]",
            )}
          >
            <div className={cn("flex items-center", i === 2 ? "gap-[10px]" : "gap-2.5")}>
              <span className={cn(
                "text-[8px] font-semibold tracking-wide",
                row.method === "GET" && "bg-zinc-100 text-zinc-600 px-1.5 py-0.5 rounded",
                row.method === "POST" && "bg-zinc-800 text-white px-[6px] py-0.5 rounded-[3px]",
                row.method === "PUT" && "bg-zinc-200 text-zinc-700 px-1.5 py-[3px] rounded",
              )}>{row.method}</span>
              <span className={cn("text-[10px] font-medium", i === 3 ? "text-zinc-700" : "text-zinc-800 dark:text-zinc-200")}>{row.path}</span>
            </div>
            <div className="flex items-center gap-2">
              {row.time && <span className="text-[9px] text-zinc-400 dark:text-zinc-500 tabular-nums font-medium">{row.time}</span>}
              <span className={cn("text-[9px] font-semibold tabular-nums", row.status === "PASS" ? "text-[#27BE8C]" : "text-red-500")}>
                {row.status === "PASS" ? "PASS" : `${row.status} error`}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

// ─── Step 5: Report ──────────────────────────────────────────────────────────

function InsightsCard() {
  return (
    <div className="rounded-xl border border-zinc-200 bg-white shadow-sm transition-all duration-300 ease-out p-6 max-w-[440px] w-full min-h-[120px] dark:bg-white/[0.04] dark:backdrop-blur-md dark:border-white/[0.08] dark:shadow-[0_4px_20px_rgba(0,0,0,0.4)] hover:shadow-md dark:hover:bg-white/[0.06] dark:hover:border-white/[0.12] dark:hover:shadow-[0_6px_30px_rgba(0,0,0,0.5)]">
      <div className="flex items-baseline justify-between mb-3.5">
        <span className="text-[12px] font-semibold text-zinc-800 dark:text-zinc-200">Insights & Summary</span>
        <span className="text-xs text-zinc-500 dark:text-zinc-400 font-medium">Step 5</span>
      </div>
      <div className="grid grid-cols-3 gap-2 mb-2.5">
        {[
          { label: "Pass rate", value: "99%", accent: true, pad: "p-2.5", r: "rounded-lg" },
          { label: "Avg latency", value: "124ms", accent: false, pad: "p-[9px]", r: "rounded-[8px]" },
          { label: "Coverage", value: "94%", accent: false, pad: "p-2.5", r: "rounded-lg" },
        ].map((s, i) => (
          <div key={i} className={cn("border border-zinc-100 dark:border-white/[0.08] bg-white dark:bg-white/[0.04]", s.pad, s.r, i === 0 && "shadow-[0_1px_2px_rgba(0,0,0,0.02)]")}>
            <div className={cn("text-[8px] text-zinc-400 dark:text-zinc-500 font-medium", i === 1 ? "mb-1.5" : "mb-1")}>{s.label}</div>
            <div className={cn("font-semibold tabular-nums leading-tight", s.accent ? "text-[#27BE8C] text-[15px]" : "text-zinc-900 dark:text-zinc-100 text-[14px]")}>{s.value}</div>
          </div>
        ))}
      </div>
      <div className="rounded-lg border border-red-100 bg-red-50/30 px-3 py-2 flex items-start justify-between">
        <div>
          <div className="text-[9px] font-semibold text-red-600">PUT /settings/profile → 403</div>
          <div className="text-[8px] text-red-400 mt-px">Missing authorization scope</div>
        </div>
        <div className="text-[8px] font-medium text-red-400 mt-0.5 whitespace-nowrap ml-3">240ms</div>
      </div>
      <div className="text-[8px] text-zinc-400 dark:text-zinc-500 font-medium mt-2 px-0.5">127 passed · 1 failed · 3.2s</div>
    </div>
  )
}

// ─── Step registry ───────────────────────────────────────────────────────────

const stepCards = [InputCard, AICard, SecurityCard, RunCard, InsightsCard]
const lineHeights = ["h-[40px]", "h-[44px]", "h-[38px]", "h-[42px]"]

// ─── Main Component ──────────────────────────────────────────────────────────

export default function DemoSection() {
  const reduceMotion = useReducedMotion()
  // Track which steps have been revealed (for line animation)
  const [revealed, setRevealed] = React.useState<boolean[]>([false, false, false, false, false])

  const markRevealed = React.useCallback((index: number) => {
    setRevealed((prev) => {
      if (prev[index]) return prev
      const next = [...prev]
      next[index] = true
      return next
    })
  }, [])

  return (
    <motion.section
      initial={reduceMotion ? false : "hidden"}
      animate={reduceMotion ? undefined : "visible"}
      variants={fadeUpContainer}
      className="border-t border-zinc-100 dark:border-white/[0.05] bg-white dark:bg-[#020617] py-20 lg:py-28"
    >
      <div className="mx-auto max-w-6xl px-6">
        <div className="flex flex-col lg:flex-row gap-12 lg:gap-24 items-start">
          {/* LEFT: Sticky text */}
          <div className="w-full lg:w-[38%] lg:sticky lg:top-28 space-y-5 flex-shrink-0">
            <motion.div variants={fadeUpItem}>
              <div className="text-[11px] font-semibold text-[#27BE8C] uppercase tracking-[0.15em] mb-3">
                Demo
              </div>
            </motion.div>
            <motion.h2
              variants={fadeUpItem}
              className="text-[28px] md:text-[34px] font-semibold text-zinc-900 dark:text-zinc-100 leading-tight"
            >
              See what your pipeline runs before you merge
            </motion.h2>
            <motion.p
              variants={fadeUpItem}
              className="text-[15px] text-zinc-500 dark:text-zinc-400 dark:text-zinc-500 leading-relaxed max-w-[340px]"
            >
              Cognitest turns your API docs into an executable pipeline — functional,
              security, and performance checks in one flow.
            </motion.p>

            <motion.div variants={fadeUpItem} className="flex flex-col gap-3 sm:flex-row pt-2">
              <Button
                asChild
                className="w-full sm:w-auto h-11 rounded-full bg-[#27BE8C] px-7 text-[14px] font-semibold text-white shadow-[0_8px_20px_-4px_rgba(39,190,140,0.25)] transition-all hover:bg-[#21a378] hover:translate-y-[-1px] active:scale-[0.98]"
              >
                <Link to="/login">Start Free</Link>
              </Button>
              <Button
                asChild
                variant="outline"
                className="w-full sm:w-auto h-11 rounded-full border-zinc-200 dark:border-white/[0.1] bg-white dark:bg-white/[0.05] px-7 text-[14px] font-semibold text-zinc-900 dark:text-zinc-100 hover:bg-zinc-50 dark:hover:bg-white/[0.1] hover:border-zinc-300 transition-all"
              >
                <Link to="/docs">View Docs</Link>
              </Button>
            </motion.div>
          </div>

          {/* RIGHT: Scroll-driven stacked pipeline */}
          <div className="w-full lg:w-[62%] flex flex-col items-center">
            {stepCards.map((Card, i) => (
              <React.Fragment key={i}>
                <ScrollReveal
                  onReveal={() => markRevealed(i)}
                >
                  <Card />
                </ScrollReveal>
                {i < stepCards.length - 1 && (
                  <GrowingLine
                    height={lineHeights[i]}
                    revealed={revealed[i + 1]}
                  />
                )}
              </React.Fragment>
            ))}
          </div>
        </div>
      </div>
    </motion.section>
  )
}
