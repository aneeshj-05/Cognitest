import { useState, useEffect } from "react"
import { motion, AnimatePresence } from "framer-motion"
import HeroSection from "@/components/landing/HeroSection"
import TrustSection from "@/components/landing/TrustSection"
import ProblemSolutionSection from "@/components/landing/ProblemSolutionSection"
import CapabilitiesSection from "@/components/landing/CapabilitiesSection"
import HowItWorksSection from "@/components/landing/HowItWorksSection"
import DemoSection from "@/components/landing/DemoSection"
import TestimonialsSection from "@/components/landing/TestimonialsSection"
import Footer from "@/components/landing/Footer"

const LandingPage = () => {
  const [isMounted, setIsMounted] = useState(false);

  useEffect(() => {
    setIsMounted(true);
  }, []);

  return (
    <AnimatePresence mode="wait">
      {isMounted && (
        <motion.div
          key="landing"
          initial="hidden"
          animate="visible"
          variants={{
            hidden: { opacity: 0, y: 30 },
            visible: {
              opacity: 1,
              y: 0,
              transition: {
                duration: 0.6,
                ease: "easeOut",
                staggerChildren: 0.1
              }
            }
          }}
          className="relative isolate bg-background"
        >
          <div aria-hidden className="pointer-events-none absolute inset-0 -z-10">
            <div className="absolute inset-0 landing-grid landing-grid-fade opacity-25" />
            <div className="absolute inset-0 bg-background" />
          </div>

          <div className="flex flex-col">
            <HeroSection />
            <TrustSection />
            <ProblemSolutionSection />
            <CapabilitiesSection />
            <HowItWorksSection />
            <DemoSection />
            <TestimonialsSection />
            <Footer />
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

export default LandingPage
