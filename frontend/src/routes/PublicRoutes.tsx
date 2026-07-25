import { lazy, Suspense, type ReactNode } from "react"
import { Route, Navigate } from "react-router-dom"
import PublicLayout from "@/components/layout/PublicLayout"

const LandingPage = lazy(() => import("@/pages/public/LandingPage"))
const DocsPage = lazy(() => import("@/pages/public/DocsPage"))
const ContactPage = lazy(() => import("@/pages/public/ContactPage"))
const LoginPage = lazy(() => import("@/pages/public/LoginPage"))
const SignupPage = lazy(() => import("@/pages/public/SignupPage"))
const VerifyOtpPage = lazy(() => import("@/pages/public/VerifyOtpPage"))
const PricingPage = lazy(() => import("@/pages/public/PricingPage"))
const InviteLandingPage = lazy(() => import("@/pages/public/InviteLandingPage"))

const withSuspense = (element: ReactNode) => (
  <Suspense fallback={<div className="p-6 text-sm text-muted-foreground">Loading...</div>}>
    {element}
  </Suspense>
)

const publicRoutes = [
  (
    <Route element={<PublicLayout />} key="public-shell">
      <Route index element={withSuspense(<LandingPage />)} />
      <Route path="docs" element={withSuspense(<DocsPage />)} />
      <Route path="contact" element={withSuspense(<ContactPage />)} />
      <Route path="login" element={withSuspense(<LoginPage />)} />
      <Route path="signup" element={withSuspense(<SignupPage />)} />
      <Route path="verify-otp" element={withSuspense(<VerifyOtpPage />)} />
      <Route path="pricing" element={withSuspense(<PricingPage />)} />
      <Route path="invite" element={withSuspense(<InviteLandingPage />)} />
      {/* Redirect removed pages */}
      <Route path="features" element={<Navigate to="/" replace />} />
      
    </Route>
  ),
]

export default publicRoutes
