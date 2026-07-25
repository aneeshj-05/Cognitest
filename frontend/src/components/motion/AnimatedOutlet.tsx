import { useContext, useMemo, type ReactNode } from "react"
import {
  UNSAFE_LocationContext,
  UNSAFE_NavigationContext,
  useLocation,
  useOutlet,
} from "react-router-dom"
import { AnimatePresence, motion, useReducedMotion } from "framer-motion"

type AnimatedOutletProps = {
  className?: string
}

type FrozenRouterProps = {
  location: ReturnType<typeof useLocation>
  children: ReactNode
}

/**
 * Prevent exiting route elements from updating to the new location while their
 * exit animation runs (avoids the "page renders twice" effect).
 */
const FrozenRouter = ({ location, children }: FrozenRouterProps) => {
  const navigationContext = useContext(UNSAFE_NavigationContext)
  const locationContext = useContext(UNSAFE_LocationContext)

  const frozenLocationContext = useMemo(
    () => ({ ...locationContext, location }),
    [locationContext, location]
  )

  return (
    <UNSAFE_NavigationContext.Provider value={navigationContext}>
      <UNSAFE_LocationContext.Provider value={frozenLocationContext}>
        {children}
      </UNSAFE_LocationContext.Provider>
    </UNSAFE_NavigationContext.Provider>
  )
}

const AnimatedOutlet = ({ className }: AnimatedOutletProps) => {
  const location = useLocation()
  const outlet = useOutlet()
  const reduceMotion = useReducedMotion()

  const transition = reduceMotion
    ? { duration: 0 }
    : { duration: 0.28, ease: [0.22, 1, 0.36, 1] as const }

  return (
    <AnimatePresence mode="wait" initial={false}>
      <motion.div
        key={location.pathname}
        initial={reduceMotion ? false : { opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={reduceMotion ? undefined : { opacity: 0 }}
        transition={transition}
        className={className}
      >
        <FrozenRouter location={location}>{outlet}</FrozenRouter>
      </motion.div>
    </AnimatePresence>
  )
}

export default AnimatedOutlet
