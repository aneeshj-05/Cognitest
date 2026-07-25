const sanitizeUrl = (value: string) => value.replace(/^["']|["']$/g, "").replace(/\/$/, "")

const rawApiUrl = String(import.meta.env.VITE_API_URL || "").trim()

export const API_BASE_URL = sanitizeUrl(rawApiUrl)
export const DEFAULT_LOCAL_TARGET_URL = "http://localhost:3000"
export const DEFAULT_BASE_URL = import.meta.env.PROD ? "" : "http://localhost:6000"
