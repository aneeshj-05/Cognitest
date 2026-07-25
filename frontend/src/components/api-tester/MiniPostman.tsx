import { useState, useRef, useEffect, useCallback } from "react"
import { X, Send, Plus, Trash2, Clock, ChevronDown, Copy, Check, History } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"

// ── Types ────────────────────────────────────────────────────────────
type HttpMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE"

interface KeyValuePair {
  id: string
  key: string
  value: string
  enabled: boolean
}

interface HistoryEntry {
  id: string
  method: HttpMethod
  url: string
  status: number
  duration: number
  timestamp: string
}

interface MiniPostmanProps {
  onClose: () => void
}

// ── Constants ────────────────────────────────────────────────────────
const METHOD_STYLES: Record<HttpMethod, string> = {
  GET:    "bg-emerald-50 text-emerald-700 border-emerald-200 hover:bg-emerald-100",
  POST:   "bg-blue-50 text-blue-700 border-blue-200 hover:bg-blue-100",
  PUT:    "bg-amber-50 text-amber-700 border-amber-200 hover:bg-amber-100",
  PATCH:  "bg-yellow-50 text-yellow-700 border-yellow-200 hover:bg-yellow-100",
  DELETE: "bg-red-50 text-red-700 border-red-200 hover:bg-red-100",
}

const METHOD_TEXT: Record<HttpMethod, string> = {
  GET:    "text-emerald-700",
  POST:   "text-blue-700",
  PUT:    "text-amber-700",
  PATCH:  "text-yellow-700",
  DELETE: "text-red-700",
}

const HISTORY_KEY = "cognitest-postman-history"
const METHODS: HttpMethod[] = ["GET", "POST", "PUT", "PATCH", "DELETE"]

function uid() {
  return Math.random().toString(36).slice(2)
}

function statusStyle(code: number): string {
  if (code >= 200 && code < 300) return "bg-emerald-50 text-emerald-700 border-emerald-200"
  if (code >= 300 && code < 400) return "bg-blue-50 text-blue-700 border-blue-200"
  if (code >= 400 && code < 500) return "bg-amber-50 text-amber-700 border-amber-200"
  if (code >= 500) return "bg-red-50 text-red-700 border-red-200"
  return "bg-muted text-muted-foreground border-border"
}

function emptyRow(): KeyValuePair {
  return { id: uid(), key: "", value: "", enabled: true }
}

// ── KV Editor ────────────────────────────────────────────────────────
function KVEditor({ rows, onChange }: { rows: KeyValuePair[]; onChange: (r: KeyValuePair[]) => void }) {
  const update = (id: string, field: keyof KeyValuePair, val: string | boolean) =>
    onChange(rows.map((r) => (r.id === id ? { ...r, [field]: val } : r)))
  const remove = (id: string) => onChange(rows.filter((r) => r.id !== id))
  const add = () => onChange([...rows, emptyRow()])

  return (
    <div className="space-y-1.5">
      {rows.map((row) => (
        <div key={row.id} className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={row.enabled}
            onChange={(e) => update(row.id, "enabled", e.target.checked)}
            className="accent-emerald-500 shrink-0 h-3.5 w-3.5"
          />
          <Input
            placeholder="Key"
            value={row.key}
            onChange={(e) => update(row.id, "key", e.target.value)}
            className="h-7 text-xs flex-1"
          />
          <Input
            placeholder="Value"
            value={row.value}
            onChange={(e) => update(row.id, "value", e.target.value)}
            className="h-7 text-xs flex-1"
          />
          <button onClick={() => remove(row.id)} className="text-muted-foreground/40 hover:text-red-500 transition-colors shrink-0">
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        </div>
      ))}
      <button
        onClick={add}
        className="flex items-center gap-1 text-xs text-muted-foreground hover:text-emerald-600 transition-colors mt-1"
      >
        <Plus className="h-3 w-3" /> Add row
      </button>
    </div>
  )
}

// ── Main Component ───────────────────────────────────────────────────
export default function MiniPostman({ onClose }: MiniPostmanProps) {
  const [method, setMethod] = useState<HttpMethod>("GET")
  const [url, setUrl] = useState("")
  const [activeTab, setActiveTab] = useState<"params" | "headers" | "body">("headers")
  const [params, setParams] = useState<KeyValuePair[]>([emptyRow()])
  const [headers, setHeaders] = useState<KeyValuePair[]>([
    { id: uid(), key: "Content-Type", value: "application/json", enabled: true },
    emptyRow(),
  ])
  const [body, setBody] = useState("")
  const [loading, setLoading] = useState(false)
  const [response, setResponse] = useState<{
    status: number
    statusText: string
    duration: number
    headers: Record<string, string>
    body: string
    size: number
  } | null>(null)
  const [responseTab, setResponseTab] = useState<"body" | "headers">("body")
  const [copied, setCopied] = useState(false)
  const [methodOpen, setMethodOpen] = useState(false)
  const [showHistory, setShowHistory] = useState(false)
  const [history, setHistory] = useState<HistoryEntry[]>(() => {
    try { return JSON.parse(localStorage.getItem(HISTORY_KEY) || "[]") } catch { return [] }
  })

  const methodRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (methodRef.current && !methodRef.current.contains(e.target as Node)) setMethodOpen(false)
    }
    document.addEventListener("mousedown", handler)
    return () => document.removeEventListener("mousedown", handler)
  }, [])

  const buildUrl = useCallback(() => {
    const active = params.filter((p) => p.enabled && p.key)
    if (!active.length) return url
    const qs = active.map((p) => `${encodeURIComponent(p.key)}=${encodeURIComponent(p.value)}`).join("&")
    return url.includes("?") ? `${url}&${qs}` : `${url}?${qs}`
  }, [url, params])

  const sendRequest = async () => {
    if (!url.trim()) return
    setLoading(true)
    setResponse(null)
    const finalUrl = buildUrl()
    const reqHeaders: Record<string, string> = {}
    headers.filter((h) => h.enabled && h.key).forEach((h) => { reqHeaders[h.key] = h.value })
    const start = Date.now()
    try {
      const init: RequestInit = { method, headers: reqHeaders }
      if (!["GET", "DELETE"].includes(method) && body.trim()) init.body = body
      const res = await fetch(finalUrl, init)
      const duration = Date.now() - start
      const text = await res.text()
      const resHeaders: Record<string, string> = {}
      res.headers.forEach((v, k) => { resHeaders[k] = v })
      setResponse({ status: res.status, statusText: res.statusText, duration, headers: resHeaders, body: text, size: new Blob([text]).size })
      const entry: HistoryEntry = { id: uid(), method, url: finalUrl, status: res.status, duration, timestamp: new Date().toLocaleTimeString() }
      setHistory((prev) => {
        const next = [entry, ...prev].slice(0, 10)
        localStorage.setItem(HISTORY_KEY, JSON.stringify(next))
        return next
      })
    } catch (err) {
      setResponse({ status: 0, statusText: "Network Error", duration: Date.now() - start, headers: {}, body: err instanceof Error ? err.message : "Request failed", size: 0 })
    } finally {
      setLoading(false)
    }
  }

  const prettyBody = () => {
    if (!response) return ""
    try { return JSON.stringify(JSON.parse(response.body), null, 2) } catch { return response.body }
  }

  const copyResponse = () => {
    navigator.clipboard.writeText(prettyBody())
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  const activeParamCount = params.filter((p) => p.enabled && p.key).length
  const activeHeaderCount = headers.filter((h) => h.enabled && h.key).length

  return (
    <div className="flex flex-col h-full bg-background border-l border-border">

      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border shrink-0">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-emerald-500" />
          <span className="text-sm font-semibold">API Tester</span>
        </div>
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowHistory((s) => !s)}
            className={`h-7 gap-1.5 text-xs ${showHistory ? "text-emerald-600 bg-emerald-50" : ""}`}
          >
            <History className="h-3.5 w-3.5" />
            History
            {history.length > 0 && (
              <span className="bg-emerald-100 text-emerald-700 text-[10px] px-1 rounded-full">{history.length}</span>
            )}
          </Button>
          <Button variant="ghost" size="icon" className="h-7 w-7" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* History panel */}
      {showHistory && (
        <div className="border-b border-border bg-muted/30 max-h-52 overflow-y-auto shrink-0">
          {history.length === 0 ? (
            <p className="text-xs text-muted-foreground text-center py-6">No history yet</p>
          ) : (
            history.map((h) => (
              <button
                key={h.id}
                onClick={() => { setMethod(h.method); setUrl(h.url); setShowHistory(false) }}
                className="w-full flex items-center gap-2 px-4 py-2 hover:bg-muted transition-colors text-left border-b border-border/50 last:border-0"
              >
                <span className={`text-[10px] font-bold w-11 shrink-0 ${METHOD_TEXT[h.method]}`}>{h.method}</span>
                <span className="text-xs text-muted-foreground truncate flex-1">{h.url}</span>
                <span className={`text-[10px] px-1.5 py-0.5 rounded border font-medium ${statusStyle(h.status)}`}>{h.status || "ERR"}</span>
                <span className="text-[10px] text-muted-foreground shrink-0">{h.timestamp}</span>
              </button>
            ))
          )}
        </div>
      )}

      {/* URL Bar */}
      <div className="flex items-center gap-2 px-4 py-3 border-b border-border shrink-0">
        <div ref={methodRef} className="relative shrink-0">
          <button
            onClick={() => setMethodOpen((o) => !o)}
            className={`flex items-center gap-1 h-9 px-3 rounded-md border text-xs font-bold transition-colors ${METHOD_STYLES[method]}`}
          >
            {method}
            <ChevronDown className="h-3 w-3 opacity-60" />
          </button>
          {methodOpen && (
            <div className="absolute top-full left-0 mt-1 z-50 bg-background border border-border rounded-lg overflow-hidden shadow-lg min-w-[90px]">
              {METHODS.map((m) => (
                <button
                  key={m}
                  onClick={() => { setMethod(m); setMethodOpen(false) }}
                  className={`block w-full text-left px-3 py-2 text-xs font-bold hover:bg-muted transition-colors ${METHOD_TEXT[m]}`}
                >
                  {m}
                </button>
              ))}
            </div>
          )}
        </div>

        <Input
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && sendRequest()}
          placeholder="https://api.example.com/endpoint"
          className="h-9 text-sm flex-1"
        />

        <Button
          onClick={sendRequest}
          disabled={loading || !url.trim()}
          className="h-9 px-4 bg-emerald-500 hover:bg-emerald-600 text-white text-xs font-semibold shrink-0 gap-1.5"
        >
          {loading ? (
            <span className="flex items-center gap-1.5">
              <span className="h-3 w-3 rounded-full border-2 border-white/30 border-t-white animate-spin" />
              Sending
            </span>
          ) : (
            <><Send className="h-3.5 w-3.5" /> Send</>
          )}
        </Button>
      </div>

      {/* Request Tabs */}
      <div className="flex border-b border-border shrink-0 px-4">
        {(["params", "headers", "body"] as const).map((tab) => {
          const count = tab === "params" ? activeParamCount : tab === "headers" ? activeHeaderCount : 0
          return (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`flex items-center gap-1.5 px-3 py-2.5 text-xs font-medium capitalize transition-colors border-b-2 -mb-px ${
                activeTab === tab
                  ? "text-emerald-600 border-emerald-500"
                  : "text-muted-foreground border-transparent hover:text-foreground"
              }`}
            >
              {tab}
              {count > 0 && (
                <span className="bg-emerald-100 text-emerald-700 text-[10px] px-1.5 rounded-full font-semibold">{count}</span>
              )}
            </button>
          )
        })}
      </div>

      {/* Request Tab Content */}
      <div className="px-4 py-3 border-b border-border shrink-0 min-h-[110px] max-h-[160px] overflow-y-auto">
        {activeTab === "params" && <KVEditor rows={params} onChange={setParams} />}
        {activeTab === "headers" && <KVEditor rows={headers} onChange={setHeaders} />}
        {activeTab === "body" && (
          <textarea
            value={body}
            onChange={(e) => setBody(e.target.value)}
            placeholder={'{\n  "key": "value"\n}'}
            className="w-full h-24 bg-muted/40 rounded-md border border-border text-xs text-foreground placeholder:text-muted-foreground resize-none outline-none font-mono p-2 focus:ring-1 focus:ring-emerald-500 focus:border-emerald-500"
          />
        )}
      </div>

      {/* Response */}
      <div className="flex flex-col flex-1 min-h-0">
        {!response && !loading && (
          <div className="flex flex-1 flex-col items-center justify-center gap-2 text-muted-foreground">
            <Send className="h-8 w-8 opacity-20" />
            <p className="text-sm">Hit Send to see the response</p>
          </div>
        )}

        {loading && (
          <div className="flex flex-1 items-center justify-center gap-2 text-muted-foreground text-sm">
            <span className="h-4 w-4 rounded-full border-2 border-muted border-t-emerald-500 animate-spin" />
            Sending request...
          </div>
        )}

        {response && !loading && (
          <>
            {/* Response status bar */}
            <div className="flex items-center gap-3 px-4 py-2.5 border-b border-border bg-muted/30 shrink-0">
              <span className={`text-xs font-semibold px-2 py-0.5 rounded border ${statusStyle(response.status)}`}>
                {response.status || "ERR"} {response.statusText}
              </span>
              <span className="text-xs text-muted-foreground flex items-center gap-1">
                <Clock className="h-3 w-3" />{response.duration}ms
              </span>
              <span className="text-xs text-muted-foreground">{response.size}B</span>

              <div className="flex items-center ml-auto gap-1">
                {(["body", "headers"] as const).map((t) => (
                  <button
                    key={t}
                    onClick={() => setResponseTab(t)}
                    className={`px-2.5 py-1 text-xs rounded capitalize transition-colors ${
                      responseTab === t
                        ? "bg-emerald-50 text-emerald-700 font-medium"
                        : "text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    {t}
                  </button>
                ))}
                <button
                  onClick={copyResponse}
                  className="ml-1 p-1 text-muted-foreground hover:text-foreground transition-colors rounded hover:bg-muted"
                >
                  {copied ? <Check className="h-3.5 w-3.5 text-emerald-500" /> : <Copy className="h-3.5 w-3.5" />}
                </button>
              </div>
            </div>

            {/* Response content */}
            <div className="flex-1 overflow-y-auto px-4 py-3">
              {responseTab === "body" && (
                <pre className="text-xs text-foreground font-mono whitespace-pre-wrap break-all leading-relaxed">
                  {prettyBody()}
                </pre>
              )}
              {responseTab === "headers" && (
                <div className="space-y-1.5">
                  {Object.entries(response.headers).map(([k, v]) => (
                    <div key={k} className="flex gap-2 text-xs">
                      <span className="text-emerald-600 font-medium shrink-0">{k}:</span>
                      <span className="text-muted-foreground break-all">{v}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  )
}
