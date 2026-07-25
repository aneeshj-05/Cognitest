import { Link } from "react-router-dom"
import { motion, useReducedMotion } from "framer-motion"
import { cn } from "@/lib/utils"

import { Button } from "@/components/ui/button"
import { fadeUpContainer, fadeUpItem } from "./motion"

type Testimonial = {
  quote: string
  role: string
  company: string
  widthClass: string
  marginTopClass: string
  paddingClass: string
}

const testimonials: Testimonial[] = [
  {
    quote: "We went from spot checks to reliable coverage without adding test maintenance work to the roadmap.",
    role: "Engineering Lead",
    company: "Product Engineering",
    widthClass: "w-full lg:max-w-[340px]",
    marginTopClass: "mt-0",
    paddingClass: "p-6",
  },
  {
    quote: "CI failures are finally actionable. When something breaks, we know exactly what changed and why it matters.",
    role: "Infrastructure Engineer",
    company: "Internal Engineering",
    widthClass: "w-full lg:max-w-[420px]",
    marginTopClass: "lg:mt-8",
    paddingClass: "p-[26px]",
  },
  {
    quote: "The security checks catch issues early—and the performance signal helps us avoid bad deploys.",
    role: "Backend Team",
    company: "Payments",
    widthClass: "w-full lg:max-w-[340px]",
    marginTopClass: "lg:mt-2",
    paddingClass: "px-6 py-7",
  },
]

function TestimonialCard({ quote, role, company, paddingClass }: Testimonial) {
  return (
    <div
      className={cn(
        "rounded-xl border border-zinc-200 bg-white shadow-sm transition-all duration-300 flex flex-col h-full",
        "dark:bg-white/[0.04] dark:backdrop-blur-md dark:border-white/[0.08] dark:shadow-[0_4px_20px_rgba(0,0,0,0.4)]",
        "hover:shadow-md hover:-translate-y-[2px] dark:hover:bg-white/[0.06] dark:hover:border-white/[0.12] dark:hover:shadow-[0_6px_30px_rgba(0,0,0,0.5)]",
        paddingClass
      )}
    >
      <p className="text-[15px] font-normal text-zinc-700 dark:text-zinc-400 leading-relaxed flex-1">
        “{quote}”
      </p>
      <div className="mt-7">
        <p className="font-medium text-zinc-900 dark:text-zinc-100">{role}</p>
        <p className="text-[13px] text-zinc-500 dark:text-zinc-400 mt-0.5">{company}</p>
      </div>
    </div>
  )
}

export default function TestimonialsSection() {
  const reduceMotion = useReducedMotion()

  return (
    <motion.section
      initial={reduceMotion ? false : "hidden"}
      animate={reduceMotion ? undefined : "visible"}
      variants={fadeUpContainer}
      className="bg-gradient-to-b from-white to-zinc-50/30 dark:bg-gradient-to-b dark:from-[#020617] dark:to-[#020617] py-20 lg:py-24"
    >
      <div className="mx-auto max-w-6xl px-6">
        {/* Testimonials - Asymmetric Flex Layout */}
        <div className="mb-14">
          <motion.div
            variants={fadeUpContainer}
            className="flex flex-col lg:flex-row items-start justify-center gap-6 lg:gap-8"
          >
            {testimonials.map((t) => (
              <motion.div key={t.company} variants={fadeUpItem} className={cn("flex-shrink-0 lg:flex-1", t.widthClass, t.marginTopClass)}>
                <TestimonialCard {...t} />
              </motion.div>
            ))}
          </motion.div>
        </div>

        {/* Unified CTA - Centered Block with Left-Aligned Text */}
        <motion.div variants={fadeUpItem} className="mt-14 lg:mt-20 flex justify-center">
          <div className="w-fit max-w-md text-left">
            <h2 className="text-[28px] md:text-[32px] font-semibold tracking-tight text-zinc-900 dark:text-white leading-tight">
              Make API quality automatic.
            </h2>
            <p className="mt-3 text-[15px] text-zinc-500 dark:text-zinc-400 max-w-[280px] leading-relaxed">
              Start with your spec. Ship with confidence.
            </p>

            <div className="mt-8 flex flex-col sm:flex-row justify-start gap-3">
              <Button
                asChild
                className="w-full sm:w-auto h-11 rounded-full bg-[#27BE8C] px-7 text-[14px] font-semibold text-white shadow-[0_8px_20px_-4px_rgba(39,190,140,0.25)] transition-all hover:bg-[#21a378] hover:-translate-y-[1px] active:scale-[0.98]"
              >
                <Link to="/login">Start Free</Link>
              </Button>
              <Button
                asChild
                variant="outline"
                className="w-full sm:w-auto h-11 rounded-full border border-zinc-200 dark:border-white/10 bg-white dark:bg-white/[0.05] px-7 text-[14px] font-semibold text-zinc-900 dark:text-zinc-200 hover:bg-zinc-50 dark:hover:bg-white/10 hover:border-zinc-300 transition-all"
              >
                <Link to="/docs">View Docs</Link>
              </Button>
            </div>
          </div>
        </motion.div>
      </div>
    </motion.section>
  )
}
