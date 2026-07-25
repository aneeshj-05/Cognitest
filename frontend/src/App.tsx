import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom"
import publicRoutes from "./routes/PublicRoutes"
import dashboardRoutes from "./routes/DashboardRoutes"
import AppProviders from "./context/AppProviders"

export default function App() {
  return (
    <AppProviders>
      <BrowserRouter
        future={{
          v7_startTransition: true,
          v7_relativeSplatPath: true,
        }}
      >
        <Routes>
          {publicRoutes}
          {dashboardRoutes}

          {/* Catch-all */}
          <Route path="*" element={<Navigate to="/" replace />} />
          <Route path="/super-admin" element={<Navigate to="/super-admin-dashboard" replace />} />
        </Routes>
      </BrowserRouter>
    </AppProviders>
  )
}
