import * as React from "react"
import { motion, AnimatePresence, useReducedMotion } from "framer-motion"
import { cn } from "@/lib/utils"

// ─── Step Data ───────────────────────────────────────────────────────────────

const STEP_COUNT = 4

// Slightly randomized interval to avoid robotic cadence
function getStepDuration() {
  return 4200 + Math.random() * 600 // 4200–4800ms
}

const steps = [
  {
    number: "01",
    title: "Upload your API spec",
    description: "Drop an OpenAPI, Swagger, or Postman collection. Endpoints are parsed instantly.",
  },
  {
    number: "02",
    title: "Coverage is generated automatically",
    description: "Positive, negative, and edge-case scenarios mapped from your schema.",
  },
  {
    number: "03",
    title: "Tests run in CI/CD",
    description: "Execute against staging or production. Every endpoint, every commit.",
  },
  {
    number: "04",
    title: "Get insights instantly",
    description: "Pass rates, latency breakdowns, and failure alerts in one view.",
  },
]

// ─── Subtle transition presets ───────────────────────────────────────────────

const panelTransition = {
  initial: { opacity: 0, y: 4 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -2 },
  transition: { duration: 0.38, ease: [0.25, 0.46, 0.45, 0.94] },
}

// ─── Step 01: Upload ─────────────────────────────────────────────────────────

function UploadView() {
  return (
    <motion.div {...panelTransition} className="flex flex-col gap-4 h-full">
      {/* File drop zone */}
      <div className="flex-1 rounded-2xl border-2 border-dashed border-zinc-200 dark:border-white/[0.06] bg-zinc-50/60 dark:bg-white/[0.02] flex flex-col items-center justify-center gap-3 px-6 py-7">
        <motion.div
          initial={{ opacity: 0, y: 5 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.12, duration: 0.35, ease: "easeOut" }}
          className="rounded-xl border border-zinc-200 dark:border-white/[0.08] bg-white dark:bg-white/[0.04] px-5 py-3.5 shadow-[0_1px_4px_rgba(0,0,0,0.03)]"
        >
          <div className="text-[12px] font-semibold text-zinc-900 dark:text-zinc-100 tracking-tight">payments_api.json</div>
          <div className="text-[10px] text-zinc-400 dark:text-zinc-500 mt-0.5">OpenAPI 3.1 · 24 KB</div>
        </motion.div>
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.45, duration: 0.3, ease: "easeOut" }}
          className="text-[10px] text-zinc-400 dark:text-zinc-500 font-medium"
        >
          Spec accepted · parsing…
        </motion.div>
      </div>

      {/* Metadata row — slightly asymmetric info */}
      <div className="flex items-center justify-between px-1">
        <div className="text-[10px] text-zinc-400 dark:text-zinc-500 font-medium">34 endpoints detected</div>
        <div className="text-[10px] text-zinc-400 dark:text-zinc-500 font-normal">v2.4.1</div>
      </div>
    </motion.div>
  )
}

// ─── Step 02: Coverage ───────────────────────────────────────────────────────

// Non-uniform percentages to break the "template" feel
const coverageBars = [
  { label: "Mapping endpoints", target: 100, delay: 0, height: "h-1.5", radius: "rounded-full" },
  { label: "Parsing schemas", target: 83, delay: 0.18, height: "h-[5px]", radius: "rounded-full" },
  { label: "Identifying edge cases", target: 57, delay: 0.34, height: "h-[7px]", radius: "rounded-[3px]" },
]

function CoverageView() {
  return (
    <motion.div {...panelTransition} className="flex flex-col h-full justify-center">
      <div className="space-y-[18px]">
        {coverageBars.map((bar, i) => (
          <div key={i} className={cn("space-y-2", i === 1 && "space-y-[7px]", i === 2 && "space-y-[9px]")}>
            <div className="flex justify-between items-baseline">
              <span className={cn("text-[11px] font-medium", i === 0 ? "text-zinc-600 dark:text-zinc-300" : "text-zinc-500 dark:text-zinc-400")}>{bar.label}</span>
              <motion.span
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: bar.delay + 0.8, duration: 0.25, ease: "easeOut" }}
                className="text-[10px] font-medium text-zinc-400 dark:text-zinc-500 tabular-nums"
              >
                {bar.target}%
              </motion.span>
            </div>
            <div className={cn(bar.height, "w-full bg-zinc-100 dark:bg-white/[0.04] overflow-hidden", bar.radius)}>
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: `${bar.target}%` }}
                transition={{ delay: bar.delay + 0.1, duration: 1.2, ease: [0.25, 0.46, 0.45, 0.94] }}
                className={cn("h-full", bar.radius, i === 2 ? "bg-[#27BE8C]/85" : "bg-[#27BE8C]")}
              />
            </div>
          </div>
        ))}
      </div>

      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 1.4, duration: 0.3, ease: "easeOut" }}
        className="text-[10px] text-zinc-400 font-medium mt-5"
      >
        128 test scenarios generated
      </motion.div>
    </motion.div>
  )
}

// ─── Step 03: Run Tests ──────────────────────────────────────────────────────

// Realistic variation: mixed naming lengths, one row missing latency, non-uniform data
const testResults = [
  { method: "GET", path: "/users", status: "PASS", time: "84ms" },
  { method: "POST", path: "/auth/login", status: "PASS", time: "112ms" },
  { method: "PUT", path: "/settings/profile", status: "403", time: "240ms" },
  { method: "GET", path: "/v1/charges", status: "PASS", time: null as string | null },
]

function TestRunView() {
  return (
    <motion.div {...panelTransition} className="flex flex-col h-full justify-center">
      {/* Slightly uneven gap between rows */}
      <div className="flex flex-col">
        {testResults.map((row, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, y: 3 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.09 + 0.1, duration: 0.3, ease: "easeOut" }}
            className={cn(
              "flex items-center justify-between rounded-xl border bg-white dark:bg-white/[0.04] dark:border-white/[0.08]",
              row.status === "403"
                ? "border-red-100 dark:border-red-900/30 bg-red-50/30 dark:bg-red-900/10"
                : "border-zinc-100",
              // Non-uniform padding and spacing per row
              i === 0 && "px-4 py-2.5 mb-2",
              i === 1 && "px-[15px] py-[9px] mb-[9px]",
              i === 2 && "px-4 py-[11px] mb-[7px]",
              i === 3 && "px-[17px] py-[10px]",
            )}
          >
            <div className={cn("flex items-center", i === 2 ? "gap-[11px]" : "gap-3")}>
              <span
                className={cn(
                  "text-[9px] font-bold tracking-wide",
                  row.method === "GET" && "bg-zinc-100 dark:bg-white/[0.06] text-zinc-600 dark:text-zinc-300 px-1.5 py-0.5 rounded",
                  row.method === "POST" && "bg-zinc-800 dark:bg-white/[0.1] text-white dark:text-zinc-100 px-[7px] py-0.5 rounded-[3px]",
                  row.method === "PUT" && "bg-zinc-200 dark:bg-white/[0.04] text-zinc-700 dark:text-zinc-300 px-1.5 py-[3px] rounded",
                )}
              >
                {row.method}
              </span>
              <span className={cn("text-[11px] font-medium", i === 3 ? "text-zinc-700 dark:text-zinc-300" : "text-zinc-800 dark:text-zinc-200")}>{row.path}</span>
            </div>
            <div className="flex items-center gap-3">
              {row.time && (
                <span className="text-[10px] text-zinc-400 tabular-nums font-medium">{row.time}</span>
              )}
              <span
                className={cn(
                  "text-[10px] font-semibold tabular-nums",
                  row.status === "PASS" ? "text-[#27BE8C]" : "text-red-500"
                )}
              >
                {row.status === "PASS" ? "PASS" : `${row.status} error`}
              </span>
            </div>
          </motion.div>
        ))}
      </div>
    </motion.div>
  )
}

// ─── Step 04: Insights ───────────────────────────────────────────────────────

function InsightsView() {
  return (
    <motion.div {...panelTransition} className="flex flex-col gap-4 h-full justify-center">
      {/* Stats — slightly different padding per card to break uniformity */}
      <div className="grid grid-cols-3 gap-3">
        {[
          { label: "Pass rate", value: "99%", accent: true, pad: "p-3.5", radius: "rounded-xl" },
          { label: "Avg latency", value: "124ms", accent: false, pad: "p-[13px]", radius: "rounded-[10px]" },
          { label: "Coverage", value: "94%", accent: false, pad: "p-3.5", radius: "rounded-xl" },
        ].map((stat, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, y: 3 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.1 + 0.08, duration: 0.3, ease: "easeOut" }}
            className={cn(
              "border border-zinc-100 dark:border-white/[0.08] bg-white dark:bg-white/[0.04]",
              stat.pad,
              stat.radius,
              i === 0 && "shadow-[0_1px_2px_rgba(0,0,0,0.03)]",
              i === 2 && "shadow-[0_1px_3px_rgba(0,0,0,0.02)]",
            )}
          >
            <div className={cn("text-[10px] text-zinc-400 dark:text-zinc-500 font-medium", i === 1 ? "mb-1.5" : "mb-1")}>{stat.label}</div>
            <div
              className={cn(
                "font-semibold tabular-nums leading-tight",
                stat.accent ? "text-[#27BE8C] text-[20px]" : "text-zinc-900 dark:text-white text-[19px]"
              )}
            >
              {stat.value}
            </div>
          </motion.div>
        ))}
      </div>

      {/* Failure alert */}
      <motion.div
        initial={{ opacity: 0, y: 3 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.42, duration: 0.3, ease: "easeOut" }}
        className="rounded-xl border border-red-100 dark:border-red-900/30 bg-red-50/40 dark:bg-red-900/10 px-4 py-3 flex items-start justify-between"
      >
        <div>
          <div className="text-[11px] font-semibold text-red-600 dark:text-red-400">PUT /settings/profile → 403 Forbidden</div>
          <div className="text-[10px] text-red-400 dark:text-red-500/80 mt-0.5">Authorization header missing scope</div>
        </div>
        <div className="text-[9px] font-medium text-red-400 mt-0.5 whitespace-nowrap ml-4">240ms</div>
      </motion.div>

      {/* Summary */}
      <div className="text-[10px] text-zinc-400 font-medium">
        1 of 128 tests require attention
      </div>
    </motion.div>
  )
}

// ─── Step Views Map ──────────────────────────────────────────────────────────

const stepViews = [UploadView, CoverageView, TestRunView, InsightsView]

// ─── Timeline Step (Right Side) ──────────────────────────────────────────────

function TimelineStep({
  step,
  index,
  isActive,
  isLast,
  onClick,
}: {
  step: (typeof steps)[0]
  index: number
  isActive: boolean
  isLast: boolean
  onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      className="flex items-stretch gap-5 text-left cursor-pointer group w-full"
    >
      {/* Timeline track */}
      <div className="flex flex-col items-center pt-0.5">
        {/* Dot — active slightly larger, inactive dots vary subtly by index */}
        <motion.div
          animate={{
            scale: isActive ? 1 : 1,
            backgroundColor: isActive ? "#27BE8C" : "#d4d4d8",
          }}
          transition={{ duration: 0.4, ease: "easeOut" }}
          className={cn(
            "rounded-full flex-shrink-0 transition-shadow duration-500",
            isActive
              ? "h-[10px] w-[10px] shadow-[0_0_0_3px_rgba(39,190,140,0.1)]"
              : cn(
                "group-hover:bg-zinc-300",
                index === 0 && "h-[7px] w-[7px]",
                index === 1 && "h-[8px] w-[8px]",
                index === 2 && "h-[7px] w-[7px]",
                index === 3 && "h-[8px] w-[8px]",
              ),
          )}
        />
        {/* Line — softer, less prominent */}
        {!isLast && (
          <div className="w-px flex-1 mt-2 mb-0">
            <div
              className={cn(
                "w-full h-full transition-colors duration-500",
                isActive ? "bg-[#27BE8C]/12" : "bg-zinc-100/70 dark:bg-white/[0.04]"
              )}
            />
          </div>
        )}
      </div>

      {/* Text content */}
      {/* Slightly varied bottom spacing per step for organic rhythm */}
      <div className={cn(
        isLast ? "pb-0" : "",
        !isLast && index === 0 && "pb-7",
        !isLast && index === 1 && "pb-[31px]",
        !isLast && index === 2 && "pb-[26px]",
      )}>
        <div
          className={cn(
            "text-[12px] font-medium tabular-nums transition-colors duration-500",
            isActive ? "text-[#27BE8C]" : "text-zinc-400"
          )}
        >
          {step.number}
        </div>
        <motion.div
          animate={{ scale: isActive ? 1.01 : 1 }}
          transition={{ duration: 0.35, ease: "easeOut" }}
          className={cn(
            "text-[15px] leading-snug transition-colors duration-500 origin-left",
            index === 0 ? "mt-[5px]" : "mt-1",
            isActive ? "text-zinc-900 dark:text-white font-semibold" : "text-zinc-500 dark:text-zinc-400 font-medium"
          )}
        >
          {step.title}
        </motion.div>
        <div
          className={cn(
            "text-[13px] leading-relaxed max-w-[280px] transition-all duration-500",
            index === 2 ? "mt-[5px]" : "mt-1.5",
            isActive ? "text-zinc-500" : "text-zinc-400 opacity-80"
          )}
        >
          {step.description}
        </div>
      </div>
    </button>
  )
}

// ─── Progress Bar ────────────────────────────────────────────────────────────

function StepProgressBar({ activeStep, isPaused, stepDuration }: { activeStep: number; isPaused: boolean; stepDuration: number }) {
  return (
    <div className="flex gap-1.5">
      {Array.from({ length: STEP_COUNT }).map((_, i) => (
        <div key={i} className="h-0.5 flex-1 rounded-full bg-zinc-100 dark:bg-white/[0.06] overflow-hidden">
          {i === activeStep && (
            <motion.div
              key={`bar-${activeStep}-${stepDuration}`}
              initial={{ width: "0%" }}
              animate={{ width: isPaused ? undefined : "100%" }}
              transition={{ duration: stepDuration / 1000, ease: "easeOut" }}
              className="h-full bg-[#27BE8C]/50 rounded-full"
            />
          )}
          {i < activeStep && (
            <div className="h-full w-full bg-[#27BE8C]/20 rounded-full" />
          )}
        </div>
      ))}
    </div>
  )
}

// ─── Main Component ──────────────────────────────────────────────────────────

export default function HowItWorksSection() {
  const [activeStep, setActiveStep] = React.useState(0)
  const [isPaused, setIsPaused] = React.useState(false)
  const [stepDuration, setStepDuration] = React.useState(getStepDuration)
  // Delayed right-side highlight for staggered feel
  const [displayedStep, setDisplayedStep] = React.useState(0)
  const reduceMotion = useReducedMotion()

  // Auto-cycle with randomized timing
  React.useEffect(() => {
    if (isPaused) return
    const duration = getStepDuration()
    setStepDuration(duration)
    const timer = setTimeout(() => {
      setActiveStep((prev) => (prev + 1) % STEP_COUNT)
    }, duration)
    return () => clearTimeout(timer)
  }, [isPaused, activeStep])

  // Slight delay between left animation and right text highlight (~120ms)
  React.useEffect(() => {
    const delay = setTimeout(() => {
      setDisplayedStep(activeStep)
    }, 120)
    return () => clearTimeout(delay)
  }, [activeStep])

  const handleStepClick = React.useCallback((index: number) => {
    setActiveStep(index)
    setDisplayedStep(index) // instant on click
    setIsPaused(true)
    setTimeout(() => setIsPaused(false), 4500)
  }, [])

  const ActiveView = stepViews[activeStep]

  return (
    <motion.section
      initial={reduceMotion ? false : "hidden"}
      animate={reduceMotion ? undefined : "visible"}
      variants={{
        hidden: { opacity: 0 },
        visible: {
          opacity: 1,
          transition: {
            staggerChildren: 0.1,
          },
        },
      }}
      className="border-t border-zinc-100 dark:border-white/[0.05] bg-white dark:bg-[#020617] py-20 lg:py-24"
    >
      <div className="mx-auto max-w-6xl px-6">
        {/* Section header */}
        <div className="mb-14">
          <motion.div
            variants={{
              hidden: { opacity: 0, y: 20 },
              visible: { opacity: 1, y: 0, transition: { duration: 0.8, ease: [0.22, 1, 0.36, 1] } }
            }}
            className="text-[11px] font-semibold text-[#27BE8C] uppercase tracking-[0.15em] mb-3"
          >
            How it works
          </motion.div>
          <motion.h2
            variants={{
              hidden: { opacity: 0, y: 20 },
              visible: { opacity: 1, y: 0, transition: { duration: 0.8, ease: [0.22, 1, 0.36, 1] } }
            }}
            className="text-[28px] md:text-[32px] font-semibold text-zinc-900 dark:text-white leading-tight max-w-md"
          >
            From API spec to production confidence
          </motion.h2>
        </div>

        {/* Split layout */}
        <motion.div
          variants={{
            hidden: { opacity: 0, y: 20 },
            visible: { opacity: 1, y: 0, transition: { duration: 0.8, ease: [0.22, 1, 0.36, 1] } }
          }}
          className="flex flex-col lg:flex-row gap-12 lg:gap-20 items-start"
        >
          {/* LEFT: Product animation container */}
          <div className="w-full lg:w-[58%]">
            <div className="rounded-2xl border border-zinc-200 bg-white shadow-sm overflow-hidden transition-all duration-300 ease-out dark:bg-white/[0.04] dark:backdrop-blur-md dark:border-white/[0.08] dark:shadow-[0_4px_20px_rgba(0,0,0,0.4)]">
              {/* Mock app header */}
              <div className="flex items-center justify-between border-b border-zinc-100 bg-zinc-50/50 px-5 py-3 dark:bg-white/[0.02] dark:border-white/[0.06]">
                <div className="flex items-center gap-3">
                  <div className="flex gap-1.5">
                    <div className="h-2 w-2 rounded-full bg-zinc-200 dark:bg-white/[0.1]" />
                    <div className="h-2 w-2 rounded-full bg-zinc-200 dark:bg-white/[0.1]" />
                    <div className="h-2 w-2 rounded-full bg-zinc-200 dark:bg-white/[0.1]" />
                  </div>
                  <div className="h-3 w-px bg-zinc-200 dark:bg-white/[0.1]" />
                  <span className="text-[10px] font-semibold text-zinc-400 dark:text-zinc-500 tracking-wide uppercase">
                    Cognitest
                  </span>
                  <span className="text-[10px] text-zinc-300 dark:text-zinc-600">/</span>
                  <span className="text-[10px] font-semibold text-zinc-700 dark:text-zinc-300">
                    Payment Gateway
                  </span>
                </div>
                <div className="flex items-center gap-1.5">
                  <div className="h-1.5 w-1.5 rounded-full bg-[#27BE8C]" />
                  <span className="text-[9px] font-semibold text-[#27BE8C]">Live</span>
                </div>
              </div>

              {/* Step progress */}
              <div className="px-5 pt-3 pb-1">
                <StepProgressBar activeStep={activeStep} isPaused={isPaused} stepDuration={stepDuration} />
              </div>

              {/* Content area */}
              <div className="px-[19px] pb-5 pt-3 min-h-[280px] md:min-h-[300px]">
                <AnimatePresence mode="wait">
                  <ActiveView key={activeStep} />
                </AnimatePresence>
              </div>
            </div>
          </div>

          {/* RIGHT: Timeline */}
          <div className="w-full lg:w-[42%] lg:pt-4">
            <div className="flex flex-col">
              {steps.map((step, i) => (
                <TimelineStep
                  key={step.number}
                  step={step}
                  index={i}
                  isActive={displayedStep === i}
                  isLast={i === steps.length - 1}
                  onClick={() => handleStepClick(i)}
                />
              ))}
            </div>
          </div>
        </motion.div>
      </div>
    </motion.section>
  )
}
