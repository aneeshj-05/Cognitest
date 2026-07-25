import * as React from "react"
import { motion } from "framer-motion"
import { cn } from "@/lib/utils"

const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.1,
    },
  },
}

const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: { 
    opacity: 1, 
    y: 0,
    transition: { duration: 0.8, ease: [0.22, 1, 0.36, 1] }
  },
}

export default function CapabilitiesSection() {
  return (
    <section className="relative overflow-hidden bg-white dark:bg-[#020617] py-14 lg:py-16">
      <div className="mx-auto max-w-7xl px-6 lg:px-8">
        
        {/* Section Header */}
        <div className="flex flex-col mb-8">
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="inline-flex items-center gap-2 mb-4 px-3 py-1 rounded-full bg-zinc-50 dark:bg-white/[0.06] border border-zinc-100 dark:border-white/[0.08] text-[10px] font-medium text-zinc-500 dark:text-zinc-400 dark:text-zinc-500 uppercase tracking-[0.2em]"
          >
            Capabilities
          </motion.div>
          
          <motion.h2
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="text-[2rem] md:text-[2.25rem] font-semibold tracking-tight text-zinc-900 dark:text-zinc-100 leading-tight mb-4 lg:whitespace-nowrap"
          >
            Built for modern API teams
          </motion.h2>
          
          <motion.p
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="text-[1rem] md:text-[1.125rem] text-zinc-500 dark:text-zinc-400 dark:text-zinc-500 font-normal max-w-2xl"
          >
            Everything needed to generate, validate, and ship reliable APIs faster.
          </motion.p>
        </div>

        {/* Bento Grid */}
        <motion.div 
          variants={containerVariants}
          initial="hidden"
          animate="visible"
          className="grid grid-cols-1 lg:grid-cols-12 gap-6"
        >
          
          {/* 1. Functional Coverage (Large Featured Card) */}
          <motion.div 
            variants={itemVariants}
            className="lg:col-span-8 group relative overflow-hidden rounded-[24px] border border-zinc-100 bg-zinc-50/50 p-6 lg:p-8 flex flex-col lg:flex-row gap-8 items-center transition-all duration-300 ease-out hover:shadow-md hover:-translate-y-1 dark:bg-white/[0.04] dark:backdrop-blur-md dark:border-white/[0.08] dark:shadow-[0_4px_20px_rgba(0,0,0,0.4)] dark:hover:bg-white/[0.06] dark:hover:border-white/[0.12] dark:hover:shadow-[0_6px_30px_rgba(0,0,0,0.5)]"
          >
            <div className="flex-1">
              <h3 className="text-xl font-semibold text-zinc-900 dark:text-zinc-100 mb-2">Functional Coverage</h3>
              <p className="text-zinc-500 dark:text-zinc-400 text-sm font-normal max-w-sm">
                Generate exhaustive functional test suites from your OpenAPI spec automatically.
              </p>
            </div>

            <div className="flex-1 w-full relative bg-white dark:bg-white/[0.04] rounded-xl border border-zinc-200 dark:border-white/[0.08] shadow-sm overflow-hidden">
              <div className="p-3 border-b border-zinc-100 dark:border-white/[0.06] bg-zinc-50/50 dark:bg-white/[0.02] flex items-center justify-between">
                <span className="text-[10px] font-medium text-zinc-400 dark:text-zinc-500 uppercase tracking-widest">Endpoints</span>
                <div className="flex gap-1">
                  <div className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                  <div className="w-1.5 h-1.5 rounded-full bg-zinc-200" />
                </div>
              </div>
              <div className="p-3 space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="px-1 py-0.5 rounded bg-emerald-50 text-emerald-600 text-[9px] font-semibold uppercase">GET</span>
                    <span className="text-[11px] font-medium text-zinc-600">/customers</span>
                  </div>
                  <span className="text-[9px] font-semibold text-emerald-500">PASS</span>
                </div>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="px-1 py-0.5 rounded bg-blue-50 text-blue-600 text-[9px] font-semibold uppercase">POST</span>
                    <span className="text-[11px] font-medium text-zinc-600">/billing</span>
                  </div>
                  <div className="flex h-1 w-8 bg-zinc-100 rounded-full overflow-hidden">
                    <div className="w-3/4 bg-emerald-500" />
                  </div>
                </div>
              </div>
            </div>
          </motion.div>

          {/* 2. Security & OWASP */}
          <motion.div 
            variants={itemVariants}
            className="lg:col-span-4 group relative overflow-hidden rounded-[24px] border border-zinc-100 bg-white p-6 transition-all duration-300 ease-out hover:shadow-md hover:-translate-y-1 dark:bg-white/[0.04] dark:backdrop-blur-md dark:border-white/[0.08] dark:shadow-[0_4px_20px_rgba(0,0,0,0.4)] dark:hover:bg-white/[0.06] dark:hover:border-white/[0.12] dark:hover:shadow-[0_6px_30px_rgba(0,0,0,0.5)]"
          >
            <h3 className="text-lg font-medium text-zinc-900 dark:text-zinc-100 mb-2">Security & OWASP</h3>
            <p className="text-zinc-500 dark:text-zinc-400 text-sm font-normal mb-6">
              Vulnerability scans aligned with OWASP Top 10.
            </p>

            {/* UI Visual: Security Health */}
            <div className="p-3 rounded-xl bg-zinc-50 dark:bg-white/[0.04] border border-zinc-100 dark:border-white/[0.08] flex items-center justify-between">
              <div className="flex flex-col">
                <span className="text-[9px] font-medium text-zinc-400 dark:text-zinc-500 uppercase tracking-tight">Security Health</span>
                <span className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">98.4%</span>
              </div>
              <div className="flex gap-1.5">
                <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                <div className="w-2 h-2 rounded-full bg-emerald-500/20" />
              </div>
            </div>
          </motion.div>

          {/* 3. CI/CD Gates */}
          <motion.div 
            variants={itemVariants}
            className="lg:col-span-4 group relative overflow-hidden rounded-[24px] border border-zinc-100 bg-white p-6 transition-all duration-300 ease-out hover:shadow-md hover:-translate-y-1 dark:bg-white/[0.04] dark:backdrop-blur-md dark:border-white/[0.08] dark:shadow-[0_4px_20px_rgba(0,0,0,0.4)] dark:hover:bg-white/[0.06] dark:hover:border-white/[0.12] dark:hover:shadow-[0_6px_30px_rgba(0,0,0,0.5)]"
          >
            <div className="flex items-start justify-between mb-4">
              <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100 uppercase tracking-wide">CI/CD Gates</h3>
              <span className="text-[10px] font-semibold text-[#27BE8C] px-1.5 py-0.5 rounded bg-emerald-50">STABLE</span>
            </div>
            
            {/* UI Visual: Pipeline */}
            <div className="flex items-center gap-1.5 p-3 rounded-lg bg-zinc-50 dark:bg-white/[0.04] border border-zinc-100 dark:border-white/[0.08]">
              <div className="w-1.5 h-1.5 rounded-full bg-[#27BE8C]" />
              <div className="w-1.5 h-1.5 rounded-full bg-[#27BE8C]" />
              <div className="w-1.5 h-1.5 rounded-full bg-zinc-200" />
              <span className="text-[10px] font-medium text-zinc-400 dark:text-zinc-500 ml-auto">Pipeline Active</span>
            </div>
          </motion.div>

          {/* 4. Performance Signals */}
          <motion.div 
            variants={itemVariants}
            className="lg:col-span-4 group relative overflow-hidden rounded-[24px] border border-zinc-100 bg-zinc-50/50 p-6 transition-all duration-300 ease-out hover:shadow-md hover:-translate-y-1 dark:bg-white/[0.04] dark:backdrop-blur-md dark:border-white/[0.08] dark:shadow-[0_4px_20px_rgba(0,0,0,0.4)] dark:hover:bg-white/[0.06] dark:hover:border-white/[0.12] dark:hover:shadow-[0_6px_30px_rgba(0,0,0,0.5)]"
          >
            <div className="flex flex-col h-full justify-between">
              <div>
                <h3 className="text-sm font-medium text-zinc-500 dark:text-zinc-400 uppercase tracking-wider mb-2">P99 Latency</h3>
                <div className="flex items-baseline gap-2">
                  <span className="text-3xl font-semibold text-zinc-900 dark:text-zinc-100 tracking-tight text-shadow-sm">124ms</span>
                  <span className="text-[10px] font-semibold text-emerald-500">−12%</span>
                </div>
              </div>
              
              <div className="flex gap-0.5 h-8 items-end mt-4">
                {[4, 6, 8, 5, 7, 9, 6].map((h, i) => (
                  <div key={i} className={cn("flex-1 rounded-t-sm", i === 5 ? "bg-[#27BE8C]" : "bg-zinc-200")} style={{ height: `${h * 10}%` }} />
                ))}
              </div>
            </div>
          </motion.div>

          {/* 5. Actionable Reports */}
          <motion.div 
            variants={itemVariants}
            className="lg:col-span-4 group relative overflow-hidden rounded-[24px] border border-zinc-100 bg-white p-6 transition-all duration-300 ease-out hover:shadow-md hover:-translate-y-1 dark:bg-white/[0.04] dark:backdrop-blur-md dark:border-white/[0.08] dark:shadow-[0_4px_20px_rgba(0,0,0,0.4)] dark:hover:bg-white/[0.06] dark:hover:border-white/[0.12] dark:hover:shadow-[0_6px_30px_rgba(0,0,0,0.5)]"
          >
            <h3 className="text-base font-semibold text-zinc-900 dark:text-zinc-100 mb-4">Actionable Insights</h3>
            
            <div className="space-y-2">
              <div className="flex items-center gap-3 p-2 rounded-lg bg-red-50/30 border border-red-100/50">
                <div className="w-1.5 h-1.5 rounded-full bg-red-500" />
                <span className="text-[11px] font-medium text-red-700">Token Exposure detected</span>
              </div>
              <div className="flex items-center gap-3 p-2 rounded-lg bg-zinc-50 dark:bg-white/[0.04] border border-zinc-100 dark:border-white/[0.08]">
                <div className="w-1.5 h-1.5 rounded-full bg-zinc-300" />
                <span className="text-[11px] font-medium text-zinc-600">Schema mismatch in /v1/users</span>
              </div>
            </div>
          </motion.div>

        </motion.div>
      </div>
    </section>
  )
}
