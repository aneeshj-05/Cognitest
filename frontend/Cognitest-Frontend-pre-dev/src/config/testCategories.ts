/**
 * Centralized configuration for test categories.
 * All category-related data should be defined here to avoid hardcoding throughout the app.
 */

export interface TestCategoryConfig {
  name: string           // Display name (e.g., "Functional")
  value: string          // Value used in API/DB (e.g., "Functional")
  icon: string           // Emoji icon
  color: string          // Color theme name
  badgeClass: string     // Tailwind classes for category badge
  description?: string   // Optional description
}

/**
 * All available test categories in the system.
 * Add new categories here and they will automatically appear in dropdowns and breakdowns.
 */
export const TEST_CATEGORIES: TestCategoryConfig[] = [
  {
    name: "Functional",
    value: "Functional",
    icon: "⚡",
    color: "blue",
    badgeClass: "bg-blue-50 text-blue-500",
    description: "Validates core API functionality with valid inputs and expected scenarios. Tests include: verifying responses match expected data, checking status codes (200, 201), validating response schemas, testing workflow sequences, and ensuring business logic works correctly.",
  },
  {
    name: "Negative",
    value: "Negative",
    icon: "⊖",
    color: "orange",
    badgeClass: "bg-orange-50 text-orange-500",
    description: "Tests error handling and edge cases. Includes: missing required fields, invalid data types, boundary values, empty payloads, oversized inputs, malformed JSON, invalid enum values, and null/undefined parameters. Ensures APIs fail gracefully with appropriate error messages.",
  },
  {
    name: "Security",
    value: "Security",
    icon: "🛡",
    color: "red",
    badgeClass: "bg-red-50 text-red-500",
    description: "Identifies vulnerabilities and compliance issues. Tests cover: SQL injection, XSS attacks, CSRF protection, authentication bypass, authorization flaws, sensitive data exposure, rate limiting, CORS misconfigurations, and OWASP Top 10 vulnerabilities.",
  },
  {
    name: "Contract",
    value: "Contract",
    icon: "📄",
    color: "emerald",
    badgeClass: "bg-emerald-500/10 text-emerald-500",
    description: "Verifies API adheres to OpenAPI/Swagger specification. Validates: request/response schemas match spec, required fields are present, data types are correct, field lengths comply with limits, required headers are included, and response structure matches contract.",
  },
  {
    name: "Fuzz",
    value: "Fuzz",
    icon: "🔀",
    color: "purple",
    badgeClass: "bg-purple-50 text-purple-500",
    description: "Tests robustness with random and unexpected inputs. Generates: random strings, special characters, very large values, negative numbers, unicode characters, and random payloads. Detects crashes, memory leaks, unhandled exceptions, and unexpected behavior.",
  },
]

/**
 * Default test category when none is selected
 */
export const DEFAULT_TEST_CATEGORY = "Functional"

/**
 * Get category config by name (case-insensitive)
 */
export function getCategoryConfig(name: string): TestCategoryConfig | undefined {
  return TEST_CATEGORIES.find(
    (cat) => cat.name.toLowerCase() === name.toLowerCase()
  )
}

/**
 * Get badge classes for a category name (case-insensitive)
 */
export function getCategoryBadgeClass(name: string): string {
  const config = getCategoryConfig(name)
  return config?.badgeClass || "bg-slate-50 text-slate-500"
}

/**
 * Get icon for a category name (case-insensitive)
 */
export function getCategoryIcon(name: string): string {
  const config = getCategoryConfig(name)
  return config?.icon || "📋"
}
