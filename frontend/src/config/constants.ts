/**
 * Centralized constants for the application.
 * All hardcoded values should be defined here.
 */

/**
 * HTTP method configuration with colors
 */
export interface HttpMethodConfig {
  method: string
  bgClass: string
  textClass: string
  borderClass: string
  fullClass: string  // Combined classes for convenience
}

export const HTTP_METHODS: HttpMethodConfig[] = [
  {
    method: "GET",
    bgClass: "bg-emerald-50",
    textClass: "text-emerald-600",
    borderClass: "border-emerald-200",
    fullClass: "bg-emerald-50 text-emerald-600 border-emerald-200",
  },
  {
    method: "POST",
    bgClass: "bg-blue-50",
    textClass: "text-blue-600",
    borderClass: "border-blue-200",
    fullClass: "bg-blue-50 text-blue-600 border-blue-200",
  },
  {
    method: "PUT",
    bgClass: "bg-amber-50",
    textClass: "text-amber-600",
    borderClass: "border-amber-200",
    fullClass: "bg-amber-50 text-amber-600 border-amber-200",
  },
  {
    method: "PATCH",
    bgClass: "bg-yellow-50",
    textClass: "text-yellow-600",
    borderClass: "border-yellow-200",
    fullClass: "bg-yellow-50 text-yellow-600 border-yellow-200",
  },
  {
    method: "DELETE",
    bgClass: "bg-red-50",
    textClass: "text-red-600",
    borderClass: "border-red-200",
    fullClass: "bg-red-50 text-red-600 border-red-200",
  },
  {
    method: "OPTIONS",
    bgClass: "bg-slate-50",
    textClass: "text-slate-600",
    borderClass: "border-slate-200",
    fullClass: "bg-slate-50 text-slate-600 border-slate-200",
  },
  {
    method: "HEAD",
    bgClass: "bg-indigo-50",
    textClass: "text-indigo-600",
    borderClass: "border-indigo-200",
    fullClass: "bg-indigo-50 text-indigo-600 border-indigo-200",
  },
]

/**
 * Get HTTP method color classes
 */
export function getMethodColors(method: string): string {
  const config = HTTP_METHODS.find((m) => m.method === method.toUpperCase())
  return config?.fullClass || "bg-slate-50 text-slate-600 border-slate-200"
}

/**
 * Get list of HTTP methods for filter UI
 */
export function getFilterableMethods(): string[] {
  return ["GET", "POST", "PUT", "PATCH", "DELETE"]
}

/**
 * API Configuration
 */
export const API_CONFIG = {
  /** Default base URL when project has none set */
  DEFAULT_BASE_URL,

  /** Default API version fallback */
  DEFAULT_API_VERSION: "1.0.0",

  /** Default max tests for generation */
  DEFAULT_MAX_TESTS: 5000,
}

/**
 * UI Configuration
 */
export const UI_CONFIG = {
  /** Date/time locale for formatting */
  DATE_LOCALE: "en-US",

  /** Fallback user initial when no name available */
  FALLBACK_USER_INITIAL: "U",

  /** Theme colors */
  COLORS: {
    PRIMARY_GREEN: "#22C55E",
    PASS_GREEN: "#22C55E",
    FAIL_RED: "#EF4444",
  },
}

/**
 * Format date using configured locale
 */
export function formatDate(dateString?: string): string {
  if (!dateString) return "-"
  const d = new Date(dateString)
  return isNaN(d.getTime())
    ? "-"
    : d.toLocaleDateString(UI_CONFIG.DATE_LOCALE, { month: "short", day: "numeric", year: "numeric" })
}

/**
 * Format date+time using configured locale
 */
export function formatDateTime(dateString?: string): string {
  if (!dateString) return "-"
  const d = new Date(dateString)
  return isNaN(d.getTime())
    ? "-"
    : d.toLocaleString(UI_CONFIG.DATE_LOCALE, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })
}

/**
 * Get user initials from name/email
 */
export function getUserInitials(name?: string | null): string {
  const displayName = name || UI_CONFIG.FALLBACK_USER_INITIAL
  return displayName
    .split(" ")
    .map((p: string) => p[0])
    .join("")
    .toUpperCase()
    .slice(0, 2)
}
import { DEFAULT_BASE_URL } from "./runtime"
