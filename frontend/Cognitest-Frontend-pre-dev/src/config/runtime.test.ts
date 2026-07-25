import { describe, expect, it } from "vitest"
import { API_BASE_URL, DEFAULT_BASE_URL, DEFAULT_LOCAL_TARGET_URL } from "./runtime"

describe("config/runtime", () => {
  it("exposes sanitized runtime constants", () => {
    expect(typeof API_BASE_URL).toBe("string")
    expect(DEFAULT_LOCAL_TARGET_URL).toBe("http://localhost:3000")
    expect(typeof DEFAULT_BASE_URL).toBe("string")
  })
})
