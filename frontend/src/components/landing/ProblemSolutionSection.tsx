import * as React from "react"
import { motion } from "framer-motion"
import { Check, X, Minus } from "lucide-react"
import { cn } from "@/lib/utils"

const manualItems = [
  "Rewrite tests every release",
  "Miss security regressions",
  "Broken CI pipelines",
  "Delayed bug detection",
]

const cognitestItems = [
  "Syncs with OpenAPI changes",
  "Functional + security coverage",
  "CI validation on every push",
  "Self-maintained live suites",
]

const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.1,
      delayChildren: 0.3,
    },
  },
}

const itemVariants = {
  hidden: { opacity: 0, x: -10 },
  visible: { opacity: 1, x: 0, transition: { duration: 0.5 } },
}

export default function ProblemSolutionSection() {
  return (
    <section className="relative overflow-hidden bg-white dark:bg-[#020617] py-16 lg:py-24">
      <div className="mx-auto max-w-7xl px-6 lg:px-8">

        {/* Section Header */}
        <div className="flex flex-col items-center text-center mb-12 lg:mb-16">
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
            className="inline-flex items-center gap-2 mb-4 px-4 py-1.5 rounded-full bg-zinc-50 dark:bg-white/[0.06] border border-zinc-100 dark:border-white/[0.08] text-[10px] font-semibold text-zinc-500 dark:text-zinc-400 dark:text-zinc-500 uppercase tracking-[0.2em] shadow-sm"
          >
            Why teams switch
          </motion.div>

          <motion.h2
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.1 }}
            className="text-[2.25rem] md:text-[3rem] font-semibold tracking-tight text-zinc-900 dark:text-zinc-100 leading-tight mb-4 max-w-[18ch] md:max-w-[22ch] mx-auto"
          >
            Manual API testing <br className="hidden md:block" /> wastes engineering time
          </motion.h2>

          <motion.p
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.2 }}
            className="text-[1rem] md:text-[1.125rem] text-zinc-500 dark:text-zinc-400 dark:text-zinc-500 font-medium max-w-2xl"
          >
            When docs change, manual suites break. <br className="hidden md:block" />
            Cognitest regenerates tests automatically, keeping you in sync.
          </motion.p>
        </div>

        {/* Comparison Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 items-stretch">

          {/* Manual Card */}
          <motion.div
            initial={{ opacity: 0, x: -30 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
            whileHover={{ y: 0 }}
            className="relative rounded-[28px] border border-zinc-200 bg-white p-6 md:p-8 flex flex-col shadow-[inset_0_1px_2px_rgba(0,0,0,0.01)] transition-all duration-300 ease-out dark:bg-white/[0.04] dark:backdrop-blur-md dark:border-white/[0.08] dark:shadow-[0_4px_20px_rgba(0,0,0,0.4)] dark:hover:bg-white/[0.06] dark:hover:border-white/[0.12]"
          >
            <div className="mb-8">
              <h3 className="text-[1.25rem] font-semibold text-zinc-600 mb-2 tracking-tight">Manual Process</h3>
              <div className="h-1 w-12 bg-zinc-100 rounded-full" />
            </div>

            <motion.ul
              variants={containerVariants}
              initial="hidden"
              animate="visible"
              className="space-y-5 flex-1"
            >
              {manualItems.map((item, i) => (
                <motion.li key={i} variants={itemVariants} className="flex items-center gap-4 text-zinc-500 dark:text-zinc-400 font-medium">
                  <div className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-zinc-50 dark:bg-white/[0.06] border border-zinc-100 dark:border-white/[0.08]">
                    <div className="h-px w-2 bg-zinc-400 dark:bg-zinc-500" />
                  </div>
                  {item}
                </motion.li>
              ))}
            </motion.ul>
          </motion.div>

          {/* Cognitest Card */}
          <motion.div
            initial={{ opacity: 0, x: 30 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
            whileHover={{ y: -6, scale: 1.01 }}
            className="relative z-10 rounded-[28px] border border-[#27BE8C]/20 bg-white p-6 md:p-8 flex flex-col shadow-[0_40px_80px_-16px_rgba(0,0,0,0.1)] ring-1 ring-[#27BE8C]/5 transition-all duration-300 ease-out dark:bg-white/[0.04] dark:backdrop-blur-md dark:border-white/[0.08] dark:shadow-[0_4px_20px_rgba(0,0,0,0.4)] dark:hover:bg-white/[0.06] dark:hover:border-white/[0.12] dark:hover:shadow-[0_6px_30px_rgba(0,0,0,0.5)]"
          >
            {/* Ambient Glow */}
            <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[120%] h-[120%] bg-[#27BE8C]/[0.03] blur-[100px] rounded-full pointer-events-none" />

            <div className="relative z-10 mb-8">
              <h3 className="text-[1.25rem] font-semibold text-zinc-900 dark:text-zinc-100 mb-2">Cognitest Automation</h3>
              <div className="h-1 w-12 bg-[#27BE8C] rounded-full" />
            </div>

            <motion.ul
              variants={containerVariants}
              initial="hidden"
              animate="visible"
              className="relative z-10 space-y-5 flex-1"
            >
              {cognitestItems.map((item, i) => (
                <motion.li key={i} variants={itemVariants} className="flex items-center gap-4 text-zinc-900 dark:text-zinc-100 font-semibold">
                  <div className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[#27BE8C]/10">
                    <div className="h-1.5 w-1.5 rounded-full bg-[#27BE8C]" />
                  </div>
                  {item}
                </motion.li>
              ))}
            </motion.ul>
          </motion.div>

        </div>
      </div>
    </section>
  )
}
