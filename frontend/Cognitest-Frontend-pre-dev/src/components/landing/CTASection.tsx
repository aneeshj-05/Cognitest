import { Link } from "react-router-dom"
import { motion, useReducedMotion } from "framer-motion"

import { Button } from "@/components/ui/button"

import { fadeUpContainer, fadeUpItem } from "./motion"

export default function CTASection() {
  const reduceMotion = useReducedMotion()

  return (
    <motion.section
      initial={reduceMotion ? false : "hidden"}
      animate={reduceMotion ? undefined : "visible"}
      variants={fadeUpContainer}
      className="border-t border-border dark:bg-[#020617] py-16 md:py-20 lg:py-24"
    >
      <div className="mx-auto max-w-6xl px-6">
        <div className="mx-auto max-w-3xl text-center">
          <motion.h2 variants={fadeUpItem} className="text-xl font-semibold tracking-tight text-foreground md:text-2xl">
            Make API quality automatic.
          </motion.h2>
          <motion.p variants={fadeUpItem} className="mt-4 text-sm text-muted-foreground md:text-base">
            Start with your spec. Ship with confidence.
          </motion.p>

          <motion.div variants={fadeUpItem} className="mt-8 flex flex-col justify-center gap-3 sm:flex-row">
            <Button
              asChild
              size="lg"
              className="w-full rounded-full bg-[linear-gradient(to_right,hsl(var(--cta-start)),hsl(var(--cta-end)))] text-primary-foreground hover:bg-[linear-gradient(to_right,hsl(var(--cta-start)),hsl(var(--cta-end)))] sm:w-auto"
            >
              <Link to="/login">Start Free</Link>
            </Button>
            <Button
              asChild
              size="lg"
              variant="outline"
              className="w-full rounded-full border border-border bg-background hover:bg-muted hover:text-foreground sm:w-auto"
            >
              <Link to="/docs">View Docs</Link>
            </Button>
          </motion.div>
        </div>
      </div>
    </motion.section>
  )
}
