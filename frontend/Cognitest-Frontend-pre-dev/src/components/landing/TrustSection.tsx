import * as React from "react"
import { motion, useInView, animate, useMotionValue, useTransform } from "framer-motion"
import { Building2, Users, Zap, ShieldCheck } from "lucide-react"
import { cn } from "@/lib/utils"

const stats = [
  {
    value: 120,
    suffix: "+",
    label: "Companies Using Cognitest",
    icon: Building2,
  },
  {
    value: 1800,
    suffix: "+",
    label: "Engineers Onboarded",
    icon: Users,
  },
  {
    value: 450,
    suffix: "k+",
    label: "Automated Test Runs",
    icon: Zap,
  },
  {
    value: 99.2,
    suffix: "%",
    label: "Pass Reliability Rate",
    icon: ShieldCheck,
  },
]

function AnimatedCounter({ value, suffix, decimals = 0 }: { value: number, suffix: string, decimals?: number }) {
  const count = useMotionValue(0)
  const rounded = useTransform(count, (latest) => latest.toFixed(decimals))
  const ref = React.useRef(null)
  const isInView = useInView(ref, { once: true, margin: "-50px" })

  React.useEffect(() => {
    if (isInView) {
      animate(count, value, {
        duration: 2.0,
        ease: "easeOut",
      })
    }
  }, [isInView, value, count])

  return (
    <span ref={ref} className="tabular-nums">
      <motion.span>{rounded}</motion.span>
      {suffix}
    </span>
  )
}

export default function TrustSection() {
  return (
    <section className="relative bg-white dark:bg-[#020617] mt-20 mb-24">
      <div className="mx-auto max-w-6xl px-6 lg:px-8">

        {/* Top Layer: Trust Statement */}
        <div className="flex flex-col items-center mb-10 lg:mb-14">
          <motion.p
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
            className="text-[10px] font-semibold text-zinc-400 dark:text-zinc-500 uppercase tracking-[0.25em] mb-4 text-center max-w-md"
          >
            Built for modern teams shipping production APIs
          </motion.p>
          <div className="h-px w-8 bg-zinc-100" />
        </div>

        {/* Bottom Layer: Stats Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-8">
          {stats.map((stat, i) => (
            <motion.div
              key={stat.label}
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.1, duration: 0.7, ease: "easeOut" }}
              className={cn(
                "relative rounded-xl border border-zinc-200 bg-gradient-to-b from-white to-zinc-50/40 p-7 md:p-8 h-[170px] flex flex-col justify-center items-start shadow-sm transition-all duration-300 ease-out",
                "dark:bg-white/[0.04] dark:backdrop-blur-md dark:border-white/[0.08] dark:shadow-[0_4px_20px_rgba(0,0,0,0.4)] dark:from-transparent dark:to-transparent",
                "hover:shadow-md hover:border-zinc-300 dark:hover:bg-white/[0.06] dark:hover:border-white/[0.12] dark:hover:shadow-[0_6px_30px_rgba(0,0,0,0.5)]",
                i % 2 !== 0 ? "mt-1" : "mt-0"
              )}
            >
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: 56 }}
                transition={{ duration: 0.6, ease: "easeOut", delay: i * 0.1 }}
                className="h-[3px] rounded-full mb-4 bg-gradient-to-r from-emerald-500 via-emerald-400 to-emerald-300 dark:from-emerald-400 dark:via-emerald-300 dark:to-transparent dark:opacity-70 shadow-[0_0_8px_rgba(16,185,129,0.25)]"
              />

              <div
                className="text-[38px] font-bold tracking-[-0.5px] leading-none bg-clip-text text-transparent"
                style={{
                  backgroundImage: "linear-gradient(180deg, #34d399 0%, #22c55e 40%, #15803d 100%)",
                  WebkitBackgroundClip: "text",
                  WebkitTextFillColor: "transparent",
                  textShadow: "0 1px 1px rgba(0,0,0,0.06)"
                }}
              >
                <AnimatedCounter
                  value={stat.value}
                  suffix={stat.suffix}
                  decimals={stat.value % 1 !== 0 ? 1 : 0}
                />
              </div>
              <div className={cn("mt-3 text-base font-medium text-zinc-700 dark:text-zinc-400", i === 1 ? "max-w-[90%]" : i === 2 ? "max-w-[80%]" : "max-w-full")}>
                {stat.label}
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  )
}
