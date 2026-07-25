import { describe, expect, it } from "vitest"
import { formatDate, formatDateTime, getMethodColors, getUserInitials } from "./constants"

describe("config/constants", () => {
  it("returns known colors for HTTP methods", () => {
    expect(getMethodColors("GET")).toContain("emerald")
    expect(getMethodColors("PATCH")).toContain("yellow")
  })

  it("returns a stable fallback for unknown methods", () => {
    expect(getMethodColors("TRACE")).toContain("slate")
  })

  it("formats date and datetime safely", () => {
    expect(formatDate("2026-01-02T03:04:05Z")).toMatch(/Jan|1|2/)
    expect(formatDate("invalid")).toBe("-")
    expect(formatDateTime(undefined)).toBe("-")
  })

  it("builds initials from available names", () => {
    expect(getUserInitials("Jane Doe")).toBe("JD")
    expect(getUserInitials("")).toBe("U")
  })
})
