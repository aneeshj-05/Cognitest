import * as React from "react"
import { Link } from "react-router-dom"
import { motion, AnimatePresence } from "framer-motion"
import {
  ArrowRight,
  CheckCircle2,
  Shield,
  Activity,
  FileJson,
  Play,
  Sparkles,
  Cpu,
  Globe,
  Terminal,
  Lock,
  Zap,
  ChevronRight,
  Layout,
  BarChart3,
  Settings,
  History,
  PlayCircle,
  ShieldCheck,
  Rocket
} from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { cn } from "@/lib/utils"

// --- Animation Variants ---

const revealUp = {
  hidden: { opacity: 0, y: 30 },
  visible: (i: number = 0) => ({
    opacity: 1,
    y: 0,
    transition: {
      delay: i,
      duration: 0.8,
      ease: [0.22, 1, 0.36, 1],
    },
  }),
}

const scaleIn = {
  hidden: { opacity: 0, scale: 0.96, y: 40 },
  visible: {
    opacity: 1,
    scale: 1,
    y: 0,
    transition: {
      delay: 0.2,
      duration: 1.2,
      ease: [0.22, 1, 0.36, 1],
    },
  },
}

// --- Sub-components ---

const DashboardPreview = () => {
  const [activeStep, setActiveStep] = React.useState(0)

  React.useEffect(() => {
    const timer = setInterval(() => {
      setActiveStep((prev) => (prev + 1) % 4)
    }, 4500)
    return () => clearInterval(timer)
  }, [])

  return (
    <motion.div
      variants={scaleIn}
      initial="hidden"
      animate="visible"
      className="relative w-full max-w-xl mx-auto lg:max-w-none"
    >
      {/* Living Float Animation Container */}
      <motion.div
        animate={{ y: [0, -8, 0] }}
        transition={{
          duration: 6,
          repeat: Infinity,
          ease: "easeInOut",
          delay: 1.4
        }}
      >
        {/* Main Dashboard Container */}
        <Card className="relative overflow-hidden rounded-[1rem] border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 shadow-[0_32px_64px_-16px_rgba(0,0,0,0.1)]">
          {/* Top App Header / Breadcrumbs */}
          <div className="flex items-center justify-between border-b border-zinc-100 dark:border-zinc-800 bg-zinc-50/50 dark:bg-zinc-900/50 px-5 py-3">
            <div className="flex items-center gap-4">
              <div className="flex gap-1.5">
                <div className="h-2.5 w-2.5 rounded-full bg-zinc-200" />
                <div className="h-2.5 w-2.5 rounded-full bg-zinc-200" />
                <div className="h-2.5 w-2.5 rounded-full bg-zinc-200" />
              </div>
              <div className="h-4 w-px bg-zinc-200" />
              <div className="flex items-center gap-2 text-[11px] font-semibold text-zinc-400 dark:text-zinc-500 uppercase tracking-wider">
                <span>Projects</span>
                <ChevronRight className="h-3 w-3" />
                <span className="text-zinc-900 dark:text-zinc-100">Payment Gateway</span>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-1.5 px-2 py-1 rounded bg-[#27BE8C]/10 text-[#27BE8C] text-[10px] font-semibold">
                <motion.div
                  animate={{ scale: [1, 1.5, 1], opacity: [1, 0.5, 1] }}
                  transition={{ duration: 1.5, repeat: Infinity }}
                  className="h-1.5 w-1.5 rounded-full bg-[#27BE8C]"
                />
                Connected
              </div>
            </div>
          </div>

          {/* Sub-Header / Tabs */}
          <div className="flex items-center gap-6 border-b border-zinc-100 dark:border-zinc-800 bg-white dark:bg-zinc-950 px-6 h-10 overflow-x-auto no-scrollbar">
            {['Specifications', 'Test Suites', 'Executions', 'Reports'].map((tab, i) => (
              <div
                key={tab}
                className={cn(
                  "text-[10px] font-semibold whitespace-nowrap relative h-full flex items-center cursor-pointer transition-colors",
                  i === 0 ? "text-zinc-900 dark:text-zinc-100" : "text-zinc-400 dark:text-zinc-500 hover:text-zinc-600"
                )}
              >
                {tab}
                {i === 0 && <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-[#27BE8C]" />}
              </div>
            ))}
          </div>

          {/* Dashboard Content */}
          <div className="flex h-[320px] md:h-[380px]">
            {/* Real Sidebar */}
            <div className="hidden md:flex w-14 flex-col items-center gap-5 border-r border-zinc-100 dark:border-zinc-800 py-5 bg-zinc-50/30 dark:bg-zinc-900/30">
              <div className="h-8 w-8 rounded-lg bg-zinc-900 flex items-center justify-center text-white"><Layout className="h-4 w-4" /></div>
              <div className="h-8 w-8 rounded-lg border border-zinc-100 dark:border-zinc-800 bg-white dark:bg-zinc-950 flex items-center justify-center text-zinc-400 dark:text-zinc-500 hover:text-zinc-600 transition-colors"><Shield className="h-4 w-4" /></div>
              <div className="h-8 w-8 rounded-lg border border-zinc-100 dark:border-zinc-800 bg-white dark:bg-zinc-950 flex items-center justify-center text-zinc-400 dark:text-zinc-500 hover:text-zinc-600 transition-colors"><BarChart3 className="h-4 w-4" /></div>
              <div className="mt-auto h-8 w-8 rounded-lg border border-zinc-100 dark:border-zinc-800 bg-white dark:bg-zinc-950 flex items-center justify-center text-zinc-400 dark:text-zinc-500 hover:text-zinc-600 transition-colors"><Settings className="h-4 w-4" /></div>
            </div>

            {/* Main Content Area */}
            <div className="flex-1 p-5 md:p-6 flex flex-col gap-5 overflow-hidden">
              {/* Context Summary Bar */}
              <div className="flex items-center justify-between text-[10px] font-semibold text-zinc-400 dark:text-zinc-500 tracking-tight uppercase border-b border-zinc-50 pb-4">
                <div className="flex items-center gap-4">
                  <div className="flex items-center gap-1.5"><History className="h-3 w-3" /> Last run: 2m ago</div>
                  <div className="h-3 w-px bg-zinc-100" />
                  <div className="flex items-center gap-1.5">
                    <div className="flex items-end gap-0.5 h-3">
                      {[0.4, 0.7, 0.5].map((h, i) => (
                        <motion.div
                          key={i}
                          animate={{ height: ["40%", "100%", "40%"] }}
                          transition={{ duration: 1.5, repeat: Infinity, delay: i * 0.2 }}
                          className="w-1 bg-[#27BE8C] rounded-full"
                        />
                      ))}
                    </div>
                    128 Tests Generated
                  </div>
                </div>
                <div className="text-[#27BE8C]">99.2% Pass Rate</div>
              </div>

              <AnimatePresence mode="wait">
                {activeStep === 0 && (
                  <motion.div
                    key="step0"
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0 }}
                    className="flex flex-col gap-4"
                  >
                    <div className="p-5 rounded-xl border-2 border-dashed border-zinc-100 dark:border-zinc-800 bg-zinc-50/30 dark:bg-zinc-900/30 flex flex-col items-center justify-center gap-3">
                      <FileJson className="h-10 w-10 text-zinc-200" />
                      <div className="text-center">
                        <div className="text-[11px] font-semibold text-zinc-900 dark:text-zinc-100 mb-1">payments_api_v1.json</div>
                        <div className="text-[9px] font-semibold text-zinc-400 dark:text-zinc-500 uppercase tracking-wider">34 Endpoints Detected</div>
                      </div>
                    </div>
                    <div className="space-y-2">
                      <div className="h-px bg-zinc-100 w-full" />
                      <div className="flex items-center justify-between text-[10px] font-semibold text-zinc-500 dark:text-zinc-400 dark:text-zinc-500">
                        <span>Environment</span>
                        <span className="text-zinc-900 dark:text-zinc-100">Staging-Cluster-B</span>
                      </div>
                    </div>
                  </motion.div>
                )}

                {activeStep === 1 && (
                  <motion.div
                    key="step1"
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0 }}
                    className="flex flex-col gap-4"
                  >
                    <div className="flex items-center gap-4 p-4 rounded-xl border border-zinc-100 dark:border-zinc-800 bg-zinc-50/30 dark:bg-zinc-900/30">
                      <div className="h-10 w-10 rounded-lg bg-white dark:bg-zinc-950 border border-zinc-100 dark:border-zinc-800 flex items-center justify-center">
                        <Cpu className="h-5 w-5 text-[#27BE8C]" />
                      </div>
                      <div className="flex flex-col">
                        <span className="text-[11px] font-semibold text-zinc-900 dark:text-zinc-100">AI Context Analysis</span>
                        <span className="text-[9px] font-semibold text-[#27BE8C] uppercase tracking-[0.15em] animate-pulse">Mapping dependencies...</span>
                      </div>
                    </div>
                    <div className="space-y-2">
                      {[
                        { label: "Parsing Payload Schemas", val: 88 },
                        { label: "Identifying Auth Chains", val: 64 },
                        { label: "Contextualizing Relations", val: 45 },
                      ].map((bar, i) => (
                        <div key={i} className="space-y-1.5">
                          <div className="flex justify-between text-[9px] font-semibold text-zinc-400 dark:text-zinc-500 uppercase">
                            <span>{bar.label}</span>
                            <span>{bar.val}%</span>
                          </div>
                          <div className="h-1.5 w-full rounded-full bg-zinc-100 relative overflow-hidden">
                            <motion.div
                              initial={{ width: 0 }}
                              animate={{ width: `${bar.val}%` }}
                              transition={{ duration: 1.5, delay: i * 0.1 }}
                              className="absolute inset-y-0 left-0 bg-[#27BE8C]"
                            />
                          </div>
                        </div>
                      ))}
                    </div>
                  </motion.div>
                )}

                {(activeStep === 2 || activeStep === 3) && (
                  <motion.div
                    key="step2"
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0 }}
                    className="flex flex-col gap-3"
                  >
                    <div className="space-y-2">
                      {[
                        { method: "POST", path: "/auth/login", status: "PASS", time: "112ms" },
                        { method: "GET", path: "/users/me", status: "PASS", time: "84ms" },
                        { method: "PUT", path: "/settings/profile", status: "FAIL", time: "240ms", error: "403 Forbidden" },
                        { method: "POST", path: "/v1/charges", status: "PASS", time: "380ms" },
                      ].map((row, i) => (
                        <motion.div
                          key={i}
                          initial={{ opacity: 0, x: -5 }}
                          animate={{ opacity: 1, x: 0 }}
                          transition={{ delay: i * 0.08 }}
                          className="flex items-center justify-between p-2.5 rounded-lg border border-zinc-100 dark:border-zinc-800 bg-white dark:bg-zinc-950 shadow-sm"
                        >
                          <div className="flex items-center gap-3">
                            <span className={cn(
                              "text-[8px] font-semibold px-1.5 py-0.5 rounded",
                              row.method === "POST" ? "bg-zinc-900 text-white" :
                                row.method === "GET" ? "bg-[#27BE8C] text-white" : "bg-blue-600 text-white"
                            )}>{row.method}</span>
                            <span className="text-[11px] font-semibold text-zinc-900 dark:text-zinc-100 tabular-nums">{row.path}</span>
                          </div>
                          <div className="flex items-center gap-3">
                            <span className="text-[9px] font-semibold text-zinc-400 dark:text-zinc-500">{row.time}</span>
                            <span className={cn("text-[9px] font-semibold", row.status === "PASS" ? "text-[#27BE8C]" : "text-red-500")}>
                              {row.status === "FAIL" ? row.error : row.status}
                            </span>
                          </div>
                        </motion.div>
                      ))}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </div>

          {/* Context Footer / Info Bar */}
          <div className="bg-zinc-50 dark:bg-zinc-900 border-t border-zinc-100 dark:border-zinc-800 px-6 py-2.5 flex items-center justify-between text-[9px] font-semibold text-zinc-400 dark:text-zinc-500 tracking-wider">
            <div className="flex items-center gap-3">
              <span>ID: CGN-7742</span>
              <span className="h-1 w-1 rounded-full bg-zinc-300" />
              <span>Worker: AWS-US-EAST-1</span>
            </div>
            <div className="flex items-center gap-1.5 text-zinc-500 dark:text-zinc-400 dark:text-zinc-500 uppercase">
              <PlayCircle className="h-3 w-3" />
              Re-run Suite
            </div>
          </div>
        </Card>
      </motion.div>
    </motion.div>
  )
}

const Headline = () => {
  return (
    <div className="mb-8 max-w-[540px] mx-auto lg:mx-0">
      <motion.h2
        custom={0.4}
        variants={revealUp}
        initial="hidden"
        animate="visible"
        className="text-[2.5rem] leading-[1.1] md:text-[3.5rem] font-semibold tracking-tight text-zinc-900 dark:text-zinc-100"
      >
        Turn your API docs <br />
        into <span className="text-[#27BE8C]">living</span> test suites
      </motion.h2>
    </div>
  )
}



const floatingLeft = [
  { text: "GET", left: "10%", delay: -8, duration: 24 },
  { text: "PUT", left: "30%", delay: -16, duration: 24 },
  { text: "DELETE", left: "15%", delay: -24, duration: 24 },
];

const floatingRight = [
  { text: "POST", left: "10%", delay: -8, duration: 24 },
  { text: "PATCH", left: "30%", delay: -16, duration: 24 },
  { text: "GET", left: "15%", delay: -24, duration: 24 },
];

function FloatingBackground() {
  return (
    <>
      <style>
        {`
          @keyframes floatUp {
            0% { top: 100%; opacity: 0; }
            10% { opacity: 1; }
            90% { opacity: 1; }
            100% { top: -20%; opacity: 0; }
          }
        `}
      </style>
      <div className="absolute inset-0 pointer-events-none hidden md:block">
        {/* Left Area */}
        <div className="absolute top-0 bottom-0 left-0 w-1/4">
          {floatingLeft.map((item, i) => (
            <div
              key={`l-${i}`}
              className="absolute text-[64px] font-black uppercase text-zinc-900/10 dark:text-zinc-100/[0.05] select-none tracking-tighter"
              style={{
                left: item.left,
                animation: `floatUp ${item.duration}s linear ${item.delay}s infinite`
              }}
            >
              {item.text}
            </div>
          ))}
        </div>
        {/* Right Area */}
        <div className="absolute top-0 bottom-0 right-0 w-1/4">
          {floatingRight.map((item, i) => (
            <div
              key={`r-${i}`}
              className="absolute text-[64px] font-black uppercase text-zinc-900/10 dark:text-zinc-100/[0.05] select-none tracking-tighter"
              style={{
                left: item.left,
                animation: `floatUp ${item.duration}s linear ${item.delay}s infinite`
              }}
            >
              {item.text}
            </div>
          ))}
        </div>
      </div>
    </>
  )
}

export default function HeroSection() {
  return (
    <>
      {/* 1. NEW HERO SECTION */}
      <motion.section
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.6 }}
        className="relative overflow-hidden bg-white dark:bg-zinc-950 pt-10 pb-10 lg:pt-16 lg:pb-12 flex flex-col items-center text-center">

        <FloatingBackground />

        <div className="relative z-10 mx-auto max-w-[820px] px-6 flex flex-col items-center">
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, ease: "easeOut" }}
            className="mb-[24px] inline-flex items-center px-4 py-[6px] rounded-full bg-[#F4F4F5] dark:bg-zinc-800 border border-[#E4E4E7] dark:border-zinc-700 text-[13px] font-medium text-[#52525B] dark:text-zinc-300 shadow-none">
            <div className="h-[6px] w-[6px] mr-[6px] rounded-full bg-[#22C55E]" />
            AI-powered API testing
          </motion.div>

          <motion.h1
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{
              duration: 0.7,
              delay: 0.1,
              ease: "easeOut",
            }}
            className="text-4xl md:text-[56px] font-semibold tracking-[-0.02em] text-[#18181B] dark:text-white leading-[1.1] max-w-[820px] mx-auto text-center mb-[16px] text-balance">
            Automate API testing with intelligent AI agents
          </motion.h1>

          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{
              duration: 0.6,
              delay: 0.2,
              ease: "easeOut",
            }}
            className="mt-[8px] mx-auto max-w-[640px] text-[18px] text-[#71717A] dark:text-zinc-400 leading-[1.6] text-center">
            Upload your OpenAPI, Swagger, or Postman docs. Cognitest
            automatically generates functional, security, and
            performance checks in seconds.
          </motion.p>

          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{
              duration: 0.5,
              delay: 0.3,
              ease: "easeOut",
            }}
            className="mt-[28px] flex flex-col sm:flex-row items-center justify-center gap-[12px]">
            <Button
              asChild
              className="group relative h-10 overflow-hidden rounded-full bg-[#27BE8C] px-8 text-[14px] font-semibold text-white shadow-[0_4px_14px_0_rgba(39,190,140,0.3)] transition-all duration-300 hover:bg-[#21a378] hover:shadow-[0_6px_20px_rgba(39,190,140,0.2)] hover:-translate-y-0.5 active:scale-95"
            >
              <Link to="/signup">
                <span className="relative z-10 flex items-center gap-2">
                  Start Free <Rocket className="h-4 w-4 transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
                </span>
              </Link>
            </Button>
            <Button
              asChild
              variant="outline"
              className="h-[44px] px-[20px] rounded-full border border-[#E4E4E7] dark:border-zinc-700 bg-white dark:bg-zinc-800 text-[#18181B] dark:text-zinc-100 hover:bg-[#F4F4F5] dark:hover:bg-zinc-700 font-medium transition-colors shadow-none group">
              <Link to="/docs" className="flex items-center gap-2">
                View Docs
                <ChevronRight className="h-4 w-4 text-zinc-400 transition-transform group-hover:translate-x-1" />
              </Link>
            </Button>
          </motion.div>
        </div>
      </motion.section>

      {/* 2. DEMO SECTION (Moved below hero, reduced top gap) */}
      <section className="relative overflow-hidden bg-white dark:bg-zinc-950 pb-10 lg:pb-16 mt-10">
        <div className="relative mx-auto max-w-7xl px-6 lg:px-8">
          <div className="flex flex-col lg:flex-row items-center gap-12 lg:gap-20">
            {/* Left Side: Product Media */}
            <div className="w-full lg:w-[54%] order-1 relative">
              <DashboardPreview />
            </div>

            {/* Right Side: Keep design intact */}
            <div className="w-full lg:w-[46%] order-2 text-center lg:text-left pt-8 lg:pt-0">
              <motion.div
                custom={0.2}
                variants={revealUp}
                initial="hidden"
                animate="visible"
                className="inline-flex items-center gap-2 mb-6 px-4 py-2 rounded-full bg-zinc-50 dark:bg-zinc-900 border border-zinc-100 dark:border-zinc-800 text-[10px] font-semibold text-zinc-500 dark:text-zinc-400 uppercase tracking-[0.2em] shadow-sm">
                <span className="text-[#27BE8C]">●</span>
                Automated Coverage Engine
              </motion.div>

              <Headline />

              {/* Compact Trust Row - generic icons removed */}
              <motion.div
                variants={revealUp}
                custom={1.0}
                initial="hidden"
                animate="visible"
                className="flex flex-wrap items-center justify-center lg:justify-start gap-x-10 gap-y-4 pt-10 border-t border-zinc-100 dark:border-zinc-800">
                {[
                  { label: "Enterprise Security" },
                  { label: "AI-Powered Coverage" },
                  { label: "CI/CD Native" },
                ].map((item, i) => (
                  <div
                    key={i}
                    className="flex items-center gap-2">
                    <span className="text-[#27BE8C] text-[10px]">
                      ●
                    </span>
                    <span className="text-[12px] font-semibold text-zinc-500 dark:text-zinc-400 tracking-tight">
                      {item.label}
                    </span>
                  </div>
                ))}
              </motion.div>
            </div>
          </div>
        </div>
      </section>
    </>
  );
}

function RocketIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg
      {...props}
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z" />
      <path d="m12 15-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z" />
      <path d="M9 12H4s.5-1 1.5-2.5S8 7 8 7" />
      <path d="M12 15v5s1-.5 2.5-1.5S17 16 17 16" />
    </svg>
  )
}
