import { Zap } from "lucide-react"
import { motion, useReducedMotion } from "framer-motion"

import { fadeUpContainer, fadeUpItem } from "./motion"

export default function Footer() {
  const reduceMotion = useReducedMotion()

  return (
    <motion.footer 
      initial={reduceMotion ? false : "hidden"}
      animate={reduceMotion ? undefined : "visible"}
      variants={fadeUpContainer}
      className="border-t border-border dark:bg-[#020617] py-8"
    >
      <motion.div variants={fadeUpItem} className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 px-6 sm:flex-row">
        <div className="flex items-center gap-2">
          <div className="flex h-6 w-6 items-center justify-center rounded-md border border-border bg-muted">
            <Zap className="h-3 w-3 text-foreground" />
          </div>
          <span className="text-sm font-semibold text-foreground">Cognitest</span>
        </div>
        <p className="text-xs text-muted-foreground">
          &copy; {new Date().getFullYear()} Cognitest. All rights reserved.
        </p>
      </motion.div>
    </motion.footer>
  )
}
