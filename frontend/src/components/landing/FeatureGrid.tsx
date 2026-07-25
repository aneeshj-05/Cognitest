import { motion, useReducedMotion } from "framer-motion"
import type { LucideIcon } from "lucide-react"

import { Badge } from "@/components/ui/badge"

import FeatureCard from "./FeatureCard"
import { fadeUpContainer, fadeUpItem } from "./motion"

type Feature = {
  icon: LucideIcon
  title: string
  description: string
}

type FeatureGridProps = {
  features: Feature[]
}

export default function FeatureGrid({ features }: FeatureGridProps) {
  const reduceMotion = useReducedMotion()

  return (
    <motion.section
      initial={reduceMotion ? false : "hidden"}
      animate={reduceMotion ? undefined : "visible"}
      variants={fadeUpContainer}
      className="border-t border-border bg-background py-16 md:py-20 lg:py-24"
    >
      <div className="mx-auto max-w-6xl px-6">
        <div className="space-y-8">
          <div className="space-y-4">
            <motion.div variants={fadeUpItem}>
              <Badge
                variant="outline"
                className="border border-border bg-background px-3 py-1 text-muted-foreground"
              >
                Core Capabilities
              </Badge>
            </motion.div>
            <motion.h2 variants={fadeUpItem} className="text-xl font-semibold text-foreground md:text-2xl">
              Ship faster with confidence.
            </motion.h2>
            <motion.p variants={fadeUpItem} className="max-w-2xl text-sm text-muted-foreground md:text-base">
              One place to generate, run, and maintain API checks — so quality doesn’t fall behind delivery.
            </motion.p>
          </div>

          <motion.div variants={fadeUpContainer} className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {features.map((f) => (
              <motion.div key={f.title} variants={fadeUpItem}>
                <FeatureCard icon={f.icon} title={f.title} description={f.description} />
              </motion.div>
            ))}
          </motion.div>
        </div>
      </div>
    </motion.section>
  )
}
