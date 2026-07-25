/**
 * Utility to get computed CSS variable values.
 * Useful for components that need real color values (like Recharts).
 */
export function getComputedColor(variableName: string): string {
  if (typeof window === "undefined") return "transparent"
  
  // Try to get the value from document element
  const style = getComputedStyle(document.documentElement)
  let value = style.getPropertyValue(`--${variableName}`).trim()
  
  if (!value) {
    // Fallback common colors if variables are missing
    const fallbacks: Record<string, string> = {
      "chart-1": "160 84% 39%", // primary-ish
      "chart-2": "215 16% 47%", // muted-ish
      "chart-3": "222 47% 11%", // foreground-ish
      "chart-4": "214 32% 91%", // border-ish
      "background": "0 0% 98%",
      "foreground": "222 47% 11%",
      "muted": "210 40% 96%",
      "muted-foreground": "215 16% 47%",
      "border": "214 32% 91%",
    }
    value = fallbacks[variableName] || "0 0% 0%"
  }
  
  // If it's a raw HSL value (like shadcn/ui uses), wrap it
  if (value && !value.startsWith("hsl") && !value.startsWith("#") && !value.startsWith("rgb")) {
    return `hsl(${value})`
  }
  
  return value || "transparent"
}
